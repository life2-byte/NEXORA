from datetime import date, datetime, timedelta

from PyQt6.QtCore import QSize, Qt, QTimer, pyqtSignal
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from frontend.assets.icons import get_icon
from frontend.core.history import history
from frontend.pages.base_page import BasePage
from frontend.styles.theme import COLORS


class _Row(QFrame):
    clicked = pyqtSignal()

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)


def _elide(label: QLabel, text: str, width: int) -> None:
    label.setText(label.fontMetrics().elidedText(text, Qt.TextElideMode.ElideRight, width))
    label.setToolTip(text)


def _day_title(day: date) -> str:
    today = date.today()
    if day == today:
        return "Today"
    if day == today - timedelta(days=1):
        return "Yesterday"
    return day.strftime("%A, %d %B %Y")


class HistoryPage(BasePage):
    open_url = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__("History", "Jo pages tu ne dekhe (sirf is computer par save hoti hai).", parent)

        bar = QWidget()
        bar_layout = QHBoxLayout(bar)
        bar_layout.setContentsMargins(0, 0, 0, 0)
        bar_layout.setSpacing(10)

        self.search = QLineEdit()
        self.search.setObjectName("SettingsInput")
        self.search.setPlaceholderText("Search history")
        self.search.setClearButtonEnabled(True)

        clear_btn = QPushButton("Clear all")
        clear_btn.setObjectName("SettingsButton")
        clear_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        clear_btn.clicked.connect(self._clear_all)

        bar_layout.addWidget(self.search, 1)
        bar_layout.addWidget(clear_btn)
        self.body.addWidget(bar)

        self.list_box = QWidget()
        self.list_layout = QVBoxLayout(self.list_box)
        self.list_layout.setContentsMargins(0, 0, 0, 0)
        self.list_layout.setSpacing(2)
        self.body.addWidget(self.list_box)
        self.body.addStretch(1)

        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(200)
        self._debounce.timeout.connect(self.refresh)
        self.search.textChanged.connect(lambda _: self._debounce.start())

    # ---------- data ----------
    def refresh(self) -> None:
        while self.list_layout.count():
            item = self.list_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        entries = history.search(self.search.text(), limit=300)
        if not entries:
            empty = QLabel("Koi history nahi mili.")
            empty.setObjectName("HintLabel")
            self.list_layout.addWidget(empty)
            return

        current_day = None
        for entry in entries:
            when = datetime.fromtimestamp(entry["visited_at"])
            if when.date() != current_day:
                current_day = when.date()
                header = QLabel(_day_title(current_day))
                header.setObjectName("DayHeader")
                self.list_layout.addWidget(header)
            self.list_layout.addWidget(self._make_row(entry, when))

    def _make_row(self, entry: dict, when: datetime) -> QWidget:
        row = _Row()
        row.setObjectName("HistoryRow")
        row.setCursor(Qt.CursorShape.PointingHandCursor)
        row.clicked.connect(lambda url=entry["url"]: self.open_url.emit(url))

        layout = QHBoxLayout(row)
        layout.setContentsMargins(10, 6, 8, 6)
        layout.setSpacing(12)

        time_label = QLabel(when.strftime("%H:%M"))
        time_label.setObjectName("HistoryTime")
        time_label.setFixedWidth(46)

        texts = QVBoxLayout()
        texts.setSpacing(1)
        title = QLabel()
        title.setObjectName("HistoryTitle")
        _elide(title, entry["title"] or entry["url"], 560)
        url = QLabel()
        url.setObjectName("HistoryUrl")
        _elide(url, entry["url"], 560)
        texts.addWidget(title)
        texts.addWidget(url)

        delete = QToolButton()
        delete.setObjectName("RowDelete")
        delete.setIcon(get_icon("x", COLORS["muted"], hover_color=COLORS["text"]))
        delete.setIconSize(QSize(12, 12))
        delete.setAutoRaise(True)
        delete.setToolTip("Remove from history")
        delete.clicked.connect(lambda _=False, vid=entry["id"]: self._delete(vid))

        layout.addWidget(time_label)
        layout.addLayout(texts, 1)
        layout.addWidget(delete)
        return row

    def _delete(self, visit_id: int) -> None:
        history.delete(visit_id)
        self.refresh()

    def _clear_all(self) -> None:
        answer = QMessageBox.question(self, "Clear history", "Saari browsing history delete kar dun?")
        if answer == QMessageBox.StandardButton.Yes:
            history.clear()
            self.refresh()