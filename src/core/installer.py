"""Download, install, and update addons."""

from __future__ import annotations

import shutil
import tempfile
import zipfile
from pathlib import Path
from typing import Callable, Optional

from .addon import Addon, addon_from_disk
from .esoui import RemoteAddonInfo, fetch_addon_details, download_zip


ProgressCB = Callable[[int, int], None]  # (bytes_done, total)


def _extract_zip(zip_path: Path, addons_dir: Path) -> list[str]:
    extracted = set()
    with zipfile.ZipFile(zip_path, "r") as zf:
        for member in zf.namelist():
            top = Path(member).parts[0] if Path(member).parts else None
            if top:
                extracted.add(top)
            zf.extract(member, addons_dir)
    return list(extracted)


def install_addon(
    info: RemoteAddonInfo,
    addons_dir: Path,
    progress_cb: Optional[ProgressCB] = None,
) -> list[Addon]:
    """
    Download and install an addon. Fetches the download URL from the API if needed.
    Returns the list of Addon objects installed (zip may contain multiple folders).
    """
    download_url = info.download_url
    if not download_url:
        details = fetch_addon_details(info.addon_id)
        download_url = details.get("download_url", "")
        info.download_url = download_url
        info.filename = details.get("filename", "")
        info.md5 = details.get("md5", "")
        if not info.description:
            info.description = details.get("description", "")

    if not download_url:
        raise RuntimeError(f"No download URL available for {info.name}")

    with tempfile.TemporaryDirectory() as tmp:
        zip_path = Path(tmp) / (info.filename or f"{info.addon_id}.zip")
        download_zip(download_url, str(zip_path), progress_cb)
        folders = _extract_zip(zip_path, addons_dir)

    addons = []
    for folder_name in folders:
        folder = addons_dir / folder_name
        if folder.is_dir():
            addon = addon_from_disk(folder)
            if addon:
                addon.addon_id = info.addon_id
                addon.esoui_url = info.info_url
                addon.download_url = download_url
                addon.remote_version = info.version
                addons.append(addon)

    return addons


def remove_addon(addon: Addon) -> None:
    if addon.folder_path and addon.folder_path.exists():
        shutil.rmtree(addon.folder_path)


def update_addon(
    addon: Addon,
    info: RemoteAddonInfo,
    addons_dir: Path,
    progress_cb: Optional[ProgressCB] = None,
) -> list[Addon]:
    remove_addon(addon)
    return install_addon(info, addons_dir, progress_cb)
