from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from backend.ai.memory_store import MAX_INSTRUCTIONS_CHARS, MAX_NOTE_CHARS, NotesStore
from frontend.core.ai_usage import ai_usage
from frontend.core.settings_manager import settings
from frontend.pages.base_page import BasePage
from frontend.styles.theme import COLORS
from frontend.widgets.card import Card
from frontend.widgets.usage_chart import UsageChart

notes_store = NotesStore(settings.config_dir / "agent_notes.json")


def _label(text: str, name: str = "FieldLabel") -> QLabel:
    label = QLabel(text)
    label.setObjectName(name)
    label.setWordWrap(True)
    return label


def _button(text: str, callback) -> QPushButton:
    btn = QPushButton(text)
    btn.setObjectName("SettingsButton")
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    btn.clicked.connect(lambda _=False: callback())
    return btn


def _combo(key: str, options: list) -> QComboBox:
    combo = QComboBox()
    for label, value in options:
        combo.addItem(label, value)
    combo.setCurrentIndex(max(0, combo.findData(settings.get(key))))
    combo.currentIndexChanged.connect(lambda _: settings.set(key, combo.currentData()))
    return combo


SPIN_STYLE = (
    f"QSpinBox {{ background:{COLORS.get('input', '#0b1220')}; color:{COLORS['text']}; border:1px solid {COLORS.get('border', '#233')};"
    " border-radius:8px; padding:6px 10px; min-height:22px; }"
)


def _fmt(n: int) -> str:
    return f"{n:,}"


class MemoryPage(BasePage):
    def __init__(self, parent=None):
        super().__init__(
            "Memory",
            "Token usage, agent ki pasand aur jo cheezein usay yaad rakhni hain.",
            parent,
        )
        self.add_cards([self._usage_card()], columns=1)
        self.add_cards([self._prefs_card(), self._notes_card()], columns=2)
        self.body.addStretch(1)

        ai_usage.changed.connect(self.refresh_usage)
        self.refresh_usage()
        self.refresh_notes()

    # ================= usage =================
    def _usage_card(self) -> Card:
        card = Card("Token usage")
        self.totals = _label("", "ValueLabel")
        card.add_widget(self.totals)
        self.session_label = _label("", "HintLabel")
        card.add_widget(self.session_label)
        self.limit_label = _label("", "HintLabel")
        card.add_widget(self.limit_label)

        card.add_widget(_label("Pichle 14 din"))
        self.chart = UsageChart()
        card.add_widget(self.chart)

        card.add_widget(_label("Meri apni limit (budget)"))
        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(8)
        self.budget_period = _combo(
            "ai_budget_period", [("Koi limit nahi", "none"), ("Roz ki limit", "day"), ("Mahine ki limit", "month")]
        )
        self.budget_tokens = QSpinBox()
        self.budget_tokens.setRange(1_000, 100_000_000)
        self.budget_tokens.setSingleStep(10_000)
        self.budget_tokens.setStyleSheet(SPIN_STYLE)
        self.budget_tokens.setSuffix(" tokens")
        self.budget_tokens.setGroupSeparatorShown(True)
        self.budget_tokens.setValue(int(settings.get("ai_budget_tokens")))
        self.budget_tokens.editingFinished.connect(lambda: settings.set("ai_budget_tokens", self.budget_tokens.value()))
        row_layout.addWidget(self.budget_period)
        row_layout.addWidget(self.budget_tokens, 1)
        card.add_widget(row)

        self.budget_bar = QProgressBar()
        self.budget_bar.setRange(0, 100)
        self.budget_bar.setTextVisible(False)
        self.budget_bar.setFixedHeight(8)
        card.add_widget(self.budget_bar)
        self.budget_label = _label("", "HintLabel")
        card.add_widget(self.budget_label)

        buttons = QWidget()
        b_layout = QHBoxLayout(buttons)
        b_layout.setContentsMargins(0, 4, 0, 0)
        b_layout.setSpacing(8)
        b_layout.addWidget(_button("Reset session counter", ai_usage.reset))
        b_layout.addWidget(_button("Clear usage history", self._clear_history))
        b_layout.addStretch(1)
        card.add_widget(buttons)
        card.add_widget(
            _label(
                "Provider paise ka balance API se nahi batate, isliye ye graph tumhari apni ginti hai (is browser se "
                "jitni AI calls hui). Provider ki asli limit (jese Groq ke tokens/minute) upar 'Provider limit' mein "
                "dikhti hai. Meri limit poori hone par agent naya kaam shuru nahi karta.",
                "HintLabel",
            )
        )
        return card

    def refresh_usage(self) -> None:
        store = ai_usage.store
        today, month, total = store.today(), store.this_month(), store.all_time()
        self.totals.setText(
            f"Aaj: {_fmt(today['total'])}   |   Is mahine: {_fmt(month['total'])}   |   Sab: {_fmt(total['total'])} tokens"
        )
        started = ai_usage.started.strftime("%H:%M")
        self.session_label.setText(
            f"Is session ({started} se): {ai_usage.calls} calls, {_fmt(ai_usage.prompt_tokens)} in / "
            f"{_fmt(ai_usage.completion_tokens)} out" + (f", model: {ai_usage.label}" if ai_usage.label else "")
        )
        limit = ai_usage.limit_text()
        self.limit_label.setText(f"Provider limit: {limit}" if limit else "Provider limit: abhi pata nahi (provider ne nahi batai ya koi call nahi hui).")
        self.chart.set_data(store.daily(14))

        status = ai_usage.budget_status()
        self.budget_tokens.setEnabled(status is not None or settings.get("ai_budget_period") != "none")
        if status is None:
            self.budget_bar.setValue(0)
            self.budget_label.setText("Koi budget set nahi.")
            return
        pct = int(round(status["fraction_used"] * 100))
        self.budget_bar.setValue(pct)
        color = "#ef4444" if pct >= 100 else "#f59e0b" if pct >= 80 else COLORS["accent"]
        self.budget_bar.setStyleSheet(f"QProgressBar::chunk {{ background:{color}; border-radius:4px; }}")
        where = "aaj" if status["period"] == "day" else "is mahine"
        self.budget_label.setText(
            f"{where.capitalize()}: {_fmt(status['used'])} / {_fmt(status['limit'])} tokens use, "
            f"{_fmt(status['remaining'])} baaki ({100 - pct}%)" + (" - LIMIT POORI" if pct >= 100 else "")
        )

    def _clear_history(self) -> None:
        if QMessageBox.question(self, "Clear usage", "Token history (graph aur totals) hamesha ke liye saaf karun?") == QMessageBox.StandardButton.Yes:
            ai_usage.clear_history()

    # ================= preferences =================
    def _prefs_card(self) -> Card:
        card = Card("Agent ki pasand (har task par lagti hai)")
        card.add_widget(_label("Jawab ki zabaan"))
        card.add_widget(
            _combo(
                "agent_language",
                [("Jis zabaan mein main likhun", "auto"), ("English", "english"), ("Roman Urdu", "roman_urdu"), ("Urdu", "urdu")],
            )
        )
        card.add_widget(_label("Jawab kitna lamba"))
        card.add_widget(_combo("agent_detail", [("Chhota", "short"), ("Normal", "normal"), ("Tafseeli", "detailed")]))
        card.add_widget(_label("Kaam karne se pehle poochna"))
        card.add_widget(
            _combo(
                "agent_confirm",
                [("Sirf risky kaam par (buy, send, delete...)", "risky"), ("Har click/type par", "always")],
            )
        )
        card.add_widget(_label("Model ka sochna (reasoning)"))
        card.add_widget(_combo("ai_thinking", [("Kam (tez, agent ke liye behtar)", "low"), ("Model ka apna default", "auto")]))
        card.add_widget(_label("Typing ki speed"))
        card.add_widget(_combo("agent_typing", [("Insaan jesi (dheere, natural)", "human"), ("Foran", "instant")]))
        card.add_widget(_label("Screenshot (tasveer dekhna)"))
        card.add_widget(_combo("ai_vision", [("Auto (model ke naam se)", "auto"), ("Hamesha on (mera model vision wala hai)", "on"), ("Band", "off")]))
        card.add_widget(_label("Ek task mein zyada se zyada steps"))
        self.max_steps = QSpinBox()
        self.max_steps.setStyleSheet(SPIN_STYLE)
        self.max_steps.setRange(3, 100)
        self.max_steps.setValue(int(settings.get("agent_max_steps")))
        self.max_steps.editingFinished.connect(lambda: settings.set("agent_max_steps", self.max_steps.value()))
        card.add_widget(self.max_steps)

        card.add_widget(_label("Agent ko batao wo kaise behave kare"))
        self.instructions = QPlainTextEdit(str(settings.get("agent_instructions") or ""))
        self.instructions.setObjectName("SettingsText")
        self.instructions.setPlaceholderText("Jese: Hamesha links do. Points mein likho. Mehngi sites se door raho. ...")
        self.instructions.setFixedHeight(110)
        card.add_widget(self.instructions)
        row = QWidget()
        r_layout = QHBoxLayout(row)
        r_layout.setContentsMargins(0, 0, 0, 0)
        r_layout.setSpacing(8)
        self.instr_status = _label("", "HintLabel")
        r_layout.addWidget(_button("Save", self._save_instructions))
        r_layout.addWidget(self.instr_status, 1)
        card.add_widget(row)
        card.add_widget(
            _label(
                f"Ye text (max {MAX_INSTRUCTIONS_CHARS} characters) aur neeche ke notes har task ke saath model ko jate hain "
                "- remote provider ho to un ke server par bhi. Isliye isme password ya private cheezein mat likho.",
                "HintLabel",
            )
        )
        return card

    def _save_instructions(self) -> None:
        text = self.instructions.toPlainText().strip()[:MAX_INSTRUCTIONS_CHARS]
        settings.set("agent_instructions", text)
        self.instructions.setPlainText(text)
        self.instr_status.setText("Save ho gaya.")

    # ================= notes =================
    def _notes_card(self) -> Card:
        card = Card("Jo agent ko yaad rakhna hai")
        holder = QWidget()
        h = QVBoxLayout(holder)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(8)
        h.addWidget(_label("Chhoti chhoti baatein jo har task mein kaam aayen (jese 'meri city Lahore hai')."))
        row = QWidget()
        r_layout = QHBoxLayout(row)
        r_layout.setContentsMargins(0, 0, 0, 0)
        r_layout.setSpacing(8)
        self.note_input = QLineEdit()
        self.note_input.setObjectName("SettingsInput")
        self.note_input.setMaxLength(MAX_NOTE_CHARS)
        self.note_input.setPlaceholderText("Ek baat likho, Enter dabao")
        self.note_input.returnPressed.connect(self._add_note)
        r_layout.addWidget(self.note_input, 1)
        r_layout.addWidget(_button("Add", self._add_note))
        h.addWidget(row)
        self.note_hint = _label("", "HintLabel")
        h.addWidget(self.note_hint)
        self.notes_box = QWidget()
        self.notes_layout = QVBoxLayout(self.notes_box)
        self.notes_layout.setContentsMargins(0, 0, 0, 0)
        self.notes_layout.setSpacing(4)
        h.addWidget(self.notes_box)
        h.addStretch(1)
        card.add_widget(holder)
        return card

    def _add_note(self) -> None:
        error = notes_store.add(self.note_input.text())
        self.note_hint.setText(error)
        if not error:
            self.note_input.clear()
            self.refresh_notes()

    def refresh_notes(self) -> None:
        while self.notes_layout.count():
            item = self.notes_layout.takeAt(0)
            if item.widget() is not None:
                w = item.widget()
                w.setParent(None)
                w.deleteLater()
        notes = notes_store.list()
        if not notes:
            self.notes_layout.addWidget(_label("Abhi koi note nahi.", "HintLabel"))
        for note in notes:
            row = QWidget()
            layout = QHBoxLayout(row)
            layout.setContentsMargins(0, 0, 0, 0)
            text = QLabel(note["text"])
            text.setWordWrap(True)
            text.setStyleSheet(f"color:{COLORS['text']}; background:transparent;")
            delete = QToolButton()
            delete.setText("✕")
            delete.setToolTip("Hata do")
            delete.setCursor(Qt.CursorShape.PointingHandCursor)
            delete.clicked.connect(lambda _=False, nid=note["id"]: self._delete_note(nid))
            layout.addWidget(text, 1)
            layout.addWidget(delete)
            self.notes_layout.addWidget(row)

    def _delete_note(self, note_id: str) -> None:
        notes_store.delete(note_id)
        self.refresh_notes()