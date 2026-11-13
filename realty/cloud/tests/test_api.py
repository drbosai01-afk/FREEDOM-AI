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
