"""On/off state for the four study links.

Missing file or a missing path means that link is on, matching the original
behavior. Explicit false turns the link off. The file survives a process
restart without Postgres.
"""

from __future__ import annotations

import json
import logging
import threading
from pathlib import Path

from app.experiment.catalog import REQUIRED_ENTRY_PATHS
from app.experiment.overrides import overrides_path

logger = logging.getLogger(__name__)

_LOCK = threading.Lock()
_PATH_ORDER = ("k7q2", "m3x9", "p8d4", "t5w1")


def switches_path() -> Path:
    return overrides_path().with_name("prompt_switches.json")


def is_path_enabled(entry_path: str) -> bool:
    cleaned = entry_path.strip().strip("/")
    if cleaned not in REQUIRED_ENTRY_PATHS:
        return False
    return _read().get(cleaned, True)


def set_path_enabled(entry_path: str, enabled: bool) -> bool:
    cleaned = entry_path.strip().strip("/")
    if cleaned not in REQUIRED_ENTRY_PATHS:
        raise KeyError(cleaned)
    with _LOCK:
        current = _read()
        current[cleaned] = bool(enabled)
        _write(current)
    return bool(enabled)


def _read() -> dict[str, bool]:
    path = switches_path()
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        logger.warning("Prompt switch file is unreadable: %s", path)
        return {}
    if not isinstance(payload, dict):
        return {}
    saved: dict[str, bool] = {}
    for key, value in payload.items():
        if key in REQUIRED_ENTRY_PATHS and isinstance(value, bool):
            saved[key] = value
    return saved


def _write(explicit: dict[str, bool]) -> None:
    path = switches_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {entry_path: bool(explicit.get(entry_path, True)) for entry_path in _PATH_ORDER}
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)
