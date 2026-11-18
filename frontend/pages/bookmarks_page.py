from datetime import datetime
from pathlib import Path

from PyQt6.QtCore import QSize, Qt, QTimer, pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPushButton,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from frontend.assets.icons import get_icon
from frontend.core.bookmarks import bookmarks
from frontend.pages.base_page import BasePage
from frontend.pages.history_page import _elide, _Row
from frontend.styles.theme import COLORS


class BookmarksPage(BasePage):
    open_url = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__("Bookmarks", "Save kiye hue pages. Star ya Ctrl+D se add karo, right-click se folder mein daalo.", parent)

        self._extra_folders: set = set()  # abhi khali naye folders (combo mein dikhane ke liye)
        bar = QWidget()
        bar_layout = QHBoxLayout(bar)
        bar_layout.setContentsMargins(0, 0, 0, 0)
        bar_layout.setSpacing(8)
        self.search = QLineEdit()
        self.search.setObjectName("SettingsInput")
        self.search.setPlaceholderText("Search bookmarks")
        self.search.setClearButtonEnabled(True)
        self.folder_combo = QComboBox()
        self.folder_combo.setMinimumWidth(170)
        self.folder_combo.currentIndexChanged.connect(lambda _: self.refresh())
        bar_layout.addWidget(self.search, 1)
        bar_layout.addWidget(self.folder_combo)
        self.body.addWidget(bar)

        tools = QWidget()
        tools_layout = QHBoxLayout(tools)
        tools_layout.setContentsMargins(0, 0, 0, 0)
        tools_layout.setSpacing(8)
        for text, fn in (
            ("New folder...", self._new_folder),
            ("Rename folder...", self._rename_folder),
            ("Delete folder", self._delete_folder),
            ("Import...", self._import),
            ("Export...", self._export),
        ):
            btn = QPushButton(text)
            btn.setObjectName("SettingsButton")
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda _=False, f=fn: f())
            tools_layout.addWidget(btn)
            if text in ("Rename folder...", "Delete folder"):
                setattr(self, "_btn_" + text.split()[0].lower(), btn)
        tools_layout.addStretch(1)
        self.body.addWidget(tools)
        self.info = QLabel("")
        self.info.setObjectName("HintLabel")
        self.body.addWidget(self.info)
        self._build_folder_combo()

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

        bookmarks.changed.connect(self.refresh)
        self.refresh()

    # ---------- folders ----------
    def _build_folder_combo(self) -> None:
        keep = self.folder_combo.currentData() if self.folder_combo.count() else None
        self.folder_combo.blockSignals(True)
        self.folder_combo.clear()
        self.folder_combo.addItem("All bookmarks", None)
        self.folder_combo.addItem("No folder", "")
        real = {f["name"]: f["count"] for f in bookmarks.folders()}
        for name in sorted(set(real) | self._extra_folders, key=str.lower):
            self.folder_combo.addItem(f"{name} ({real.get(name, 0)})", name)
        index = self.folder_combo.findData(keep)
        self.folder_combo.setCurrentIndex(max(0, index))
        self.folder_combo.blockSignals(False)
        chosen = bool(self.folder_combo.currentData())
        self._btn_rename.setEnabled(chosen)
        self._btn_delete.setEnabled(chosen)

    def _current_folder(self):
        return self.folder_combo.currentData()

    def _ask_name(self, title: str, text: str = "") -> str:
        name, ok = QInputDialog.getText(self, title, "Folder ka naam:", text=text)
        return name.strip()[:60] if ok else ""

    def _new_folder(self) -> None:
        name = self._ask_name("New folder")
        if name:
            self._extra_folders.add(name)
            self._build_folder_combo()
            self.folder_combo.setCurrentIndex(self.folder_combo.findData(name))
            self.info.setText(f"'{name}' ban gaya. Bookmark pe right-click → Move to folder se is mein daalo.")

    def _rename_folder(self) -> None:
        old = self._current_folder()
        if not old:
            return
        new = self._ask_name("Rename folder", old)
        if new and new != old:
            bookmarks.rename_folder(old, new)

    def _delete_folder(self) -> None:
        name = self._current_folder()
        if not name:
            return
        box = QMessageBox(self)
        box.setWindowTitle("Delete folder")
        box.setText(f"'{name}' folder delete karun?")
        keep = box.addButton("Folder hatao, bookmarks rakho", QMessageBox.ButtonRole.AcceptRole)
        wipe = box.addButton("Bookmarks bhi delete", QMessageBox.ButtonRole.DestructiveRole)
        box.addButton(QMessageBox.StandardButton.Cancel)
        box.exec()
        if box.clickedButton() is keep:
            bookmarks.delete_folder(name, False)
        elif box.clickedButton() is wipe:
            bookmarks.delete_folder(name, True)

    def _import(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Import bookmarks", str(Path.home()), "Bookmarks HTML (*.html *.htm)"
        )
        if not path:
            return
        try:
            new, dup = bookmarks.import_file(path)
        except Exception as e:  # kharab file
            self.info.setText(f"Import nahi hua: {e}")
            return
        self.info.setText(f"{new} bookmarks import hue" + (f", {dup} pehle se maujood the." if dup else "."))

    def _export(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "Export bookmarks", str(Path.home() / "bookmarks.html"), "Bookmarks HTML (*.html)"
        )
        if path:
            count = bookmarks.export_file(path if path.lower().endswith((".html", ".htm")) else path + ".html")
            self.info.setText(f"{count} bookmarks export hue.")

    def _row_menu(self, entry: dict, pos) -> None:
        menu = QMenu(self)
        move = menu.addMenu("Move to folder")
        move.addAction("No folder", lambda: bookmarks.move(entry["id"], ""))
        names = {f["name"] for f in bookmarks.folders()} | self._extra_folders
        for name in sorted(names, key=str.lower):
            move.addAction(name, lambda n=name: bookmarks.move(entry["id"], n))
        move.addSeparator()
        move.addAction("New folder...", lambda: self._move_to_new(entry))
        menu.addAction("Open", lambda: self.open_url.emit(entry["url"]))
        menu.addAction("Delete", lambda: bookmarks.delete(entry["id"]))
        menu.exec(pos)

    def _move_to_new(self, entry: dict) -> None:
        name = self._ask_name("New folder")
        if name:
            bookmarks.move(entry["id"], name)

    def refresh(self) -> None:
        self._build_folder_combo()
        while self.list_layout.count():
            item = self.list_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        entries = bookmarks.search(self.search.text(), folder=self._current_folder())
        if not entries:
            empty = QLabel("Abhi koi bookmark nahi.")
            empty.setObjectName("HintLabel")
            self.list_layout.addWidget(empty)
            return

        for entry in entries:
            self.list_layout.addWidget(self._make_row(entry))

    def _make_row(self, entry: dict) -> QWidget:
        row = _Row()
        row.setObjectName("HistoryRow")
        row.setCursor(Qt.CursorShape.PointingHandCursor)
        row.clicked.connect(lambda url=entry["url"]: self.open_url.emit(url))
        row.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        row.customContextMenuRequested.connect(lambda p, e=entry, r=row: self._row_menu(e, r.mapToGlobal(p)))

        layout = QHBoxLayout(row)
        layout.setContentsMargins(10, 6, 8, 6)
        layout.setSpacing(12)

        date_label = QLabel(datetime.fromtimestamp(entry["created_at"]).strftime("%d %b"))
        date_label.setObjectName("HistoryTime")
        date_label.setFixedWidth(46)

        texts = QVBoxLayout()
        texts.setSpacing(1)
        title = QLabel()
        title.setObjectName("HistoryTitle")
        _elide(title, entry["title"] or entry["url"], 560)
        url = QLabel()
        url.setObjectName("HistoryUrl")
        _elide(url, (f"[{entry['folder']}]  " if entry.get("folder") else "") + entry["url"], 560)
        texts.addWidget(title)
        texts.addWidget(url)

        delete = QToolButton()
        delete.setObjectName("RowDelete")
        delete.setIcon(get_icon("x", COLORS["muted"], hover_color=COLORS["text"]))
        delete.setIconSize(QSize(12, 12))
        delete.setAutoRaise(True)
        delete.setToolTip("Remove bookmark")
        delete.clicked.connect(lambda _=False, bid=entry["id"]: bookmarks.delete(bid))

        layout.addWidget(date_label)
        layout.addLayout(texts, 1)
        layout.addWidget(delete)
        return row