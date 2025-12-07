# tests/test_main.py
from fastapi.testclient import TestClient
from app.main import app
from app.database import Base, engine

# Reset DB for tests
Base.metadata.drop_all(bind=engine)
Base.metadata.create_all(bind=engine)

client = TestClient(app)

def test_create_short_url():
    payload = {"url": "https://example.com"}
    resp = client.post("/api/shorten", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["original_url"] == "https://example.com"
    assert "short_code" in data


def test_invalid_url():
    payload = {"url": "not-a-valid-url"}
    resp = client.post("/api/shorten", json=payload)
    # handled by validation exception handler
    assert resp.status_code == 422
    data = resp.json()
    assert data["detail"] == "Invalid request data"


def test_redirect_and_click_count():
    payload = {"url": "https://example.com"}
    resp = client.post("/api/shorten", json=payload)
    short_code = resp.json()["short_code"]

    resp2 = client.get(f"/{short_code}", allow_redirects=False)
    assert resp2.status_code == 307
    assert resp2.headers["location"] == "https://example.com"

    resp3 = client.get(f"/api/stats/{short_code}")
    data = resp3.json()
    assert data["click_count"] == 1


def test_expiry():
    payload = {"url": "https://example.com", "expires_in_days": 0}
    resp = client.post("/api/shorten", json=payload)
    short_code = resp.json()["short_code"]

    resp2 = client.get(f"/{short_code}", allow_redirects=False)
    assert resp2.status_code == 410


def test_custom_alias():
    payload = {"url": "https://example.org", "custom_alias": "uma123"}
    resp = client.post("/api/shorten", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["short_code"] == "uma123"

    # same alias should fail
    resp2 = client.post("/api/shorten", json=payload)
    assert resp2.status_code == 400


def test_qr_endpoint():
    payload = {"url": "https://example.net"}
    resp = client.post("/api/shorten", json=payload)
    short_code = resp.json()["short_code"]

    qr_resp = client.get(f"/api/qr/{short_code}")
    assert qr_resp.status_code == 200
    assert qr_resp.headers["content-type"] == "image/png"
