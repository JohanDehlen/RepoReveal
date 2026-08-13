from __future__ import annotations

import json
import os
import re
from pathlib import Path


_GEOMETRY_PATTERN = re.compile(r"^\d+x\d+(?:[+-]\d+){2}$")


def settings_path() -> Path:
    base = os.environ.get("LOCALAPPDATA")
    if base:
        return Path(base) / "RepoRip" / "settings.json"
    return Path.home() / ".reporip" / "settings.json"


def is_valid_geometry(value: object) -> bool:
    return isinstance(value, str) and bool(_GEOMETRY_PATTERN.fullmatch(value))


def load_window_geometry(*, default: str = "1120x650") -> str:
    path = settings_path()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, TypeError):
        return default

    geometry = payload.get("window_geometry") if isinstance(payload, dict) else None
    return geometry if is_valid_geometry(geometry) else default


def save_window_geometry(geometry: str) -> None:
    if not is_valid_geometry(geometry):
        return

    path = settings_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps({"window_geometry": geometry}, indent=2),
            encoding="utf-8",
        )
    except OSError:
        # Window shutdown should never be blocked by a settings-write failure.
        return