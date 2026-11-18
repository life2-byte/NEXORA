from datetime import datetime
from typing import Optional

from backend.privacy.policy import block_reason, host_of
from backend.security import secrets
from frontend.core.settings_manager import settings

LOG_FILE = settings.config_dir / "ai_activity.log"
LOG_MAX_BYTES = 400_000


def ai_globally_enabled() -> bool:
    return bool(settings.get("ai_enabled"))


def custom_blocklist() -> list:
    return list(settings.get("ai_blocklist_custom") or [])


def url_block_reason(url: str) -> Optional[str]:
    return block_reason(url, custom_blocklist())


def tool_block_reason(view, url: Optional[str] = None) -> Optional[str]:
    """Agent ka tool is view/url pe chal sakta hai? None = haan, warna wajah."""
    if not ai_globally_enabled():
        return "AI is turned off in Settings"
    if not getattr(view, "ai_enabled", True):
        return "AI is disabled in this window"
    if view.url().scheme() == "nexora":  # browser ke apne security pages: faisla sirf user karega
        return "this is a browser security page. The user must decide."
    return url_block_reason(url if url is not None else view.url().toString())


def remote_key_name() -> str:
    return f"api_key:{settings.get('ai_remote_provider')}"


def readiness() -> Optional[str]:
    """None = AI chalane ke liye setup poora; warna kya baqi hai."""
    if settings.get("ai_provider") == "local":
        if not (settings.get("ai_local_model") or "").strip():
            return "Local model ka naam Settings mein daalo."
        return None
    if settings.get("ai_remote_provider") == "custom":
        if not (settings.get("ai_remote_base_url") or "").strip():
            return "Custom provider ka Base URL Settings mein daalo."
    elif not secrets.has_secret(remote_key_name()):
        return "Remote API key Settings mein save karo."
    if not (settings.get("ai_remote_model") or "").strip():
        return "Remote model ka naam Settings mein daalo."
    return None


# ---------- activity log (sirf metadata, page ka text kabhi nahi) ----------
def audit(tool: str, url: str, chars: int, outcome: str) -> None:
    if not settings.get("ai_log_enabled"):
        return
    host = host_of(url) or "-"
    line = f"{datetime.now():%Y-%m-%d %H:%M:%S} | {tool} | {host} | {chars} chars | {outcome}\n"
    try:
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with LOG_FILE.open("a", encoding="utf-8") as f:
            f.write(line)
        if LOG_FILE.stat().st_size > LOG_MAX_BYTES:
            lines = LOG_FILE.read_text(encoding="utf-8").splitlines()[-1000:]
            LOG_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")
    except OSError:
        pass


def read_log(limit: int = 300) -> str:
    try:
        lines = LOG_FILE.read_text(encoding="utf-8").splitlines()
    except OSError:
        return ""
    return "\n".join(reversed(lines[-limit:]))  # naya upar


def clear_log() -> None:
    try:
        LOG_FILE.unlink()
    except OSError:
        pass