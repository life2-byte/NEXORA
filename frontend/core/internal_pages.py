"""Nexora ke apne pages (nexora://...): security warning page. Website in pages ko nahi khol sakti
(BrowserPage sirf tab action leta hai jab current page khud nexora:// ho)."""

from html import escape
from urllib.parse import parse_qs, quote, urlencode, urlparse

from PyQt6.QtCore import QBuffer, QByteArray, QIODevice
from PyQt6.QtWebEngineCore import QWebEngineUrlRequestJob, QWebEngineUrlScheme, QWebEngineUrlSchemeHandler

from frontend.core.profile import get_profile

SCHEME = "nexora"


def register_scheme() -> None:
    """QApplication banne se PEHLE hona zaroori hai (is module ke import par ho jata hai)."""
    scheme = QWebEngineUrlScheme(QByteArray(SCHEME.encode()))
    scheme.setSyntax(QWebEngineUrlScheme.Syntax.Host)
    scheme.setFlags(QWebEngineUrlScheme.Flag.SecureScheme | QWebEngineUrlScheme.Flag.LocalAccessAllowed)
    QWebEngineUrlScheme.registerScheme(scheme)


register_scheme()


def warning_url(kind: str, url: str, detail: str = "") -> str:
    query = urlencode({"kind": kind, "url": url, "detail": detail}, quote_via=quote)
    return f"{SCHEME}://warning/?{query}"


def action_url(action: str, kind: str = "", url: str = "") -> str:
    query = urlencode({"kind": kind, "url": url}, quote_via=quote)
    return f"{SCHEME}://{action}/?{query}"


_CSS = """
body{margin:0;min-height:100vh;display:flex;align-items:center;justify-content:center;
background:#0b1220;color:#e6eaf2;font-family:'Segoe UI','Inter','Ubuntu',sans-serif}
.card{max-width:560px;margin:24px;padding:34px 38px;background:#111a2b;border:1px solid #1f2d45;border-radius:16px}
.icon{font-size:44px;line-height:1}
h1{font-size:24px;margin:14px 0 10px}
p{color:#aab4c8;line-height:1.55;margin:8px 0}
.host{color:#e6eaf2;font-weight:600;word-break:break-all}
.detail{margin-top:14px;padding:10px 12px;background:#0b1220;border-radius:8px;color:#7f8ba3;font-size:13px}
.row{display:flex;gap:12px;margin-top:26px;flex-wrap:wrap}
a.btn{display:inline-block;text-decoration:none;padding:10px 20px;border-radius:10px;font-weight:600}
a.safe{background:#38bdf8;color:#0b1220}
a.risk{background:transparent;color:#f87171;border:1px solid #5b2a30}
a.risk:hover{background:#2a1418}
"""

_TEXT = {
    "http": (
        "&#9888;",
        "This site isn't secure",
        "doesn't support a secure (HTTPS) connection. Anything you type here, like passwords or card "
        "numbers, can be read by others on the network.",
        "Continue to site (not secure)",
    ),
    "cert": (
        "&#128274;",
        "Your connection isn't private",
        "has a security certificate that can't be trusted. Someone might be trying to read or change "
        "your data. Don't enter passwords or card details here.",
        "Proceed anyway (unsafe)",
    ),
    "cert-fatal": (
        "&#128683;",
        "This connection can't be trusted",
        "has a security certificate problem that can't be bypassed.",
        "",
    ),
}


def warning_html(kind: str, url: str, detail: str) -> str:
    icon, title, text, proceed_label = _TEXT.get(kind, _TEXT["cert-fatal"])
    host = urlparse(url).hostname or url
    proceed = ""
    if proceed_label:
        proceed = f'<a class="btn risk" href="{escape(action_url("proceed", kind, url))}">{proceed_label}</a>'
    detail_html = f'<div class="detail">{escape(detail)}</div>' if detail else ""
    return (
        f'<!doctype html><html><head><meta charset="utf-8"><title>{escape(title)}</title>'
        f"<style>{_CSS}</style></head><body><div class='card'>"
        f"<div class='icon'>{icon}</div><h1>{escape(title)}</h1>"
        f"<p><span class='host'>{escape(host)}</span> {text}</p>{detail_html}"
        f'<div class="row"><a class="btn safe" href="{escape(action_url("back"))}">Go back</a>{proceed}</div>'
        "</div></body></html>"
    )


class InternalPageHandler(QWebEngineUrlSchemeHandler):
    def requestStarted(self, job: QWebEngineUrlRequestJob) -> None:
        url = job.requestUrl()
        if url.host() != "warning":
            job.fail(QWebEngineUrlRequestJob.Error.UrlNotFound)
            return
        q = parse_qs(url.query(url.ComponentFormattingOption.FullyEncoded))
        get = lambda k: (q.get(k) or [""])[0]
        html = warning_html(get("kind"), get("url"), get("detail"))
        buffer = QBuffer(job)  # job ke saath khatam hoga
        buffer.setData(QByteArray(html.encode("utf-8")))
        buffer.open(QIODevice.OpenModeFlag.ReadOnly)
        job.reply(QByteArray(b"text/html"), buffer)


_handler = None


def install() -> None:
    """QApplication aur profile banne ke baad ek dafa call karo."""
    global _handler
    _handler = InternalPageHandler()
    get_profile().installUrlSchemeHandler(QByteArray(SCHEME.encode()), _handler)