import os
import uuid
os.environ.setdefault("JWT_SECRET", "unit-test-secret-do-not-use-in-production")
os.environ["DATABASE_URL"] = "sqlite:///./test_" + uuid.uuid4().hex + ".db"
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def account(email):
    result = client.post("/api/register", json={"email": email, "password": "secure_password_2026"})
    assert result.status_code == 201, result.text
    return {"Authorization": "Bearer " + result.json()["access_token"]}

def test_auth_and_private_sync():
    a = account("a_" + uuid.uuid4().hex + "@example.com")
    b = account("b_" + uuid.uuid4().hex + "@example.com")
    payload = {"record_id": "flat_1", "version": 0, "data": {"title": "Квартира", "price": "5000000"}}
    r = client.put("/api/records/properties", headers=a, json=payload)
    assert r.status_code == 200
    assert r.json()["version"] == 1
    assert len(client.get("/api/records/properties", headers=a).json()) == 1
    assert client.get("/api/records/properties", headers=b).json() == []
    assert client.get("/api/records/properties").status_code == 401
    assert client.put("/api/records/properties", headers=a, json=payload).status_code == 409
    payload["version"] = 1
    payload["data"]["price"] = "4900000"
    assert client.put("/api/records/properties", headers=a, json=payload).json()["version"] == 2
    assert client.delete("/api/records/properties/flat_1?version=1", headers=a).status_code == 409
    assert client.delete("/api/records/properties/flat_1?version=2", headers=a).status_code == 200
    assert client.get("/api/records/properties", headers=a).json() == []

def test_login_validation():
    email = "c_" + uuid.uuid4().hex + "@example.com"
    account(email)
    assert client.post("/api/login", json={"email": email, "password": "wrong_password_111"}).status_code == 401
    assert client.post("/api/login", json={"email": email, "password": "secure_password_2026"}).status_code == 200
    assert client.get("/api/records/wrong", headers=account("d_"+uuid.uuid4().hex+"@example.com")).status_code == 422

def test_catalog_import_scoped_deduplicated_and_atomic():
    a = account("import_a_" + uuid.uuid4().hex + "@example.com")
    b = account("import_b_" + uuid.uuid4().hex + "@example.com")
    item = {"record_id": "legacy_catalog_0001", "data": {
        "title": "ЖК Тест", "address": "Краснодар", "price": "4000000", "source": "test"}}
    endpoint = "/api/import/properties"
    first = client.post(endpoint, headers=a, json={"records": [item]})
    assert first.status_code == 200, first.text
    assert first.json() == {"added": 1, "skipped_existing": 0, "received": 1}
    second = client.post(endpoint, headers=a, json={"records": [item]})
    assert second.status_code == 200 and second.json()["skipped_existing"] == 1
    assert len(client.get("/api/records/properties", headers=a).json()) == 1
    assert client.get("/api/records/properties", headers=b).json() == []
    assert client.post(endpoint, json={"records": [item]}).status_code == 401
    bad = {"record_id": "legacy_catalog_0002", "data": {"title": "Вторая", "safe_code": "1234"}}
    assert client.post(endpoint, headers=a, json={"records": [item, bad]}).status_code == 422
    assert len(client.get("/api/records/properties", headers=a).json()) == 1
    assert client.post(endpoint, headers=a, json={"records": [item, item]}).status_code == 422
    assert client.post(endpoint, headers=a, json={"records": []}).status_code == 422

def test_snapshot_chunk_verify_download_and_user_isolation():
    import hashlib
    import json
    raw = json.dumps({"records": [{"id": "flat", "photos": ["photo-data"], "status": "review"}]}, ensure_ascii=False).encode()
    a = account("backup_a_" + uuid.uuid4().hex + "@example.com")
    b = account("backup_b_" + uuid.uuid4().hex + "@example.com")
    digest = hashlib.sha256(raw).hexdigest()
    s = client.post("/api/backups", headers=a, json={"size": len(raw), "sha256": digest})
    assert s.status_code == 201, s.text
    sid = s.json()["id"]
    assert client.get(f"/api/backups/{sid}/download", headers=a).status_code == 409
    assert client.put(f"/api/backups/{sid}/chunks/0", headers=b, json={"hex_data": raw.hex()}).status_code == 404
    assert client.put(f"/api/backups/{sid}/chunks/0", headers=a, json={"hex_data": raw.hex()}).status_code == 200
    assert client.post(f"/api/backups/{sid}/verify", headers=a).json()["verified"] is True
    result = client.get(f"/api/backups/{sid}/download", headers=a)
    assert result.content == raw
    assert result.headers["cache-control"] == "no-store"
    assert client.get(f"/api/backups/{sid}/download", headers=b).status_code == 404
    assert client.put(f"/api/backups/{sid}/chunks/0", headers=a, json={"hex_data": raw.hex()}).status_code == 409
    assert client.get("/api/backups", headers=b).json() == []
    assert client.get("/api/backups", headers=a).json()[0]["sha256"] == digest

def test_snapshot_rejects_corruption():
    import hashlib
    raw = b'{"example": true}'
    a = account("backup_corrupt_" + uuid.uuid4().hex + "@example.com")
    s = client.post("/api/backups", headers=a, json={"size": len(raw), "sha256": hashlib.sha256(raw).hexdigest()})
    sid = s.json()["id"]
    bad = b'{"example": fals}'
    assert len(bad) == len(raw)
    assert client.put(f"/api/backups/{sid}/chunks/0", headers=a, json={"hex_data": bad.hex()}).status_code == 200
    assert client.post(f"/api/backups/{sid}/verify", headers=a).status_code == 409


def full_notebook():
    return {
        "properties": [{"id": "flat_1", "title": "Квартира", "priceRub": 4500000, "photos": ["data:image/jpeg;base64,AAAA"]}],
        "queue": [{"id": "queue_1", "title": "Требует разбора"}],
        "clients": [{"id": "client_1", "name": "Тестовый клиент", "phone": "+70000000000"}],
        "collections": [], "notes": [], "showings": [], "sources": [{"id": "source_1", "title": "Прайс"}],
        "settings": {"custom": "сохраняется без изменений"}
    }

def test_full_notebook_sync_preserves_fields_and_recovery():
    a = account("sync_a_" + uuid.uuid4().hex + "@example.com")
    b = account("sync_b_" + uuid.uuid4().hex + "@example.com")
    endpoint = "/api/sync/state"
    assert client.get(endpoint, headers=a).json() == {"version": 0, "data": None}
    initial = full_notebook()
    saved = client.put(endpoint, headers=a, json={"expected_version": 0, "data": initial})
    assert saved.status_code == 200, saved.text
    assert saved.json()["version"] == 1
    assert client.get(endpoint, headers=a).json()["data"] == initial
    assert client.get(endpoint, headers=b).json()["data"] is None
    assert client.get(endpoint).status_code == 401
    changed = full_notebook()
    changed["properties"][0]["priceRub"] = 4300000
    assert client.put(endpoint, headers=a, json={"expected_version": 0, "data": changed}).status_code == 409
    up = client.put(endpoint, headers=a, json={"expected_version": 1, "data": changed})
    assert up.status_code == 200 and up.json()["version"] == 2
    recovered = client.get("/api/sync/history/1", headers=a)
    assert recovered.json()["data"] == initial
    assert client.get("/api/sync/history/1", headers=b).status_code == 404
    assert client.get(endpoint, headers=a).json()["data"] == changed
    assert client.get("/api/sync/history", headers=a).json()[0]["version"] == 1

def test_sync_rejects_truncated_state_and_duplicate_ids():
    a = account("sync_validate_" + uuid.uuid4().hex + "@example.com")
    endpoint = "/api/sync/state"
    assert client.put(endpoint, headers=a, json={"expected_version": 0, "data": {"properties": []}}).status_code == 422
    duplicate = full_notebook()
    duplicate["properties"] *= 2
    assert client.put(endpoint, headers=a, json={"expected_version": 0, "data": duplicate}).status_code == 422
    initial = full_notebook()
    initial["properties"] = [{"id": "p_" + str(n)} for n in range(20)]
    assert client.put(endpoint, headers=a, json={"expected_version": 0, "data": initial}).status_code == 200
    incomplete = full_notebook()
    assert client.put(endpoint, headers=a, json={"expected_version": 1, "data": incomplete}).status_code == 409
    assert client.get(endpoint, headers=a).json()["data"] == initial
    ok = client.put(endpoint, headers=a, json={"expected_version": 1, "data": incomplete, "allow_shrink": True})
    assert ok.status_code == 200


def test_sync_catalog_large_counts():
    a = account("sync_many_" + uuid.uuid4().hex + "@example.com")
    value = full_notebook()
    value["properties"] = [{"id": "flat_"+str(i), "title": "Объект "+str(i), "priceRub": 3000000+i} for i in range(1161)]
    value["queue"] = [{"id": "queue_"+str(i), "status": "review"} for i in range(532)]
    value["sources"] = [{"id": "source_"+str(i), "sourceUrl": "https://example.com"} for i in range(96)]
    saved = client.put("/api/sync/state", headers=a, json={"expected_version": 0, "data": value})
    assert saved.status_code == 200, saved.text
    assert saved.json()["counts"]["properties"] == 1161
    assert saved.json()["counts"]["queue"] == 532
    assert saved.json()["counts"]["sources"] == 96
    loaded = client.get("/api/sync/state", headers=a)
    assert loaded.status_code == 200
    assert loaded.json()["data"] == value


def test_alembic_upgrade_from_empty_database(tmp_path):
    import subprocess
    import sys
    from pathlib import Path
    dbfile = tmp_path / "migration-test.sqlite3"
    env = os.environ.copy()
    env["FREEDOM_MIGRATING"] = "1"
    env["DATABASE_URL"] = "sqlite:///" + str(dbfile)
    env["ENVIRONMENT"] = "test"
    root = Path(__file__).resolve().parent.parent
    result = subprocess.run([sys.executable, "-m", "alembic", "-c", "alembic.ini", "upgrade", "head"],
                            cwd=str(root), env=env, capture_output=True, text=True, timeout=90)
    assert result.returncode == 0, (result.stdout + result.stderr)[-1500:]
    import sqlite3
    with sqlite3.connect(dbfile) as conn:
        present = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        assert {"catalog_entries", "users", "records", "cloud_states", "cloud_state_history",
                "email_challenges", "auth_attempts", "alembic_version"}.issubset(present)
        version = conn.execute("SELECT version_num FROM alembic_version").fetchone()[0]
        assert version == "0002_catalog_entries"

def test_invalid_activation_does_not_verify_account():
    assert client.get("/api/verify-email", params={"token": "invalid" * 10}).status_code == 400

def test_login_rate_limit_is_enforced():
    email = "bruteforce_" + uuid.uuid4().hex + "@example.com"
    for _ in range(12):
        r = client.post("/api/login", json={"email": email, "password": "incorrect_password_2026"})
        assert r.status_code == 401, r.text
    blocked = client.post("/api/login", json={"email": email, "password": "incorrect_password_2026"})
    assert blocked.status_code == 429
    assert blocked.headers["retry-after"] == "3600"


def test_verified_email_flow_without_sending_real_email(monkeypatch):
    import main
    import hashlib
    token = "valid-verification-token-" + uuid.uuid4().hex + uuid.uuid4().hex
    email = "verify_" + uuid.uuid4().hex + "@example.com"
    sent = []
    monkeypatch.setattr(main, "ENVIRONMENT", "production")
    monkeypatch.setattr(main, "send_activation", lambda address, secret: sent.append((address, secret)))
    from fastapi.testclient import TestClient
    isolated = TestClient(main.app)
    created = isolated.post("/api/register", json={"email": email, "password": "secure_password_2026"})
    assert created.status_code == 201, created.text
    assert "access_token" not in created.json()
    assert len(sent) == 1 and sent[0][0] == email
    assert isolated.post("/api/login", json={"email": email, "password": "secure_password_2026"}).status_code == 403
    verified = isolated.get("/api/verify-email", params={"token": sent[0][1]})
    assert verified.status_code == 200 and verified.json()["verified"] is True
    assert isolated.get("/api/verify-email", params={"token": sent[0][1]}).status_code == 400
    assert isolated.post("/api/login", json={"email": email, "password": "secure_password_2026"}).status_code == 200

def test_chunked_sync_roundtrip_and_retry_safety():
    import json
    import hashlib
    user = account("chunks_" + uuid.uuid4().hex + "@example.com")
    full = full_notebook()
    full["properties"] = [{"id": "p_"+str(i), "rawText": "X"*400, "priceRub": 4000000+i}
                          for i in range(1161)]
    full["queue"] = [{"id": "q_"+str(i), "sourceUrl": "https://example.com/"+str(i)}
                     for i in range(532)]
    full["sources"] = [{"id": "s_"+str(i), "name": "Прайс"} for i in range(96)]
    raw = json.dumps(full, ensure_ascii=False).encode("utf8")
    assert len(raw)>128*1024
    started = client.post("/api/backups", headers=user, json={
        "size":len(raw),"sha256":hashlib.sha256(raw).hexdigest()})
    assert started.status_code == 201
    sid = started.json()["id"]
    step = started.json()["chunk_bytes"]
    for i in range(0,len(raw),step):
        body={"hex_data":raw[i:i+step].hex()}
        saved=client.put("/api/backups/"+sid+"/chunks/"+str(i//step),headers=user,json=body)
        assert saved.status_code == 200, saved.text
    assert client.post("/api/backups/"+sid+"/verify",headers=user).status_code == 200
    saved=client.post("/api/sync/from-backup",headers=user,json={
        "snapshot_id":sid,"expected_version":0})
    assert saved.status_code == 200, saved.text
    assert saved.json()["counts"]["properties"] == 1161
    assert client.get("/api/sync/state",headers=user).json()["data"] == full
    assert client.post("/api/sync/from-backup",headers=user,json={
        "snapshot_id":sid,"expected_version":0}).status_code == 409


def test_health_is_not_ready_without_production_postgres():
    result = client.get("/api/health")
    assert result.status_code == 503
    assert result.json()["ready"] is False
    assert result.headers["cache-control"] == "no-store"

def test_catalog_import_is_dry_run_and_non_destructive(tmp_path):
    import json
    import subprocess
    import sys
    from pathlib import Path
    seed = {
        "properties": [{"id": "p_"+str(i)} for i in range(1161)],
        "pendingProperties": [{"id": "q_"+str(i)} for i in range(532)],
        "sources": [{"id": "s_"+str(i)} for i in range(96)]
    }
    source = tmp_path / "synthetic-only.json"
    source.write_text(json.dumps(seed), encoding="utf-8")
    root = Path(__file__).resolve().parent.parent
    p = subprocess.run([sys.executable, "-m", "scripts.import_catalog", str(source)],
                       cwd=str(root), capture_output=True, text=True, timeout=45)
    assert p.returncode == 0, p.stderr
    info = json.loads(p.stdout)
    assert info["dry_run"] is True
    assert info["counts"] == {"property":1161, "pending":532, "source":96}
    # Duplicate IDs are rejected without touching the database.
    seed["properties"][1]["id"] = seed["properties"][0]["id"]
    source.write_text(json.dumps(seed), encoding="utf-8")
    bad = subprocess.run([sys.executable, "-m", "scripts.import_catalog", str(source)],
                         cwd=str(root), capture_output=True, text=True, timeout=45)
    assert bad.returncode != 0
