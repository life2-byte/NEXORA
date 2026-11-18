from PyQt6.QtCore import QDateTime, QSize, Qt, QTimer
from PyQt6.QtGui import QGuiApplication
from PyQt6.QtNetwork import QNetworkCookie
from PyQt6.QtWidgets import (
    QCheckBox,
    QDateTimeEdit,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
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
from frontend.core.cookies import get_cookie_manager
from frontend.pages.base_page import BasePage
from frontend.pages.history_page import _elide, _Row
from frontend.styles.theme import COLORS


def _name(c: QNetworkCookie) -> str:
    return bytes(c.name()).decode("utf-8", "replace")


def _value(c: QNetworkCookie) -> str:
    return bytes(c.value()).decode("utf-8", "replace")


def _expiry_text(c: QNetworkCookie) -> str:
    if c.isSessionCookie():
        return "Session"
    return c.expirationDate().toString("dd MMM yyyy, HH:mm")


def _flags_text(c: QNetworkCookie) -> str:
    flags = [f"path {c.path() or '/'}"]
    if c.isSecure():
        flags.append("Secure")
    if c.isHttpOnly():
        flags.append("HttpOnly")
    return "  ·  ".join(flags)


class _ValueLabel(QLabel):
    """Cookie ki value default mein chhupi rehti hai (••••). Click karo to dikhe, dobara click pe phir chhup jaye."""

    def __init__(self, text: str, width: int, masked: bool = True):
        super().__init__()
        self.setObjectName("HistoryUrl")
        self._text = text
        self._width = width
        self._masked = masked and bool(text)
        self._shown = False
        if self._masked:
            self.setCursor(Qt.CursorShape.PointingHandCursor)
            self.setToolTip("Click karke value dekho")
        self._render()

    def _render(self) -> None:
        if self._masked and not self._shown:
            shown = "•" * min(max(len(self._text), 6), 24)
        else:
            shown = self._text
        self.setText(self.fontMetrics().elidedText(shown, Qt.TextElideMode.ElideRight, self._width))

    def mousePressEvent(self, event) -> None:
        if self._masked and event.button() == Qt.MouseButton.LeftButton:
            self._shown = not self._shown
            self._render()
        super().mousePressEvent(event)


class _CookieDialog(QDialog):
    """Cookie add ya edit karne ki window. Edit mein domain/name/path badal nahi sakte."""

    def __init__(self, cookie: QNetworkCookie | None = None, parent=None):
        super().__init__(parent)
        editing = cookie is not None
        self.setWindowTitle("Edit cookie" if editing else "Add cookie")
        self.setMinimumWidth(420)

        self.domain = QLineEdit(cookie.domain() if editing else "")
        self.domain.setPlaceholderText("example.com")
        self.name = QLineEdit(_name(cookie) if editing else "")
        self.value = QLineEdit(_value(cookie) if editing else "")
        self.path = QLineEdit(cookie.path() if editing else "/")
        self.secure = QCheckBox("Secure (sirf https)")
        self.http_only = QCheckBox("HttpOnly")
        self.session = QCheckBox("Session cookie (browser band hone par delete)")
        self.expires = QDateTimeEdit(QDateTime.currentDateTime().addYears(1))
        self.expires.setCalendarPopup(True)
        self.expires.setDisplayFormat("dd MMM yyyy, HH:mm")

        if editing:
            self.secure.setChecked(cookie.isSecure())
            self.http_only.setChecked(cookie.isHttpOnly())
            self.session.setChecked(cookie.isSessionCookie())
            if not cookie.isSessionCookie():
                self.expires.setDateTime(cookie.expirationDate())
            for w in (self.domain, self.name, self.path):
                w.setReadOnly(True)
        else:
            self.session.setChecked(False)
        self.expires.setEnabled(not self.session.isChecked())
        self.session.toggled.connect(lambda on: self.expires.setEnabled(not on))

        form = QFormLayout()
        form.addRow("Domain", self.domain)
        form.addRow("Name", self.name)
        form.addRow("Value", self.value)
        form.addRow("Path", self.path)
        form.addRow("", self.session)
        form.addRow("Expires", self.expires)
        form.addRow("", self.secure)
        form.addRow("", self.http_only)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)

    def result_args(self) -> dict:
        return dict(
            domain=self.domain.text(),
            name=self.name.text(),
            value=self.value.text(),
            path=self.path.text(),
            expires=None if self.session.isChecked() else self.expires.dateTime(),
            secure=self.secure.isChecked(),
            http_only=self.http_only.isChecked(),
        )


class CookiesPage(BasePage):
    def __init__(self, parent=None):
        super().__init__("Cookies", "Sab sites ke cookies dekho, edit karo ya delete karo.", parent)
        self.manager = get_cookie_manager()
        self._open_domains: set[str] = set()

        # ---------- top bar ----------
        top = QHBoxLayout()
        top.setSpacing(8)
        self.search = QLineEdit()
        self.search.setObjectName("SettingsInput")
        self.search.setPlaceholderText("Search domain ya cookie name")
        self.search.setClearButtonEnabled(True)
        top.addWidget(self.search, 1)

        add_btn = QPushButton("Add cookie")
        add_btn.setObjectName("SettingsButton")
        add_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        add_btn.clicked.connect(self._add)
        clear_btn = QPushButton("Delete all")
        clear_btn.setObjectName("SettingsButton")
        clear_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        clear_btn.clicked.connect(self._delete_all)
        top.addWidget(add_btn)
        top.addWidget(clear_btn)
        self.body.addLayout(top)

        self.summary = QLabel()
        self.summary.setObjectName("HintLabel")
        self.body.addWidget(self.summary)

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
        self.manager.changed.connect(self.refresh)
        self.refresh()

    # ---------- list ----------
    def showEvent(self, event) -> None:
        super().showEvent(event)
        self.manager.reload()

    def refresh(self) -> None:
        while self.list_layout.count():
            widget = self.list_layout.takeAt(0).widget()
            if widget is not None:
                widget.deleteLater()

        query = self.search.text()
        groups = self.manager.grouped(query)
        total = sum(len(v) for v in groups.values())
        self.summary.setText(f"{total} cookies, {len(groups)} sites")

        if not groups:
            empty = QLabel("Koi cookie nahi mili.")
            empty.setObjectName("HintLabel")
            self.list_layout.addWidget(empty)
            return

        searching = bool(query.strip())
        for domain, cookies in groups.items():
            self.list_layout.addWidget(self._make_domain(domain, cookies, expanded=searching))

    def _icon_button(self, icon: str, tip: str, callback) -> QToolButton:
        btn = QToolButton()
        btn.setObjectName("RowDelete")
        btn.setIcon(get_icon(icon, COLORS["muted"], hover_color=COLORS["text"]))
        btn.setIconSize(QSize(12, 12))
        btn.setAutoRaise(True)
        btn.setToolTip(tip)
        btn.clicked.connect(lambda _=False: callback())
        return btn

    def _make_domain(self, domain: str, cookies: list, expanded: bool) -> QWidget:
        wrapper = QWidget()
        col = QVBoxLayout(wrapper)
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(2)

        is_open = expanded or domain in self._open_domains

        header = _Row()
        header.setObjectName("HistoryRow")
        header.setCursor(Qt.CursorShape.PointingHandCursor)
        h = QHBoxLayout(header)
        h.setContentsMargins(10, 8, 8, 8)
        h.setSpacing(12)

        arrow = QLabel("▾" if is_open else "▸")
        arrow.setObjectName("HistoryTime")
        arrow.setFixedWidth(16)
        title = QLabel(domain)
        title.setObjectName("HistoryTitle")
        count = QLabel(f"{len(cookies)}")
        count.setObjectName("HistoryTime")
        h.addWidget(arrow)
        h.addWidget(title, 1)
        h.addWidget(count)
        h.addWidget(self._icon_button("x", f"Delete all cookies of {domain}", lambda d=domain: self.manager.delete_domain(d)))
        col.addWidget(header)

        details = QWidget()
        dl = QVBoxLayout(details)
        dl.setContentsMargins(28, 0, 0, 4)
        dl.setSpacing(2)
        for cookie in cookies:
            dl.addWidget(self._make_cookie(cookie))
        details.setVisible(is_open)
        col.addWidget(details)

        def toggle() -> None:
            show = not details.isVisible()
            details.setVisible(show)
            arrow.setText("▾" if show else "▸")
            (self._open_domains.add if show else self._open_domains.discard)(domain)

        header.clicked.connect(toggle)
        return wrapper

    def _make_cookie(self, cookie: QNetworkCookie) -> QWidget:
        row = QWidget()
        row.setObjectName("HistoryRow")
        layout = QHBoxLayout(row)
        layout.setContentsMargins(10, 6, 8, 6)
        layout.setSpacing(8)

        texts = QVBoxLayout()
        texts.setSpacing(1)
        name = QLabel()
        name.setObjectName("HistoryTitle")
        _elide(name, _name(cookie), 420)
        if self.manager.is_disk_only(cookie):
            value = _ValueLabel("(encrypted, site kholne par value dikhegi)", 420, masked=False)
        else:
            value = _ValueLabel(_value(cookie) or "(empty)", 420, masked=bool(_value(cookie)))
        meta = QLabel(f"{_expiry_text(cookie)}  ·  {_flags_text(cookie)}")
        meta.setObjectName("HistoryTime")
        texts.addWidget(name)
        texts.addWidget(value)
        texts.addWidget(meta)

        layout.addLayout(texts, 1)
        layout.addWidget(self._icon_button("copy", "Copy value", lambda c=cookie: self._copy(c)))
        layout.addWidget(self._icon_button("edit", "Edit", lambda c=cookie: self._edit(c)))
        layout.addWidget(self._icon_button("x", "Delete cookie", lambda c=cookie: self.manager.delete(c)))
        return row

    # ---------- actions ----------
    def _copy(self, cookie: QNetworkCookie) -> None:
        if self.manager.is_disk_only(cookie):
            QMessageBox.information(self, "Cookie", "Is cookie ki value abhi encrypted hai. Site kholo to value mil jayegi.")
            return
        QGuiApplication.clipboard().setText(_value(cookie))

    def _edit(self, cookie: QNetworkCookie) -> None:
        if self.manager.is_disk_only(cookie):
            QMessageBox.information(self, "Cookie", "Is cookie ki value abhi encrypted hai. Pehle site kholo, phir edit karo.")
            return
        dialog = _CookieDialog(cookie, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            error = self.manager.save(**dialog.result_args())
            if error:
                QMessageBox.warning(self, "Cookie", error)

    def _add(self) -> None:
        dialog = _CookieDialog(None, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            error = self.manager.save(**dialog.result_args())
            if error:
                QMessageBox.warning(self, "Cookie", error)

    def _delete_all(self) -> None:
        if self.manager.count() == 0:
            return
        answer = QMessageBox.question(
            self,
            "Delete all cookies",
            f"{self.manager.count()} cookies delete hongi aur sab sites se logout ho jayega. Pakka?",
        )
        if answer == QMessageBox.StandardButton.Yes:
            self.manager.delete_all()