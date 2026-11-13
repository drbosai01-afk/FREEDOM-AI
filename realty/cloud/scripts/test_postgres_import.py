"""Synthetic-only PostgreSQL importer integration test; no real personal data."""
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from sqlalchemy import create_engine, select, func
from main import CatalogEntry

if not os.environ.get("DATABASE_URL", "").startswith("postgresql"):
    raise RuntimeError("Run only against disposable PostgreSQL CI database")
if os.environ.get("ENVIRONMENT") != "production":
    raise RuntimeError("Importer requires the production dialect guard")
parts = {
    "properties": [{"id": "synthetic-flat-" + str(i), "title": "Test apartment " + str(i)} for i in range(1161)],
    "pendingProperties": [{"id": "synthetic-queue-" + str(i)} for i in range(532)],
    "sources": [{"id": "synthetic-source-" + str(i)} for i in range(96)]
}
with tempfile.TemporaryDirectory() as temp:
    path = Path(temp) / "synthetic.json"
    content = json.dumps(parts, separators=(",", ":")).encode()
    path.write_bytes(content)
    digest = hashlib.sha256(content).hexdigest()
    env = os.environ.copy()
    env["ALLOW_CATALOG_IMPORT"] = "YES"
    env["BACKUP_SEED_SHA256"] = "187dfd2f0bc03c2b174f8c6df223015fe6932491cad718b06d6b57edfedbbafb"
    command = [sys.executable, "-m", "scripts.import_catalog", str(path), "--apply", "--confirm-sha", digest]
    for attempt in range(2):
        result = subprocess.run(command, cwd=str(Path(__file__).resolve().parent.parent),
                                env=env, capture_output=True, text=True, timeout=90)
        if result.returncode != 0:
            raise RuntimeError(result.stderr + result.stdout)
        print("import attempt", attempt + 1, result.stdout.strip())
    engine = create_engine(os.environ["DATABASE_URL"])
    with engine.connect() as conn:
        count = conn.scalar(select(func.count()).select_from(CatalogEntry.__table__))
        assert count == 1161 + 532 + 96, count
        assert conn.scalar(select(func.count()).select_from(CatalogEntry.__table__).where(
            CatalogEntry.kind == "property")) == 1161
    print("Synthetic import PostgreSQL count verified:", count)
