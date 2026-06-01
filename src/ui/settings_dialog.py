"""Settings dialog."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QLineEdit, QPushButton,
    QHBoxLayout, QDialogButtonBox, QFileDialog, QCheckBox, QLabel, QComboBox,
)

from ..core.paths import detect_addons_dir, detect_saved_vars_dir


class SettingsDialog(QDialog):
    def __init__(self, config, parent=None):
        super().__init__(parent)
        self.config = config
        self.setWindowTitle("Settings")
        self.setMinimumWidth(500)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        form = QFormLayout()

        # AddOns directory
        addons_row = QHBoxLayout()
        self._addons_dir = QLineEdit(self.config.addons_dir)
        self._addons_dir.setPlaceholderText("Path to ESO AddOns folder…")
        btn_browse_addons = QPushButton("Browse…")
        btn_detect = QPushButton("Auto-detect")
        addons_row.addWidget(self._addons_dir)
        addons_row.addWidget(btn_browse_addons)
        addons_row.addWidget(btn_detect)
        form.addRow("AddOns directory:", addons_row)

        # SavedVariables directory
        sv_row = QHBoxLayout()
        self._saved_vars_dir = QLineEdit(self.config.saved_vars_dir)
        self._saved_vars_dir.setPlaceholderText("Path to ESO SavedVariables folder (optional)…")
        btn_browse_sv = QPushButton("Browse…")
        btn_detect_sv = QPushButton("Auto-detect")
        sv_row.addWidget(self._saved_vars_dir)
        sv_row.addWidget(btn_browse_sv)
        sv_row.addWidget(btn_detect_sv)
        form.addRow("SavedVariables directory:", sv_row)

        self._backup_saved_vars = QCheckBox("Include SavedVariables in backups")
        self._backup_saved_vars.setChecked(self.config.backup_include_saved_vars)
        form.addRow("", self._backup_saved_vars)

        # Backup directory
        backup_row = QHBoxLayout()
        self._backup_dir = QLineEdit(self.config.backup_dir)
        self._backup_dir.setPlaceholderText("Where to save backups…")
        btn_browse_backup = QPushButton("Browse…")
        backup_row.addWidget(self._backup_dir)
        backup_row.addWidget(btn_browse_backup)
        form.addRow("Backup directory:", backup_row)

        # Browse tab default sort
        sort_row = QHBoxLayout()
        self._sort_col = QComboBox()
        _COLS = [
            ("Title",     0),
            ("Version",   1),
            ("Author",    2),
            ("Category",  3),
            ("Downloads", 4),
            ("Updated",   5),
        ]
        for label, col_id in _COLS:
            self._sort_col.addItem(label, col_id)
        self._sort_col.setCurrentIndex(
            next((i for i, (_, c) in enumerate(_COLS) if c == self.config.browse_sort_column), 5)
        )
        self._sort_order = QComboBox()
        self._sort_order.addItem("Descending", "desc")
        self._sort_order.addItem("Ascending",  "asc")
        self._sort_order.setCurrentIndex(0 if self.config.browse_sort_order == "desc" else 1)
        sort_row.addWidget(self._sort_col)
        sort_row.addWidget(self._sort_order)
        sort_row.addStretch()
        form.addRow("Browse default sort:", sort_row)

        # Options
        self._auto_update = QCheckBox("Check for updates on launch")
        self._auto_update.setChecked(self.config.auto_update_on_launch)
        form.addRow("", self._auto_update)

        layout.addLayout(form)

        # OK / Cancel
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        # Wire browse buttons
        btn_browse_addons.clicked.connect(self._browse_addons)
        btn_browse_backup.clicked.connect(self._browse_backup)
        btn_detect.clicked.connect(self._auto_detect)
        btn_browse_sv.clicked.connect(self._browse_sv)
        btn_detect_sv.clicked.connect(self._auto_detect_sv)

    def _browse_addons(self):
        path = QFileDialog.getExistingDirectory(self, "Select AddOns Directory", self._addons_dir.text())
        if path:
            self._addons_dir.setText(path)

    def _browse_backup(self):
        path = QFileDialog.getExistingDirectory(self, "Select Backup Directory", self._backup_dir.text())
        if path:
            self._backup_dir.setText(path)

    def _browse_sv(self):
        path = QFileDialog.getExistingDirectory(self, "Select SavedVariables Directory", self._saved_vars_dir.text())
        if path:
            self._saved_vars_dir.setText(path)

    def _auto_detect_sv(self):
        addons = Path(self._addons_dir.text()) if self._addons_dir.text() else None
        detected = detect_saved_vars_dir(addons)
        if detected:
            self._saved_vars_dir.setText(str(detected))
        else:
            self._saved_vars_dir.setPlaceholderText("Could not auto-detect — please browse manually")

    def _auto_detect(self):
        detected = detect_addons_dir()
        if detected:
            self._addons_dir.setText(str(detected))
        else:
            self._addons_dir.setPlaceholderText("Could not auto-detect — please browse manually")

    def _save(self):
        self.config.addons_dir = self._addons_dir.text().strip()
        self.config.backup_dir = self._backup_dir.text().strip()
        self.config.saved_vars_dir = self._saved_vars_dir.text().strip()
        self.config.backup_include_saved_vars = self._backup_saved_vars.isChecked()
        self.config.auto_update_on_launch = self._auto_update.isChecked()
        self.config.browse_sort_column = self._sort_col.currentData()
        self.config.browse_sort_order = self._sort_order.currentData()
        self.config.save()
        self.accept()
