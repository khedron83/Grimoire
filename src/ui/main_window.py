"""Main application window."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QMainWindow, QTabWidget, QStatusBar, QWidget,
    QHBoxLayout, QLabel, QPushButton, QMessageBox,
)
from PySide6.QtGui import QAction, QDesktopServices
from PySide6.QtCore import QUrl

from ..core.config import Config
from ..core.paths import detect_addons_dir
from .browse_tab import BrowseTab
from .installed_tab import InstalledTab
from .backup_tab import BackupTab
from .settings_dialog import SettingsDialog
from .workers import UpdateCheckWorker, APP_VERSION


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.config = Config()
        self.setWindowTitle("Grimoire")
        self.setMinimumSize(900, 600)
        self._update_worker = None
        self._setup_ui()
        self._first_run_check()
        self._check_for_update()

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

        # Update banner (hidden until an update is found)
        self._update_banner = QWidget()
        self._update_banner.setStyleSheet(
            "background:#6a4fc8; color:white; padding:4px 8px;"
        )
        banner_layout = QHBoxLayout(self._update_banner)
        banner_layout.setContentsMargins(8, 4, 8, 4)
        self._update_label = QLabel()
        self._update_label.setOpenExternalLinks(False)
        dl_btn = QPushButton("Download")
        dl_btn.setFixedWidth(90)
        dl_btn.clicked.connect(self._open_releases)
        dismiss_btn = QPushButton("✕")
        dismiss_btn.setFixedWidth(28)
        dismiss_btn.clicked.connect(self._update_banner.hide)
        banner_layout.addWidget(self._update_label)
        banner_layout.addStretch()
        banner_layout.addWidget(dl_btn)
        banner_layout.addWidget(dismiss_btn)
        self._update_banner.hide()

        # Central widget: banner + tabs stacked vertically
        central = QWidget()
        from PySide6.QtWidgets import QVBoxLayout
        vbox = QVBoxLayout(central)
        vbox.setContentsMargins(0, 0, 0, 0)
        vbox.setSpacing(0)
        vbox.addWidget(self._update_banner)

        self._tabs = QTabWidget()
        self._browse_tab = BrowseTab(self.config)
        self._installed_tab = InstalledTab(self.config)
        self._backup_tab = BackupTab(self.config)
        self._tabs.addTab(self._installed_tab, "Installed")
        self._tabs.addTab(self._browse_tab, "Browse")
        self._tabs.addTab(self._backup_tab, "Backup")
        vbox.addWidget(self._tabs)
        self.setCentralWidget(central)
        self._tabs.currentChanged.connect(self._on_tab_changed)

        # Status bar
        self._status = QStatusBar()
        self.setStatusBar(self._status)

        # Cross-tab signals
        self._browse_tab.addon_installed.connect(self._on_addons_installed)
        self._browse_tab.addon_list_loaded.connect(self._on_addon_list_loaded)
        self._browse_tab.status_message.connect(self._status.showMessage)
        self._installed_tab.status_message.connect(self._status.showMessage)
        self._backup_tab.status_message.connect(self._status.showMessage)
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

        self._installed_tab.refresh()
        # Fetch remote addon list in background so update info is ready immediately
        self._browse_tab.load_addon_list()

    def _on_tab_changed(self, index: int):
        if self._tabs.widget(index) is self._backup_tab:
            self._backup_tab.refresh()

    def _on_addon_list_loaded(self, all_addons: list):
        # Two-pass map: dirs first (low priority), then name (high priority).
        # Prevents addons that bundle a library in their dirs list from
        # hijacking dep lookups for that library's own ESOUI listing.
        remote_map = {}
        for info in all_addons:
            for dir_name in info.dirs:
                remote_map[dir_name] = info
        for info in all_addons:
            remote_map[info.name] = info
        self._installed_tab.set_remote_info(remote_map)

    def _check_for_update(self):
        self._update_worker = UpdateCheckWorker()
        self._update_worker.update_available.connect(self._show_update_banner)
        self._update_worker.start()

    def _show_update_banner(self, tag: str):
        self._update_label.setText(f"Update available: {tag}")
        self._update_banner.show()

    def _open_releases(self):
        QDesktopServices.openUrl(
            QUrl("https://github.com/khedron83/Grimoire/releases/latest")
        )

    def _on_addons_installed(self, addons):
        self._installed_tab.refresh()
        self._browse_tab.set_installed(self._installed_tab.get_installed_map())

    def _open_settings(self):
        dlg = SettingsDialog(self.config, self)
        if dlg.exec():
            self._installed_tab.refresh()

    def _show_about(self):
        dlg = QMessageBox(self)
        dlg.setWindowTitle("About Grimoire")
        dlg.setTextFormat(Qt.TextFormat.RichText)
        dlg.setText(
            f"<b>Grimoire</b> v{APP_VERSION}<br><br>"
            "An addon manager for The Elder Scrolls Online.<br>"
            "Browse, install, and update addons from ESOUI.com<br>"
            "with automatic dependency resolution.<br><br>"
            "Works on Windows, Linux, and Steam Deck.<br><br>"
            "Licensed under the GNU General Public License v3.0."
        )
        dlg.setStandardButtons(QMessageBox.StandardButton.Ok)
        dlg.exec()
