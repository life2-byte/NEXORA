from PyQt6.QtCore import QSize, pyqtSignal
from PyQt6.QtWidgets import QHBoxLayout, QMenu, QToolButton, QWidget

from frontend.assets.icons import get_icon
from frontend.core import profiles
from frontend.styles.theme import COLORS
from frontend.widgets.profile_menu import ProfileMenu, avatar_icon


class ToolbarActions(QWidget):
    """Omnibox ke right side ke buttons: bookmark star, downloads, account."""

    bookmark_toggled = pyqtSignal(bool)
    downloads_clicked = pyqtSignal()
    settings_clicked = pyqtSignal()
    profile_edited = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        self.star_btn = self._make_button("star", "Bookmark this page", checkable=True)
        self.star_btn.toggled.connect(self.bookmark_toggled.emit)

        self.downloads_btn = self._make_button("download", "Downloads")
        self.downloads_btn.clicked.connect(self.downloads_clicked.emit)

        self.account_btn = QToolButton()
        self.account_btn.setObjectName("AccountButton")
        self.account_btn.setIconSize(QSize(24, 24))
        self.account_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)

        menu = ProfileMenu(self.account_btn)
        menu.settings_requested.connect(self.settings_clicked.emit)
        menu.edited.connect(self._refresh_profile)
        self.account_btn.setMenu(menu)
        self._refresh_profile()

        layout.addWidget(self.star_btn)
        layout.addWidget(self.downloads_btn)
        layout.addSpacing(6)
        layout.addWidget(self.account_btn)

    def _refresh_profile(self) -> None:
        me = profiles.current_profile()
        self.account_btn.setIcon(avatar_icon(me["name"], me["color"]))
        self.account_btn.setToolTip(f"Profile: {me['name']}")
        self.profile_edited.emit()

    def _make_button(self, icon_name: str, tooltip: str, checkable: bool = False) -> QToolButton:
        btn = QToolButton()
        btn.setObjectName("NavButton")
        btn.setIcon(
            get_icon(
                icon_name,
                COLORS["muted"],
                active_color=COLORS["accent"],
                hover_color=COLORS["text"],
            )
        )
        btn.setIconSize(QSize(18, 18))
        btn.setAutoRaise(True)
        btn.setCheckable(checkable)
        btn.setToolTip(tooltip)
        return btn

    def set_bookmarked(self, value: bool) -> None:
        self.star_btn.blockSignals(True)
        self.star_btn.setChecked(value)
        self.star_btn.blockSignals(False)