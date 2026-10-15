from pathlib import Path

from PyQt6.QtCore import QEasingCurve, Qt, QTimer, QVariantAnimation, pyqtSignal
from PyQt6.QtGui import QBrush, QColor, QLinearGradient, QPainter, QPainterPath, QPixmap
from PyQt6.QtWidgets import (
    QButtonGroup,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from frontend.assets.icons import get_icon

ASSETS = Path(__file__).resolve().parents[1] / "assets" / "sidebar"

COLLAPSED_W = 56
EXPANDED_W = 248

BRAND_NAME = "Agentic Browser"
TAGLINE = "Not just a browser.\nAn agent that gets things done."

SURFACE = "#0e1626"
BORDER = "#1f2d45"
ICON_MUTED = "#9aa7c0"
ICON_ACTIVE = "#38bdf8"

# (key, label, icon)
ITEMS = [
    ("home", "Home", "home"),
    ("browse", "Browse", "globe"),
    ("agents", "Agents", "cpu"),
    ("tasks", "Tasks", "check-square"),
    ("memory", "Memory", "database"),
    ("downloads", "Downloads", "download"),
    ("bookmarks", "Bookmarks", "bookmark"),
    ("settings", "Settings", "settings"),
]


def _find(stem: str, exts: tuple) -> Path | None:
    for ext in exts:
        path = ASSETS / f"{stem}.{ext}"
        if path.exists():
            return path
    return None


def _rounded_logo(size: int, radius: int) -> QPixmap:
    dpr = 2
    pix = QPixmap(size * dpr, size * dpr)
    pix.setDevicePixelRatio(dpr)
    pix.fill(Qt.GlobalColor.transparent)

    painter = QPainter(pix)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

    path = QPainterPath()
    path.addRoundedRect(0, 0, size, size, radius, radius)
    painter.setClipPath(path)
    painter.fillRect(0, 0, size, size, QColor("#0a1226"))

    logo_path = _find("logo", ("png", "webp", "jpg", "jpeg"))
    if logo_path:
        src = QPixmap(str(logo_path))
        if not src.isNull():
            margin = int(src.width() * 0.10)  # logo ke aas paas ka khali andhera kaat do
            src = src.copy(margin, margin, src.width() - 2 * margin, src.height() - 2 * margin)
            src = src.scaled(
                size * dpr,
                size * dpr,
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation,
            )
            src.setDevicePixelRatio(dpr)
            painter.drawPixmap(0, 0, src)
    painter.end()
    return pix


class SidebarItem(QPushButton):
    def __init__(self, icon_name: str, text: str, parent=None):
        super().__init__(parent)
        self.setObjectName("SidebarItem")
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(44)
        self.setToolTip(text)
        self._icon_name = icon_name

        layout = QHBoxLayout(self)
        layout.setContentsMargins(17, 0, 12, 0)  # icon ka center = 28px (collapsed width ka beech)
        layout.setSpacing(14)

        self.icon_label = QLabel()
        self.icon_label.setFixedSize(22, 22)
        self.icon_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

        self.text_label = QLabel(text)
        self.text_label.setObjectName("SidebarText")
        self.text_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

        layout.addWidget(self.icon_label)
        layout.addWidget(self.text_label, 1)

        self.toggled.connect(lambda _: self._refresh_icon())
        self._refresh_icon()

    def _refresh_icon(self) -> None:
        color = ICON_ACTIVE if self.isChecked() else ICON_MUTED
        self.icon_label.setPixmap(get_icon(self._icon_name, color).pixmap(22, 22))


class Sidebar(QWidget):
    """Icons-only rail; mouse aane pe nebula image ke saath khulti hai (content ke upar float)."""

    item_selected = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("Sidebar")
        self.setFixedWidth(COLLAPSED_W)
        self.resize(COLLAPSED_W, 600)

        self._expanded = False
        self._text_widgets: list[QWidget] = []
        self.buttons: dict[str, SidebarItem] = {}

        self._bg_source = self._load_bg()
        self._bg_cache = QPixmap()
        self._bg_cache_h = -1

        self._build()
        self._set_text_visible(False)

        self._expand_timer = QTimer(self)
        self._expand_timer.setSingleShot(True)
        self._expand_timer.timeout.connect(self.expand)

        self._collapse_timer = QTimer(self)
        self._collapse_timer.setSingleShot(True)
        self._collapse_timer.timeout.connect(self.collapse)

        self._anim = QVariantAnimation(self)
        self._anim.setDuration(190)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._anim.valueChanged.connect(self._on_anim_value)
        self._anim.finished.connect(self._on_anim_finished)

    # ---------- build ----------
    def _load_bg(self) -> QPixmap:
        path = _find("sidebar_bg", ("jpg", "jpeg", "png", "webp"))
        if path is None:
            return QPixmap()
        pix = QPixmap(str(path))
        if not pix.isNull() and pix.width() > 600:
            pix = pix.scaledToWidth(600, Qt.TransformationMode.SmoothTransformation)
        return pix

    def _build(self) -> None:
        # content hamesha EXPANDED_W chauda hai; sidebar chhoti ho to bas clip ho jata hai
        self.content = QWidget(self)
        self.content.move(0, 0)
        self.content.setFixedWidth(EXPANDED_W)

        layout = QVBoxLayout(self.content)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        brand = QWidget()
        brand.setFixedHeight(64)
        brand_layout = QHBoxLayout(brand)
        brand_layout.setContentsMargins(10, 0, 12, 0)
        brand_layout.setSpacing(12)
        logo = QLabel()
        logo.setFixedSize(36, 36)
        logo.setPixmap(_rounded_logo(36, 10))
        name = QLabel(BRAND_NAME)
        name.setObjectName("BrandName")
        brand_layout.addWidget(logo)
        brand_layout.addWidget(name, 1)
        self._text_widgets.append(name)
        layout.addWidget(brand)

        self.group = QButtonGroup(self)
        self.group.setExclusive(True)
        for key, label, icon in ITEMS:
            item = SidebarItem(icon, label)
            item.clicked.connect(lambda _, k=key: self._on_item_clicked(k))
            self.group.addButton(item)
            self.buttons[key] = item
            self._text_widgets.append(item.text_label)
            layout.addWidget(item)

        layout.addStretch(1)

        tag_box = QWidget()
        tag_layout = QVBoxLayout(tag_box)
        tag_layout.setContentsMargins(18, 0, 14, 22)
        tagline = QLabel(TAGLINE)
        tagline.setObjectName("Tagline")
        tagline.setWordWrap(True)
        tag_layout.addWidget(tagline)
        self._text_widgets.append(tag_box)
        layout.addWidget(tag_box)

        self.buttons["home"].setChecked(True)

    # ---------- public ----------
    def select(self, name: str) -> None:
        if name in self.buttons:
            self.buttons[name].setChecked(True)

    def expand(self) -> None:
        if self._expanded:
            return
        self._expanded = True
        self._set_text_visible(True)
        self._animate_to(EXPANDED_W)

    def collapse(self) -> None:
        if not self._expanded:
            return
        self._expanded = False
        self._animate_to(COLLAPSED_W)

    # ---------- internals ----------
    def _on_item_clicked(self, key: str) -> None:
        self.item_selected.emit(key)
        self._expand_timer.stop()
        self.collapse()

    def _set_text_visible(self, visible: bool) -> None:
        for widget in self._text_widgets:
            widget.setVisible(visible)

    def _animate_to(self, target: int) -> None:
        self._anim.stop()
        self._anim.setStartValue(self.width())
        self._anim.setEndValue(target)
        self._anim.start()

    def _on_anim_value(self, value) -> None:
        self.setFixedWidth(int(value))
        self.update()

    def _on_anim_finished(self) -> None:
        if not self._expanded:
            self._set_text_visible(False)

    def _progress(self) -> float:
        p = (self.width() - COLLAPSED_W) / (EXPANDED_W - COLLAPSED_W)
        return max(0.0, min(1.0, p))

    def _rescale_bg(self) -> None:
        height = self.height()
        self._bg_cache_h = height
        if self._bg_source.isNull() or height <= 0:
            self._bg_cache = QPixmap()
            return
        self._bg_cache = self._bg_source.scaled(
            EXPANDED_W,
            height,
            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.SmoothTransformation,
        )

    # ---------- events ----------
    def enterEvent(self, event) -> None:
        self._collapse_timer.stop()
        if not self._expanded:
            self._expand_timer.start(140)
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self._expand_timer.stop()
        if self._expanded:
            self._collapse_timer.start(300)
        super().leaveEvent(event)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self.content.setFixedHeight(self.height())
        if self.height() != self._bg_cache_h:
            self._rescale_bg()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        painter.fillRect(self.rect(), QColor(SURFACE))

        progress = self._progress()
        if progress > 0:
            painter.setOpacity(progress)
            if not self._bg_cache.isNull():
                sx = max(0, (self._bg_cache.width() - EXPANDED_W) // 2)
                painter.drawPixmap(0, 0, self._bg_cache, sx, 0, EXPANDED_W, self.height())
            # text padhne layak banane ke liye upar neeche gehra gradient
            grad = QLinearGradient(0, 0, 0, self.height())
            grad.setColorAt(0.0, QColor(8, 12, 24, 215))
            grad.setColorAt(0.45, QColor(8, 12, 24, 110))
            grad.setColorAt(1.0, QColor(8, 12, 24, 225))
            painter.fillRect(self.rect(), QBrush(grad))
            painter.setOpacity(1.0)

        painter.setPen(QColor(BORDER))
        painter.drawLine(self.width() - 1, 0, self.width() - 1, self.height())