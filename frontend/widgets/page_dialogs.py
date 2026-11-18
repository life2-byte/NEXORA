"""Site se aane wale sawalon ki Qt windows (page ke andar nahi, isliye agent unhe click nahi kar sakta)."""

from html import escape
from typing import Optional

from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QVBoxLayout,
)


def ask_certificate(parent, host: str, description: str) -> bool:
    """True = user ne 'Proceed anyway' chuna."""
    box = QMessageBox(parent)
    box.setIcon(QMessageBox.Icon.Warning)
    box.setWindowTitle("Your connection is not private")
    box.setText(f"<b>{escape(host)}</b> ka security certificate theek nahi hai.")
    box.setInformativeText(
        f"{description}\n\n"
        "Aage jaoge to koi aur tumhara data (password, card) dekh ya badal sakta hai. "
        "Is site pe kuch private mat daalna."
    )
    back = box.addButton("Go back (safe)", QMessageBox.ButtonRole.AcceptRole)
    proceed = box.addButton("Proceed anyway (unsafe)", QMessageBox.ButtonRole.DestructiveRole)
    box.setDefaultButton(back)
    box.exec()
    return box.clickedButton() is proceed


def ask_credentials(parent, host: str, realm: str) -> Optional[tuple[str, str]]:
    """(username, password) ya None agar user ne cancel kiya."""
    dialog = QDialog(parent)
    dialog.setWindowTitle("Sign in")
    dialog.setMinimumWidth(380)

    title = QLabel(f"<b>{escape(host)}</b> ko username aur password chahiye.")
    title.setWordWrap(True)
    hint = QLabel(escape(realm)) if realm else None

    user = QLineEdit()
    password = QLineEdit()
    password.setEchoMode(QLineEdit.EchoMode.Password)

    form = QFormLayout()
    form.addRow("Username", user)
    form.addRow("Password", password)

    buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
    buttons.accepted.connect(dialog.accept)
    buttons.rejected.connect(dialog.reject)

    layout = QVBoxLayout(dialog)
    layout.addWidget(title)
    if hint is not None:
        layout.addWidget(hint)
    layout.addLayout(form)
    layout.addWidget(buttons)
    user.setFocus()

    if dialog.exec() != QDialog.DialogCode.Accepted:
        return None
    return user.text(), password.text()