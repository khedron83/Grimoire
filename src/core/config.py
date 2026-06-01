"""Persistent app configuration stored as JSON."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


def _config_dir() -> Path:
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", Path.home()))
    else:
        base = Path.home() / ".config"
    return base / "eso-addon-manager"


def _config_path() -> Path:
    return _config_dir() / "config.json"


_DEFAULTS: dict[str, Any] = {
    "addons_dir": "",
    "backup_dir": "",
    "saved_vars_dir": "",
    "backup_include_saved_vars": False,
    "auto_update_on_launch": False,
    "theme": "dark",
    "browse_sort_column": 5,   # COL_UPDATED
    "browse_sort_order": "desc",
}


class Config:
    def __init__(self) -> None:
        self._data: dict[str, Any] = dict(_DEFAULTS)
        self._load()

    def _load(self) -> None:
        path = _config_path()
        if path.exists():
            try:
                self._data.update(json.loads(path.read_text()))
            except (json.JSONDecodeError, OSError):
                pass

    def save(self) -> None:
        path = _config_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self._data, indent=2))

    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self._data[key] = value

    @property
    def addons_dir(self) -> str:
        return self._data.get("addons_dir", "")

    @addons_dir.setter
    def addons_dir(self, v: str) -> None:
        self._data["addons_dir"] = v

    @property
    def backup_dir(self) -> str:
        return self._data.get("backup_dir", "")

    @backup_dir.setter
    def backup_dir(self, v: str) -> None:
        self._data["backup_dir"] = v

    @property
    def auto_update_on_launch(self) -> bool:
        return bool(self._data.get("auto_update_on_launch", False))

    @auto_update_on_launch.setter
    def auto_update_on_launch(self, v: bool) -> None:
        self._data["auto_update_on_launch"] = v

    @property
    def saved_vars_dir(self) -> str:
        return self._data.get("saved_vars_dir", "")

    @saved_vars_dir.setter
    def saved_vars_dir(self, v: str) -> None:
        self._data["saved_vars_dir"] = v

    @property
    def backup_include_saved_vars(self) -> bool:
        return bool(self._data.get("backup_include_saved_vars", False))

    @backup_include_saved_vars.setter
    def backup_include_saved_vars(self, v: bool) -> None:
        self._data["backup_include_saved_vars"] = v

    @property
    def browse_sort_column(self) -> int:
        return int(self._data.get("browse_sort_column", 5))

    @browse_sort_column.setter
    def browse_sort_column(self, v: int) -> None:
        self._data["browse_sort_column"] = v

    @property
    def browse_sort_order(self) -> str:
        return self._data.get("browse_sort_order", "desc")

    @browse_sort_order.setter
    def browse_sort_order(self, v: str) -> None:
        self._data["browse_sort_order"] = v


import os  # noqa: E402 — placed after class to avoid circular ref in _config_dir
