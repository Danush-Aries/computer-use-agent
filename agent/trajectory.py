"""Trajectory recording — saves all agent actions to trajectory.json."""

import json
import time
from pathlib import Path
from typing import Any


TRAJECTORY_FILE = Path("trajectory.json")


def _load() -> list[dict]:
    if TRAJECTORY_FILE.exists():
        try:
            return json.loads(TRAJECTORY_FILE.read_text())
        except (json.JSONDecodeError, OSError):
            return []
    return []


def record_action(action_type: str, params: dict[str, Any], result: Any = None) -> dict:
    """Append one action entry to trajectory.json and return it."""
    entry = {
        "timestamp": time.time(),
        "action": action_type,
        "params": params,
        "result": result,
    }
    entries = _load()
    entries.append(entry)
    TRAJECTORY_FILE.write_text(json.dumps(entries, indent=2))
    return entry


def load_trajectory() -> list[dict]:
    """Return the full recorded trajectory."""
    return _load()


def clear_trajectory() -> None:
    """Wipe the trajectory file."""
    TRAJECTORY_FILE.write_text("[]")
