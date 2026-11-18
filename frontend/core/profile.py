from PyQt6 import sip
from PyQt6.QtWebEngineCore import QWebEngineProfile

from frontend.core.settings_manager import settings

PROFILE_NAME = "nexora" if settings.profile_id == "default" else f"nexora-{settings.profile_id}"

_profile = None


def get_profile() -> QWebEngineProfile:
    """Poori app ka ek permanent profile (cookies, logins, cache restart ke baad bhi rehte hain).
    Pages banane se pehle (QApplication ke baad) pehli baar call hota hai."""
    global _profile
    if _profile is None:
        profile = QWebEngineProfile(PROFILE_NAME)  # naam dene se persistent banta hai
        profile.setPersistentStoragePath(str(settings.config_dir / "profile"))
        profile.setCachePath(str(settings.config_dir / "cache"))
        profile.setHttpAcceptLanguage("en-US,en;q=0.9")
        if hasattr(profile, "setPersistentPermissionsPolicy"):  # Qt 6.8+
            policy = QWebEngineProfile.PersistentPermissionsPolicy.StoreOnDisk
            profile.setPersistentPermissionsPolicy(policy)
        _profile = profile
    return _profile


def dispose_profile() -> None:
    """Band hote waqt, saare pages delete hone ke BAAD profile delete karo."""
    global _profile
    if _profile is not None and not sip.isdeleted(_profile):
        sip.delete(_profile)
    _profile = None