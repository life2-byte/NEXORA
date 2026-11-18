"""API keys ko OS keyring mein rakhta hai (settings file mein kabhi nahi). Qt ka koi code nahi."""

from typing import Optional

try:
    import keyring
except ImportError:  # pip install keyring
    keyring = None

SERVICE = "nexora-browser"


def available() -> bool:
    if keyring is None:
        return False
    try:
        return "backends.fail" not in type(keyring.get_keyring()).__module__
    except Exception:
        return False


def set_secret(name: str, value: str) -> Optional[str]:
    """None = save ho gayi; warna error message."""
    if not available():
        return "System keyring nahi mila (pip install keyring, aur GNOME Keyring chalna chahiye)."
    try:
        keyring.set_password(SERVICE, name, value)
        return None
    except Exception as e:
        return f"Key save nahi hui: {e}"


def get_secret(name: str) -> Optional[str]:
    if not available():
        return None
    try:
        return keyring.get_password(SERVICE, name)
    except Exception:
        return None


def has_secret(name: str) -> bool:
    return bool(get_secret(name))


def delete_secret(name: str) -> None:
    if not available():
        return
    try:
        keyring.delete_password(SERVICE, name)
    except Exception:
        pass