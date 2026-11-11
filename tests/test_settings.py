import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.experiment.catalog import load_condition_catalog, save_condition_settings
from app.main import app


def _copy_catalog(tmp_path: Path) -> Path:
    source = Path("app/experiment/conditions.json")
    target = tmp_path / "conditions.json"
    target.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
    return target


def test_settings_page_lists_each_study_path() -> None:
    response = TestClient(app).get("/setting")
    assert response.status_code == 200
    html = response.text
    assert "实验条件" in html
    assert "/static/settings.js" in html
    for path in ("k7q2", "m3x9", "p8d4", "t5w1"):
        assert f'data-entry-path="{path}"' in html
    assert "使用 RAG 检索" in html


def test_save_condition_settings_updates_persona_and_rag(tmp_path: Path) -> None:
    path = _copy_catalog(tmp_path)
    original = load_condition_catalog(path)
    payload = {
        "shared_rules": original.conditions[0].shared_rules,
        "shared_rules_without_rag": original.conditions[0].shared_rules_no_rag,
        "conditions": [
            {
                "entry_path": condition.entry_path,
                "persona": (
                    condition.persona + "\n设置页追加的一句。"
                    if condition.entry_path == "k7q2"
                    else condition.persona
                ),
                "rag_enabled": condition.entry_path != "m3x9",
            }
            for condition in original.conditions
        ],
    }

    saved = save_condition_settings(payload, path)
    assert "设置页追加的一句。" in saved.require("k7q2").persona
    assert saved.require("m3x9").rag_enabled is False
    assert saved.require("k7q2").rag_enabled is True

    stored = json.loads(path.read_text(encoding="utf-8"))
    by_path = {item["entry_path"]: item for item in stored["conditions"]}
    assert by_path["m3x9"]["rag_enabled"] is False
    assert by_path["k7q2"]["opening_message"]


def test_settings_api_rejects_a_blank_persona(tmp_path: Path, monkeypatch) -> None:
    path = _copy_catalog(tmp_path)
    monkeypatch.setattr("app.experiment.catalog.catalog_path", lambda: path)
    catalog = load_condition_catalog(path)
    body = {
        "shared_rules": catalog.conditions[0].shared_rules,
        "shared_rules_without_rag": catalog.conditions[0].shared_rules_no_rag,
        "conditions": [
            {
                "entry_path": condition.entry_path,
                "persona": "" if condition.entry_path == "t5w1" else condition.persona,
                "rag_enabled": True,
            }
            for condition in catalog.conditions
        ],
    }

    response = TestClient(app).put("/api/v1/settings/conditions", json=body)
    assert response.status_code == 400
