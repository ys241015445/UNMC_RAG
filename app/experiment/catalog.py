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
_PARTICIPANT_LEAK = re.compile(r"\b(LL|LH|HL|HH)\b|competence|warmth", re.IGNORECASE)
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
    temperature: float
    max_tokens: int
    opening_message: str
    persona: str
    shared_rules: str
    refusals: dict[str, str]

    @property
    def system_prompt(self) -> str:
        return f"{self.persona.strip()}\n\n{self.shared_rules.strip()}"

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

    raw_conditions = payload.get("conditions")
    if not isinstance(raw_conditions, list) or not raw_conditions:
        raise ValueError("Condition catalog needs a conditions list")

    conditions: list[ExperimentCondition] = []
    for index, raw in enumerate(raw_conditions):
        conditions.append(_parse_condition(raw, shared_rules, index))

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
    openings = [condition.opening_message for condition in conditions]
    if len(set(prompts)) != len(prompts):
        raise ValueError("Each condition needs its own system prompt")
    if len(set(openings)) != len(openings):
        raise ValueError("Each condition needs its own opening message")

    return ConditionCatalog(tuple(conditions))


def get_condition_catalog() -> ConditionCatalog:
    """Reload when the JSON file changes so prompt edits apply without a code change."""

    path = catalog_path()
    mtime_ns = path.stat().st_mtime_ns
    return _cached_catalog(str(path.resolve()), mtime_ns)


@lru_cache(maxsize=4)
def _cached_catalog(path: str, mtime_ns: int) -> ConditionCatalog:
    del mtime_ns
    return load_condition_catalog(Path(path))


def _parse_condition(raw: object, shared_rules: str, index: int) -> ExperimentCondition:
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

    return ExperimentCondition(
        entry_path=entry_path,
        condition_id=condition_id,
        competence=competence,
        warmth=warmth,
        temperature=temperature,
        max_tokens=max_tokens,
        opening_message=opening_message,
        persona=persona,
        shared_rules=shared_rules,
        refusals=refusals,
    )


def _assert_participant_safe(label: str, text: str) -> None:
    if _PARTICIPANT_LEAK.search(text):
        raise ValueError(f"{label} would reveal the study design to participants")
