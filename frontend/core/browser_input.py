"""Asli mouse/keyboard events aur screenshot (canvas, Docs, games ke liye). GUI thread par chalta hai.
Screenshot sirf RAM mein (base64) rehta hai - disk par kabhi nahi likha jata."""

import base64
import hashlib
import random
from typing import Callable

from PyQt6.QtCore import QBuffer, QByteArray, QIODevice, QPoint, Qt, QTimer
from PyQt6.QtGui import QColor, QFont, QKeyEvent, QMouseEvent, QPainter
from PyQt6.QtWidgets import QApplication

from frontend.core import ai_privacy as privacy

MAX_SHOT_WIDTH = 900      # model ko itni chaudi tasveer (tokens aur RAM bachte hain)
MAX_CROP_WIDTH = 900      # zoom wali tasveer (chhota hissa, zyada tafseel)
JPEG_QUALITY = 55
MAX_TYPED_CHARS = 400

SPECIAL = {
    "enter": Qt.Key.Key_Return, "return": Qt.Key.Key_Return, "tab": Qt.Key.Key_Tab, "escape": Qt.Key.Key_Escape,
    "esc": Qt.Key.Key_Escape, "backspace": Qt.Key.Key_Backspace, "delete": Qt.Key.Key_Delete,
    "space": Qt.Key.Key_Space, "arrowup": Qt.Key.Key_Up, "arrowdown": Qt.Key.Key_Down, "arrowleft": Qt.Key.Key_Left,
    "arrowright": Qt.Key.Key_Right, "up": Qt.Key.Key_Up, "down": Qt.Key.Key_Down, "left": Qt.Key.Key_Left,
    "right": Qt.Key.Key_Right, "home": Qt.Key.Key_Home, "end": Qt.Key.Key_End, "pageup": Qt.Key.Key_PageUp,
    "pagedown": Qt.Key.Key_PageDown,
}
MODS = {"ctrl": Qt.KeyboardModifier.ControlModifier, "control": Qt.KeyboardModifier.ControlModifier,
        "shift": Qt.KeyboardModifier.ShiftModifier, "alt": Qt.KeyboardModifier.AltModifier}


def _target(view):
    """Jis widget par asli events jate hain (QtWebEngine ka andar wala render widget)."""
    return view.focusProxy() or view


def _draw_ticks(img) -> None:
    """Kinaron par har 100px ke nishan aur number: model ko coordinates andaze se nahi, parhne parte hain."""
    p = QPainter(img)
    font = QFont("sans-serif")
    font.setPixelSize(11)
    p.setFont(font)
    for v in range(100, max(img.width(), img.height()), 100):
        for color, off in ((QColor(0, 0, 0), 1), (QColor(255, 235, 59), 0)):
            p.setPen(color)
            if v < img.width():
                p.drawLine(v + off, 0, v + off, 6)
                p.drawText(v + 3 + off, 16 + off, str(v))
            if v < img.height():
                p.drawLine(0, v + off, 6, v + off)
                p.drawText(8 + off, v + 4 + off, str(v))
    p.end()


def take_screenshot(view, crop=None, last_hash: str = ""):
    """crop = (x, y, w, h) page pixels mein, ya None. Wapas dict, ya {"error": text}.
    mapping: page_pixel = o + tasveer_pixel * scale"""
    reason = privacy.tool_block_reason(view)
    if reason:
        return {"error": f"BLOCKED screenshot: {reason}"}
    pix = view.grab()
    if pix.isNull() or pix.width() < 2:
        return {"error": "FAILED screenshot: the tab has nothing to show yet (is it loaded?)"}
    pix.setDevicePixelRatio(1.0)
    k = pix.width() / max(1, view.width())          # tasveer pixel per page pixel
    ox = oy = 0.0
    page_w = view.width()
    if crop:
        cx, cy, cw, ch = crop
        cx, cy = max(0, min(cx, view.width() - 20)), max(0, min(cy, view.height() - 20))
        cw, ch = max(20, min(cw, view.width() - cx)), max(20, min(ch, view.height() - cy))
        pix = pix.copy(int(cx * k), int(cy * k), int(cw * k), int(ch * k))
        ox, oy, page_w = float(cx), float(cy), cw
    out_w = min(MAX_CROP_WIDTH if crop else MAX_SHOT_WIDTH, max(pix.width(), 1) if not crop else int(pix.width() * 2))
    img = pix.toImage().scaledToWidth(out_w, Qt.TransformationMode.SmoothTransformation)
    _draw_ticks(img)
    data = QByteArray()
    buf = QBuffer(data)
    buf.open(QIODevice.OpenModeFlag.WriteOnly)
    img.save(buf, "JPEG", JPEG_QUALITY)
    buf.close()
    raw = bytes(data)
    digest = hashlib.md5(raw).hexdigest()
    return {
        "b64": "" if digest == last_hash else base64.b64encode(raw).decode("ascii"),
        "same": digest == last_hash, "hash": digest,
        "w": img.width(), "h": img.height(),
        "scale": page_w / img.width(), "ox": ox, "oy": oy,
    }


def click_at(view, x: int, y: int, shot: dict, double: bool = False) -> str:
    reason = privacy.tool_block_reason(view)
    if reason:
        return f"BLOCKED click_at: {reason}"
    if not (0 <= x < shot["w"] and 0 <= y < shot["h"]):
        return f"FAILED click_at: ({x},{y}) is outside the picture ({shot['w']}x{shot['h']}). Use the pixel numbers on its edges."
    px, py = int(shot["ox"] + x * shot["scale"]), int(shot["oy"] + y * shot["scale"])
    if not (0 <= px < view.width() and 0 <= py < view.height()):
        return f"FAILED click_at: ({x},{y}) is outside the page. Take a new screenshot."
    target = _target(view)
    pos = QPoint(px, py)
    g = target.mapToGlobal(pos)
    btn = Qt.MouseButton.LeftButton
    for etype, buttons in (
        (QMouseEvent.Type.MouseMove, Qt.MouseButton.NoButton),
        (QMouseEvent.Type.MouseButtonPress, btn),
        (QMouseEvent.Type.MouseButtonRelease, Qt.MouseButton.NoButton),
    ) * (2 if double else 1):
        ev = QMouseEvent(etype, pos.toPointF(), g.toPointF(), btn if etype != QMouseEvent.Type.MouseMove else Qt.MouseButton.NoButton,
                         buttons, Qt.KeyboardModifier.NoModifier)
        QApplication.sendEvent(target, ev)
    return f"OK click_at ({x},{y})"


def _send_key(target, key, mods=Qt.KeyboardModifier.NoModifier, text: str = "") -> None:
    for etype in (QKeyEvent.Type.KeyPress, QKeyEvent.Type.KeyRelease):
        QApplication.sendEvent(target, QKeyEvent(etype, key, mods, text))


def parse_combo(combo: str):
    """'Ctrl+Shift+A' -> (Qt.Key, modifiers, text) ya None."""
    parts = [p.strip() for p in combo.split("+") if p.strip()]
    if not parts:
        return None
    mods = Qt.KeyboardModifier.NoModifier
    for p in parts[:-1]:
        m = MODS.get(p.lower())
        if m is None:
            return None
        mods |= m
    last = parts[-1]
    if last.lower() in SPECIAL:
        return SPECIAL[last.lower()], mods, ""
    if len(last) == 1:
        ch = last
        key = getattr(Qt.Key, f"Key_{ch.upper()}", None) if ch.isalnum() else None
        if key is None:
            return None
        has_ctrl = bool(mods & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.AltModifier))
        return key, mods, "" if has_ctrl else ch
    if last.upper().startswith("F") and last[1:].isdigit():
        key = getattr(Qt.Key, f"Key_{last.upper()}", None)
        return (key, mods, "") if key is not None else None
    return None


def press_keys(view, text: str, key: str, human: bool, done: Callable[[str], None]) -> None:
    reason = privacy.tool_block_reason(view)
    if reason:
        done(f"BLOCKED press_keys: {reason}")
        return
    target = _target(view)
    target.setFocus()
    if key:
        parsed = parse_combo(key)
        if parsed is None:
            done(f"FAILED press_keys: unknown key '{key}'. Use e.g. Enter, Tab, Escape, ArrowDown, Ctrl+A.")
            return
        k, mods, ch = parsed
        _send_key(target, k, mods, ch)
        if not text:
            done(f"OK press_keys {key}")
            return
    if not text:
        done("FAILED press_keys: give text or key")
        return
    text = text[:MAX_TYPED_CHARS]
    pos = [0]

    def tick() -> None:
        if privacy.tool_block_reason(view):
            done("BLOCKED press_keys: the page moved to a private site")
            return
        if pos[0] >= len(text):
            done(f'OK press_keys typed {len(text)} chars' + (f" after {key}" if key else ""))
            return
        ch = text[pos[0]]
        pos[0] += 1
        if ch == "\n":
            _send_key(target, Qt.Key.Key_Return)
        else:
            k = getattr(Qt.Key, f"Key_{ch.upper()}", None) if ch.isascii() and ch.isalnum() else None
            _send_key(target, k if k is not None else Qt.Key.Key_unknown,
                      Qt.KeyboardModifier.ShiftModifier if ch.isupper() else Qt.KeyboardModifier.NoModifier, ch)
        QTimer.singleShot(random.randint(35, 110) if human else 0, tick)

    tick()