from pathlib import Path
from PyQt6.QtCore import PYQT_VERSION_STR, QT_VERSION_STR, Qt, QUrl, pyqtSignal
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWebEngineCore import qWebEngineChromiumVersion
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QListWidget,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)
from backend.ai.presets import LOCAL_KINDS, REMOTE_PRESETS
from frontend.core.adblock import get_adblock
from frontend.core.ai_connect import ConnectionTester
from frontend.core.ai_provider import model_hint
from frontend.core.ai_usage import ai_usage
from frontend.core.profile import get_profile
from backend.privacy.policy import DEFAULT_BLOCK_DOMAINS, normalize_entry
from backend.security import secrets
from frontend.core import ai_privacy
from frontend.core.history import history
from frontend.api.backend_client import backend_client
from frontend.core.convert_worker import ConvertWorker
from frontend.core.settings_manager import SEARCH_ENGINES, settings
from frontend.core.web_profile import cache_size_text, clear_cache, clear_cookies
from frontend.pages.base_page import BasePage
from frontend.widgets.card import Card
from PyQt6.QtCore import PYQT_VERSION_STR, QT_VERSION_STR, Qt, QTimer, QUrl

IMAGE_FILTER = "Images (*.png *.jpg *.jpeg *.webp *.gif *.bmp)"
VIDEO_FILTER = "Videos (*.webm *.mp4 *.mkv *.mov *.avi *.ogv *.ogg)"
REMOTE_WARNING = (
    "Remote model chunne par, jab agent kaam karega, jo pages wo parhta hai un ka text tere chune "
    "hue provider ke server par jayega (passwords aur blocklist wali sites nahi).\n\n"
    "Local model mein kuch bhi tere computer se bahar nahi jata.\n\nRemote use karna hai?"
)

SHORTCUTS_TEXT = (
    "Ctrl+T       New tab\n"
    "Ctrl+W       Close tab\n"
    "Ctrl+L       Focus address bar\n"
    "Ctrl+=       Zoom in\n"
    "Ctrl+-       Zoom out\n"
    "Ctrl+0       Reset zoom\n"
    "F12          Developer tools\n"
    "Ctrl+U       View page source\n"
    "Ctrl+Shift+D Agent: read page\n"
    "Alt+Enter    Ask AI (address bar mein)\n"
    "Ctrl+Shift+A Search open tabs\n"
    "Ctrl+Alt+S   Site settings (zoom, ads, permissions)\n"
    "Ctrl+F       Find in page\n"
    "Ctrl+P       Print\n"
    "Ctrl+N       New window\n"
    "Ctrl+Shift+N New window without AI\n"
    "Ctrl+H       History\n"
    "Ctrl+D       Bookmark this page\n"
    "Ctrl+Shift+O Open page in default browser\n"
    "Ctrl+Shift+T Reopen closed tab\n"
    "Ctrl+J       Downloads page\n"
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
    open_page = pyqtSignal(str)
    def __init__(self, parent=None):
        super().__init__(
            "Settings",
            "Changes turant lagti hain aur save ho jati hain.",
            parent,
        )
        self._worker = None
        self._tmp_path = None
        self._tester = ConnectionTester()
        self._tester.finished.connect(self._on_test_done)
        self._sync = {}  # setting key -> widget ko update karne wala function

        self.add_section("General")
        self.add_cards([self._startup_card(), self._window_card()], columns=2)
        self.add_section("AI and privacy")
        self.add_cards([self._ai_card(), self._visibility_card()], columns=2)
        self.add_cards([self._local_card(), self._remote_card()], columns=2)
        self.add_cards([self._log_card()], columns=2)
        self.add_section("Home page")
        self.add_cards([self._background_card()], columns=2)
        self.add_section("Browsing")
        self.add_cards([self._page_card(), self._search_card()], columns=2)
        self.add_section("Downloads, network and privacy")
        self.add_cards(
                        [
                self._downloads_card(),
                self._network_card(),
                self._privacy_card(),
                self._permissions_card(),
            ],
            columns=2,
        )
        self.add_section("About")
        self.add_cards([self._shortcuts_card(), self._about_card()], columns=2)
        self.body.addStretch(1)

        self._sync_ai_cards()
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
                [
                    ("Home page", "home"),
                    ("Continue where I left off", "restore"),
                    ("Blank page", "blank"),
                    ("Custom URL", "custom"),
                ],
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

        card.add_widget(_label("Meri backgrounds (sirf is profile ke folder mein save hoti hain)"))
        self.bg_combo = QComboBox()
        self.bg_combo.currentIndexChanged.connect(self._on_bg_pick)
        card.add_widget(self.bg_combo)
        self._fill_bg_combo()

        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 6, 0, 0)
        row_layout.setSpacing(8)
        self.video_btn = _button("Add video...", self._choose_video)
        row_layout.addWidget(_button("Default", lambda: settings.set_many({"bg_mode": "default", "bg_path": ""})))
        row_layout.addWidget(_button("Add image...", self._choose_image))
        row_layout.addWidget(self.video_btn)
        row_layout.addWidget(_button("None", lambda: settings.set("bg_mode", "none")))
        row_layout.addStretch(1)
        card.add_widget(row)
        card.add_widget(_button("Remove selected background", self._remove_bg))

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
        card.add_widget(self._checkbox("Show most visited sites on home page", "show_most_visited"))
        card.add_widget(
            _label(
                "Default sirf moon wallpaper hai. Tumhari image/video app mein nahi, is profile ke folder mein copy hoti hai. "
                ".webm seedha lagti hai, mp4/mkv auto .webm mein convert hogi (ffmpeg chahiye).",
                "HintLabel",
            )
        )
        return card

    def _fill_bg_combo(self) -> None:
        current = settings.get("bg_path")
        self.bg_combo.blockSignals(True)
        self.bg_combo.clear()
        self.bg_combo.addItem("Choose a saved background...", None)
        for item in settings.list_backgrounds():
            self.bg_combo.addItem(f"{item['kind'].title()}: {item['name']}", item["path"])
        index = self.bg_combo.findData(current)
        self.bg_combo.setCurrentIndex(max(0, index))
        self.bg_combo.blockSignals(False)

    def _on_bg_pick(self, _index: int) -> None:
        path = self.bg_combo.currentData()
        if path:
            settings.use_background(path)

    def _remove_bg(self) -> None:
        path = self.bg_combo.currentData()
        if path:
            settings.remove_background(path)
            self._fill_bg_combo()

    # ---------- Browsing ----------
    def _page_card(self) -> Card:
        card = Card("Pages")
        card.add_widget(_label("Default zoom"))
        card.add_widget(self._slider("zoom", 50, 200, "%"))
        card.add_widget(_label("Font size (naye load hone wale pages pe)"))
        card.add_widget(self._slider("font_size", 12, 28, "px"))
        card.add_widget(self._checkbox("Smooth scrolling", "smooth_scroll"))
        card.add_widget(self._checkbox("Force dark mode on websites", "force_dark_web"))
        card.add_widget(_button("User scripts (apni extensions)...", lambda: self.open_page.emit("scripts")))
        return card
        # ---------- AI and privacy ----------
    def _line_edit(self, key: str, placeholder: str = "") -> QLineEdit:
        edit = QLineEdit(str(settings.get(key) or ""))
        edit.setObjectName("SettingsInput")
        edit.setPlaceholderText(placeholder)
        edit.editingFinished.connect(lambda: settings.set(key, edit.text().strip()))
        self._sync[key] = lambda v: edit.setText(str(v or ""))
        return edit

    def _ai_card(self) -> Card:
        card = Card("AI")
        card.add_widget(self._checkbox("Enable AI features", "ai_enabled"))
        card.add_widget(
            _label(
                "Band ho to omnibox sirf search/URL ke liye hai, agent tools band, aur koi page AI ko nahi dikhta.",
                "HintLabel",
            )
        )
        card.add_widget(_label("Model kahan chale"))
        self.provider_combo = QComboBox()
        self.provider_combo.addItem("Local model (data tere computer se bahar nahi jata)", "local")
        self.provider_combo.addItem("Remote API (page text provider ke server par jata hai)", "remote")
        self.provider_combo.setCurrentIndex(max(0, self.provider_combo.findData(settings.get("ai_provider"))))
        self.provider_combo.currentIndexChanged.connect(self._on_provider_changed)
        self._sync["ai_provider"] = lambda v: self._quiet(
            self.provider_combo,
            lambda: self.provider_combo.setCurrentIndex(max(0, self.provider_combo.findData(v))),
        )
        card.add_widget(self.provider_combo)
        self.ai_status = _label("", "HintLabel")
        card.add_widget(self.ai_status)
        self.usage_label = _label(ai_usage.status_text(), "HintLabel")
        card.add_widget(self.usage_label)
        ai_usage.changed.connect(lambda: self.usage_label.setText(ai_usage.status_text()))
        card.add_widget(
            _label("Sidebar ka 'New window (no AI)' is switch se alag hai, wahan AI hamesha band rehta hai.", "HintLabel")
        )
        return card

    def _on_provider_changed(self, _index: int) -> None:
        provider = self.provider_combo.currentData()
        if provider == "remote" and not settings.get("ai_remote_consent"):
            answer = QMessageBox.question(self, "Remote AI", REMOTE_WARNING)
            if answer != QMessageBox.StandardButton.Yes:
                self._quiet(
                    self.provider_combo,
                    lambda: self.provider_combo.setCurrentIndex(
                        max(0, self.provider_combo.findData(settings.get("ai_provider")))
                    ),
                )
                return
            settings.set("ai_remote_consent", True)
        settings.set("ai_provider", provider)

    def _local_card(self) -> Card:
        card = Card("Local model")
        card.add_widget(_label("Kaunsa local server"))
        self.local_kind_combo = self._combo(
            "ai_local_kind", [(info[0], key) for key, info in LOCAL_KINDS.items()]
        )
        card.add_widget(self.local_kind_combo)
        card.add_widget(_label("Endpoint"))
        self.local_endpoint_edit = self._line_edit("ai_local_endpoint", "")
        card.add_widget(self.local_endpoint_edit)
        card.add_widget(_label("Model name"))
        card.add_widget(self._line_edit("ai_local_model", "e.g. qwen2.5:7b"))
        card.add_widget(_button("Test connection", self._test_connection))
        card.add_widget(
            _label(
                "Ollama, LM Studio, llama.cpp ya koi bhi OpenAI-style server chalega. "
                "Chhote laptop par bade models dheeme chalte hain.",
                "HintLabel",
            )
        )
        self.local_usage = _label(ai_usage.status_text(), "HintLabel")
        card.add_widget(self.local_usage)
        ai_usage.changed.connect(lambda: self.local_usage.setText(ai_usage.status_text()))
        self._update_local_hint()
        self.local_card = card
        return card

    def _update_local_hint(self) -> None:
        info = LOCAL_KINDS.get(settings.get("ai_local_kind"), LOCAL_KINDS["ollama"])
        self.local_endpoint_edit.setPlaceholderText(info[2])

    def _remote_card(self) -> Card:
        card = Card("Remote API")
        card.add_widget(_label("Provider"))
        card.add_widget(
            self._combo("ai_remote_provider", [(info[0], key) for key, info in REMOTE_PRESETS.items()])
        )
        card.add_widget(_label("Model name"))
        self.remote_model_edit = self._line_edit("ai_remote_model", "")
        card.add_widget(self.remote_model_edit)
        card.add_widget(_label("Base URL (sirf Custom ke liye)"))
        card.add_widget(self._line_edit("ai_remote_base_url", "https://..."))
        card.add_widget(_label("API key"))
        self.key_edit = QLineEdit()
        self.key_edit.setObjectName("SettingsInput")
        self.key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.key_edit.setPlaceholderText("key paste karo, phir Save key")
        card.add_widget(self.key_edit)

        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(8)
        row_layout.addWidget(_button("Save key", self._save_key))
        row_layout.addWidget(_button("Remove key", self._remove_key))
        row_layout.addWidget(_button("Test connection", self._test_connection))
        row_layout.addStretch(1)
        card.add_widget(row)

        self.key_status = _label("", "HintLabel")
        card.add_widget(self.key_status)
        self.remote_usage = _label(ai_usage.status_text(), "HintLabel")
        card.add_widget(self.remote_usage)
        ai_usage.changed.connect(lambda: self.remote_usage.setText(ai_usage.status_text()))
        card.add_widget(
            _label("Key system keyring mein save hoti hai, settings file ya log mein kabhi nahi.", "HintLabel")
        )
        self._update_key_status()
        self._update_remote_hint()
        self.remote_card = card
        return card

    def _update_remote_hint(self) -> None:
        hint = model_hint(settings.get("ai_remote_provider"))
        self.remote_model_edit.setPlaceholderText(f"e.g. {hint}" if hint else "model id")

    # ---------- connection test ----------
    def _test_connection(self) -> None:
        if self._tester.running:
            return
        self.ai_status.setText("Connection test ho raha hai...")
        self._tester.start()

    def _on_test_done(self, report) -> None:
        self._sync_ai_cards()
        if report.ok:
            lines = [
                f"Model: {report.model}",
                f"Jawab: {report.message}",
                f"Time: {report.latency_ms} ms",
                f"Is test mein tokens: {report.usage.prompt_tokens} in / {report.usage.completion_tokens} out",
            ]
            limit = ai_usage.limit_text(report.limits)
            lines.append(f"Limit: {limit}" if limit else "Limit: is provider ne limit nahi batai.")
            QMessageBox.information(self, report.title, "\n".join(lines))
            ai_usage.record(report.usage, report.limits, report.model)
        else:
            QMessageBox.warning(self, report.title, report.message)

    def _update_key_status(self, extra: str = "") -> None:
        if extra:
            text = extra
        elif not secrets.available():
            text = "System keyring nahi mila: pip install keyring (aur GNOME Keyring chalna chahiye)."
        elif secrets.has_secret(ai_privacy.remote_key_name()):
            text = "Key saved (system keyring mein)."
        else:
            text = "Key set nahi hai."
        self.key_status.setText(text)

    def _save_key(self) -> None:
        value = self.key_edit.text().strip()
        if not value:
            return
        error = secrets.set_secret(ai_privacy.remote_key_name(), value)
        self.key_edit.clear()
        self._update_key_status(error or "Key save ho gayi (system keyring mein).")
        self._sync_ai_cards()

    def _remove_key(self) -> None:
        secrets.delete_secret(ai_privacy.remote_key_name())
        self._update_key_status("Key hata di.")
        self._sync_ai_cards()

    def _visibility_card(self) -> Card:
        card = Card("What the AI can see")
        card.add_widget(
            _label(
                "Built-in blocklist: accounts/sign-in, email, banks aur payments, password managers, "
                "private messaging, aur login/checkout pages. Agent inhein padh nahi sakta aur in par "
                "navigate bhi nahi karta.",
                "HintLabel",
            )
        )
        card.add_widget(_label("Teri apni blocklist (har line mein ek domain)"))
        self.blocklist_edit = QPlainTextEdit()
        self.blocklist_edit.setObjectName("SettingsText")
        self.blocklist_edit.setPlaceholderText("example.com\nmy-company-intranet.com")
        self.blocklist_edit.setFixedHeight(110)
        self.blocklist_edit.setPlainText("\n".join(settings.get("ai_blocklist_custom") or []))
        card.add_widget(self.blocklist_edit)
        card.add_widget(_button("Save blocklist", self._save_blocklist))
        self.blocklist_hint = _label(
            f"Built-in: {len(DEFAULT_BLOCK_DOMAINS)} domains + keywords (bank, wallet, mail.)", "HintLabel"
        )
        card.add_widget(self.blocklist_hint)
        self.visibility_card = card
        return card

    def _save_blocklist(self) -> None:
        entries = []
        for line in self.blocklist_edit.toPlainText().splitlines():
            domain = normalize_entry(line)
            if domain and domain not in entries:
                entries.append(domain)
        settings.set("ai_blocklist_custom", entries)
        self.blocklist_edit.setPlainText("\n".join(entries))
        self.blocklist_hint.setText(f"{len(entries)} site(s) saved.")

    def _log_card(self) -> Card:
        card = Card("AI activity log")
        card.add_widget(
            _label(
                "Jab bhi agent ka tool kisi page ko chhoone ki koshish kare, yahan likha jata hai: waqt, "
                "tool, site aur size. Page ka text ya passwords kabhi nahi. File sirf tere computer par hai.",
                "HintLabel",
            )
        )
        card.add_widget(self._checkbox("Keep AI activity log", "ai_log_enabled"))
        card.add_widget(_button("View log", self._show_log))
        card.add_widget(_button("Clear log", self._clear_log))
        self.log_hint = _label("", "HintLabel")
        card.add_widget(self.log_hint)
        return card

    def _show_log(self) -> None:
        dialog = QDialog(self)
        dialog.setWindowTitle("AI tool activity")
        dialog.resize(760, 460)
        layout = QVBoxLayout(dialog)
        view = QPlainTextEdit()
        view.setObjectName("SettingsText")
        view.setReadOnly(True)
        view.setPlainText(ai_privacy.read_log(300) or "Abhi koi activity nahi.")
        layout.addWidget(view)
        dialog.exec()

    def _clear_log(self) -> None:
        ai_privacy.clear_log()
        self.log_hint.setText("Log clear ho gaya.")

    def _sync_ai_cards(self) -> None:
        on = bool(settings.get("ai_enabled"))
        provider = settings.get("ai_provider")
        self.provider_combo.setEnabled(on)
        self.local_card.setEnabled(on and provider == "local")
        self.remote_card.setEnabled(on and provider == "remote")

        if not on:
            text = "AI band hai: kuch bhi AI ko nahi dikhta."
        else:
            problem = ai_privacy.readiness()
            if problem:
                text = f"Setup baqi: {problem}"
            elif provider == "local":
                text = "Ready: local model, data tere computer se bahar nahi jata."
            else:
                text = "Ready: remote API, agent ke padhe hue pages ka text provider ko jayega."
        self.ai_status.setText(text)
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

    def _network_card(self) -> Card:
        card = Card("Network and cache")
        card.add_widget(_label("Cache size limit"))
        card.add_widget(
            self._combo(
                "cache_limit_mb",
                [
                    ("Automatic", 0),
                    ("100 MB", 100),
                    ("250 MB", 250),
                    ("500 MB", 500),
                    ("1 GB", 1024),
                    ("2 GB", 2048),
                ],
            )
        )
        self.cache_label = _label("", "HintLabel")
        self._update_cache_label()
        card.add_widget(self.cache_label)
        card.add_widget(_button("Clear cache", self._clear_cache))
        card.add_widget(
            _label("Cache sirf pages tez load karne ke liye hai. Delete karne se logins nahi jate.", "HintLabel")
        )
        return card

    def _privacy_card(self) -> Card:
        card = Card("Privacy")
        card.add_widget(self._checkbox("Save browsing history", "save_history"))
        card.add_widget(self._checkbox("Block pop-up windows", "block_popups"))
        card.add_widget(self._checkbox("Block third-party cookies", "block_third_party_cookies"))
        card.add_widget(_button("Manage cookies...", lambda: self.open_page.emit("cookies")))
        card.add_widget(
            self._checkbox("Delete cookies when browser closes (restart ke baad)", "clear_cookies_on_exit")
        )
        card.add_widget(
            _label("Captcha baar baar aaye to third-party cookies block mat rakho.", "HintLabel")
        )
        self.clear_hint = _label("", "HintLabel")
        card.add_widget(_button("Clear cookies (sab sites se logout)", self._clear_cookies))
        card.add_widget(_button("Clear browsing history", self._clear_history))
        card.add_widget(self.clear_hint)

        # ---- ads, https, passwords ----
        card.add_widget(self._checkbox("Block ads and trackers", "adblock_enabled"))
        self.adblock_hint = _label(get_adblock().stats_text(), "HintLabel")
        card.add_widget(self.adblock_hint)
        card.add_widget(_button("Update filter lists", self._update_filters))
        get_adblock().update_finished.connect(self.adblock_hint.setText)
        card.add_widget(self._checkbox("Open sites over HTTPS first (http pe warning)", "https_first"))
        card.add_widget(self._checkbox("Offer to save passwords", "passwords_enabled"))
        card.add_widget(_button("Manage passwords...", lambda: self.open_page.emit("passwords")))
        return card

    def _update_filters(self) -> None:
        self.adblock_hint.setText("Lists download ho rahi hain...")
        get_adblock().update_lists()

    def _update_cache_label(self) -> None:
        self.cache_label.setText(f"Cache on disk: {cache_size_text()}")

    def _clear_cache(self) -> None:
        clear_cache()
        QTimer.singleShot(1500, self._update_cache_label)

    def _clear_cookies(self) -> None:
        clear_cookies()
        self.clear_hint.setText("Cookies clear ho gayi, sab sites se logout ho gaye.")

    def _clear_history(self) -> None:
        history.clear()
        self.clear_hint.setText("History clear ho gayi.")



    # ---------- About ----------
    def _shortcuts_card(self) -> Card:
        card = Card("Shortcuts")
        card.add_widget(_label(SHORTCUTS_TEXT, "ValueLabel"))
        return card

    def _about_card(self) -> Card:
        card = Card("About")
        card.add_widget(_label("Nexora (dev build)", "ValueLabel"))
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
            return "Current: none (sirf plain dark)"
        return "Current: default (moon wallpaper)"

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

        self._convert_name = Path(path).stem
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
        settings.set_background("video", out_path, getattr(self, "_convert_name", ""))
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
        if key in ("bg_mode", "bg_path", "bg_library"):
            self.bg_status.setText(self._bg_status_text())
            self._fill_bg_combo()
        if key == "ai_local_kind":
            self._update_local_hint()
        if key == "startup_mode":
            self.startup_url.setEnabled(value == "custom")
        if key in ("ai_enabled", "ai_provider", "ai_local_model", "ai_remote_provider"):
            if key == "ai_remote_provider":
                self._update_key_status()
                self._update_remote_hint()
            self._sync_ai_cards()
    def _permissions_card(self) -> Card:
        card = Card("Site permissions")
        card.add_widget(
            _label(
                "Sites ne camera, mic, location, notifications jese jo haan/na ki, wo yahan se wapas le sakte ho.",
                "HintLabel",
            )
        )
        card.add_widget(_button("Manage site permissions...", self._manage_permissions))
        return card

    def _manage_permissions(self) -> None:
        profile = get_profile()
        if not hasattr(profile, "listAllPermissions"):
            QMessageBox.information(self, "Site permissions", "Is feature ke liye Qt 6.8 ya naya chahiye.")
            return

        dialog = QDialog(self)
        dialog.setWindowTitle("Site permissions")
        dialog.resize(660, 420)
        layout = QVBoxLayout(dialog)
        listing = QListWidget()
        layout.addWidget(listing)
        saved: list = []

        def fill() -> None:
            listing.clear()
            saved.clear()
            for perm in profile.listAllPermissions():
                state = perm.state().name
                if state not in ("Granted", "Denied"):
                    continue
                saved.append(perm)
                origin = perm.origin()
                where = origin.host() or origin.toString()
                listing.addItem(f"{where}   -   {perm.permissionType().name}   -   {state}")
            if not saved:
                listing.addItem("Koi saved permission nahi.")

        def remove_selected() -> None:
            row = listing.currentRow()
            if 0 <= row < len(saved):
                saved[row].reset()
                fill()

        def remove_all() -> None:
            for perm in list(saved):
                perm.reset()
            fill()

        row_widget = QWidget()
        row_layout = QHBoxLayout(row_widget)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(8)
        row_layout.addWidget(_button("Remove selected", remove_selected))
        row_layout.addWidget(_button("Remove all", remove_all))
        row_layout.addStretch(1)
        row_layout.addWidget(_button("Close", dialog.accept))
        layout.addWidget(row_widget)

        fill()
        dialog.exec()