from fastapi.testclient import TestClient

from app.experiment.catalog import get_condition_catalog
from app.main import app

PATHS = ("k7q2", "m3x9", "p8d4", "t5w1")
FORBIDDEN = ("competence", "warmth", "condition_id", "low competence", "high warmth")


def test_opaque_paths_render_the_same_chat_shell() -> None:
    catalog = get_condition_catalog()
    client = TestClient(app)

    for path in PATHS:
        response = client.get(f"/{path}")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
        html = response.text
        assert 'id="message-list"' in html
        assert 'id="chat-form"' in html
        assert 'id="school-email"' in html
        assert 'id="submit-btn"' in html
        assert ">Send<" in html
        assert f'data-entry-path="{path}"' in html
        assert "/static/session-chat.js" in html

        lowered = html.casefold()
        for word in FORBIDDEN:
            assert word not in lowered

        condition = catalog.require(path)
        assert condition.opening_message in html
        assert condition.persona.split("\n", 1)[0] not in html
        for other in catalog.conditions:
            if other.entry_path != path:
                assert other.entry_path not in html
                assert other.opening_message not in html


def test_unknown_page_is_not_a_study_entry() -> None:
    response = TestClient(app).get("/not-a-study-path")
    assert response.status_code == 404


def test_session_script_does_not_list_conditions() -> None:
    response = TestClient(app).get("/static/session-chat.js")
    assert response.status_code == 200
    script = response.text
    assert "/api/v1/chat/" in script
    assert "sessionStorage" in script
    assert "X-School-Email" in script
    for token in (*PATHS, "LL", "LH", "HL", "HH", "competence", "warmth"):
        assert token not in script
