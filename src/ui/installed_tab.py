"""Installed addons tab — list, remove, update, backup/restore."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QLabel, QHeaderView, QAbstractItemView, QMessageBox,
    QFileDialog, QGroupBox, QProgressBar,
)

from ..core.addon import Addon
from ..core.esoui import RemoteAddonInfo
from .workers import ScanWorker, UpdateWorker, BackupWorker, RestoreWorker
from ..core.esoui import RemoteAddonInfo


class InstalledTab(QWidget):
    addon_removed = Signal(str)    # addon name
    status_message = Signal(str)

    def __init__(self, config, parent=None):
        super().__init__(parent)
        self.config = config
        self._addons: list[Addon] = []
        self._remote: dict[str, RemoteAddonInfo] = {}
        self._worker = None
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # Toolbar
        toolbar = QHBoxLayout()
        self._btn_refresh = QPushButton("Refresh")
        self._btn_update_all = QPushButton("Update All")
        self._btn_remove = QPushButton("Remove Selected")
        self._btn_remove.setEnabled(False)
        toolbar.addWidget(self._btn_refresh)
        toolbar.addWidget(self._btn_update_all)
        toolbar.addWidget(self._btn_remove)
        toolbar.addStretch()
        layout.addLayout(toolbar)

        # Addon table
        self._table = QTableWidget()
        self._table.setColumnCount(5)
        self._table.setHorizontalHeaderLabels(
            ["Name", "Installed", "Latest", "Author", "Status"]
        )
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self._table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._table.setAlternatingRowColors(True)
        layout.addWidget(self._table, 1)

        # Progress
        self._progress = QProgressBar()
        self._progress.setVisible(False)
        self._progress_label = QLabel("")
        layout.addWidget(self._progress_label)
        layout.addWidget(self._progress)

        # Backup / Restore
        backup_group = QGroupBox("Backup & Restore")
        backup_layout = QHBoxLayout(backup_group)
        self._btn_backup = QPushButton("Create Backup")
        self._btn_restore = QPushButton("Restore Backup…")
        self._backup_label = QLabel("")
        backup_layout.addWidget(self._btn_backup)
        backup_layout.addWidget(self._btn_restore)
        backup_layout.addWidget(self._backup_label)
        backup_layout.addStretch()
        layout.addWidget(backup_group)

        # Connections
        self._btn_refresh.clicked.connect(self.refresh)
        self._btn_update_all.clicked.connect(self._update_all)
        self._btn_remove.clicked.connect(self._remove_selected)
        self._btn_backup.clicked.connect(self._create_backup)
        self._btn_restore.clicked.connect(self._restore_backup)
        self._table.itemSelectionChanged.connect(self._on_selection_changed)

    def set_addons(self, addons: list[Addon]):
        self._addons = addons
        self._populate_table()

    def set_remote_info(self, remote: dict[str, RemoteAddonInfo]):
        self._remote = remote
        self._populate_table()

    def get_installed_map(self) -> dict[str, Addon]:
        return {a.name: a for a in self._addons}

    def _populate_table(self):
        self._table.setRowCount(0)
        for addon in self._addons:
            row = self._table.rowCount()
            self._table.insertRow(row)
            title_item = QTableWidgetItem(addon.title or addon.name)
            title_item.setData(Qt.UserRole, addon.name)
            self._table.setItem(row, 0, title_item)
            self._table.setItem(row, 1, QTableWidgetItem(addon.version))

            remote = self._remote.get(addon.name)
            latest = remote.version if remote else "—"
            self._table.setItem(row, 2, QTableWidgetItem(latest))
            self._table.setItem(row, 3, QTableWidgetItem(addon.author))

            if remote and remote.version and addon.version and remote.version != addon.version:
                status = "Update available"
            elif remote:
                status = "Up to date"
            else:
                status = ""
            self._table.setItem(row, 4, QTableWidgetItem(status))

    def refresh(self):
        addons_dir = self.config.addons_dir
        if not addons_dir:
            self.status_message.emit("AddOns directory not set — check Settings.")
            return
        self._worker = ScanWorker(Path(addons_dir))
        self._worker.finished.connect(self.set_addons)
        self._worker.error.connect(lambda e: self.status_message.emit(f"Scan error: {e}"))
        self._worker.start()

    def _on_selection_changed(self):
        has_selection = bool(self._table.selectionModel().selectedRows())
        self._btn_remove.setEnabled(has_selection)

    def _remove_selected(self):
        selected_rows = sorted(
            {idx.row() for idx in self._table.selectionModel().selectedRows()},
            reverse=True,
        )
        if not selected_rows:
            return
        # Look up addons by name stored in the row, not by list index,
        # so this stays correct if the table is ever sorted.
        addons_to_remove = []
        for row in selected_rows:
            item = self._table.item(row, 0)
            if not item:
                continue
            name = item.data(Qt.UserRole)
            addon = next((a for a in self._addons if a.name == name), None)
            if addon:
                addons_to_remove.append(addon)

        if not addons_to_remove:
            return
        names = [a.title or a.name for a in addons_to_remove]
        answer = QMessageBox.question(
            self, "Remove Addons",
            f"Remove {len(addons_to_remove)} addon(s)?\n" + "\n".join(names),
        )
        if answer != QMessageBox.Yes:
            return
        from ..core.installer import remove_addon
        for addon in addons_to_remove:
            remove_addon(addon)
            self.addon_removed.emit(addon.name)
        self.refresh()

    def _update_all(self):
        updates = [
            a for a in self._addons
            if a.name in self._remote and self._remote[a.name].version != a.version
        ]
        if not updates:
            self.status_message.emit("All addons are up to date.")
            return
        addons_dir = Path(self.config.addons_dir)
        self._run_updates(updates, addons_dir)

    def _run_updates(self, queue: list[Addon], addons_dir: Path):
        if not queue:
            self.status_message.emit("Updates complete.")
            self._progress.setVisible(False)
            self.refresh()
            return
        addon = queue.pop(0)
        info = self._remote.get(addon.name)
        if not info:
            self._run_updates(queue, addons_dir)
            return
        self._progress.setVisible(True)
        self._progress.setRange(0, 0)
        worker = UpdateWorker(addon, info, addons_dir)
        worker.progress.connect(self._progress_label.setText)
        worker.finished.connect(lambda _: self._run_updates(queue, addons_dir))
        worker.error.connect(lambda e: self.status_message.emit(f"Update error: {e}"))
        worker.start()
        self._worker = worker

    def _create_backup(self):
        backup_dir = self.config.backup_dir or str(Path.home() / "eso-addon-backups")
        addons_dir = self.config.addons_dir
        if not addons_dir:
            self.status_message.emit("AddOns directory not set.")
            return
        self._progress.setVisible(True)
        self._progress.setRange(0, 0)
        worker = BackupWorker(Path(addons_dir), Path(backup_dir))
        worker.progress.connect(self._progress_label.setText)
        worker.finished.connect(self._on_backup_done)
        worker.error.connect(lambda e: self.status_message.emit(f"Backup error: {e}"))
        worker.start()
        self._worker = worker

    def _on_backup_done(self, zip_path: str):
        self._progress.setVisible(False)
        self._backup_label.setText(f"Last backup: {Path(zip_path).name}")
        self.status_message.emit(f"Backup saved to {zip_path}")

    def _restore_backup(self):
        backup_dir = self.config.backup_dir or str(Path.home() / "eso-addon-backups")
        zip_path, _ = QFileDialog.getOpenFileName(
            self, "Select Backup", backup_dir, "Zip files (*.zip)"
        )
        if not zip_path:
            return
        addons_dir = self.config.addons_dir
        if not addons_dir:
            self.status_message.emit("AddOns directory not set.")
            return
        answer = QMessageBox.question(
            self, "Restore Backup",
            f"Restore from {Path(zip_path).name}?\nExisting addons will be overwritten.",
        )
        if answer != QMessageBox.Yes:
            return
        self._progress.setVisible(True)
        self._progress.setRange(0, 0)
        worker = RestoreWorker(Path(zip_path), Path(addons_dir))
        worker.progress.connect(self._progress_label.setText)
        worker.finished.connect(self._on_restore_done)
        worker.error.connect(lambda e: self.status_message.emit(f"Restore error: {e}"))
        worker.start()
        self._worker = worker

    def _on_restore_done(self):
        self._progress.setVisible(False)
        self.status_message.emit("Restore complete.")
        self.refresh()
