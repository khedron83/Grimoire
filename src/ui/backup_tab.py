"""Backup & Restore tab."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
    QProgressBar, QLineEdit, QMessageBox, QFileDialog, QCheckBox,
)

from ..core.backup import create_backup, restore_backup, list_backups
from .workers import BackupWorker, RestoreWorker


class BackupTab(QWidget):
    status_message = Signal(str)

    def __init__(self, config, parent=None):
        super().__init__(parent)
        self.config = config
        self._worker = None
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # ── Backup section ───────────────────────────────────────
        create_row = QHBoxLayout()
        self._label_input = QLineEdit()
        self._label_input.setPlaceholderText("Optional label (e.g. 'before patch')…")
        self._chk_sv = QCheckBox("Include SavedVariables")
        self._btn_backup = QPushButton("Create Backup")
        create_row.addWidget(self._label_input, 1)
        create_row.addWidget(self._chk_sv)
        create_row.addWidget(self._btn_backup)
        layout.addLayout(create_row)

        # ── Backup list ──────────────────────────────────────────
        self._table = QTableWidget()
        self._table.setColumnCount(3)
        self._table.setHorizontalHeaderLabels(["Filename", "Size", "Date"])
        hdr = self._table.horizontalHeader()
        hdr.setSectionResizeMode(0, QHeaderView.Stretch)
        hdr.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self._table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._table.setAlternatingRowColors(True)
        layout.addWidget(self._table, 1)

        # ── Restore / Delete row ─────────────────────────────────
        action_row = QHBoxLayout()
        self._btn_restore = QPushButton("Restore Selected")
        self._btn_restore.setEnabled(False)
        self._btn_delete = QPushButton("Delete Selected")
        self._btn_delete.setEnabled(False)
        self._btn_open_dir = QPushButton("Open Backup Folder")
        action_row.addWidget(self._btn_restore)
        action_row.addWidget(self._btn_delete)
        action_row.addStretch()
        action_row.addWidget(self._btn_open_dir)
        layout.addLayout(action_row)

        # ── Progress ─────────────────────────────────────────────
        self._progress_label = QLabel("")
        self._progress = QProgressBar()
        self._progress.setVisible(False)
        self._progress.setMaximumHeight(6)
        layout.addWidget(self._progress_label)
        layout.addWidget(self._progress)

        # ── Connections ──────────────────────────────────────────
        self._btn_backup.clicked.connect(self._create_backup)
        self._btn_restore.clicked.connect(self._restore_selected)
        self._btn_delete.clicked.connect(self._delete_selected)
        self._btn_open_dir.clicked.connect(self._open_dir)
        self._table.itemSelectionChanged.connect(self._on_selection_changed)

    # ── Public API ────────────────────────────────────────────────

    def refresh(self):
        """Reload the backup list from disk."""
        self._chk_sv.setChecked(self.config.backup_include_saved_vars)
        backup_dir = self._backup_dir()
        if not backup_dir:
            return
        backups = list_backups(backup_dir)
        self._table.setRowCount(0)
        for path in backups:
            row = self._table.rowCount()
            self._table.insertRow(row)
            self._table.setItem(row, 0, QTableWidgetItem(path.name))
            size_mb = path.stat().st_size / (1024 * 1024)
            self._table.setItem(row, 1, QTableWidgetItem(f"{size_mb:.1f} MB"))
            import datetime
            mtime = datetime.datetime.fromtimestamp(path.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
            self._table.setItem(row, 2, QTableWidgetItem(mtime))
            self._table.item(row, 0).setData(Qt.UserRole, str(path))

    # ── Internals ─────────────────────────────────────────────────

    def _backup_dir(self) -> Path | None:
        d = self.config.backup_dir or str(Path.home() / "eso-addon-backups")
        return Path(d) if d else None

    def _on_selection_changed(self):
        has = bool(self._table.selectionModel().selectedRows())
        self._btn_restore.setEnabled(has)
        self._btn_delete.setEnabled(has)

    def _selected_path(self) -> Path | None:
        rows = self._table.selectionModel().selectedRows()
        if not rows:
            return None
        item = self._table.item(rows[0].row(), 0)
        return Path(item.data(Qt.UserRole)) if item else None

    def _create_backup(self):
        addons_dir = self.config.addons_dir
        if not addons_dir:
            self.status_message.emit("AddOns directory not set — check Settings.")
            return
        backup_dir = self._backup_dir()
        sv_dir = None
        if self._chk_sv.isChecked() and self.config.saved_vars_dir:
            sv_dir = Path(self.config.saved_vars_dir)
        self._set_busy(True)
        worker = BackupWorker(
            Path(addons_dir), backup_dir,
            label=self._label_input.text().strip(),
            saved_vars_dir=sv_dir,
        )
        worker.progress.connect(self._progress_label.setText)
        worker.finished.connect(self._on_backup_done)
        worker.error.connect(self._on_error)
        worker.start()
        self._worker = worker

    def _on_backup_done(self, zip_path: str):
        self._set_busy(False)
        self._label_input.clear()
        self.status_message.emit(f"Backup saved: {Path(zip_path).name}")
        self.refresh()

    def _restore_selected(self):
        zip_path = self._selected_path()
        if not zip_path:
            return
        addons_dir = self.config.addons_dir
        if not addons_dir:
            self.status_message.emit("AddOns directory not set — check Settings.")
            return
        if QMessageBox.question(
            self, "Restore Backup",
            f"Restore from {zip_path.name}?\nExisting addons will be overwritten.",
        ) != QMessageBox.Yes:
            return
        sv_dir = Path(self.config.saved_vars_dir) if self.config.saved_vars_dir else None
        self._set_busy(True)
        worker = RestoreWorker(zip_path, Path(addons_dir), saved_vars_dir=sv_dir)
        worker.progress.connect(self._progress_label.setText)
        worker.finished.connect(self._on_restore_done)
        worker.error.connect(self._on_error)
        worker.start()
        self._worker = worker

    def _on_restore_done(self):
        self._set_busy(False)
        self.status_message.emit("Restore complete.")

    def _delete_selected(self):
        zip_path = self._selected_path()
        if not zip_path:
            return
        if QMessageBox.question(
            self, "Delete Backup",
            f"Permanently delete {zip_path.name}?",
        ) != QMessageBox.Yes:
            return
        try:
            zip_path.unlink()
        except OSError as e:
            self.status_message.emit(f"Delete failed: {e}")
        self.refresh()

    def _open_dir(self):
        import subprocess, sys
        d = self._backup_dir()
        if not d:
            return
        d.mkdir(parents=True, exist_ok=True)
        if sys.platform == "win32":
            subprocess.Popen(["explorer", str(d)])
        else:
            subprocess.Popen(["xdg-open", str(d)])

    def _on_error(self, msg: str):
        self._set_busy(False)
        self.status_message.emit(f"Error: {msg}")

    def _set_busy(self, busy: bool):
        self._progress.setVisible(busy)
        self._progress.setRange(0, 0)
        self._btn_backup.setEnabled(not busy)
        self._btn_restore.setEnabled(not busy)
