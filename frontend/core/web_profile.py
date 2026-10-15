from PyQt6.QtWebEngineCore import QWebEngineProfile, QWebEngineSettings

from frontend.core.settings_manager import settings

WA = QWebEngineSettings.WebAttribute
FS = QWebEngineSettings.FontSize

_state = {"block_third_party": False}


def _cookie_filter(request) -> bool:
    # True = cookie allow, False = block
    return not (_state["block_third_party"] and request.thirdParty)


def apply_web_settings() -> None:
    profile = QWebEngineProfile.defaultProfile()
    s = profile.settings()
    s.setAttribute(WA.PlaybackRequiresUserGesture, False)
    s.setAttribute(WA.ScrollAnimatorEnabled, bool(settings.get("smooth_scroll")))
    s.setAttribute(WA.JavascriptCanOpenWindows, not settings.get("block_popups"))

    force_dark = getattr(WA, "ForceDarkMode", None)  # purane Qt mein nahi hota
    if force_dark is not None:
        s.setAttribute(force_dark, bool(settings.get("force_dark_web")))

    s.setFontSize(FS.DefaultFontSize, int(settings.get("font_size")))

    _state["block_third_party"] = bool(settings.get("block_third_party_cookies"))
    profile.cookieStore().setCookieFilter(_cookie_filter)

    policy = QWebEngineProfile.PersistentCookiesPolicy
    profile.setPersistentCookiesPolicy(
        policy.NoPersistentCookies
        if settings.get("clear_cookies_on_exit")
        else policy.AllowPersistentCookies
    )


def clear_browsing_data() -> None:
    profile = QWebEngineProfile.defaultProfile()
    profile.clearHttpCache()
    profile.cookieStore().deleteAllCookies()