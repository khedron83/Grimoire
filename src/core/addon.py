"""Addon data model and manifest parser (.addon and .txt)."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class Addon:
    # From ESOUI / local manifest
    addon_id: Optional[int] = None       # ESOUI numeric ID
    name: str = ""                        # folder name on disk
    title: str = ""                       # ## Title:
    version: str = ""                     # ## Version: (installed)
    remote_version: str = ""             # latest version on ESOUI
    author: str = ""
    description: str = ""
    depends_on: list[str] = field(default_factory=list)   # addon folder names
    esoui_url: str = ""                   # info page URL
    download_url: str = ""               # download page URL
    installed: bool = False
    enabled: bool = True
    folder_path: Optional[Path] = None


# Matches "## Key: Value" lines in addon manifest .txt files
_MANIFEST_RE = re.compile(r"^##\s*(\w+)\s*:\s*(.+)$", re.MULTILINE)


def parse_manifest(txt_path: Path) -> dict[str, str]:
    """Parse an ESO addon .txt manifest and return key→value pairs."""
    try:
        text = txt_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return {}
    return {m.group(1): m.group(2).strip() for m in _MANIFEST_RE.finditer(text)}


def _parse_deps(raw: str) -> list[str]:
    """Strip version hints and return a list of dependency folder names."""
    return [
        re.split(r"[><=]+", dep.strip())[0]
        for dep in re.split(r"[\s,]+", raw)
        if dep.strip()
    ]


def addon_from_disk(folder: Path) -> Optional[Addon]:
    """
    Read an addon folder and build an Addon from its manifest.
    ESO manifests use .addon extension; .txt is the legacy format.
    Returns None if no manifest is found.
    """
    # Prefer .addon (modern), fall back to .txt (legacy)
    manifests = list(folder.glob("*.addon")) or list(folder.glob("*.txt"))
    if not manifests:
        return None

    # Prefer the file whose stem matches the folder name
    manifest_path = next(
        (m for m in manifests if m.stem.lower() == folder.name.lower()),
        manifests[0],
    )
    meta = parse_manifest(manifest_path)

    # DependsOn = required on all platforms
    # PCDependsOn = required on PC (Windows/Linux — always us)
    depends = _parse_deps(meta.get("DependsOn", ""))
    depends += _parse_deps(meta.get("PCDependsOn", ""))
    # Deduplicate while preserving order
    seen: set[str] = set()
    unique_deps = []
    for d in depends:
        if d not in seen:
            seen.add(d)
            unique_deps.append(d)

    return Addon(
        name=folder.name,
        title=meta.get("Title", folder.name),
        version=meta.get("Version", ""),
        author=meta.get("Author", ""),
        description=meta.get("Description", ""),
        depends_on=unique_deps,
        installed=True,
        folder_path=folder,
    )


def scan_addons_dir(addons_dir: Path) -> list[Addon]:
    """Return Addon objects for every addon folder found on disk."""
    addons = []
    for item in sorted(addons_dir.iterdir()):
        if item.is_dir():
            addon = addon_from_disk(item)
            if addon:
                addons.append(addon)
    return addons
