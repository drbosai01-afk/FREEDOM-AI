"""YooKassa API adapter. All credentials stay server-side.

Webhook payloads are NOT authenticated: always re-fetch payment from YooKassa
before granting access, validate amount/currency/metadata, and deduplicate.
"""
import base64
import json
import os
import uuid
from datetime import datetime, timedelta, timezone
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

API_ORIGIN = "https://api.yookassa.ru/v3"
PRICE = "680.00"
CURRENCY = "RUB"
PLAN = "realtor_monthly"

class YooKassaError(Exception):
    pass

def credentials():
    shop = os.getenv("YOOKASSA_SHOP_ID", "").strip()
    key = os.getenv("YOOKASSA_SECRET_KEY", "").strip()
    if not shop or not key:
        raise YooKassaError("ЮKassa ещё не подключена: требуются shopId и секретный ключ")
    return shop, key

def api_request(method, path, payload=None, *, idempotence_key=None, opener=urlopen):
    shop, secret = credentials()
    if not path.startswith("/payments") or "://" in path or ".." in path:
        raise ValueError("Invalid payment API path")
    auth = base64.b64encode((shop + ":" + secret).encode()).decode()
    headers = {"Authorization": "Basic " + auth, "Accept": "application/json"}
    data = None
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    if method == "POST":
        if not idempotence_key:
            raise ValueError("POST requires an idempotence key")
        headers["Idempotence-Key"] = idempotence_key
    try:
        with opener(Request(API_ORIGIN + path, data=data, headers=headers, method=method), timeout=12) as response:
            result = json.loads(response.read())
    except (HTTPError, URLError, TimeoutError, ValueError) as exc:
        raise YooKassaError("Платёжный сервис временно недоступен") from exc
    if not isinstance(result, dict):
        raise YooKassaError("Некорректный ответ платёжного сервиса")
    return result

def create_payment(*, order_id, user_id, return_url, receipt_email=None, opener=urlopen):
    if not return_url.startswith("https://"):
        raise ValueError("Return URL must use HTTPS")
    payload = {
        "amount": {"value": PRICE, "currency": CURRENCY},
        "capture": True,
        "confirmation": {"type": "redirect", "return_url": return_url},
        "description": "Дневник риелтора — доступ на 1 месяц",
        "metadata": {"order_id": str(order_id), "user_id": str(user_id), "plan": PLAN},
    }
    # Configure receipts only when YooKassa is responsible for issuing them.
    if receipt_email and os.getenv("YOOKASSA_RECEIPTS_ENABLED") == "1":
        payload["receipt"] = {"customer": {"email": receipt_email},
            "items": [{"description": "Дневник риелтора — подписка на 1 месяц",
                       "quantity": "1.00", "amount": {"value": PRICE, "currency": CURRENCY},
                       "vat_code": int(os.getenv("YOOKASSA_VAT_CODE", "1")),
                       "payment_mode": "full_payment", "payment_subject": "service"}]}
    result = api_request("POST", "/payments", payload, idempotence_key=str(order_id), opener=opener)
    if not result.get("id") or not result.get("confirmation", {}).get("confirmation_url"):
        raise YooKassaError("ЮKassa не вернула ссылку для оплаты")
    return result

def fetch_payment(payment_id, *, opener=urlopen):
    if not isinstance(payment_id, str) or not 1 <= len(payment_id) <= 80 or any(c not in "0123456789abcdef-" for c in payment_id.lower()):
        raise ValueError("Invalid payment ID")
    return api_request("GET", "/payments/" + quote(payment_id, safe=""), opener=opener)

def validate_paid(payment, *, payment_id, order_id, user_id):
    return (
        payment.get("id") == payment_id
        and payment.get("status") == "succeeded"
        and payment.get("paid") is True
        and payment.get("amount") == {"value": PRICE, "currency": CURRENCY}
        and payment.get("metadata", {}).get("order_id") == str(order_id)
        and payment.get("metadata", {}).get("user_id") == str(user_id)
        and payment.get("metadata", {}).get("plan") == PLAN
        and payment.get("refunded_amount", {}).get("value", "0.00") == "0.00"
    )

def extend_paid_until(previous, *, at=None):
    at = at or datetime.now(timezone.utc)
    if previous and previous.tzinfo is None:
        previous = previous.replace(tzinfo=timezone.utc)
    start = max(at, previous) if previous else at
    return start + timedelta(days=30)
