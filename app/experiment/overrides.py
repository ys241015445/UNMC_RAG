"""Saved prompt text for the four study paths.

Built-in prompts stay in conditions.json. Edits are stored in a JSON file so
they survive a process restart without a database. Deleting a path's entry
restores that path's built-in prompt.
"""

from __future__ import annotations

import json
import logging
import threading
from pathlib import Path

from app.config import get_settings
from app.experiment.catalog import REQUIRED_ENTRY_PATHS, ExperimentCondition

logger = logging.getLogger(__name__)

MAX_PROMPT_CHARS = 12_000
_LOCK = threading.Lock()


class PromptOverrideError(ValueError):
    """A prompt edit that should be shown back to the editor."""


def default_overrides_path() -> Path:
    return Path("data/experiment/prompt_overrides.json")


def overrides_path() -> Path:
    configured = get_settings().experiment_prompt_overrides_path.strip()
    if configured:
        return Path(configured)
    return default_overrides_path()


def effective_system_prompt(condition: ExperimentCondition) -> str:
    custom = load_overrides().get(condition.entry_path, "")
    if custom:
        return custom
    return condition.system_prompt


def load_overrides() -> dict[str, str]:
    with _LOCK:
        return _read()


def save_override(entry_path: str, prompt: str) -> str:
    path = _require_path(entry_path)
    text = prompt.strip()
    if not text:
        raise PromptOverrideError("Enter a prompt before saving.")
    if len(text) > MAX_PROMPT_CHARS:
        raise PromptOverrideError("That prompt is too long to save.")
    with _LOCK:
        current = _read()
        current[path] = text
        _write(current)
    return text


def reset_override(entry_path: str) -> None:
    path = _require_path(entry_path)
    with _LOCK:
        current = _read()
        current.pop(path, None)
        _write(current)


def _require_path(entry_path: str) -> str:
    cleaned = entry_path.strip().strip("/")
    if cleaned not in REQUIRED_ENTRY_PATHS:
        raise KeyError(cleaned)
    return cleaned


def _read() -> dict[str, str]:
    path = overrides_path()
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        logger.warning("Prompt overrides file is unreadable: %s", path)
        return {}
    if not isinstance(payload, dict):
        return {}
    saved: dict[str, str] = {}
    for key, value in payload.items():
        if key in REQUIRED_ENTRY_PATHS and isinstance(value, str) and value.strip():
            saved[key] = value.strip()
    return saved


def _write(data: dict[str, str]) -> None:
    path = overrides_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)
