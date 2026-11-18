"""Agent ke 'notes' (jo cheezein usay yaad rakhni hain) aur unse prompt ka hissa. Qt ka koi code nahi."""

import json
import os
import time
import uuid
from pathlib import Path

MAX_NOTES = 30
MAX_NOTE_CHARS = 200
MAX_INSTRUCTIONS_CHARS = 2000

LANGUAGES = {
    "auto": "Reply in the language the user writes in.",
    "english": "Always reply in English.",
    "roman_urdu": "Always reply in Roman Urdu (Urdu written in English letters).",
    "urdu": "Always reply in Urdu script.",
}
DETAIL = {
    "short": "Keep answers very short: a few sentences or a tight bullet list.",
    "normal": "Give clear answers of moderate length.",
    "detailed": "Give thorough, detailed answers with the reasoning and sources.",
}
CONFIRM = {
    "risky": "Ask the user before risky actions (submitting forms, buying, paying, deleting, sending, posting). Do other steps without asking.",
    "always": "Ask the user before every action that changes something on a page (click, type, submit). Reading and scrolling need no approval.",
}


class NotesStore:
    def __init__(self, path):
        self._path = Path(path)

    def _read(self) -> list:
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
            return [n for n in data if isinstance(n, dict) and n.get("text")]
        except (OSError, ValueError):
            return []

    def _write(self, notes: list) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._path.with_suffix(".tmp")
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(notes, f, ensure_ascii=False)
        os.replace(tmp, self._path)

    def list(self) -> list:
        return self._read()

    def add(self, text: str) -> str:
        """'' = add ho gaya, warna wajah."""
        text = " ".join(text.split())[:MAX_NOTE_CHARS]
        if not text:
            return "Khali note add nahi hota."
        notes = self._read()
        if len(notes) >= MAX_NOTES:
            return f"Zyada se zyada {MAX_NOTES} notes rakh sakte ho. Purane hata do."
        if any(n["text"].lower() == text.lower() for n in notes):
            return "Ye note pehle se maujood hai."
        notes.append({"id": uuid.uuid4().hex[:8], "text": text, "created": int(time.time())})
        self._write(notes)
        return ""

    def delete(self, note_id: str) -> None:
        self._write([n for n in self._read() if n["id"] != note_id])

    def clear(self) -> None:
        self._write([])


def memory_block(prefs: dict, notes: list) -> str:
    """System prompt mein lagne wala hissa. prefs: language, detail, confirm, instructions."""
    lines = ["USER PREFERENCES (set by the user in Settings; follow them):"]
    lines.append("- " + LANGUAGES.get(prefs.get("language"), LANGUAGES["auto"]))
    lines.append("- " + DETAIL.get(prefs.get("detail"), DETAIL["normal"]))
    lines.append("- " + CONFIRM.get(prefs.get("confirm"), CONFIRM["risky"]))
    instructions = (prefs.get("instructions") or "").strip()[:MAX_INSTRUCTIONS_CHARS]
    if instructions:
        lines.append("- Extra instructions from the user:\n" + "\n".join("  " + ln for ln in instructions.splitlines()))
    texts = [n["text"] if isinstance(n, dict) else str(n) for n in notes]
    if texts:
        lines.append("THINGS THE USER ASKED YOU TO REMEMBER:")
        lines.extend(f"- {t}" for t in texts)
    return "\n".join(lines)