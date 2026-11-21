"""Owner-only CLI: grant lifetime complimentary access to an existing verified account.

Usage on the trusted server:
  python grant_complimentary.py --email <email>

Requires DATABASE_URL and confirmation by an administrator with server access.
Never expose this action through a public HTTP endpoint.
"""
import argparse
from sqlalchemy import Table, MetaData, select
from sqlalchemy.orm import Session
from main import User
from main import engine

def grant(email, db):
    email = email.strip().lower()
    user = db.scalar(select(User).where(User.email == email))
    if user is None or not user.email_verified:
        raise ValueError("The user must register and verify their email first")
    Subscription = Table("subscriptions", MetaData(), autoload_with=engine)
    row = db.execute(select(Subscription.c.user_id).where(Subscription.c.user_id == user.id)).first()
    if row is None:
        from datetime import datetime, timedelta, timezone
        now = datetime.now(timezone.utc)
        db.execute(Subscription.insert().values(user_id=user.id,trial_started_at=now,
            trial_ends_at=now+timedelta(days=5),status="complimentary",complimentary=1))
    else:
        db.execute(Subscription.update().where(Subscription.c.user_id == user.id)
                   .values(complimentary=1,status="complimentary"))
    db.commit()
    return user.id

if __name__ == "__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--email",required=True)
    args=parser.parse_args()
    from main import SessionLocal
    with SessionLocal() as db:
        uid=grant(args.email,db)
    print(f"Permanent complimentary access granted to account ID {uid}")
