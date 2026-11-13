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

# In production, reject ephemeral storage and missing credentials: fail closed.
ENVIRONMENT = os.getenv("ENVIRONMENT", "development").lower()
configured_database = os.getenv("DATABASE_URL", "").strip()
if ENVIRONMENT == "production" and not configured_database:
    raise RuntimeError("DATABASE_URL (persistent PostgreSQL) is required in production")
DATABASE_URL = configured_database or "sqlite:///./realty.db"
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = "postgresql+psycopg://" + DATABASE_URL[len("postgres://"):]
elif DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = "postgresql+psycopg://" + DATABASE_URL[len("postgresql://"):]
if ENVIRONMENT == "production" and not DATABASE_URL.startswith("postgresql+psycopg://"):
    raise RuntimeError("Only persistent PostgreSQL is permitted in production")
JWT_SECRET = os.getenv("JWT_SECRET")
if not JWT_SECRET:
    # Dev-only fallback; production must set JWT_SECRET and must not reuse ephemeral secrets.
    if ENVIRONMENT == "production":
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


# Full-fidelity backups are isolated from live record tables.
import hashlib
import json
import uuid
from sqlalchemy import Boolean, LargeBinary
from fastapi import Response

MAX_BACKUP = 25 * 1024 * 1024
CHUNK_SIZE = 128 * 1024

class Snapshot(Base):
    __tablename__ = "snapshots"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    size: Mapped[int] = mapped_column(Integer)
    checksum: Mapped[str] = mapped_column(String(64))
    verified: Mapped[bool] = mapped_column(Boolean, default=False)

class SnapshotChunk(Base):
    __tablename__ = "snapshot_chunks"
    snapshot_id: Mapped[str] = mapped_column(ForeignKey("snapshots.id"), primary_key=True)
    part: Mapped[int] = mapped_column(Integer, primary_key=True)
    payload: Mapped[bytes] = mapped_column(LargeBinary)

Base.metadata.create_all(engine)

class SnapshotStart(BaseModel):
    size: int = Field(ge=2, le=MAX_BACKUP)
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")

class ChunkInput(BaseModel):
    hex_data: str = Field(min_length=2, max_length=CHUNK_SIZE*2, pattern=r"^[a-fA-F0-9]+$")

def own_snapshot(db: Session, user: User, sid: str):
    row = db.get(Snapshot, sid)
    if row is None or row.user_id != user.id:
        raise HTTPException(404, "Резервная копия не найдена")
    return row

@app.post("/api/backups", status_code=201)
def create_backup(body: SnapshotStart, user: User = Depends(current_user), db: Session = Depends(session)):
    row = Snapshot(id=str(uuid.uuid4()), user_id=user.id, size=body.size, checksum=body.sha256, verified=False)
    db.add(row)
    db.commit()
    return {"id": row.id, "chunk_bytes": CHUNK_SIZE}

@app.put("/api/backups/{sid}/chunks/{part}")
def upload_backup_chunk(sid: str, part: int, body: ChunkInput, user: User = Depends(current_user), db: Session = Depends(session)):
    row = own_snapshot(db, user, sid)
    if row.verified:
        raise HTTPException(409, "Резервная копия уже проверена")
    n = (row.size + CHUNK_SIZE - 1) // CHUNK_SIZE
    if part < 0 or part >= n:
        raise HTTPException(422, "Номер фрагмента вне диапазона")
    raw = bytes.fromhex(body.hex_data)
    if len(raw) != min(CHUNK_SIZE, row.size - part*CHUNK_SIZE):
        raise HTTPException(422, "Неверный размер фрагмента")
    old = db.get(SnapshotChunk, (sid, part))
    if old:
        if old.payload != raw:
            raise HTTPException(409, "Фрагмент уже существует с другим содержимым")
    else:
        db.add(SnapshotChunk(snapshot_id=sid, part=part, payload=raw))
        db.commit()
    return {"saved": part}

def get_backup_bytes(db, row):
    parts = db.scalars(select(SnapshotChunk).where(SnapshotChunk.snapshot_id==row.id).order_by(SnapshotChunk.part)).all()
    n = (row.size + CHUNK_SIZE - 1) // CHUNK_SIZE
    if len(parts) != n or any(p.part != i for i,p in enumerate(parts)):
        raise HTTPException(409, "Резервная копия загружена не полностью")
    blob = b"".join(p.payload for p in parts)
    if len(blob) != row.size or hashlib.sha256(blob).hexdigest() != row.checksum:
        raise HTTPException(409, "Не совпадает контрольная сумма")
    return blob

@app.post("/api/backups/{sid}/verify")
def verify_backup(sid: str, user: User = Depends(current_user), db: Session = Depends(session)):
    row = own_snapshot(db, user, sid)
    blob = get_backup_bytes(db, row)
    try:
        value = json.loads(blob)
    except (ValueError, UnicodeDecodeError):
        raise HTTPException(422, "Некорректный файл JSON")
    if not isinstance(value, (dict,list)):
        raise HTTPException(422, "Неожиданный формат JSON")
    row.verified = True
    db.commit()
    return {"verified": True, "bytes": row.size, "sha256": row.checksum, "id": row.id}

@app.get("/api/backups")
def list_backups(user: User = Depends(current_user), db: Session = Depends(session)):
    items = db.scalars(select(Snapshot).where(Snapshot.user_id==user.id)).all()
    return [{"id": x.id, "bytes": x.size, "verified": x.verified, "sha256": x.checksum} for x in items]

@app.get("/api/backups/{sid}/download")
def download_backup(sid: str, user: User = Depends(current_user), db: Session = Depends(session)):
    row = own_snapshot(db, user, sid)
    if not row.verified:
        raise HTTPException(409, "Резервная копия не проверена")
    blob = get_backup_bytes(db,row)
    return Response(blob, media_type="application/json", headers={
        "Content-Disposition": 'attachment; filename="freedom-realty-snapshot.json"',
        "Cache-Control": "no-store"
    })


# Lossless personal-notebook synchronization. No automatic destructive merging.
import gzip
import hashlib
import json
from sqlalchemy import LargeBinary, update
from sqlalchemy.exc import IntegrityError
from fastapi.responses import JSONResponse

MAX_SYNC_JSON = 100 * 1024 * 1024
MAX_SYNC_GZIP = 60 * 1024 * 1024
STATE_LISTS = ("properties", "queue", "clients", "collections", "notes", "showings", "sources")

class CloudState(Base):
    __tablename__ = "cloud_states"
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    packed: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    checksum: Mapped[str] = mapped_column(String(64), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

class CloudStateHistory(Base):
    __tablename__ = "cloud_state_history"
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    version: Mapped[int] = mapped_column(Integer, primary_key=True)
    packed: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    checksum: Mapped[str] = mapped_column(String(64), nullable=False)

Base.metadata.create_all(engine)

class CloudStateInput(BaseModel):
    expected_version: int = Field(ge=0)
    data: dict
    allow_shrink: bool = False

def state_counts(value):
    return {key: len(value[key]) for key in STATE_LISTS}

def encode_cloud_state(value):
    if not isinstance(value, dict) or any(not isinstance(value.get(key), list) for key in STATE_LISTS):
        raise HTTPException(422, "Ожидается полный экспорт Блокнота с семью разделами")
    for key in STATE_LISTS:
        items = value[key]
        if not all(isinstance(x, dict) and isinstance(x.get("id"), str) and x["id"] for x in items):
            raise HTTPException(422, "У записей отсутствуют строковые идентификаторы: " + key)
        ids = [x["id"] for x in items]
        if len(ids) != len(set(ids)):
            raise HTTPException(422, "Найдены повторяющиеся ID: " + key)
    raw = json.dumps(value, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8")
    if len(raw) > MAX_SYNC_JSON:
        raise HTTPException(413, "Размер каталога превышает ограничение 100 МБ")
    packed = gzip.compress(raw, compresslevel=6)
    if len(packed) > MAX_SYNC_GZIP:
        raise HTTPException(413, "Сжатый каталог превышает ограничение 60 МБ")
    return packed, hashlib.sha256(raw).hexdigest()

def decode_cloud_state(packed, checksum):
    raw = gzip.decompress(packed)
    if len(raw) > MAX_SYNC_JSON or hashlib.sha256(raw).hexdigest() != checksum:
        raise HTTPException(500, "Ошибка целостности сохранённого каталога")
    return json.loads(raw)

@app.get("/api/sync/state")
def fetch_cloud_state(user: User = Depends(current_user), db: Session = Depends(session)):
    row = db.get(CloudState, user.id)
    if row is None:
        return JSONResponse({"version": 0, "data": None}, headers={"Cache-Control": "no-store"})
    return JSONResponse({"version": row.version, "data": decode_cloud_state(row.packed, row.checksum),
                         "sha256": row.checksum, "updated_at": row.updated_at.isoformat()},
                        headers={"Cache-Control": "no-store"})

@app.put("/api/sync/state")
def push_cloud_state(body: CloudStateInput, user: User = Depends(current_user), db: Session = Depends(session)):
    packed, checksum = encode_cloud_state(body.data)
    previous = db.get(CloudState, user.id)
    if previous is None:
        if body.expected_version != 0:
            raise HTTPException(409, "Версия облака отличается. Сначала загрузите облачную копию.")
        db.add(CloudState(user_id=user.id, version=1, packed=packed, checksum=checksum, updated_at=datetime.now(timezone.utc)))
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            raise HTTPException(409, "Облачный каталог уже создан на другом устройстве")
        return {"version": 1, "sha256": checksum, "counts": state_counts(body.data)}
    if previous.version != body.expected_version:
        raise HTTPException(409, "Облачная база изменена на другом устройстве: перезагрузите её перед сохранением")
    old_data = decode_cloud_state(previous.packed, previous.checksum)
    if not body.allow_shrink:
        for key in ("properties", "queue", "clients", "collections", "notes", "showings"):
            if len(old_data[key]) > 0 and len(body.data[key]) < len(old_data[key]) * 0.9:
                raise HTTPException(409, "Подозрение на потерю записей раздела " + key + ". Требуется подтверждённое восстановление.")
    db.add(CloudStateHistory(user_id=user.id, version=previous.version, packed=previous.packed, checksum=previous.checksum))
    result = db.execute(update(CloudState).where(
        CloudState.user_id == user.id, CloudState.version == body.expected_version
    ).values(version=body.expected_version+1, packed=packed, checksum=checksum,
             updated_at=datetime.now(timezone.utc)))
    if result.rowcount != 1:
        db.rollback()
        raise HTTPException(409, "Конфликт одновременных изменений")
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Конфликт сохранения версии")
    return {"version": body.expected_version+1, "sha256": checksum, "counts": state_counts(body.data)}

@app.get("/api/sync/history")
def cloud_state_history(user: User = Depends(current_user), db: Session = Depends(session)):
    records = db.scalars(select(CloudStateHistory).where(CloudStateHistory.user_id == user.id)
                         .order_by(CloudStateHistory.version.desc()).limit(30)).all()
    return [{"version": r.version, "sha256": r.checksum} for r in records]

@app.get("/api/sync/history/{version}")
def cloud_state_recovery(version: int, user: User = Depends(current_user), db: Session = Depends(session)):
    row = db.get(CloudStateHistory, (user.id, version))
    if row is None:
        raise HTTPException(404, "Предыдущая версия не найдена")
    return JSONResponse({"version": version, "data": decode_cloud_state(row.packed, row.checksum)},
                        headers={"Cache-Control": "no-store"})
