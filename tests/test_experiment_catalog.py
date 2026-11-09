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
    "k7q2": "limited and uncertain, and your tone is cold",
    "m3x9": "friendly and encouraging, and you are not very sure",
    "p8d4": "cold and formal",
    "t5w1": "precise and confident, and you are also friendly and supportive",
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
