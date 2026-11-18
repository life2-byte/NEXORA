from pathlib import Path

import threading

from PyQt6.QtCore import QObject, Qt, QUrl, pyqtSignal
from PyQt6.QtGui import QDesktopServices, QFontDatabase
from PyQt6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from backend.extensions.userscripts import MAX_SIZE, TEMPLATE_JS, fetch_script, parse_header
from frontend.core.userscripts import get_userscripts
from frontend.pages.base_page import BasePage
from frontend.styles.theme import COLORS


class _Editor(QDialog):
    def __init__(self, filename: str, text: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Edit script" if filename else "New script")
        self.resize(720, 520)
        self.name = QLineEdit(filename or "my-script.js")
        self.name.setReadOnly(bool(filename))
        self.edit = QPlainTextEdit(text)
        self.edit.setFont(QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont))
        self.edit.setTabStopDistance(32)
        save = QPushButton("Save")
        cancel = QPushButton("Cancel")
        save.clicked.connect(self.accept)
        cancel.clicked.connect(self.reject)
        row = QHBoxLayout()
        row.addStretch(1)
        row.addWidget(cancel)
        row.addWidget(save)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("File ka naam (.js ya .css)"))
        layout.addWidget(self.name)
        layout.addWidget(self.edit, 1)
        layout.addLayout(row)

    def values(self) -> tuple:
        return self.name.text().strip(), self.edit.toPlainText()


class _Fetcher(QObject):
    done = pyqtSignal(str, str, str)  # filename, text, error

    def fetch(self, url: str) -> None:
        def work() -> None:
            try:
                name, text = fetch_script(url)
                self.done.emit(name, text, "")
            except ValueError as e:
                self.done.emit("", "", str(e))

        threading.Thread(target=work, daemon=True).start()


class _Preview(QDialog):
    """Install se pehle poora code dikhao."""

    def __init__(self, filename: str, text: str, url: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Install script?")
        self.resize(720, 520)
        meta = parse_header(text)
        sites = ", ".join(meta["match"]) or "KOI @match NAHI (ye kahin nahi chalegi)"
        head = QLabel(
            f"<b>{meta['name'] or filename}</b><br>Link: {url}<br>Chalegi in sites par: {sites}<br>"
            "Neeche poora code parh lo. Samajh na aaye ya bharosa na ho to Cancel karo."
        )
        head.setWordWrap(True)
        code = QPlainTextEdit(text)
        code.setReadOnly(True)
        code.setFont(QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont))
        install = QPushButton("Install")
        cancel = QPushButton("Cancel")
        cancel.setDefault(True)
        install.clicked.connect(self.accept)
        cancel.clicked.connect(self.reject)
        row = QHBoxLayout()
        row.addStretch(1)
        row.addWidget(cancel)
        row.addWidget(install)
        layout = QVBoxLayout(self)
        layout.addWidget(head)
        layout.addWidget(code, 1)
        layout.addLayout(row)


class _Row(QWidget):
    def __init__(self, item, manager, page):
        super().__init__()
        self.setObjectName("ScriptRow")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(f"#ScriptRow {{ background:{COLORS['panel']}; border-radius:8px; }}")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)

        self.toggle = QCheckBox()
        self.toggle.setChecked(manager.is_enabled(item.filename))
        self.toggle.setEnabled(item.valid)
        self.toggle.toggled.connect(lambda on: manager.set_enabled(item.filename, on))

        info = QVBoxLayout()
        info.setSpacing(2)
        title = QLabel(f"{item.name}  ({item.filename})")
        title.setStyleSheet(f"color:{COLORS['text']}; font-weight:600; background:transparent;")
        if item.valid:
            where = ", ".join(item.meta["match"][:3]) + (" ..." if len(item.meta["match"]) > 3 else "")
            detail = f"{where}  |  {item.meta['run-at']}  |  {item.meta['world']}"
        else:
            detail = "@match nahi mila: ye script kahin nahi chalegi (header mein @match likho)"
        sub = QLabel(detail)
        sub.setStyleSheet(f"color:{COLORS['muted']}; background:transparent;")
        sub.setWordWrap(True)
        info.addWidget(title)
        info.addWidget(sub)

        edit = QPushButton("Edit")
        delete = QPushButton("Delete")
        for b in (edit, delete):
            b.setObjectName("SettingsButton")
            b.setCursor(Qt.CursorShape.PointingHandCursor)
        edit.clicked.connect(lambda: page.edit_script(item.filename))
        delete.clicked.connect(lambda: page.delete_script(item))

        layout.addWidget(self.toggle)
        layout.addLayout(info, 1)
        layout.addWidget(edit)
        layout.addWidget(delete)


class ScriptsPage(BasePage):
    def __init__(self, parent=None):
        super().__init__(
            "User scripts",
            "Apni chhoti extensions: JS ya CSS jo chuni hui sites par chalti hai. Chrome Web Store ki extensions nahi chalti.",
            parent,
        )
        self._manager = get_userscripts()
        self._fetcher = _Fetcher()
        self._fetcher.done.connect(self._on_fetched)
        self._fetch_url = ""

        warn = QLabel(
            "Dhyan: script us site ke page ke andar chalti hai (wahi page jis par tum password daalte ho). "
            "Sirf wahi script lagao jo tum ne khud likhi ho ya jis par poora bharosa ho. "
            "Passwords wali sites par scripts ka @match mat do."
        )
        warn.setObjectName("HintLabel")
        warn.setWordWrap(True)
        self.body.addWidget(warn)

        bar = QWidget()
        bar_layout = QHBoxLayout(bar)
        bar_layout.setContentsMargins(0, 0, 0, 0)
        bar_layout.setSpacing(8)
        for text, fn in (
            ("New script...", self.new_script),
            ("Add from file...", self.add_file),
            ("Install from link...", self.install_from_link),
            ("Open scripts folder", self.open_folder),
        ):
            btn = QPushButton(text)
            btn.setObjectName("SettingsButton")
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda _=False, f=fn: f())
            bar_layout.addWidget(btn)
        bar_layout.addStretch(1)
        self.body.addWidget(bar)

        self.info = QLabel("")
        self.info.setObjectName("HintLabel")
        self.info.setWordWrap(True)
        self.body.addWidget(self.info)

        self.list_box = QWidget()
        self.list_layout = QVBoxLayout(self.list_box)
        self.list_layout.setContentsMargins(0, 0, 0, 0)
        self.list_layout.setSpacing(6)
        self.body.addWidget(self.list_box)
        self.body.addStretch(1)
        self.refresh()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self.refresh()

    def refresh(self) -> None:
        while self.list_layout.count():
            item = self.list_layout.takeAt(0)
            if item.widget() is not None:
                item.widget().deleteLater()
        scripts = self._manager.scripts()
        if not scripts:
            empty = QLabel("Abhi koi script nahi. 'New script...' se shuru karo.")
            empty.setObjectName("HintLabel")
            self.list_layout.addWidget(empty)
        for item in scripts:
            self.list_layout.addWidget(_Row(item, self._manager, self))

    def _saved(self, filename: str) -> None:
        self.info.setText(f"'{filename}' save ho gayi. Khuli hui tabs ko reload karo (F5) taake script lage.")
        self.refresh()

    def new_script(self) -> None:
        dialog = _Editor("", TEMPLATE_JS, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._store(*dialog.values(), new=True)

    def edit_script(self, filename: str) -> None:
        path = self._manager.store.folder / filename
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return
        dialog = _Editor(filename, text, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._store(*dialog.values(), new=False)

    def _store(self, filename: str, text: str, new: bool) -> None:
        try:
            if new:
                filename = self._manager.store.unique_name(filename)
            self._saved(self._manager.save(filename, text))
        except (ValueError, OSError) as e:
            QMessageBox.warning(self, "User scripts", str(e))

    def add_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Add script", str(Path.home()), "Scripts (*.js *.css)")
        if not path:
            return
        file = Path(path)
        if file.stat().st_size > MAX_SIZE:
            QMessageBox.warning(self, "User scripts", "File bohat bari hai (512 KB se zyada).")
            return
        self._store(file.name, file.read_text(encoding="utf-8", errors="replace"), new=True)

    def install_from_link(self) -> None:
        url, ok = QInputDialog.getText(
            self, "Install from link", "Script ka seedha (raw) https link, jese .../name.user.js ya .css:"
        )
        if ok and url.strip():
            self._fetch_url = url.strip()
            self.info.setText("Download ho rahi hai...")
            self._fetcher.fetch(self._fetch_url)

    def _on_fetched(self, filename: str, text: str, error: str) -> None:
        if error:
            self.info.setText(error)
            return
        self.info.setText("")
        if _Preview(filename, text, self._fetch_url, self).exec() == QDialog.DialogCode.Accepted:
            self._store(filename, text, new=True)

    def delete_script(self, item) -> None:
        answer = QMessageBox.question(self, "Delete script", f"'{item.name}' delete karun?")
        if answer == QMessageBox.StandardButton.Yes:
            self._manager.delete(item.filename)
            self.refresh()

    def open_folder(self) -> None:
        folder = self._manager.store.folder
        folder.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder)))