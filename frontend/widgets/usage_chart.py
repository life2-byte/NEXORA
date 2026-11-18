from datetime import date

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QColor, QFont, QPainter, QPen
from PyQt6.QtWidgets import QToolTip, QWidget

from frontend.styles.theme import COLORS

INPUT_COLOR = QColor("#4f6b8f")  # prompt (input) tokens
OUTPUT_COLOR = QColor(COLORS["accent"])  # jawab (output) tokens


def _nice_max(value: int) -> int:
    if value <= 0:
        return 100
    step = 10 ** (len(str(int(value))) - 1)
    for mult in (1, 2, 5, 10):
        if value <= step * mult:
            return step * mult
    return step * 10


def _short(n: int) -> str:
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M".replace(".0M", "M")
    if n >= 1000:
        return f"{n / 1000:.1f}k".replace(".0k", "k")
    return str(n)


class UsageChart(QWidget):
    """Roz ke tokens ka stacked bar chart (input neeche, output upar). Hover par tafseel."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(190)
        self.setMouseTracking(True)
        self._data: list = []
        self._hover = -1
        self._bars: list = []

    def set_data(self, data: list) -> None:
        """[{'day': 'YYYY-MM-DD', 'prompt', 'completion', 'calls'}]"""
        self._data = data
        self.update()

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        left, right, top, bottom = 46, 8, 14, 38
        w, h = self.width() - left - right, self.height() - top - bottom
        font = QFont(self.font())
        font.setPointSizeF(max(7.5, font.pointSizeF() - 1))
        p.setFont(font)
        muted, border = QColor(COLORS["muted"]), QColor(COLORS["border"])

        peak = max((d["prompt"] + d["completion"] for d in self._data), default=0)
        top_value = _nice_max(peak)
        for frac in (0, 0.5, 1):  # gridlines
            y = top + h * (1 - frac)
            p.setPen(QPen(border, 1))
            p.drawLine(QPointF(left, y), QPointF(left + w, y))
            p.setPen(muted)
            p.drawText(QRectF(0, y - 8, left - 6, 16), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, _short(int(top_value * frac)))

        self._bars = []
        n = max(1, len(self._data))
        slot = w / n
        bar_w = max(4.0, slot * 0.62)
        today = date.today().isoformat()
        for i, d in enumerate(self._data):
            x = left + i * slot + (slot - bar_w) / 2
            h_in = h * d["prompt"] / top_value
            h_out = h * d["completion"] / top_value
            base = top + h
            p.setPen(Qt.PenStyle.NoPen)
            if h_in > 0.5:  # input neeche
                p.setBrush(INPUT_COLOR)
                p.drawRect(QRectF(x, base - h_in, bar_w, h_in))
            if d["completion"] > 0:  # output upar (kam az kam 2px dikhe)
                h_out = max(h_out, 2.0)
                p.setBrush(OUTPUT_COLOR)
                p.drawRect(QRectF(x, base - h_in - h_out, bar_w, h_out))
            if i == self._hover:
                p.setPen(QPen(QColor(COLORS["text"]), 1))
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.drawRect(QRectF(x - 2, top, bar_w + 4, h))
            self._bars.append(QRectF(left + i * slot, top, slot, h + bottom - 10))
            if i % 2 == (n - 1) % 2 or n <= 8:  # aaj wala label hamesha, baqi ek chhor ke
                label = d["day"][8:10]
                p.setPen(QColor(COLORS["accent"]) if d["day"] == today else muted)
                p.drawText(QRectF(left + i * slot, base + 4, slot, 14), Qt.AlignmentFlag.AlignHCenter, label)

        # legend
        ly = self.height() - 14
        for j, (text, color) in enumerate((("Input tokens", INPUT_COLOR), ("Output tokens", OUTPUT_COLOR))):
            lx = left + j * 120
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(color)
            p.drawRoundedRect(QRectF(lx, ly + 2, 9, 9), 2, 2)
            p.setPen(muted)
            p.drawText(QRectF(lx + 14, ly - 2, 100, 16), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, text)
        if peak == 0:
            p.setPen(muted)
            p.drawText(QRectF(left, top, w, h), Qt.AlignmentFlag.AlignCenter, "Abhi koi usage nahi. AI chalane par yahan graph banega.")
        p.end()

    def mouseMoveEvent(self, event) -> None:
        pos = event.position()
        index = next((i for i, r in enumerate(self._bars) if r.contains(pos)), -1)
        if index != self._hover:
            self._hover = index
            self.update()
        if index >= 0:
            d = self._data[index]
            day = date.fromisoformat(d["day"]).strftime("%d %b")
            QToolTip.showText(
                event.globalPosition().toPoint(),
                f"{day}: {d['prompt']:,} in / {d['completion']:,} out, {d['calls']} calls",
                self,
            )
        else:
            QToolTip.hideText()

    def leaveEvent(self, _event) -> None:
        self._hover = -1
        self.update()