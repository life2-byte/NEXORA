from typing import Iterable, Optional
from urllib.parse import urlparse

DEFAULT_BLOCK_DOMAINS = (
    # accounts / sign-in
    "accounts.google.com", "myaccount.google.com", "login.live.com",
    "login.microsoftonline.com", "account.microsoft.com", "appleid.apple.com",
    "id.apple.com",
    # email
    "mail.google.com", "outlook.live.com", "outlook.office.com",
    "outlook.office365.com", "mail.yahoo.com", "proton.me", "protonmail.com",
    "tutanota.com", "fastmail.com",
    # payments / wallets
    "paypal.com", "pay.google.com", "wise.com", "payoneer.com",
    "dashboard.stripe.com", "easypaisa.com.pk", "jazzcash.com.pk",
    # password managers
    "bitwarden.com", "1password.com", "lastpass.com", "dashlane.com",
    "keepersecurity.com",
    # private messaging
    "web.whatsapp.com", "web.telegram.org", "messenger.com",
)
BLOCK_HOST_KEYWORDS = ("bank", "banking", "paypal", "wallet")
BLOCK_HOST_PREFIXES = ("mail.", "webmail.", "email.")
BLOCK_PATH_KEYWORDS = (
    "login", "signin", "sign-in", "log-in", "password", "checkout", "payment", "billing",
)

REASON_SITE = (
    "this site is on the AI privacy blocklist (accounts, email, banking, payments or private "
    "messages). The user must handle it themselves."
)
REASON_LOGIN = "this looks like a login or payment page. The user must complete it themselves."
REASON_CUSTOM = "this site is on the user's own AI blocklist."


def host_of(text: str) -> str:
    t = (text or "").strip()
    if not t or " " in t:
        return ""
    if "://" not in t:
        t = "https://" + t
    try:
        return (urlparse(t).hostname or "").lower()
    except ValueError:
        return ""


def _path_of(text: str) -> str:
    t = (text or "").strip()
    if not t or " " in t:
        return ""
    if "://" not in t:
        t = "https://" + t
    try:
        return urlparse(t).path.lower()
    except ValueError:
        return ""


def normalize_entry(text: str) -> str:
    """User ki likhi hui entry se saaf domain (www. hata ke)."""
    host = host_of(text)
    return host[4:] if host.startswith("www.") else host


def _matches(host: str, domain: str) -> bool:
    return host == domain or host.endswith("." + domain)


def block_reason(text: str, custom: Iterable[str] = ()) -> Optional[str]:
    """None = AI dekh sakta hai; warna wajah (agent ko dikhane layak text)."""
    host = host_of(text)
    if not host:
        return None

    for entry in custom:
        domain = normalize_entry(entry)
        if domain and _matches(host, domain):
            return REASON_CUSTOM

    if any(_matches(host, d) for d in DEFAULT_BLOCK_DOMAINS):
        return REASON_SITE
    if any(k in host for k in BLOCK_HOST_KEYWORDS) or host.startswith(BLOCK_HOST_PREFIXES):
        return REASON_SITE

    path = _path_of(text)
    if any(k in path for k in BLOCK_PATH_KEYWORDS):
        return REASON_LOGIN
    return None