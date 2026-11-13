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
