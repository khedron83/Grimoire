"""Main application window."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QMainWindow, QTabWidget, QStatusBar, QMenuBar, QMenu,
    QMessageBox, QLabel,
)
from PySide6.QtGui import QAction

from ..core.config import Config
from ..core.paths import detect_addons_dir
from .browse_tab import BrowseTab
from .installed_tab import InstalledTab
from .settings_dialog import SettingsDialog


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.config = Config()
        self.setWindowTitle("ESO Addon Manager")
        self.setMinimumSize(900, 600)
        self._setup_ui()
        self._first_run_check()

    def _setup_ui(self):
        # Menu bar
        menu = self.menuBar()
        file_menu = menu.addMenu("File")
        settings_action = QAction("Settings…", self)
        settings_action.triggered.connect(self._open_settings)
        file_menu.addAction(settings_action)
        file_menu.addSeparator()
        quit_action = QAction("Quit", self)
        quit_action.triggered.connect(self.close)
        file_menu.addAction(quit_action)

        help_menu = menu.addMenu("Help")
        about_action = QAction("About", self)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)

        # Tabs
        self._tabs = QTabWidget()
        self._browse_tab = BrowseTab(self.config)
        self._installed_tab = InstalledTab(self.config)
        self._tabs.addTab(self._installed_tab, "Installed")
        self._tabs.addTab(self._browse_tab, "Browse")
        self.setCentralWidget(self._tabs)

        # Status bar
        self._status = QStatusBar()
        self.setStatusBar(self._status)

        # Cross-tab signals
        self._browse_tab.addon_installed.connect(self._on_addons_installed)
        self._browse_tab.status_message.connect(self._status.showMessage)
        self._installed_tab.status_message.connect(self._status.showMessage)
        self._installed_tab.addon_removed.connect(
            lambda name: self._browse_tab.set_installed(
                self._installed_tab.get_installed_map()
            )
        )

    def _first_run_check(self):
        if not self.config.addons_dir:
            detected = detect_addons_dir()
            if detected:
                self.config.addons_dir = str(detected)
                self.config.save()
                self._status.showMessage(f"Auto-detected AddOns at {detected}")
            else:
                self._status.showMessage(
                    "AddOns directory not found — open Settings to configure."
                )
                self._open_settings()
                return

        if self.config.auto_update_on_launch:
            self._installed_tab.refresh()

        self._installed_tab.refresh()

    def _on_addons_installed(self, addons):
        self._installed_tab.refresh()
        self._browse_tab.set_installed(self._installed_tab.get_installed_map())

    def _open_settings(self):
        dlg = SettingsDialog(self.config, self)
        if dlg.exec():
            self._installed_tab.refresh()

    def _show_about(self):
        QMessageBox.about(
            self,
            "ESO Addon Manager",
            "ESO Addon Manager\n\n"
            "Installs and updates Elder Scrolls Online addons from ESOUI.com.\n"
            "Supports auto-dependency resolution and backup/restore.\n\n"
            "Works on Windows, Linux, and Steam Deck.",
        )
