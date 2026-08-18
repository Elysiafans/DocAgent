from app.main import app
from fastapi.testclient import TestClient

client = TestClient(app)


def test_health_endpoint():
    resp = client.get("/api/v1/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
