from fastapi.testclient import TestClient

from app.main import app


def test_chat_page_renders() -> None:
    response = TestClient(app).get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "Ask" in response.text
    assert 'id="chat-form"' in response.text
    assert "school-email" in response.text
    assert 'id="notice-panel"' in response.text


def test_static_assets_available() -> None:
    css = TestClient(app).get("/static/chat.css")
    js = TestClient(app).get("/static/chat.js")
    assert css.status_code == 200
    assert "notice-panel" in css.text
    assert js.status_code == 200
    assert "/api/v1/chat" in js.text
    assert "Outside my lane" in js.text
    assert "insufficient_evidence" in js.text
    assert "link.textContent = title" in js.text
    assert "item.append(` — ${citation.location}`)" not in js.text
