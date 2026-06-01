"""QThread workers for background operations."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6.QtCore import QThread, Signal

from ..core.addon import Addon, scan_addons_dir
from ..core.esoui import RemoteAddonInfo
from ..core.installer import install_addon, remove_addon, update_addon
from ..core.backup import create_backup, restore_backup
from ..core.dependency import resolve_install_set, DependencyError


class ScanWorker(QThread):
    finished = Signal(list)   # list[Addon]
    error = Signal(str)

    def __init__(self, addons_dir: Path):
        super().__init__()
        self.addons_dir = addons_dir

    def run(self):
        try:
            addons = scan_addons_dir(self.addons_dir)
            self.finished.emit(addons)
        except Exception as e:
            self.error.emit(str(e))


class InstallWorker(QThread):
    progress = Signal(str)    # status message
    finished = Signal(list)   # list[Addon] installed
    error = Signal(str)

    def __init__(
        self,
        info: RemoteAddonInfo,
        addons_dir: Path,
        installed: dict[str, Addon],
        available: dict[str, "RemoteAddonInfo"],
    ):
        super().__init__()
        self.info = info
        self.addons_dir = addons_dir
        self.installed = installed
        self.available = available

    def run(self):
        try:
            all_installed: list[Addon] = []
            # on-disk installed map we keep updated as we install deps
            live_installed = dict(self.installed)

            queue = [self.info]
            seen_ids: set[int] = set()

            while queue:
                remote = queue.pop(0)
                if remote.addon_id in seen_ids:
                    continue
                seen_ids.add(remote.addon_id)

                # Skip if every dir is already on disk
                if remote.dirs and all(d in live_installed for d in remote.dirs):
                    continue

                self.progress.emit(f"Installing {remote.name}…")
                batch = install_addon(
                    remote,
                    self.addons_dir,
                    progress_cb=lambda done, total, n=remote.name: self.progress.emit(
                        f"Downloading {n}: {done // 1024}KB"
                        + (f" / {total // 1024}KB" if total else "")
                    ),
                )
                all_installed.extend(batch)
                for a in batch:
                    live_installed[a.name] = a

                # Queue any missing dependencies from the freshly installed manifests
                for addon in batch:
                    for dep_name in addon.depends_on:
                        if dep_name in live_installed:
                            continue
                        dep_remote = self.available.get(dep_name)
                        if dep_remote:
                            queue.append(dep_remote)
                        else:
                            self.progress.emit(f"Warning: dependency '{dep_name}' not found")

            self.finished.emit(all_installed)
        except Exception as e:
            self.error.emit(str(e))


class UpdateWorker(QThread):
    progress = Signal(str)
    finished = Signal(list)   # list[Addon]
    error = Signal(str)

    def __init__(self, addon: Addon, info: RemoteAddonInfo, addons_dir: Path):
        super().__init__()
        self.addon = addon
        self.info = info
        self.addons_dir = addons_dir

    def run(self):
        try:
            self.progress.emit(f"Updating {self.addon.title or self.addon.name}…")
            updated = update_addon(
                self.addon,
                self.info,
                self.addons_dir,
                progress_cb=lambda done, total: self.progress.emit(
                    f"Downloading {self.info.name}: {done // 1024}KB"
                    + (f" / {total // 1024}KB" if total else "")
                ),
            )
            self.finished.emit(updated)
        except Exception as e:
            self.error.emit(str(e))


class BackupWorker(QThread):
    progress = Signal(str)
    finished = Signal(str)    # path to created zip
    error = Signal(str)

    def __init__(self, addons_dir: Path, backup_dir: Path,
                 label: str = "", saved_vars_dir: Optional[Path] = None):
        super().__init__()
        self.addons_dir = addons_dir
        self.backup_dir = backup_dir
        self.label = label
        self.saved_vars_dir = saved_vars_dir

    def run(self):
        try:
            zip_path = create_backup(
                self.addons_dir,
                self.backup_dir,
                self.label,
                saved_vars_dir=self.saved_vars_dir,
                progress_cb=lambda name: self.progress.emit(f"Backing up {name}"),
            )
            self.finished.emit(str(zip_path))
        except Exception as e:
            self.error.emit(str(e))


class RestoreWorker(QThread):
    progress = Signal(str)
    finished = Signal()
    error = Signal(str)

    def __init__(self, zip_path: Path, addons_dir: Path, saved_vars_dir: Optional[Path] = None):
        super().__init__()
        self.zip_path = zip_path
        self.addons_dir = addons_dir
        self.saved_vars_dir = saved_vars_dir

    def run(self):
        try:
            restore_backup(
                self.zip_path,
                self.addons_dir,
                saved_vars_dir=self.saved_vars_dir,
                progress_cb=lambda name: self.progress.emit(f"Restoring {name}"),
            )
            self.finished.emit()
        except Exception as e:
            self.error.emit(str(e))
