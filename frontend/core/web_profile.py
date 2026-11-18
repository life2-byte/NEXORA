import os
import sys
from pathlib import Path

from PyQt6.QtWebEngineCore import (
    QWebEngineProfile,
    QWebEngineScript,
    QWebEngineSettings,
    qWebEngineChromiumVersion,
)

from frontend.core.profile import get_profile
from frontend.core.settings_manager import settings

WA = QWebEngineSettings.WebAttribute
FS = QWebEngineSettings.FontSize

DICTIONARIES = Path(__file__).resolve().parents[1] / "assets" / "dictionaries"
PAGE_TOOLS = Path(__file__).parent / "bridge_scripts" / "page_tools.js"
_PAGE_TOOLS_JS = PAGE_TOOLS.read_text(encoding="utf-8")

_state = {"block_third_party": False}


def _cookie_filter(request) -> bool:
    # True = cookie allow, False = block
    return not (_state["block_third_party"] and request.thirdParty)


def make_page_tools_script() -> QWebEngineScript:
    """Agent ke tools wali script. Sirf AI-enabled tabs ke page mein daali jati hai."""
    script = QWebEngineScript()
    script.setName("agent-page-tools")
    script.setSourceCode(_PAGE_TOOLS_JS)
    script.setInjectionPoint(QWebEngineScript.InjectionPoint.DocumentReady)
    script.setWorldId(QWebEngineScript.ScriptWorldId.ApplicationWorld.value)
    script.setRunsOnSubFrames(False)
    return script


def apply_web_settings() -> None:
    profile = get_profile()
    # profile.setHttpUserAgent(_compatible_user_agent())

    s = profile.settings()
    s.setAttribute(WA.PlaybackRequiresUserGesture, False)
    s.setAttribute(WA.ScrollAnimatorEnabled, bool(settings.get("smooth_scroll")))
    s.setAttribute(WA.JavascriptCanOpenWindows, not settings.get("block_popups"))

    force_dark = getattr(WA, "ForceDarkMode", None)  # purane Qt mein nahi hota
    if force_dark is not None:
        s.setAttribute(force_dark, bool(settings.get("force_dark_web")))

    s.setFontSize(FS.DefaultFontSize, int(settings.get("font_size")))

    # cache limit (0 = automatic)
    profile.setHttpCacheMaximumSize(int(settings.get("cache_limit_mb") or 0) * 1024 * 1024)
    languages = sorted(p.stem for p in DICTIONARIES.glob("*.bdic"))
    if languages and settings.get("spellcheck"):
        profile.setSpellCheckLanguages(languages)
        profile.setSpellCheckEnabled(True)
    else:
        profile.setSpellCheckEnabled(False)
    _state["block_third_party"] = bool(settings.get("block_third_party_cookies"))
    profile.cookieStore().setCookieFilter(_cookie_filter)

    policy = QWebEngineProfile.PersistentCookiesPolicy
    profile.setPersistentCookiesPolicy(
        policy.NoPersistentCookies
        if settings.get("clear_cookies_on_exit")
        else policy.AllowPersistentCookies
    )


def clear_cache() -> None:
    get_profile().clearHttpCache()


def clear_cookies() -> None:
    get_profile().cookieStore().deleteAllCookies()


def clear_browsing_data() -> None:
    clear_cache()
    clear_cookies()


def cache_size_bytes() -> int:
    total = 0
    for folder, _dirs, files in os.walk(settings.config_dir / "cache"):
        for name in files:
            try:
                total += os.path.getsize(os.path.join(folder, name))
            except OSError:
                pass
    return total


def cache_size_text() -> str:
    mb = cache_size_bytes() / (1024 * 1024)
    return "under 1 MB" if mb < 1 else f"{mb:.0f} MB"