"""Browse/search all ESO addons using the MMOUI JSON API."""

from __future__ import annotations

import re
from pathlib import Path

from PySide6.QtCore import Qt, Signal, QThread, QSortFilterProxyModel, QTimer
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
    QLabel, QProgressBar, QTextBrowser, QSplitter, QComboBox,
)

from ..core.esoui import RemoteAddonInfo, fetch_all_addons, fetch_addon_details
from ..core.addon import Addon
from .workers import InstallWorker


# ── Workers ───────────────────────────────────────────────────────────────────

class _LoadAllWorker(QThread):
    finished = Signal(list)   # list[RemoteAddonInfo]
    error = Signal(str)

    def run(self):
        try:
            self.finished.emit(fetch_all_addons())
        except Exception as e:
            self.error.emit(str(e))


class _DetailsWorker(QThread):
    finished = Signal(int, dict)   # addon_id, details dict
    error = Signal(str)

    def __init__(self, addon_id: int):
        super().__init__()
        self.addon_id = addon_id

    def run(self):
        try:
            self.finished.emit(self.addon_id, fetch_addon_details(self.addon_id))
        except Exception as e:
            self.error.emit(str(e))


# ── Table columns ─────────────────────────────────────────────────────────────

COL_TITLE    = 0
COL_VERSION  = 1
COL_AUTHOR   = 2
COL_CAT      = 3
COL_DL       = 4
COL_UPDATED  = 5


class _NumericItem(QTableWidgetItem):
    def __init__(self, text: str, value: int):
        super().__init__(text)
        self._value = value

    def __lt__(self, other):
        if isinstance(other, _NumericItem):
            return self._value < other._value
        return super().__lt__(other)


class _DateItem(QTableWidgetItem):
    """Sort by unix timestamp stored in UserRole."""
    def __init__(self, text: str, timestamp: int):
        super().__init__(text)
        self._ts = timestamp

    def __lt__(self, other):
        if isinstance(other, _DateItem):
            return self._ts < other._ts
        return super().__lt__(other)


# ── Browse tab ────────────────────────────────────────────────────────────────

class BrowseTab(QWidget):
    addon_installed = Signal(list)
    status_message = Signal(str)
    addon_list_loaded = Signal(list)   # emitted with full list[RemoteAddonInfo]

    def __init__(self, config, parent=None):
        super().__init__(parent)
        self.config = config
        self._all_addons: list[RemoteAddonInfo] = []
        self._displayed: list[RemoteAddonInfo] = []  # after filter
        self._addon_by_id: dict[int, RemoteAddonInfo] = {}
        self._installed: dict[str, Addon] = {}
        self._worker = None
        self._detail_info: RemoteAddonInfo | None = None
        # Debounce filter typing
        self._filter_timer = QTimer()
        self._filter_timer.setSingleShot(True)
        self._filter_timer.setInterval(250)
        self._filter_timer.timeout.connect(self._apply_filter)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # ── Top bar ──────────────────────────────────────────────
        top = QHBoxLayout()

        self._btn_load = QPushButton("Load Addon List")
        self._btn_refresh = QPushButton("Refresh")
        self._btn_refresh.setVisible(False)
        top.addWidget(self._btn_load)
        top.addWidget(self._btn_refresh)

        top.addSpacing(12)

        self._filter_input = QLineEdit()
        self._filter_input.setPlaceholderText("Filter by name, author, category…")
        self._filter_input.setEnabled(False)
        top.addWidget(self._filter_input, 1)

        self._cat_combo = QComboBox()
        self._cat_combo.setMinimumWidth(180)
        self._cat_combo.addItem("All Categories", "")
        self._cat_combo.setEnabled(False)
        top.addWidget(self._cat_combo)

        layout.addLayout(top)

        # ── Splitter ─────────────────────────────────────────────
        splitter = QSplitter(Qt.Horizontal)

        self._table = QTableWidget()
        self._table.setColumnCount(6)
        self._table.setHorizontalHeaderLabels(
            ["Title", "Version", "Author", "Category", "Downloads", "Updated"]
        )
        hdr = self._table.horizontalHeader()
        hdr.setSectionResizeMode(COL_TITLE,   QHeaderView.Stretch)
        hdr.setSectionResizeMode(COL_VERSION, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(COL_AUTHOR,  QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(COL_CAT,     QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(COL_DL,      QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(COL_UPDATED, QHeaderView.ResizeToContents)
        hdr.setSectionsClickable(True)
        self._table.setSortingEnabled(True)
        self._table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._table.setAlternatingRowColors(True)
        splitter.addWidget(self._table)

        # Detail panel
        detail = QWidget()
        dl = QVBoxLayout(detail)
        dl.setContentsMargins(6, 6, 6, 6)

        self._detail_title = QLabel()
        self._detail_title.setWordWrap(True)
        f = self._detail_title.font()
        f.setBold(True)
        f.setPointSize(f.pointSize() + 1)
        self._detail_title.setFont(f)

        self._detail_meta = QLabel()
        self._detail_meta.setWordWrap(True)
        self._detail_meta.setStyleSheet("color: #aaa; font-size: 11px;")

        self._detail_desc = QTextBrowser()

        self._btn_install = QPushButton("Install")
        self._btn_install.setEnabled(False)

        dl.addWidget(self._detail_title)
        dl.addWidget(self._detail_meta)
        dl.addWidget(self._detail_desc)
        dl.addWidget(self._btn_install)
        splitter.addWidget(detail)
        splitter.setSizes([600, 320])
        layout.addWidget(splitter, 1)

        # ── Status bar ───────────────────────────────────────────
        bot = QHBoxLayout()
        self._status_label = QLabel("")
        bot.addWidget(self._status_label)
        bot.addStretch()
        self._progress = QProgressBar()
        self._progress.setVisible(False)
        self._progress.setMaximumHeight(6)
        self._progress.setMaximumWidth(200)
        bot.addWidget(self._progress)
        layout.addLayout(bot)

        # ── Connections ──────────────────────────────────────────
        self._btn_load.clicked.connect(self._load_list)
        self._btn_refresh.clicked.connect(self._load_list)
        self._filter_input.textChanged.connect(lambda _: self._filter_timer.start())
        self._cat_combo.currentIndexChanged.connect(lambda _: self._apply_filter())
        self._table.currentCellChanged.connect(
            lambda row, _c, _pr, _pc: self._on_row_changed(row)
        )
        self._btn_install.clicked.connect(self._install_selected)

    # ── Public API ────────────────────────────────────────────────

    def set_installed(self, installed: dict[str, Addon]):
        self._installed = installed
        self._refresh_install_status()

    # ── List loading ──────────────────────────────────────────────

    def _load_list(self):
        self._btn_load.setEnabled(False)
        self._btn_refresh.setEnabled(False)
        self._set_busy(True)
        self._status_label.setText("Fetching addon list from MMOUI API…")
        self._worker = _LoadAllWorker()
        self._worker.finished.connect(self._on_list_loaded)
        self._worker.error.connect(self._on_error)
        self._worker.start()

    def _on_list_loaded(self, addons: list):
        self._all_addons = addons
        self._addon_by_id = {a.addon_id: a for a in addons}
        self._set_busy(False)
        self._btn_load.setVisible(False)
        self._btn_refresh.setVisible(True)
        self._btn_refresh.setEnabled(True)
        self._filter_input.setEnabled(True)
        self._cat_combo.setEnabled(True)

        # Populate category combo
        cats = sorted({a.category for a in addons if a.category})
        self._cat_combo.blockSignals(True)
        self._cat_combo.clear()
        self._cat_combo.addItem("All Categories", "")
        for cat in cats:
            self._cat_combo.addItem(cat, cat)
        self._cat_combo.blockSignals(False)

        # Apply saved default sort before populating
        col = self.config.browse_sort_column
        order = (Qt.AscendingOrder if self.config.browse_sort_order == "asc"
                 else Qt.DescendingOrder)
        self._table.horizontalHeader().setSortIndicator(col, order)

        self.addon_list_loaded.emit(addons)

        self._apply_filter()

    # ── Filtering ─────────────────────────────────────────────────

    def _apply_filter(self):
        query = self._filter_input.text().strip().lower()
        cat = self._cat_combo.currentData()

        filtered = self._all_addons
        if cat:
            filtered = [a for a in filtered if a.category == cat]
        if query:
            filtered = [
                a for a in filtered
                if query in a.name.lower()
                or query in a.author.lower()
                or query in a.category.lower()
            ]

        self._displayed = filtered
        self._populate_table(filtered)
        total = len(self._all_addons)
        shown = len(filtered)
        self._status_label.setText(
            f"{shown} addons" if shown == total else f"{shown} / {total} addons"
        )

    # ── Table ─────────────────────────────────────────────────────

    def _populate_table(self, addons: list[RemoteAddonInfo]):
        self._table.setSortingEnabled(False)
        self._table.setRowCount(0)
        for info in addons:
            row = self._table.rowCount()
            self._table.insertRow(row)
            self._fill_row(row, info)
        self._table.setSortingEnabled(True)
        self._clear_detail()

    def _addon_for_row(self, row: int) -> RemoteAddonInfo | None:
        """Look up the correct addon for a (possibly sorted) table row by stored ID."""
        item = self._table.item(row, COL_TITLE)
        if not item:
            return None
        return self._addon_by_id.get(item.data(Qt.UserRole))

    def _fill_row(self, row: int, info: RemoteAddonInfo):
        title_item = QTableWidgetItem(info.name)
        title_item.setData(Qt.UserRole, info.addon_id)
        self._apply_install_color(title_item, info)
        self._table.setItem(row, COL_TITLE,   title_item)
        self._table.setItem(row, COL_VERSION, QTableWidgetItem(info.version))
        self._table.setItem(row, COL_AUTHOR,  QTableWidgetItem(info.author))
        self._table.setItem(row, COL_CAT,     QTableWidgetItem(info.category))
        self._table.setItem(row, COL_DL,
            _NumericItem(f"{info.downloads_total:,}", info.downloads_total))

        import datetime
        ts_sec = info.date // 1000
        date_str = datetime.datetime.fromtimestamp(ts_sec).strftime("%Y-%m-%d") if ts_sec else ""
        self._table.setItem(row, COL_UPDATED, _DateItem(date_str, info.date))

    def _apply_install_color(self, item: QTableWidgetItem, info: RemoteAddonInfo):
        # Match against dirs[] — the actual folder names on disk
        inst = self._find_installed(info)
        if inst:
            if inst.version and info.version and inst.version != info.version:
                item.setForeground(Qt.yellow)
                item.setText(f"{info.name}  ↑")
            else:
                item.setForeground(Qt.green)

    def _find_installed(self, info: RemoteAddonInfo) -> Addon | None:
        """Match a remote addon to an installed one via UIDir folder names."""
        for dir_name in info.dirs:
            if dir_name in self._installed:
                return self._installed[dir_name]
        # Fallback: match by display name
        return self._installed.get(info.name)

    def _refresh_install_status(self):
        for row in range(self._table.rowCount()):
            info = self._addon_for_row(row)
            if not info:
                continue
            item = self._table.item(row, COL_TITLE)
            item.setText(info.name)
            item.setForeground(self._table.palette().text().color())
            self._apply_install_color(item, info)

    # ── Detail panel ─────────────────────────────────────────────

    def _on_row_changed(self, row: int):
        if row < 0:
            self._clear_detail()
            return
        info = self._addon_for_row(row)
        if not info:
            self._clear_detail()
            return
        self._detail_info = info
        self._detail_title.setText(info.name)

        import datetime
        date_str = (datetime.datetime.fromtimestamp(info.date // 1000).strftime("%Y-%m-%d")
                    if info.date else "")
        self._detail_meta.setText(
            f"Author: {info.author}  |  Version: {info.version}  |  "
            f"Category: {info.category}  |  "
            f"{info.downloads_total:,} total / {info.downloads_monthly:,} monthly  |  "
            f"Updated: {date_str}"
        )

        if info.description:
            self._detail_desc.setPlainText(info.description)
        else:
            self._detail_desc.setPlainText("Loading…")
            w = _DetailsWorker(info.addon_id)
            w.finished.connect(self._on_details_fetched)
            w.start()
            self._details_worker = w

        self._update_install_button(info)

    def _on_details_fetched(self, addon_id: int, details: dict):
        # Update the stored addon
        for a in self._all_addons:
            if a.addon_id == addon_id:
                a.description = details.get("description", "")
                a.download_url = details.get("download_url", "")
                a.filename = details.get("filename", "")
                a.md5 = details.get("md5", "")
                break
        if self._detail_info and self._detail_info.addon_id == addon_id:
            self._detail_info.description = details.get("description", "")
            self._detail_info.download_url = details.get("download_url", "")
            self._detail_desc.setPlainText(details.get("description") or "(No description)")

    def _clear_detail(self):
        self._detail_title.setText("")
        self._detail_meta.setText("")
        self._detail_desc.clear()
        self._btn_install.setEnabled(False)
        self._detail_info = None

    def _update_install_button(self, info: RemoteAddonInfo):
        inst = self._find_installed(info)
        if inst and inst.version and info.version and inst.version != info.version:
            self._btn_install.setText(f"Update  ({inst.version} → {info.version})")
            self._btn_install.setEnabled(True)
        elif inst:
            self._btn_install.setText("Installed")
            self._btn_install.setEnabled(False)
        else:
            self._btn_install.setText("Install")
            self._btn_install.setEnabled(True)

    # ── Install ───────────────────────────────────────────────────

    def _install_selected(self):
        if not self._detail_info:
            return
        addons_dir = self.config.addons_dir
        if not addons_dir:
            self.status_message.emit("AddOns directory not set — check Settings.")
            return
        # Build folder-name → RemoteAddonInfo for dep resolution
        dir_to_addon: dict[str, RemoteAddonInfo] = {}
        for a in self._all_addons:
            for d in a.dirs:
                dir_to_addon[d] = a

        self._btn_install.setEnabled(False)
        self._set_busy(True)
        worker = InstallWorker(self._detail_info, Path(addons_dir), self._installed, dir_to_addon)
        worker.progress.connect(self._status_label.setText)
        worker.finished.connect(self._on_install_done)
        worker.error.connect(self._on_install_error)
        worker.start()
        self._install_worker = worker

    def _on_install_done(self, addons: list):
        self._set_busy(False)
        names = ", ".join(a.title or a.name for a in addons)
        self.status_message.emit(f"Installed: {names}")
        self.addon_installed.emit(addons)
        for a in addons:
            self._installed[a.name] = a
        self._refresh_install_status()
        if self._detail_info:
            self._update_install_button(self._detail_info)

    def _on_install_error(self, msg: str):
        self._set_busy(False)
        if self._detail_info:
            self._update_install_button(self._detail_info)
        self.status_message.emit(f"Install error: {msg}")

    def _on_error(self, msg: str):
        self._set_busy(False)
        self._btn_load.setEnabled(True)
        self._btn_refresh.setEnabled(True)
        self.status_message.emit(f"Error: {msg}")

    def _set_busy(self, busy: bool):
        self._progress.setVisible(busy)
        self._progress.setRange(0, 0)
