"""Five-day free trial and 680 RUB/month access policy.

Never charge automatically. A payment provider must verify a signed webhook before
granting a paid period. Keep license data separate from user records.
"""
from datetime import datetime, timedelta, timezone
from sqlalchemy import DateTime, ForeignKey, Integer, String, select
from sqlalchemy.orm import Mapped, mapped_column

TRIAL_DAYS = 5
MONTHLY_PRICE_RUB = 680
PLAN_CODE = "realtor_monthly"

def utcnow():
    return datetime.now(timezone.utc)

def configure_subscription(Base):
    class Subscription(Base):
        __tablename__ = "subscriptions"
        user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
        trial_started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
        trial_ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
        paid_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
        payment_provider: Mapped[str | None] = mapped_column(String(40), nullable=True)
        provider_customer_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
        status: Mapped[str] = mapped_column(String(20), nullable=False, default="trial")
        complimentary: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    return Subscription

def activate_trial(db, model, user_id: int, *, at=None):
    """Create once. Repeated registration/login cannot reset the trial."""
    current = db.get(model, user_id)
    if current is not None:
        return current
    at = at or utcnow()
    row = model(user_id=user_id, trial_started_at=at,
                trial_ends_at=at + timedelta(days=TRIAL_DAYS),
                status="trial")
    db.add(row)
    db.flush()
    return row

def entitlement(row, *, at=None):
    at = at or utcnow()
    if row is None:
        return {"status": "inactive", "allowed": False, "trial_ends_at": None,
                "paid_until": None, "monthly_price_rub": MONTHLY_PRICE_RUB,
                "currency": "RUB", "plan": PLAN_CODE}
    if getattr(row, "complimentary", 0) == 1:
        return {"status": "complimentary", "allowed": True, "trial_ends_at": None,
                "paid_until": None, "monthly_price_rub": MONTHLY_PRICE_RUB,
                "currency": "RUB", "plan": PLAN_CODE}
    trial_end = row.trial_ends_at.replace(tzinfo=timezone.utc) if row.trial_ends_at.tzinfo is None else row.trial_ends_at
    paid_end = row.paid_until.replace(tzinfo=timezone.utc) if row.paid_until and row.paid_until.tzinfo is None else row.paid_until
    status = "paid" if paid_end and paid_end > at else "trial" if trial_end > at else "expired"
    return {"status": status, "allowed": status in ("trial", "paid"),
            "trial_ends_at": trial_end.isoformat(),
            "paid_until": paid_end.isoformat() if paid_end else None,
            "monthly_price_rub": MONTHLY_PRICE_RUB, "currency": "RUB", "plan": PLAN_CODE}

def require_entitlement(row, *, at=None):
    from fastapi import HTTPException
    value = entitlement(row, at=at)
    if not value["allowed"]:
        raise HTTPException(402, detail="Пробный период завершён. Для продолжения нужна подписка 680 ₽/мес.")
    return value
