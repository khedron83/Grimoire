"""Addon data model and manifest parser (.addon and .txt)."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


_SIDECAR = ".eso-addon-manager.json"


@dataclass
class Addon:
    addon_id: Optional[int] = None
    name: str = ""
    title: str = ""
    version: str = ""
    remote_version: str = ""
    author: str = ""
    description: str = ""
    depends_on: list[str] = field(default_factory=list)
    esoui_url: str = ""
    download_url: str = ""
    installed: bool = False
    enabled: bool = True
    folder_path: Optional[Path] = None
    install_date: int = 0   # UIDate ms timestamp written on install; 0 = manually installed


_MANIFEST_RE = re.compile(r"^##\s*(\w+)\s*:\s*(.+)$", re.MULTILINE)
# ESO color/texture codes: |cRRGGBB ... |r   and   |tN:N:path|t
_ESO_CODE_RE = re.compile(r'\|[cC][0-9a-fA-F]+|\|r|\|t[^|]*(?:\|t)?')


def parse_manifest(path: Path) -> dict[str, str]:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return {}
    return {m.group(1): m.group(2).strip() for m in _MANIFEST_RE.finditer(text)}


def _parse_deps(raw: str) -> list[str]:
    return [
        re.split(r"[><=]+", dep.strip())[0]
        for dep in re.split(r"[\s,]+", raw)
        if dep.strip()
    ]


def write_sidecar(folder: Path, addon_id: int, install_date: int) -> None:
    """Write metadata sidecar so we can do date-based update checks later."""
    try:
        (folder / _SIDECAR).write_text(
            json.dumps({"addon_id": addon_id, "install_date": install_date})
        )
    except OSError:
        pass


def _read_sidecar(folder: Path) -> dict:
    try:
        return json.loads((folder / _SIDECAR).read_text())
    except (OSError, json.JSONDecodeError):
        return {}


def addon_from_disk(folder: Path) -> Optional[Addon]:
    manifests = list(folder.glob("*.addon")) or list(folder.glob("*.txt"))
    if not manifests:
        return None

    manifest_path = next(
        (m for m in manifests if m.stem.lower() == folder.name.lower()),
        manifests[0],
    )
    meta = parse_manifest(manifest_path)

    depends = _parse_deps(meta.get("DependsOn", ""))
    depends += _parse_deps(meta.get("PCDependsOn", ""))
    seen: set[str] = set()
    unique_deps = [d for d in depends if not (seen.add(d) or d in seen - {d})]

    sidecar = _read_sidecar(folder)

    def _clean(s: str) -> str:
        return _ESO_CODE_RE.sub("", s).strip()

    return Addon(
        name=folder.name,
        title=_clean(meta.get("Title", folder.name)) or folder.name,
        version=meta.get("Version", ""),
        author=_clean(meta.get("Author", "")),
        description=meta.get("Description", ""),
        depends_on=unique_deps,
        installed=True,
        folder_path=folder,
        addon_id=sidecar.get("addon_id"),
        install_date=sidecar.get("install_date", 0),
    )


def scan_addons_dir(addons_dir: Path) -> list[Addon]:
    addons = []
    for item in sorted(addons_dir.iterdir()):
        if item.is_dir():
            addon = addon_from_disk(item)
            if addon:
                addons.append(addon)
    return addons
