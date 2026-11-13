import json
from datetime import datetime, timezone, timedelta
from urllib.request import Request
import pytest
from yookassa import create_payment, fetch_payment, validate_paid, extend_paid_until, YooKassaError

class FakeResponse:
    def __init__(self, data): self.data = data
    def __enter__(self): return self
    def __exit__(self, *args): pass
    def read(self): return json.dumps(self.data).encode()

def test_checkout_server_credentials_and_fixed_price(monkeypatch):
    monkeypatch.setenv("YOOKASSA_SHOP_ID", "test_shop")
    monkeypatch.setenv("YOOKASSA_SECRET_KEY", "secret")
    def opener(req: Request, timeout):
        assert req.get_method() == "POST"
        assert req.get_header("Idempotence-key") == "order-123"
        assert req.get_header("Authorization").startswith("Basic ")
        data = json.loads(req.data)
        assert data["amount"] == {"value": "680.00", "currency": "RUB"}
        assert data["capture"] is True
        assert data["metadata"] == {"order_id": "order-123", "user_id": "42", "plan": "realtor_monthly"}
        assert "receipt" not in data
        return FakeResponse({"id": "abc-123", "confirmation": {"confirmation_url": "https://yoomoney.ru/checkout/test"}})
    result = create_payment(order_id="order-123", user_id=42,
        return_url="https://diary.example.com/", opener=opener)
    assert result["id"] == "abc-123"

def test_fail_closed_when_keys_missing(monkeypatch):
    monkeypatch.delenv("YOOKASSA_SHOP_ID", raising=False)
    monkeypatch.delenv("YOOKASSA_SECRET_KEY", raising=False)
    with pytest.raises(YooKassaError):
        create_payment(order_id="order", user_id=1, return_url="https://example.com/")

def test_webhook_data_never_trusted_without_verified_payment():
    valid = {"id": "abc-123", "status": "succeeded", "paid": True,
        "amount": {"value": "680.00", "currency": "RUB"},
        "metadata": {"order_id": "order-123", "user_id": "42", "plan": "realtor_monthly"}}
    assert validate_paid(valid, payment_id="abc-123", order_id="order-123", user_id=42)
    for key, wrong in [("status", "pending"), ("paid", False),
                       ("amount", {"value": "6.80", "currency": "RUB"}),
                       ("id", "another")]:
        p = dict(valid, **{key: wrong})
        assert not validate_paid(p, payment_id="abc-123", order_id="order-123", user_id=42)
    p = dict(valid, metadata={"order_id": "order-123", "user_id": "999", "plan": "realtor_monthly"})
    assert not validate_paid(p, payment_id="abc-123", order_id="order-123", user_id=42)

def test_renewal_stacks_from_current_expiry():
    now = datetime(2026, 11, 13, tzinfo=timezone.utc)
    assert extend_paid_until(None, at=now) == now + timedelta(days=30)
    assert extend_paid_until(now + timedelta(days=10), at=now) == now + timedelta(days=40)
