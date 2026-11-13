"""Safe seed import into versioned PostgreSQL; dry-run is the default.
No updates or deletions; conflicting IDs stop the entire transaction.
Do not use for private client records; those belong to encrypted account snapshots.
"""
import argparse
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from sqlalchemy import select, func
from main import SessionLocal, CatalogEntry, ENVIRONMENT, DATABASE_URL

KIND_MAP = {"properties": "property", "pendingProperties": "pending", "sources": "source"}
SOURCE_BACKUP_SHA = "187dfd2f0bc03c2b174f8c6df223015fe6932491cad718b06d6b57edfedbbafb"

def parse(path):
    binary = Path(path).read_bytes()
    digest = hashlib.sha256(binary).hexdigest()
    value = json.loads(binary)
    if not isinstance(value, dict):
        raise ValueError("Expected a catalog JSON object")
    verified = {}
    for label, kind in KIND_MAP.items():
        rows = value.get(label)
        if not isinstance(rows, list):
            raise ValueError("Missing array: " + label)
        if not all(isinstance(x, dict) and isinstance(x.get("id"), str) and x["id"] for x in rows):
            raise ValueError("Invalid record id in " + label)
        ids = [x["id"] for x in rows]
        if len(ids) != len(set(ids)):
            raise ValueError("Duplicate IDs in " + label)
        verified[kind] = rows
    return digest, verified

def run():
    ap = argparse.ArgumentParser()
    ap.add_argument("catalog")
    ap.add_argument("--apply", action="store_true", help="Write only after human-reviewed database readiness")
    ap.add_argument("--confirm-sha", default="")
    ap.add_argument("--expected-properties", type=int, default=1161)
    ap.add_argument("--expected-pending", type=int, default=532)
    ap.add_argument("--expected-sources", type=int, default=96)
    args = ap.parse_args()
    digest, groups = parse(args.catalog)
    expected = {"property": args.expected_properties, "pending": args.expected_pending, "source": args.expected_sources}
    counts = {name: len(rows) for name, rows in groups.items()}
    if counts != expected:
        raise SystemExit("FAIL: source counts mismatch " + str(counts))
    print(json.dumps({"dry_run": not args.apply, "sha256": digest, "counts": counts}, ensure_ascii=False))
    if not args.apply:
        return
    if ENVIRONMENT != "production" or not DATABASE_URL.startswith("postgresql+psycopg://"):
        raise SystemExit("FAIL: importing requires PostgreSQL production environment")
    if os.getenv("ALLOW_CATALOG_IMPORT") != "YES":
        raise SystemExit("FAIL: import gate not enabled")
    if os.getenv("BACKUP_SEED_SHA256") != SOURCE_BACKUP_SHA:
        raise SystemExit("FAIL: immutable original seed backup has not been acknowledged")
    if args.confirm_sha != digest:
        raise SystemExit("FAIL: confirm-sha mismatch")
    with SessionLocal() as session:
        inserted = 0
        for kind, rows in groups.items():
            for item in rows:
                existing = session.get(CatalogEntry, (kind, item["id"]))
                if existing is not None:
                    if existing.data != item:
                        session.rollback()
                        raise SystemExit("FAIL: existing record mismatch, refused non-idempotent import")
                    continue
                session.add(CatalogEntry(kind=kind, record_id=item["id"], data=item,
                                         source_hash=digest, imported_at=datetime.now(timezone.utc)))
                inserted += 1
        session.commit()
        final = {kind: session.scalar(select(func.count()).select_from(CatalogEntry).where(CatalogEntry.kind==kind))
                 for kind in groups}
        if any(final[k] < counts[k] for k in groups):
            raise SystemExit("FAIL: import count mismatch; check database before any next step")
    print(json.dumps({"status": "committed", "inserted": inserted, "counts_after": final}, ensure_ascii=False))

if __name__ == "__main__":
    run()
