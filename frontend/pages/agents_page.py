from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from backend.ai.agents import ALL_TOOLS, MAX_CUSTOM, AgentStore
from frontend.core.settings_manager import settings
from frontend.pages.base_page import BasePage
from frontend.styles.theme import COLORS
from frontend.widgets.card import Card

agent_store = AgentStore(settings.config_dir / "agents.json")

TOOL_TEXT = {
    "list_tabs": "Tabs dekhna",
    "new_tab": "Naya tab kholna",
    "switch_tab": "Tab badalna",
    "close_tab": "Tab band karna",
    "read_page": "Page padhna",
    "find": "Page mein dhoondna",
    "click": "Click karna",
    "type_text": "Type karna",
    "scroll": "Scroll karna",
    "press_keys": "Keyboard keys dabana",
    "wait": "Intezar karna",
    "page_api": "Site ka data (JSON) seedha parhna",
    "screenshot": "Page ki tasveer dekhna (vision model)",
    "click_at": "Tasveer par jagah click karna",
    "nav": "Back / Forward / Reload",
    "go": "URL par jana",
}
RISKY = {"click", "type_text", "go", "new_tab", "press_keys", "click_at"}


def _btn(text, cb):
    b = QPushButton(text)
    b.setObjectName("SettingsButton")
    b.setCursor(Qt.CursorShape.PointingHandCursor)
    b.clicked.connect(lambda _=False: cb())
    return b


class AgentEditor(QDialog):
    def __init__(self, agent: dict, readonly: bool, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Agent dekho" if readonly else "Agent")
        self.setMinimumWidth(480)
        self.agent = dict(agent)
        form = QFormLayout()
        self.name = QLineEdit(agent.get("name", ""))
        self.name.setMaxLength(40)
        self.desc = QLineEdit(agent.get("description", ""))
        self.desc.setMaxLength(200)
        self.model = QLineEdit(agent.get("model", ""))
        self.model.setPlaceholderText("Khali = settings wala model")
        self.instr = QPlainTextEdit(agent.get("instructions", ""))
        self.instr.setFixedHeight(120)
        for w in (self.name, self.desc, self.model):
            w.setObjectName("SettingsInput")
        form.addRow("Naam", self.name)
        form.addRow("Kya karta hai", self.desc)
        form.addRow("Model (optional)", self.model)
        form.addRow("Hidayat (English behtar)", self.instr)
        self.checks = {}
        tools = QVBoxLayout()
        for t in ALL_TOOLS:
            c = QCheckBox(TOOL_TEXT.get(t, t) + ("  (asar karta hai)" if t in RISKY else ""))
            c.setChecked(t in agent.get("tools", []))
            self.checks[t] = c
            tools.addWidget(c)
        form.addRow("Allowed kaam", tools)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close if readonly else
                                   QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)
        if readonly:
            for w in (self.name, self.desc, self.model):
                w.setReadOnly(True)
            self.instr.setReadOnly(True)
            for c in self.checks.values():
                c.setEnabled(False)

    def result_agent(self) -> dict:
        a = dict(self.agent)
        a.update(
            name=self.name.text().strip(),
            description=self.desc.text().strip(),
            model=self.model.text().strip(),
            instructions=self.instr.toPlainText().strip(),
            tools=[t for t, c in self.checks.items() if c.isChecked()],
        )
        return a


class AgentsPage(BasePage):
    def __init__(self, parent=None):
        super().__init__("Agents", "Agent = ek tayyar role: kya kar sakta hai aur kaise kaam karta hai.", parent)
        self.card = Card("Tumhare agents")
        self.holder = QWidget()
        self.rows = QVBoxLayout(self.holder)
        self.rows.setContentsMargins(0, 0, 0, 0)
        self.rows.setSpacing(10)
        self.card.add_widget(self.holder)
        self.card.add_widget(_btn("+ Naya agent", self._new))
        hint = QLabel(
            "Naye task mein jo agent 'default' hai wo chalega. Tools kam rakho to agent mehfooz rehta hai - "
            "Reader kuch click nahi kar sakta. Risky kaam (khareedna, bhejna, delete) par Memory page ki setting ke mutabiq poochta hai."
        )
        hint.setObjectName("HintLabel")
        hint.setWordWrap(True)
        self.card.add_widget(hint)
        self.add_cards([self.card], columns=1)
        self.body.addStretch(1)
        self.refresh()

    def refresh(self) -> None:
        while self.rows.count():
            item = self.rows.takeAt(0)
            if item.widget() is not None:
                w = item.widget()
                w.setParent(None)
                w.deleteLater()
        default = settings.get("default_agent")
        agents = agent_store.all()
        if not any(a["id"] == default for a in agents):
            default = "browser"
        for a in agents:
            self.rows.addWidget(self._row(a, a["id"] == default))

    def _row(self, a: dict, is_default: bool) -> QWidget:
        box = QWidget()
        box.setStyleSheet(f"QWidget#AgentRow {{ border:1px solid {COLORS.get('border', '#233')}; border-radius:10px; }}")
        box.setObjectName("AgentRow")
        v = QVBoxLayout(box)
        v.setContentsMargins(12, 10, 12, 10)
        title = QLabel(f"<b>{a['name']}</b>" + ("  - default" if is_default else "") + ("  (built-in)" if a["builtin"] else ""))
        title.setStyleSheet("background:transparent;")
        desc = QLabel(a["description"])
        desc.setWordWrap(True)
        desc.setObjectName("HintLabel")
        tools = QLabel("Kaam: " + (", ".join(TOOL_TEXT.get(t, t) for t in a["tools"]) or "koi nahi"))
        tools.setWordWrap(True)
        tools.setObjectName("HintLabel")
        v.addWidget(title)
        v.addWidget(desc)
        v.addWidget(tools)
        row = QHBoxLayout()
        if not is_default:
            row.addWidget(_btn("Default banao", lambda a=a: self._set_default(a["id"])))
        row.addWidget(_btn("Dekho" if a["builtin"] else "Edit", lambda a=a: self._edit(a)))
        row.addWidget(_btn("Copy", lambda a=a: self._copy(a)))
        if not a["builtin"]:
            row.addWidget(_btn("Delete", lambda a=a: self._delete(a)))
        row.addStretch(1)
        v.addLayout(row)
        return box

    def _set_default(self, agent_id: str) -> None:
        settings.set("default_agent", agent_id)
        self.refresh()

    def _save(self, agent: dict) -> bool:
        _id, error = agent_store.save(agent)
        if error:
            QMessageBox.warning(self, "Agent", error)
            return False
        return True

    def _new(self) -> None:
        if len([a for a in agent_store.all() if not a["builtin"]]) >= MAX_CUSTOM:
            QMessageBox.information(self, "Agent", f"Zyada se zyada {MAX_CUSTOM} apne agents.")
            return
        dlg = AgentEditor({"name": "", "description": "", "instructions": "", "tools": ["list_tabs", "read_page", "find", "scroll"], "model": ""}, False, self)
        while dlg.exec() == QDialog.DialogCode.Accepted:
            if self._save(dlg.result_agent()):
                break
        self.refresh()

    def _edit(self, a: dict) -> None:
        dlg = AgentEditor(a, a["builtin"], self)
        while dlg.exec() == QDialog.DialogCode.Accepted and not a["builtin"]:
            if self._save(dlg.result_agent()):
                break
        self.refresh()

    def _copy(self, a: dict) -> None:
        c = dict(a, name=(a["name"] + " copy")[:40], builtin=False)
        c.pop("id", None)
        self._save(c)
        self.refresh()

    def _delete(self, a: dict) -> None:
        if QMessageBox.question(self, "Agent", f"'{a['name']}' delete karun?") == QMessageBox.StandardButton.Yes:
            agent_store.delete(a["id"])
            if settings.get("default_agent") == a["id"]:
                settings.set("default_agent", "browser")
            self.refresh()