"""Platform-aware ESO AddOns directory detection."""

import os
import sys
from pathlib import Path
from typing import Optional


ESO_STEAM_APP_ID = "306130"

# Relative path inside the Proton prefix to the AddOns folder
_PROTON_ADDONS_REL = Path(
    "pfx/drive_c/users/steamuser/Documents/Elder Scrolls Online/live/AddOns"
)


def _steam_library_paths() -> list[Path]:
    """Return all Steam library root paths."""
    base = Path.home() / ".local/share/Steam"
    libraries = [base]

    vdf = base / "steamapps/libraryfolders.vdf"
    if vdf.exists():
        import re
        text = vdf.read_text(errors="replace")
        for match in re.finditer(r'"path"\s+"([^"]+)"', text):
            libraries.append(Path(match.group(1)))

    return libraries


def _find_proton_addons() -> Optional[Path]:
    """Locate the ESO AddOns folder inside a Proton compatdata prefix."""
    for lib in _steam_library_paths():
        compat = lib / "steamapps/compatdata" / ESO_STEAM_APP_ID
        if compat.exists():
            return compat / _PROTON_ADDONS_REL
    return None


def detect_addons_dir() -> Optional[Path]:
    """
    Return the best-guess ESO AddOns directory for the current platform.
    Returns None if nothing is found (user will be prompted in settings).
    """
    if sys.platform == "win32":
        docs = Path.home() / "Documents"
        candidate = docs / "Elder Scrolls Online/live/AddOns"
        return candidate if candidate.exists() else docs / "Elder Scrolls Online/live/AddOns"

    # Linux / Steam Deck: try Proton prefix first, then native
    proton = _find_proton_addons()
    if proton:
        return proton

    native = Path.home() / "Documents/Elder Scrolls Online/live/AddOns"
    if native.exists():
        return native

    return None


def ensure_addons_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
