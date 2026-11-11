from fastapi.testclient import TestClient

from app.main import app

EMAIL = {"X-School-Email": "student@unmc.edu"}


def test_conversations_stay_available_without_postgres() -> None:
    with TestClient(app) as client:
        listed = client.get("/api/v1/conversations", headers=EMAIL)
        assert listed.status_code == 200
        assert listed.json() == {"conversations": []}

        saved = client.put(
            "/api/v1/conversations/local-1",
            headers=EMAIL,
            json={
                "title": "Graduation",
                "messages": [{"role": "user", "content": "When is graduation?"}],
            },
        )
        assert saved.status_code == 200

        loaded = client.get("/api/v1/conversations/local-1", headers=EMAIL)
        assert loaded.status_code == 200
        body = loaded.json()
        assert body["title"] == "Graduation"
        assert body["messages"][0]["content"] == "When is graduation?"
