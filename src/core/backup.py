"""Backup and restore the ESO AddOns directory."""

from __future__ import annotations

import zipfile
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional


def create_backup(
    addons_dir: Path,
    backup_dir: Path,
    label: str = "",
    saved_vars_dir: Optional[Path] = None,
    progress_cb: Optional[Callable[[str], None]] = None,
) -> Path:
    """
    Zip addons_dir (and optionally saved_vars_dir) into backup_dir.
    Inside the zip: AddOns/ and SavedVariables/ at the root.
    Returns the path of the created zip file.
    """
    backup_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    suffix = f"_{label}" if label else ""
    zip_path = backup_dir / f"eso_addons_{timestamp}{suffix}.zip"

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for file in sorted(addons_dir.rglob("*")):
            if file.is_file():
                arcname = Path("AddOns") / file.relative_to(addons_dir)
                if progress_cb:
                    progress_cb(str(arcname))
                zf.write(file, arcname)

        if saved_vars_dir and saved_vars_dir.exists():
            for file in sorted(saved_vars_dir.rglob("*")):
                if file.is_file():
                    arcname = Path("SavedVariables") / file.relative_to(saved_vars_dir)
                    if progress_cb:
                        progress_cb(str(arcname))
                    zf.write(file, arcname)

    return zip_path


def restore_backup(
    zip_path: Path,
    addons_dir: Path,
    saved_vars_dir: Optional[Path] = None,
    progress_cb: Optional[Callable[[str], None]] = None,
) -> None:
    """
    Extract a backup zip. Handles both flat (old) and structured (AddOns/ + SavedVariables/) zips.
    """
    with zipfile.ZipFile(zip_path, "r") as zf:
        members = zf.namelist()
        has_structure = any(m.startswith("AddOns/") for m in members)

        for member in members:
            if progress_cb:
                progress_cb(member)
            if has_structure:
                if member.startswith("AddOns/"):
                    rel = member[len("AddOns/"):]
                    if rel:
                        dest = addons_dir / rel
                        dest.parent.mkdir(parents=True, exist_ok=True)
                        if not member.endswith("/"):
                            with zf.open(member) as src, open(dest, "wb") as dst:
                                dst.write(src.read())
                elif member.startswith("SavedVariables/") and saved_vars_dir:
                    rel = member[len("SavedVariables/"):]
                    if rel:
                        dest = saved_vars_dir / rel
                        dest.parent.mkdir(parents=True, exist_ok=True)
                        if not member.endswith("/"):
                            with zf.open(member) as src, open(dest, "wb") as dst:
                                dst.write(src.read())
            else:
                # Legacy flat zip — extract everything into addons_dir
                zf.extract(member, addons_dir)


def list_backups(backup_dir: Path) -> list[Path]:
    """Return backup zips sorted newest-first."""
    if not backup_dir.exists():
        return []
    return sorted(
        backup_dir.glob("eso_addons_*.zip"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
