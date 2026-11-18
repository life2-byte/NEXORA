import shutil
import sqlite3
import tempfile
from pathlib import Path
from typing import Optional

from PyQt6.QtCore import QDateTime, QObject, QTimer, QUrl, pyqtSignal
from PyQt6.QtNetwork import QNetworkCookie

from frontend.core.profile import get_profile
from frontend.core.settings_manager import settings


def _key(c: QNetworkCookie) -> tuple:
    return (c.domain(), c.path(), bytes(c.name()).decode("utf-8", "replace"))


_WEBKIT_EPOCH_OFFSET = 11644473600  # Chromium time 1601 se shuru hota hai, Unix 1970 se


def read_disk_cookies(db_path: Path) -> list[QNetworkCookie]:
    """Chromium ki 'Cookies' sqlite file se cookies ka naam, domain, path, expiry aur flags padhta hai.
    Value encrypted hoti hai isliye khali rehti hai. File ko copy karke padhta hai taake lock ka masla na ho."""
    if not db_path.exists():
        return []
    result: list[QNetworkCookie] = []
    with tempfile.TemporaryDirectory() as tmp:
        copy = Path(tmp) / "Cookies"
        try:
            shutil.copy2(db_path, copy)
            journal = db_path.with_name(db_path.name + "-journal")
            if journal.exists():
                shutil.copy2(journal, Path(tmp) / "Cookies-journal")
            con = sqlite3.connect(f"file:{copy}?mode=ro", uri=True)
            rows = con.execute(
                "SELECT host_key, name, path, expires_utc, is_secure, is_httponly, has_expires FROM cookies"
            ).fetchall()
            con.close()
        except (OSError, sqlite3.Error):
            return []
    for host, name, path, expires_utc, secure, http_only, has_expires in rows:
        cookie = QNetworkCookie(str(name).encode("utf-8"), b"")
        cookie.setDomain(host)
        cookie.setPath(path or "/")
        cookie.setSecure(bool(secure))
        cookie.setHttpOnly(bool(http_only))
        if has_expires and expires_utc:
            unix = expires_utc // 1_000_000 - _WEBKIT_EPOCH_OFFSET
            if unix > 0:
                cookie.setExpirationDate(QDateTime.fromSecsSinceEpoch(unix))
        result.append(cookie)
    return result


class CookieManager(QObject):
    """Profile ke cookie store ko mirror karta hai. UI sirf is se baat kare."""

    changed = pyqtSignal()

    def __init__(self):
        super().__init__()
        self._cookies: dict[tuple, QNetworkCookie] = {}
        self._disk_only: set[tuple] = set()  # disk se aayi cookies jin ki value hamare paas nahi
        self._store = get_profile().cookieStore()

        # startup pe hazaron signals aate hain, isliye refresh ko debounce karte hain
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(150)
        self._timer.timeout.connect(self.changed.emit)

        self._store.cookieAdded.connect(self._on_added)
        self._store.cookieRemoved.connect(self._on_removed)
        self._store.loadAllCookies()
        QTimer.singleShot(1500, self._store.loadAllCookies)
        self._load_disk()  # Qt purani cookies nahi bhejta, isliye file se bhi padhte hain

    def _load_disk(self) -> None:
        for cookie in read_disk_cookies(settings.config_dir / "profile" / "Cookies"):
            key = _key(cookie)
            if key not in self._cookies:  # live cookie (asli value ke saath) ko na badlo
                self._cookies[key] = cookie
                self._disk_only.add(key)
        self._timer.start()

    def is_disk_only(self, cookie: QNetworkCookie) -> bool:
        return _key(cookie) in self._disk_only

    def reload(self) -> None:
        self._store.loadAllCookies()

    # ---------- store signals ----------
    def _on_added(self, cookie: QNetworkCookie) -> None:
        key = _key(cookie)
        self._cookies[key] = QNetworkCookie(cookie)
        self._disk_only.discard(key)
        self._timer.start()

    def _on_removed(self, cookie: QNetworkCookie) -> None:
        self._cookies.pop(_key(cookie), None)
        self._disk_only.discard(_key(cookie))
        self._timer.start()

    # ---------- read ----------
    def count(self) -> int:
        return len(self._cookies)

    def grouped(self, query: str = "") -> dict[str, list[QNetworkCookie]]:
        """{domain: [cookies]} sorted. Query domain ya cookie ke naam pe match karti hai."""
        q = query.strip().lower()
        groups: dict[str, list[QNetworkCookie]] = {}
        for cookie in self._cookies.values():
            domain = cookie.domain().lstrip(".")
            name = bytes(cookie.name()).decode("utf-8", "replace")
            if q and q not in domain.lower() and q not in name.lower():
                continue
            groups.setdefault(domain, []).append(cookie)
        for items in groups.values():
            items.sort(key=lambda c: bytes(c.name()))
        return dict(sorted(groups.items()))

    # ---------- write ----------
    @staticmethod
    def _origin(cookie: QNetworkCookie) -> QUrl:
        scheme = "https" if cookie.isSecure() else "http"
        return QUrl(f"{scheme}://{cookie.domain().lstrip('.')}{cookie.path() or '/'}")

    def delete(self, cookie: QNetworkCookie) -> None:
        self._store.deleteCookie(cookie, self._origin(cookie))
        self._cookies.pop(_key(cookie), None)  # signal ka intezar nahi, UI turant update
        self._disk_only.discard(_key(cookie))
        self._timer.start()

    def delete_domain(self, domain: str) -> None:
        for cookie in list(self.grouped().get(domain, [])):
            self.delete(cookie)

    def delete_all(self) -> None:
        self._store.deleteAllCookies()
        self._cookies.clear()
        self._disk_only.clear()
        self._timer.start()

    def save(
        self,
        domain: str,
        name: str,
        value: str,
        path: str = "/",
        expires: Optional[QDateTime] = None,
        secure: bool = False,
        http_only: bool = False,
    ) -> Optional[str]:
        """Naya cookie banata hai ya usi (domain, path, name) wale ko badalta hai. None = ok, warna error text."""
        domain, name, path = domain.strip(), name.strip(), (path.strip() or "/")
        if not domain or not name:
            return "Domain aur name zaroori hain."
        cookie = QNetworkCookie(name.encode(), value.encode())
        cookie.setDomain(domain)
        cookie.setPath(path)
        cookie.setSecure(secure)
        cookie.setHttpOnly(http_only)
        if expires is not None:
            cookie.setExpirationDate(expires)
        self._store.setCookie(cookie, self._origin(cookie))
        return None


_manager: Optional[CookieManager] = None


def get_cookie_manager() -> CookieManager:
    """QApplication banne ke baad pehli dafa call karo (MainWindow ke pages se pehle)."""
    global _manager
    if _manager is None:
        _manager = CookieManager()
    return _manager