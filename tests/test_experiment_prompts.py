from fastapi.testclient import TestClient

from app.conversations.store import InMemoryConversationStore
from app.experiment.catalog import get_condition_catalog
from app.experiment.overrides import (
    effective_system_prompt,
    load_overrides,
    overrides_path,
    reset_override,
)
from app.main import app
from tests.test_experiment_api import EMAIL_HEADER, ChunkRetriever, RecordingGenerator, _client

CUSTOM = "Answer in one short sentence and stay with the evidence."
PATHS = ("k7q2", "m3x9", "p8d4", "t5w1")


def _clear_overrides() -> None:
    path = overrides_path()
    if path.exists():
        path.unlink()


def test_editor_lists_four_builtin_prompts() -> None:
    _clear_overrides()
    response = TestClient(app).get("/prompts")

    assert response.status_code == 200
    html = response.text
    assert html.count('name="prompt"') == 4
    assert "Built-in prompt" in html
    assert "Saved prompt" not in html
    for path, marker in (
        ("k7q2", "limited and uncertain, and your tone is cold"),
        ("m3x9", "friendly and encouraging, and you are not very sure"),
        ("p8d4", "cold and formal"),
        ("t5w1", "precise and confident, and you are also friendly and supportive"),
    ):
        assert f"/{path}" in html
        assert marker in html
    assert "condition_id" not in html
    assert "competence" not in html.casefold()
    assert "warmth" not in html.casefold()
    assert "/prompts" not in TestClient(app).get("/k7q2").text


def test_saved_prompt_is_used_on_that_path_and_restore_returns_the_default() -> None:
    _clear_overrides()
    catalog = get_condition_catalog()
    try:
        page = TestClient(app)
        saved = page.post("/prompts/k7q2", data={"prompt": CUSTOM})
        assert saved.status_code == 200
        assert "Saved the prompt for /k7q2." in saved.text
        assert CUSTOM in saved.text
        assert "Saved prompt" in saved.text
        assert "friendly and encouraging, and you are not very sure" in saved.text
        assert CUSTOM not in catalog.require("k7q2").system_prompt

        generator = RecordingGenerator()
        chat = _client(InMemoryConversationStore(), generator, ChunkRetriever())
        used = chat.post(
            "/api/v1/chat/k7q2/messages",
            json={"message": "When is the graduation ceremony?"},
            headers=EMAIL_HEADER,
        )
        other = chat.post(
            "/api/v1/chat/m3x9/messages",
            json={"message": "When is the graduation ceremony?"},
            headers=EMAIL_HEADER,
        )
        assert used.status_code == 200
        assert other.status_code == 200
        assert generator.calls[-2]["system_prompt"] == CUSTOM
        assert "friendly and encouraging" in generator.calls[-1]["system_prompt"]

        restored = page.post("/prompts/k7q2/reset", data={"prompt": "ignored"})
        assert "Restored the built-in prompt for /k7q2." in restored.text
        assert "limited and uncertain, and your tone is cold" in restored.text
        assert CUSTOM not in restored.text
        assert "k7q2" not in load_overrides()

        chat.post(
            "/api/v1/chat/k7q2/messages",
            json={"message": "When is the graduation ceremony?"},
            headers=EMAIL_HEADER,
        )
        assert "limited and uncertain" in generator.calls[-1]["system_prompt"]
    finally:
        _clear_overrides()


def test_empty_prompt_is_rejected_and_unknown_path_is_missing() -> None:
    _clear_overrides()
    client = TestClient(app)
    rejected = client.post("/prompts/p8d4", data={"prompt": "   "})
    assert rejected.status_code == 400
    assert "Enter a prompt before saving." in rejected.text
    assert load_overrides() == {}
    assert client.post("/prompts/nope", data={"prompt": CUSTOM}).status_code == 404
    assert client.post("/prompts/nope/reset").status_code == 404


def test_unreadable_override_file_falls_back_to_the_builtin_prompt() -> None:
    path = overrides_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{", encoding="utf-8")
    try:
        assert load_overrides() == {}
        condition = get_condition_catalog().require("t5w1")
        assert effective_system_prompt(condition) == condition.system_prompt
    finally:
        _clear_overrides()


def test_reset_is_safe_when_the_path_was_never_customized() -> None:
    _clear_overrides()
    reset_override("t5w1")
    assert load_overrides() == {}
