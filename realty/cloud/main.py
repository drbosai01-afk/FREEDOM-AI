"""FREEDOM REALTY cloud API. Each account sees only its own records."""
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Literal

import jwt
from fastapi import Depends, FastAPI, HTTPException, Header, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, EmailStr, Field
from pwdlib import PasswordHash
from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, UniqueConstraint, create_engine, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./realty.db")
JWT_SECRET = os.getenv("JWT_SECRET")
if not JWT_SECRET:
    # Dev-only fallback; production must set JWT_SECRET and must not reuse ephemeral secrets.
    if os.getenv("ENVIRONMENT", "development") == "production":
        raise RuntimeError("Set JWT_SECRET in production")
    JWT_SECRET = secrets.token_urlsafe(48)

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite:") else {}, pool_pre_ping=True)
SessionLocal = sessionmaker(engine, expire_on_commit=False)
password_hash = PasswordHash.recommended()
app = FastAPI(title="FREEDOM REALTY API", version="0.2.0")
RecordType = Literal["properties", "clients", "shows"]

class Base(DeclarativeBase):
    pass

class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    password_digest: Mapped[str] = mapped_column(String(255))

class Record(Base):
    __tablename__ = "records"
    __table_args__ = (UniqueConstraint("user_id", "kind", "record_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    kind: Mapped[str] = mapped_column(String(20))
    record_id: Mapped[str] = mapped_column(String(100))
    data: Mapped[dict] = mapped_column(JSON)
    version: Mapped[int] = mapped_column(Integer, default=1)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

Base.metadata.create_all(engine)

class Credentials(BaseModel):
    email: EmailStr
    password: str = Field(min_length=10, max_length=128)

class ImportItem(BaseModel):
    record_id: str = Field(min_length=1, max_length=100, pattern=r"^[a-zA-Z0-9_-]+$")
    data: dict[str, str]

class ImportBatch(BaseModel):
    records: list[ImportItem] = Field(min_length=1, max_length=300)

class RecordInput(BaseModel):
    record_id: str = Field(min_length=1, max_length=100, pattern=r"^[a-zA-Z0-9_-]+$")
    data: dict[str, str] = Field(default_factory=dict)
    version: int = Field(default=0, ge=0)

def session():
    with SessionLocal() as db:
        yield db

def current_user(authorization: str | None = Header(default=None), db: Session = Depends(session)) -> User:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Требуется авторизация")
    try:
        payload = jwt.decode(authorization[7:], JWT_SECRET, algorithms=["HS256"])
        uid = int(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError):
        raise HTTPException(401, "Неверный или просроченный токен")
    user = db.get(User, uid)
    if user is None:
        raise HTTPException(401, "Пользователь не найден")
    return user

def issue_token(user: User) -> dict:
    expiry = datetime.now(timezone.utc) + timedelta(hours=12)
    token = jwt.encode({"sub": str(user.id), "exp": expiry}, JWT_SECRET, algorithm="HS256")
    return {"access_token": token, "token_type": "bearer"}

@app.post("/api/register", status_code=201)
def register(creds: Credentials, db: Session = Depends(session)):
    email = str(creds.email).lower()
    if db.scalar(select(User).where(User.email == email)):
        raise HTTPException(409, "Этот email уже зарегистрирован")
    user = User(email=email, password_digest=password_hash.hash(creds.password))
    db.add(user)
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(409, "Не удалось создать аккаунт")
    db.refresh(user)
    return issue_token(user)

@app.post("/api/login")
def login(creds: Credentials, db: Session = Depends(session)):
    user = db.scalar(select(User).where(User.email == str(creds.email).lower()))
    if not user or not password_hash.verify(creds.password, user.password_digest):
        raise HTTPException(401, "Неверный email или пароль")
    return issue_token(user)

@app.get("/api/me")
def me(user: User = Depends(current_user)):
    return {"id": user.id, "email": user.email}

def record_json(item: Record):
    return {"record_id": item.record_id, "data": item.data, "version": item.version, "updated_at": item.updated_at.isoformat()}

@app.get("/api/records/{kind}")
def list_records(kind: RecordType, user: User = Depends(current_user), db: Session = Depends(session)):
    items = db.scalars(select(Record).where(Record.user_id == user.id, Record.kind == kind).order_by(Record.updated_at.desc())).all()
    return [record_json(x) for x in items]

@app.put("/api/records/{kind}")
def upsert_record(kind: RecordType, body: RecordInput, user: User = Depends(current_user), db: Session = Depends(session)):
    if len(str(body.data).encode("utf-8")) > 16000 or any(len(k) > 50 or len(v) > 5000 for k,v in body.data.items()):
        raise HTTPException(422, "Слишком большая запись")
    existing = db.scalar(select(Record).where(Record.user_id == user.id, Record.kind == kind, Record.record_id == body.record_id))
    if existing:
        if existing.version != body.version:
            raise HTTPException(409, "Запись изменена на другом устройстве. Обновите список.")
        existing.data = body.data
        existing.version += 1
        existing.updated_at = datetime.now(timezone.utc)
        item = existing
    else:
        if body.version != 0:
            raise HTTPException(409, "Запись больше не существует. Обновите список.")
        item = Record(user_id=user.id, kind=kind, record_id=body.record_id, data=body.data, version=1, updated_at=datetime.now(timezone.utc))
        db.add(item)
    db.commit()
    db.refresh(item)
    return record_json(item)

@app.post("/api/import/properties")
def import_properties(batch: ImportBatch, user: User = Depends(current_user), db: Session = Depends(session)):
    """Import privately; never replace existing records or import access codes into public source."""
    ids = [item.record_id for item in batch.records]
    if len(set(ids)) != len(ids):
        raise HTTPException(422, "Повторяющиеся идентификаторы в файле")
    allowed = {"title", "district", "address", "rooms", "area", "floor", "price", "condition", "url", "notes", "source"}
    for item in batch.records:
        if not item.data.get("title", "").strip():
            raise HTTPException(422, "У объекта нет названия")
        if set(item.data) - allowed or any(len(k) > 50 or len(v) > 5000 for k, v in item.data.items()):
            raise HTTPException(422, "Недопустимые поля или слишком длинные значения")
        if len(str(item.data).encode("utf-8")) > 16000:
            raise HTTPException(422, "Слишком большая запись")
    existing = set(db.scalars(select(Record.record_id).where(
        Record.user_id == user.id, Record.kind == "properties", Record.record_id.in_(ids)
    )).all())
    fresh = [item for item in batch.records if item.record_id not in existing]
    for item in fresh:
        db.add(Record(user_id=user.id, kind="properties", record_id=item.record_id, data=item.data, version=1))
    db.commit()
    return {"added": len(fresh), "skipped_existing": len(batch.records) - len(fresh), "received": len(batch.records)}

@app.delete("/api/records/{kind}/{record_id}")
def delete_record(kind: RecordType, record_id: str, version: int, user: User = Depends(current_user), db: Session = Depends(session)):
    item = db.scalar(select(Record).where(Record.user_id == user.id, Record.kind == kind, Record.record_id == record_id))
    if not item:
        raise HTTPException(404, "Запись не найдена")
    if item.version != version:
        raise HTTPException(409, "Запись изменена на другом устройстве. Обновите список.")
    db.delete(item)
    db.commit()
    return {"deleted": True}

@app.get("/api/health")
def health():
    return {"status": "ok"}

@app.get("/")
def home():
    return FileResponse(os.path.join(os.path.dirname(__file__), "cloud.html"))
