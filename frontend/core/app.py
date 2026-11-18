import sys

from PyQt6 import sip
from PyQt6.QtWidgets import QApplication, QMessageBox

from frontend.core import profiles
from frontend.core.profile import dispose_profile
from frontend.core.web_profile import apply_web_settings
from frontend.styles.theme import apply_theme
from frontend.windows.main_window import MainWindow


def _cleanup() -> None:
    """Band hote waqt pehle saari windows (aur un ke pages), phir profile delete."""
    app = QApplication.instance()
    for widget in list(app.topLevelWidgets()):
        if not sip.isdeleted(widget):
            sip.delete(widget)
    dispose_profile()


def create_app(theme: str | None = None):
    app = QApplication(sys.argv)
    app.setApplicationName("Nexora")

    if not profiles.acquire_lock():
        QMessageBox.warning(
            None,
            "Nexora",
            "Ye profile pehle se khula hua hai.",
        )
        sys.exit(0)

    apply_theme(app, theme)
    apply_web_settings()

    window = MainWindow()

    app.aboutToQuit.connect(_cleanup)
    return app, window