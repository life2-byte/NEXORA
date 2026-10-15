import sys

from PyQt6.QtWidgets import QApplication

from frontend.styles.theme import apply_theme
from frontend.windows.main_window import MainWindow


def create_app(theme: str = "dark"):
    app = QApplication(sys.argv)
    app.setApplicationName("Agentic Browser")
    apply_theme(app, theme)
    window = MainWindow()
    return app, window