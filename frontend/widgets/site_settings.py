from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QCheckBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QVBoxLayout,
)

from frontend.core.cookies import get_cookie_manager
from frontend.core.profile import get_profile
from frontend.core.settings_manager import settings

ZOOM_MIN, ZOOM_MAX = 50, 200


class SiteSettingsDialog(QDialog):
    """Ek site (host) ki apni settings: zoom, ad blocker, permissions, cookies."""

    def __init__(self, host: str, parent=None):
        super().__init__(parent)
        self.host = host.lower()
        self.setWindowTitle("Site settings")
        self.setMinimumWidth(420)

        layout = QVBoxLayout(self)
        title = QLabel(f"<b>{self.host}</b>")
        title.setTextFormat(Qt.TextFormat.RichText)
        layout.addWidget(title)

        # ---- zoom ----
        self._site_zoom = dict(settings.get("site_zoom") or {})
        current = int(self._site_zoom.get(self.host, settings.get("zoom")))
        layout.addWidget(QLabel("Zoom (sirf is site ke liye)"))
        row = QHBoxLayout()
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(ZOOM_MIN, ZOOM_MAX)
        self.slider.setSingleStep(10)
        self.slider.setValue(current)
        self.zoom_label = QLabel(f"{current}%")
        self.zoom_label.setFixedWidth(48)
        self.slider.valueChanged.connect(lambda v: self.zoom_label.setText(f"{v}%"))
        self.slider.sliderReleased.connect(self._save_zoom)
        self.slider.actionTriggered.connect(lambda _a: self._save_zoom_later())
        reset = QPushButton("Default")
        reset.clicked.connect(self._reset_zoom)
        row.addWidget(self.slider, 1)
        row.addWidget(self.zoom_label)
        row.addWidget(reset)
        layout.addLayout(row)

        # ---- ads ----
        self.ads = QCheckBox("Block ads and trackers on this site")
        self.ads.setChecked(self.host not in (settings.get("adblock_allow") or []))
        self.ads.toggled.connect(self._toggle_ads)
        layout.addWidget(self.ads)
        if not settings.get("adblock_enabled"):
            note = QLabel("Ad blocker poore browser mein band hai (Settings → Privacy).")
            note.setObjectName("HintLabel")
            layout.addWidget(note)

        # ---- reset buttons ----
        self.status = QLabel("")
        self.status.setObjectName("HintLabel")
        perms = QPushButton("Reset permissions (camera, mic, location...)")
        perms.clicked.connect(self._reset_permissions)
        cookies = QPushButton("Clear cookies for this site")
        cookies.clicked.connect(self._clear_cookies)
        layout.addWidget(perms)
        layout.addWidget(cookies)
        layout.addWidget(self.status)

        close = QPushButton("Close")
        close.clicked.connect(self.accept)
        layout.addWidget(close, 0, Qt.AlignmentFlag.AlignRight)

    # ---------- zoom ----------
    def _save_zoom_later(self) -> None:
        from PyQt6.QtCore import QTimer

        QTimer.singleShot(0, self._save_zoom)  # keyboard/arrow se badle to bhi save

    def _save_zoom(self) -> None:
        value = round(self.slider.value() / 10) * 10
        saved = dict(settings.get("site_zoom") or {})
        if value == int(settings.get("zoom")):
            saved.pop(self.host, None)
        else:
            saved[self.host] = value
        settings.set("site_zoom", saved)

    def _reset_zoom(self) -> None:
        saved = dict(settings.get("site_zoom") or {})
        saved.pop(self.host, None)
        settings.set("site_zoom", saved)
        self.slider.setValue(int(settings.get("zoom")))

    # ---------- ads ----------
    def _toggle_ads(self, on: bool) -> None:
        allow = [h for h in (settings.get("adblock_allow") or []) if h != self.host]
        if not on:
            allow.append(self.host)
        settings.set("adblock_allow", allow)
        self.status.setText("Page reload karo taake tabdeeli nazar aaye.")

    # ---------- permissions / cookies ----------
    def _reset_permissions(self) -> None:
        profile = get_profile()
        if not hasattr(profile, "listAllPermissions"):
            self.status.setText("Is ke liye Qt 6.8 ya naya chahiye.")
            return
        count = 0
        for perm in profile.listAllPermissions():
            if perm.origin().host().lower() == self.host and perm.state().name in ("Granted", "Denied"):
                perm.reset()
                count += 1
        self.status.setText(f"{count} permission(s) reset hui.")

    def _clear_cookies(self) -> None:
        manager = get_cookie_manager()
        count = 0
        for domain in list(manager.grouped()):
            if domain == self.host or self.host.endswith("." + domain) or domain.endswith("." + self.host):
                count += len(manager.grouped().get(domain, []))
                manager.delete_domain(domain)
        self.status.setText(f"{count} cookie(s) delete hui. Page reload karo.")