"""Load competence × warmth personas from researcher-editable JSON."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from app.config import get_settings

# Public URL segments. Which segment maps to which cell is data in conditions.json.
REQUIRED_ENTRY_PATHS = frozenset({"k7q2", "m3x9", "p8d4", "t5w1"})
CONDITION_IDS = frozenset({"LL", "LH", "HL", "HH"})
_CELL_TRAITS = {
    "LL": ("low", "low"),
    "LH": ("low", "high"),
    "HL": ("high", "low"),
    "HH": ("high", "high"),
}
_PARTICIPANT_LEAK = re.compile(r"\b(?:LL|LH|HL|HH)\b|(?i:competence|warmth)")
_REFUSAL_REASONS = (
    "off_topic",
    "insufficient_evidence",
    "prompt_injection",
    "generation_failed",
    "default",
)


@dataclass(frozen=True, slots=True)
class ExperimentCondition:
    """One study cell. `system_prompt` is never rendered in the participant UI."""

    entry_path: str
    condition_id: str
    competence: str
    warmth: str
    rag_enabled: bool
    temperature: float
    max_tokens: int
    opening_message: str
    persona: str
    shared_rules: str
    shared_rules_no_rag: str
    refusals: dict[str, str]

    @property
    def system_prompt(self) -> str:
        """Prompt used when retrieval is on (the default)."""

        return self.prompt_for(rag_enabled=True)

    def prompt_for(self, *, rag_enabled: bool) -> str:
        rules = self.shared_rules_no_rag if not rag_enabled else self.shared_rules
        return f"{self.persona.strip()}\n\n{rules.strip()}"

    def refusal_text(self, reason: str) -> str:
        text = self.refusals.get(reason) or self.refusals.get("default") or ""
        cleaned = text.strip()
        if cleaned:
            return cleaned
        return "I cannot answer that from the campus materials."


class ConditionCatalog:
    def __init__(self, conditions: tuple[ExperimentCondition, ...]) -> None:
        self.conditions = conditions
        self._by_path = {condition.entry_path: condition for condition in conditions}

    def get(self, entry_path: str) -> ExperimentCondition | None:
        return self._by_path.get(entry_path.strip().strip("/"))

    def require(self, entry_path: str) -> ExperimentCondition:
        condition = self.get(entry_path)
        if condition is None:
            raise KeyError(entry_path)
        return condition

    @property
    def entry_paths(self) -> tuple[str, ...]:
        return tuple(self._by_path)

    def mapping(self) -> dict[str, str]:
        return {condition.entry_path: condition.condition_id for condition in self.conditions}


def default_catalog_path() -> Path:
    return Path(__file__).resolve().parent / "conditions.json"


def catalog_path() -> Path:
    override = get_settings().experiment_conditions_path.strip()
    if override:
        return Path(override)
    return default_catalog_path()


def load_condition_catalog(path: Path | None = None) -> ConditionCatalog:
    source = path or catalog_path()
    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise ValueError(f"Condition catalog not found: {source}") from error
    except json.JSONDecodeError as error:
        raise ValueError(f"Condition catalog is not valid JSON: {source}") from error

    if not isinstance(payload, dict):
        raise ValueError("Condition catalog must be a JSON object")

    shared_rules = str(payload.get("shared_rules") or "").strip()
    if not shared_rules:
        raise ValueError("Condition catalog needs shared_rules")
    shared_rules_no_rag = str(payload.get("shared_rules_without_rag") or "").strip()
    if not shared_rules_no_rag:
        shared_rules_no_rag = shared_rules
    default_rag_enabled = _as_bool(
        payload.get("rag_enabled", True),
        label="rag_enabled",
        fallback=True,
    )

    raw_conditions = payload.get("conditions")
    if not isinstance(raw_conditions, list) or not raw_conditions:
        raise ValueError("Condition catalog needs a conditions list")

    conditions: list[ExperimentCondition] = []
    for index, raw in enumerate(raw_conditions):
        conditions.append(
            _parse_condition(
                raw,
                shared_rules,
                index,
                default_rag_enabled=default_rag_enabled,
                shared_rules_no_rag=shared_rules_no_rag,
            )
        )

    paths = [condition.entry_path for condition in conditions]
    ids = [condition.condition_id for condition in conditions]
    if set(paths) != REQUIRED_ENTRY_PATHS or len(paths) != len(REQUIRED_ENTRY_PATHS):
        raise ValueError(
            "Condition catalog must define exactly the entry paths "
            + ", ".join(sorted(REQUIRED_ENTRY_PATHS))
        )
    if set(ids) != CONDITION_IDS or len(ids) != len(CONDITION_IDS):
        raise ValueError("Condition catalog must assign LL, LH, HL, and HH once each")

    prompts = [condition.system_prompt for condition in conditions]
    if len(set(prompts)) != len(prompts):
        raise ValueError("Each condition needs its own system prompt")

    return ConditionCatalog(tuple(conditions))


def get_condition_catalog() -> ConditionCatalog:
    """Reload when the JSON file changes so prompt edits apply without a code change."""

    path = catalog_path()
    mtime_ns = path.stat().st_mtime_ns
    return _cached_catalog(str(path.resolve()), mtime_ns)


def save_condition_settings(
    updates: dict[str, object],
    path: Path | None = None,
) -> ConditionCatalog:
    """Write persona text and per-path RAG switches back to the catalog file."""

    source = path or catalog_path()
    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"Condition catalog cannot be read: {source}") from error
    if not isinstance(payload, dict):
        raise ValueError("Condition catalog must be a JSON object")

    if "shared_rules" in updates:
        payload["shared_rules"] = str(updates.get("shared_rules") or "")
    if "shared_rules_without_rag" in updates:
        payload["shared_rules_without_rag"] = str(updates.get("shared_rules_without_rag") or "")

    raw_conditions = payload.get("conditions")
    if not isinstance(raw_conditions, list):
        raise ValueError("Condition catalog needs a conditions list")
    by_path = {
        str(item.get("entry_path") or "").strip(): item
        for item in raw_conditions
        if isinstance(item, dict)
    }
    incoming = updates.get("conditions")
    if not isinstance(incoming, list) or not incoming:
        raise ValueError("Settings need one entry for each study path")

    seen: set[str] = set()
    for item in incoming:
        if not isinstance(item, dict):
            raise ValueError("Each settings entry must be an object")
        entry_path = str(item.get("entry_path") or "").strip()
        target = by_path.get(entry_path)
        if target is None:
            raise ValueError(f"Unknown study path: {entry_path or '(blank)'}")
        if entry_path in seen:
            raise ValueError(f"Duplicate study path: {entry_path}")
        seen.add(entry_path)
        persona = str(item.get("persona") or "").strip()
        if not persona:
            raise ValueError(f"{entry_path} needs a persona prompt")
        if "rag_enabled" not in item:
            raise ValueError(f"{entry_path} needs a rag_enabled switch")
        target["persona"] = persona
        target["rag_enabled"] = _as_bool(
            item.get("rag_enabled"),
            label=f"{entry_path} rag_enabled",
            fallback=False,
        )

    if seen != REQUIRED_ENTRY_PATHS:
        missing = ", ".join(sorted(REQUIRED_ENTRY_PATHS - seen))
        raise ValueError(f"Settings must include every study path: {missing}")

    encoded = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    temporary = source.with_suffix(".json.tmp")
    temporary.write_text(encoded, encoding="utf-8")
    try:
        catalog = load_condition_catalog(temporary)
    except ValueError:
        temporary.unlink(missing_ok=True)
        raise
    temporary.replace(source)
    return catalog


@lru_cache(maxsize=4)
def _cached_catalog(path: str, mtime_ns: int) -> ConditionCatalog:
    del mtime_ns
    return load_condition_catalog(Path(path))


def _parse_condition(
    raw: object,
    shared_rules: str,
    index: int,
    *,
    default_rag_enabled: bool,
    shared_rules_no_rag: str,
) -> ExperimentCondition:
    if not isinstance(raw, dict):
        raise ValueError(f"conditions[{index}] must be an object")

    entry_path = str(raw.get("entry_path") or "").strip()
    condition_id = str(raw.get("condition_id") or "").strip()
    if condition_id not in _CELL_TRAITS:
        raise ValueError(f"conditions[{index}] has an unknown condition_id")

    expected_competence, expected_warmth = _CELL_TRAITS[condition_id]
    competence = str(raw.get("competence") or "").strip().casefold()
    warmth = str(raw.get("warmth") or "").strip().casefold()
    if (competence, warmth) != (expected_competence, expected_warmth):
        raise ValueError(
            f"{condition_id} must be competence={expected_competence}, warmth={expected_warmth}"
        )

    try:
        temperature = float(raw.get("temperature"))
        max_tokens = int(raw.get("max_tokens"))
    except (TypeError, ValueError) as error:
        raise ValueError(
            f"{entry_path or index} needs numeric temperature and max_tokens"
        ) from error
    if not 0 <= temperature <= 1.5:
        raise ValueError(f"{entry_path} temperature must be between 0 and 1.5")
    if not 64 <= max_tokens <= 2048:
        raise ValueError(f"{entry_path} max_tokens must be between 64 and 2048")

    opening_message = str(raw.get("opening_message") or "").strip()
    persona = str(raw.get("persona") or "").strip()
    if not opening_message or not persona:
        raise ValueError(f"{entry_path or condition_id} needs persona and opening_message")

    refusals_raw = raw.get("refusals")
    if not isinstance(refusals_raw, dict):
        raise ValueError(f"{entry_path or condition_id} needs a refusals object")
    refusals = {reason: str(refusals_raw.get(reason) or "").strip() for reason in _REFUSAL_REASONS}
    if any(not text for text in refusals.values()):
        raise ValueError(
            f"{entry_path or condition_id} refusals need "
            + ", ".join(_REFUSAL_REASONS)
        )

    _assert_participant_safe(f"{entry_path} opening_message", opening_message)
    for reason, text in refusals.items():
        _assert_participant_safe(f"{entry_path} refusal {reason}", text)

    rag_enabled = _as_bool(
        raw.get("rag_enabled", default_rag_enabled),
        label=f"{entry_path or condition_id} rag_enabled",
        fallback=default_rag_enabled,
    )

    return ExperimentCondition(
        entry_path=entry_path,
        condition_id=condition_id,
        competence=competence,
        warmth=warmth,
        rag_enabled=rag_enabled,
        temperature=temperature,
        max_tokens=max_tokens,
        opening_message=opening_message,
        persona=persona,
        shared_rules=shared_rules,
        shared_rules_no_rag=shared_rules_no_rag,
        refusals=refusals,
    )


def _as_bool(value: object, *, label: str, fallback: bool) -> bool:
    if value is None:
        return fallback
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().casefold()
        if lowered in {"true", "1", "yes", "on"}:
            return True
        if lowered in {"false", "0", "no", "off"}:
            return False
    if isinstance(value, (int, float)) and value in {0, 1}:
        return bool(value)
    raise ValueError(f"{label} must be a boolean")


def _assert_participant_safe(label: str, text: str) -> None:
    if _PARTICIPANT_LEAK.search(text):
        raise ValueError(f"{label} would reveal the study design to participants")
