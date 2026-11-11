from fastapi.testclient import TestClient

from app.main import app


def test_health_endpoint() -> None:
    response = TestClient(app).get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "unmc-rag"}


def test_ready_endpoint_skips_database_when_unconfigured() -> None:
    response = TestClient(app).get("/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "unmc-rag", "database": "disabled"}
