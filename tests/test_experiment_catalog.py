import json
from pathlib import Path

import pytest

from app.api.experiment import clip_dialogue
from app.experiment.catalog import get_condition_catalog, load_condition_catalog
from app.rag.contracts import DialogueTurn

DOCUMENTED_MAPPING = {
    "k7q2": "LL",
    "m3x9": "LH",
    "p8d4": "HL",
    "t5w1": "HH",
}

PROMPT_MARKERS = {
    "k7q2": "能力混淆",
    "m3x9": "不改变内容深度",
    "p8d4": "禁止为让用户听懂",
    "t5w1": "温和易懂地表达专业内容",
}


def test_documented_path_mapping_and_distinct_prompts() -> None:
    catalog = get_condition_catalog()

    assert catalog.mapping() == DOCUMENTED_MAPPING
    prompts = [catalog.require(path).system_prompt for path in DOCUMENTED_MAPPING]
    assert len(set(prompts)) == 4
    for path, marker in PROMPT_MARKERS.items():
        condition = catalog.require(path)
        assert marker in condition.system_prompt
        assert condition.condition_id == DOCUMENTED_MAPPING[path]
        assert marker not in condition.opening_message


def test_catalog_rejects_participant_facing_condition_labels(tmp_path: Path) -> None:
    source = Path("app/experiment/conditions.json").read_text(encoding="utf-8")
    payload = json.loads(source)
    payload["conditions"][0]["opening_message"] = "You are in the LL group."
    path = tmp_path / "conditions.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="opening_message"):
        load_condition_catalog(path)


def test_nginx_proxies_each_study_path() -> None:
    nginx = Path("deploy/nginx.conf").read_text(encoding="utf-8")
    for path in DOCUMENTED_MAPPING:
        assert path in nginx


def test_clip_dialogue_keeps_the_newest_turns() -> None:
    turns = [DialogueTurn(role="user", content=str(index)) for index in range(5)]

    assert [turn.content for turn in clip_dialogue(turns, 2)] == ["3", "4"]
    assert clip_dialogue(turns, 0) == []


def _write_catalog(tmp_path: Path, mutate) -> Path:
    payload = json.loads(Path("app/experiment/conditions.json").read_text(encoding="utf-8"))
    mutate(payload)
    path = tmp_path / "conditions.json"
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return path


def test_rag_switch_defaults_to_enabled() -> None:
    catalog = get_condition_catalog()

    assert all(condition.rag_enabled for condition in catalog.conditions)
    assert "Reply using only the [Evidence]" in catalog.require("k7q2").system_prompt


def test_global_rag_switch_disables_every_condition(tmp_path: Path) -> None:
    path = _write_catalog(tmp_path, lambda payload: payload.update(rag_enabled=False))

    catalog = load_condition_catalog(path)

    assert all(not condition.rag_enabled for condition in catalog.conditions)
    prompt = catalog.require("k7q2").prompt_for(rag_enabled=False)
    assert "Retrieval is turned off" in prompt
    assert "Reply using only the [Evidence]" not in prompt


def test_condition_can_override_global_rag_switch(tmp_path: Path) -> None:
    def mutate(payload: dict) -> None:
        payload["rag_enabled"] = True
        payload["conditions"][0]["rag_enabled"] = False

    path = _write_catalog(tmp_path, mutate)

    catalog = load_condition_catalog(path)

    assert catalog.require("k7q2").rag_enabled is False
    assert catalog.require("m3x9").rag_enabled is True


def test_rag_switch_rejects_non_boolean(tmp_path: Path) -> None:
    path = _write_catalog(tmp_path, lambda payload: payload.update(rag_enabled="maybe"))

    with pytest.raises(ValueError, match="rag_enabled"):
        load_condition_catalog(path)
