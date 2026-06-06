"""Entry point."""

import sys
from pathlib import Path
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QPalette, QColor, QIcon
from PySide6.QtCore import Qt

from .ui.main_window import MainWindow

_ICON = Path(__file__).parent / "resources" / "icon.svg"


def _apply_dark_palette(app: QApplication) -> None:
    app.setStyle("Fusion")
    palette = QPalette()
    dark = QColor(45, 45, 45)
    mid = QColor(60, 60, 60)
    light = QColor(80, 80, 80)
    text = QColor(220, 220, 220)
    highlight = QColor(0, 120, 215)
    palette.setColor(QPalette.Window, dark)
    palette.setColor(QPalette.WindowText, text)
    palette.setColor(QPalette.Base, QColor(30, 30, 30))
    palette.setColor(QPalette.AlternateBase, mid)
    palette.setColor(QPalette.ToolTipBase, dark)
    palette.setColor(QPalette.ToolTipText, text)
    palette.setColor(QPalette.Text, text)
    palette.setColor(QPalette.Button, mid)
    palette.setColor(QPalette.ButtonText, text)
    palette.setColor(QPalette.BrightText, Qt.red)
    palette.setColor(QPalette.Highlight, highlight)
    palette.setColor(QPalette.HighlightedText, Qt.white)
    palette.setColor(QPalette.Link, highlight)
    app.setPalette(palette)


def main() -> None:
    app = QApplication(sys.argv)
    app.setApplicationName("Grimoire")
    app.setOrganizationName("grimoire")
    if _ICON.exists():
        app.setWindowIcon(QIcon(str(_ICON)))
    _apply_dark_palette(app)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
