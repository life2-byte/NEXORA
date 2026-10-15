from pathlib import Path

from PyQt6.QtCore import PYQT_VERSION_STR, QT_VERSION_STR, Qt, QUrl
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWebEngineCore import qWebEngineChromiumVersion
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSlider,
    QWidget,
)

from frontend.api.backend_client import backend_client
from frontend.core.convert_worker import ConvertWorker
from frontend.core.settings_manager import SEARCH_ENGINES, settings
from frontend.core.web_profile import clear_browsing_data
from frontend.pages.base_page import BasePage
from frontend.widgets.card import Card

IMAGE_FILTER = "Images (*.png *.jpg *.jpeg *.webp *.gif *.bmp)"
VIDEO_FILTER = "Videos (*.webm *.mp4 *.mkv *.mov *.avi *.ogv *.ogg)"

SHORTCUTS_TEXT = (
    "Ctrl+T    New tab\n"
    "Ctrl+W    Close tab\n"
    "Ctrl+L    Focus address bar\n"
    "Ctrl+=    Zoom in\n"
    "Ctrl+-    Zoom out\n"
    "Ctrl+0    Reset zoom\n"
    "Alt+Enter Ask AI (address bar mein)"
)


def _label(text: str, name: str = "FieldLabel") -> QLabel:
    label = QLabel(text)
    label.setObjectName(name)
    label.setWordWrap(True)
    return label


def _button(text: str, callback) -> QPushButton:
    btn = QPushButton(text)
    btn.setObjectName("SettingsButton")
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    btn.clicked.connect(callback)
    return btn


class SettingsPage(BasePage):
    def __init__(self, parent=None):
        super().__init__(
            "Settings",
            "Changes turant lagti hain aur save ho jati hain.",
            parent,
        )
        self._worker = None
        self._tmp_path = None
        self._sync = {}  # setting key -> widget ko update karne wala function

        self.add_section("General")
        self.add_cards([self._startup_card(), self._window_card()], columns=2)
        self.add_section("Home page")
        self.add_cards([self._background_card()], columns=2)
        self.add_section("Browsing")
        self.add_cards([self._page_card(), self._search_card()], columns=2)
        self.add_section("Downloads and privacy")
        self.add_cards([self._downloads_card(), self._privacy_card()], columns=2)
        self.add_section("About")
        self.add_cards([self._shortcuts_card(), self._about_card()], columns=2)
        self.body.addStretch(1)

        settings.changed.connect(self._on_setting_changed)
        QApplication.instance().aboutToQuit.connect(self._shutdown_worker)

    # ---------- bound controls (settings ke saath sync rehte hain) ----------
    def _quiet(self, widget, fn) -> None:
        widget.blockSignals(True)
        fn()
        widget.blockSignals(False)

    def _checkbox(self, text: str, key: str) -> QCheckBox:
        box = QCheckBox(text)
        box.setChecked(bool(settings.get(key)))
        box.toggled.connect(lambda checked: settings.set(key, checked))
        self._sync[key] = lambda v: self._quiet(box, lambda: box.setChecked(bool(v)))
        return box

    def _combo(self, key: str, options: list) -> QComboBox:
        combo = QComboBox()
        for label, value in options:
            combo.addItem(label, value)
        combo.setCurrentIndex(max(0, combo.findData(settings.get(key))))
        combo.currentIndexChanged.connect(lambda _: settings.set(key, combo.currentData()))
        self._sync[key] = lambda v: self._quiet(
            combo, lambda: combo.setCurrentIndex(max(0, combo.findData(v)))
        )
        return combo

    def _slider(self, key: str, minimum: int, maximum: int, suffix: str) -> QWidget:
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        value = int(settings.get(key))
        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setRange(minimum, maximum)
        slider.setValue(value)

        label = QLabel(f"{value}{suffix}")
        label.setObjectName("ValueLabel")
        label.setFixedWidth(52)

        def handle(v: int) -> None:
            label.setText(f"{v}{suffix}")
            settings.set(key, v)

        def sync(v) -> None:
            self._quiet(slider, lambda: slider.setValue(int(v)))
            label.setText(f"{int(v)}{suffix}")

        slider.valueChanged.connect(handle)
        self._sync[key] = sync

        layout.addWidget(slider, 1)
        layout.addWidget(label)
        return row

    # ---------- General ----------
    def _startup_card(self) -> Card:
        card = Card("Startup")
        card.add_widget(_label("When the browser opens"))
        card.add_widget(
            self._combo(
                "startup_mode",
                [("Home page", "home"), ("Blank page", "blank"), ("Custom URL", "custom")],
            )
        )

        self.startup_url = QLineEdit(str(settings.get("startup_url")))
        self.startup_url.setObjectName("SettingsInput")
        self.startup_url.setPlaceholderText("https://example.com")
        self.startup_url.setEnabled(settings.get("startup_mode") == "custom")
        self.startup_url.editingFinished.connect(
            lambda: settings.set("startup_url", self.startup_url.text().strip())
        )
        self._sync["startup_url"] = lambda v: self.startup_url.setText(str(v))
        card.add_widget(self.startup_url)

        card.add_widget(_label("New tab opens"))
        card.add_widget(
            self._combo("newtab_mode", [("Home page", "home"), ("Blank page", "blank")])
        )
        return card

    def _window_card(self) -> Card:
        card = Card("Window and AI")
        card.add_widget(self._checkbox("Remember window size and position", "restore_geometry"))
        card.add_widget(self._checkbox("Show AI activity strip while the agent works", "ai_strip"))
        return card

    # ---------- Appearance ----------


    def _background_card(self) -> Card:
        card = Card("Home background")
        self.bg_status = _label(self._bg_status_text(), "HintLabel")
        card.add_widget(self.bg_status)

        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 6, 0, 0)
        row_layout.setSpacing(8)
        self.video_btn = _button("Video...", self._choose_video)
        row_layout.addWidget(_button("Default", lambda: settings.set("bg_mode", "default")))
        row_layout.addWidget(_button("Image...", self._choose_image))
        row_layout.addWidget(self.video_btn)
        row_layout.addWidget(_button("None", lambda: settings.set("bg_mode", "none")))
        row_layout.addStretch(1)
        card.add_widget(row)

        # ---- video conversion status ----
        self.convert_label = _label("", "HintLabel")
        card.add_widget(self.convert_label)

        self.convert_row = QWidget()
        convert_layout = QHBoxLayout(self.convert_row)
        convert_layout.setContentsMargins(0, 0, 0, 0)
        convert_layout.setSpacing(8)
        self.convert_bar = QProgressBar()
        self.convert_bar.setRange(0, 100)
        self.convert_bar.setTextVisible(False)
        self.convert_bar.setFixedHeight(6)
        self.cancel_btn = _button("Cancel", self._cancel_conversion)
        convert_layout.addWidget(self.convert_bar, 1)
        convert_layout.addWidget(self.cancel_btn)
        self.convert_row.hide()
        card.add_widget(self.convert_row)

        card.add_widget(_label("Dim (overlay)"))
        card.add_widget(self._slider("bg_dim", 0, 90, "%"))
        card.add_widget(self._checkbox("Animate video background", "bg_animated"))
        card.add_widget(
            _label(
                ".webm seedha lagti hai. mp4/mkv jaisi video chunoge to auto .webm mein "
                "convert hogi (thora time lagega, ffmpeg chahiye).",
                "HintLabel",
            )
        )
        return card

    # ---------- Browsing ----------
    def _page_card(self) -> Card:
        card = Card("Pages")
        card.add_widget(_label("Default zoom"))
        card.add_widget(self._slider("zoom", 50, 200, "%"))
        card.add_widget(_label("Font size (naye load hone wale pages pe)"))
        card.add_widget(self._slider("font_size", 12, 28, "px"))
        card.add_widget(self._checkbox("Smooth scrolling", "smooth_scroll"))
        card.add_widget(self._checkbox("Force dark mode on websites", "force_dark_web"))
        return card

    def _search_card(self) -> Card:
        card = Card("Search")
        card.add_widget(_label("Default search engine"))
        card.add_widget(self._combo("search_engine", [(n, n) for n in SEARCH_ENGINES]))
        return card

    # ---------- Downloads and privacy ----------
    def _downloads_card(self) -> Card:
        card = Card("Downloads")
        card.add_widget(_label("Save files to"))
        self.download_dir_label = _label(str(settings.get("download_dir")), "ValueLabel")
        self._sync["download_dir"] = lambda v: self.download_dir_label.setText(str(v))
        card.add_widget(self.download_dir_label)
        card.add_widget(_button("Change folder...", self._choose_download_dir))
        card.add_widget(self._checkbox("Ask where to save each file", "ask_download"))
        return card

    def _privacy_card(self) -> Card:
        card = Card("Privacy")
        card.add_widget(self._checkbox("Block pop-up windows", "block_popups"))
        card.add_widget(self._checkbox("Block third-party cookies", "block_third_party_cookies"))
        card.add_widget(
            self._checkbox("Delete cookies when browser closes (restart ke baad)", "clear_cookies_on_exit")
        )
        self.clear_hint = _label("", "HintLabel")
        card.add_widget(_button("Clear cache and cookies", self._clear_data))
        card.add_widget(self.clear_hint)
        return card



    # ---------- About ----------
    def _shortcuts_card(self) -> Card:
        card = Card("Shortcuts")
        card.add_widget(_label(SHORTCUTS_TEXT, "ValueLabel"))
        return card

    def _about_card(self) -> Card:
        card = Card("About")
        card.add_widget(_label("Agentic Browser (dev build)", "ValueLabel"))
        card.add_widget(
            _label(
                f"Engine: Chromium {qWebEngineChromiumVersion()} | "
                f"Qt {QT_VERSION_STR} | PyQt {PYQT_VERSION_STR}",
                "HintLabel",
            )
        )
        card.add_widget(_label(f"Settings folder: {settings.config_dir}", "HintLabel"))
        card.add_widget(_button("Open settings folder", self._open_config_dir))
        card.add_widget(_button("Reset all settings", self._reset_all))
        return card

    # ---------- actions ----------
    def _bg_status_text(self) -> str:
        mode = settings.get("bg_mode")
        if mode in ("image", "video"):
            return f"Current: your {mode} ({Path(settings.get('bg_path')).name})"
        if mode == "none":
            return "Current: none"
        return "Current: default (bundled image + video)"

    def _choose_image(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Choose background image", str(Path.home()), IMAGE_FILTER
        )
        if path:
            settings.set_background("image", path)

    def _choose_video(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Choose background video", str(Path.home()), VIDEO_FILTER
        )
        if not path:
            return
        if backend_client.needs_video_conversion(path):
            self._start_conversion(path)
        else:
            settings.set_background("video", path)
            self.convert_label.setText("")

    def _choose_download_dir(self) -> None:
        path = QFileDialog.getExistingDirectory(
            self, "Choose download folder", str(settings.get("download_dir"))
        )
        if path:
            settings.set("download_dir", path)

    def _clear_data(self) -> None:
        clear_browsing_data()
        self.clear_hint.setText("Cache aur cookies clear ho gayi.")

    def _open_config_dir(self) -> None:
        settings.config_dir.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(settings.config_dir)))

    def _reset_all(self) -> None:
        answer = QMessageBox.question(
            self,
            "Reset settings",
            "Saari settings default par chali jayengi. Pakka?",
        )
        if answer == QMessageBox.StandardButton.Yes:
            settings.reset()

    # ---------- video conversion (backend) ----------
    def _start_conversion(self, path: str) -> None:
        if self._worker is not None and self._worker.isRunning():
            return
        if not backend_client.ffmpeg_available():
            self.convert_label.setText("ffmpeg nahi mila. Terminal mein chala: sudo apt install ffmpeg")
            return

        settings.config_dir.mkdir(parents=True, exist_ok=True)
        self._tmp_path = settings.config_dir / "converting.webm"

        self._worker = ConvertWorker(path, str(self._tmp_path))
        self._worker.progress.connect(self._on_convert_progress)
        self._worker.done.connect(self._on_convert_done)
        self._worker.failed.connect(self._on_convert_failed)

        self.convert_bar.setValue(0)
        self.convert_row.show()
        self.video_btn.setEnabled(False)
        self.convert_label.setText("Video .webm mein convert ho rahi hai, thora time lagega...")
        self._worker.start()

    def _on_convert_progress(self, value: int) -> None:
        self.convert_bar.setValue(value)
        self.convert_label.setText(f"Converting video... {value}%")

    def _on_convert_done(self, out_path: str) -> None:
        settings.set_background("video", out_path)
        self._finish_conversion("Video convert ho gayi aur background lag gaya.")

    def _on_convert_failed(self, message: str) -> None:
        self._finish_conversion(
            "Conversion cancel kar di." if message == "Cancelled" else f"Conversion fail: {message}"
        )

    def _finish_conversion(self, message: str) -> None:
        if self._tmp_path is not None:
            self._tmp_path.unlink(missing_ok=True)
        self.convert_row.hide()
        self.video_btn.setEnabled(True)
        self.convert_label.setText(message)

    def _cancel_conversion(self) -> None:
        if self._worker is not None and self._worker.isRunning():
            self._worker.cancel()
            self.convert_label.setText("Cancel ho raha hai...")

    def _shutdown_worker(self) -> None:
        if self._worker is not None and self._worker.isRunning():
            self._worker.cancel()
            self._worker.wait(5000)

    # ---------- sync ----------
    def _on_setting_changed(self, key: str, value) -> None:
        setter = self._sync.get(key)
        if setter:
            setter(value)
        if key in ("bg_mode", "bg_path"):
            self.bg_status.setText(self._bg_status_text())
        if key == "startup_mode":
            self.startup_url.setEnabled(value == "custom")