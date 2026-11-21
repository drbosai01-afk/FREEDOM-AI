from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from subscription import TRIAL_DAYS, MONTHLY_PRICE_RUB, entitlement, require_entitlement

NOW = datetime(2026, 11, 13, 12, tzinfo=timezone.utc)

def test_trial_last_five_days_and_expires_exactly():
    row = SimpleNamespace(trial_started_at=NOW, trial_ends_at=NOW+timedelta(days=5), paid_until=None)
    assert TRIAL_DAYS == 5
    assert MONTHLY_PRICE_RUB == 680
    assert entitlement(row, at=NOW)["status"] == "trial"
    assert entitlement(row, at=NOW+timedelta(days=5)-timedelta(seconds=1))["allowed"]
    assert entitlement(row, at=NOW+timedelta(days=5))["status"] == "expired"

def test_paid_period_after_trial_and_no_auto_charge():
    row = SimpleNamespace(trial_started_at=NOW-timedelta(days=30),
        trial_ends_at=NOW-timedelta(days=25), paid_until=NOW+timedelta(days=10))
    assert entitlement(row, at=NOW)["status"] == "paid"
    assert entitlement(row, at=NOW+timedelta(days=10))["status"] == "expired"

def test_no_record_means_denied():
    from fastapi import HTTPException
    assert entitlement(None, at=NOW)["allowed"] is False
    try:
        require_entitlement(None, at=NOW)
        assert False, "must deny access"
    except HTTPException as error:
        assert error.status_code == 402
