"""Settings + keyring se ProviderConfig banata hai (local ya remote, jo user ne chuna)."""

from urllib.parse import urlsplit

from backend.ai.base import ProviderConfig, ProviderError
from backend.ai.presets import LOCAL_KINDS, REMOTE_PRESETS
from backend.ai.providers import Provider, make_provider
from backend.security import secrets
from frontend.core.settings_manager import settings


def _normalize_url(url: str) -> str:
    url = (url or "").strip().rstrip("/")
    if url and "://" not in url:
        url = "http://" + url
    return url


def _is_local_host(host: str) -> bool:
    return host in ("localhost", "127.0.0.1", "::1") or host.endswith(".local")


def current_config() -> ProviderConfig:
    """Galti par ProviderError('config', ...) jisme user ke liye saaf message hota hai."""
    if settings.get("ai_provider") == "local":
        kind_key = settings.get("ai_local_kind") or "ollama"
        label, kind, default_url = LOCAL_KINDS.get(kind_key, LOCAL_KINDS["ollama"])
        return ProviderConfig(
            kind=kind,
            base_url=_normalize_url(settings.get("ai_local_endpoint")) or default_url,
            model=(settings.get("ai_local_model") or "").strip(),
            api_key="",
            label=label.split(" (")[0],
            timeout=120,  # local model pehli dafa load hote waqt slow hota hai
        )

    key = settings.get("ai_remote_provider") or "anthropic"
    label, kind, preset_url, _hint = REMOTE_PRESETS.get(key, REMOTE_PRESETS["custom"])
    base = _normalize_url(settings.get("ai_remote_base_url")) if key == "custom" else preset_url
    if not base:
        raise ProviderError("config", "Custom provider ke liye Base URL daalo (jese https://api.example.com/v1).")
    parts = urlsplit(base)
    if parts.scheme != "https" and not _is_local_host(parts.hostname or ""):
        raise ProviderError("config", "Remote provider ka URL https:// se shuru hona chahiye (warna key raste mein dikh sakti hai).")
    api_key = secrets.get_secret(f"api_key:{key}") or ""
    if not api_key and key != "custom":
        raise ProviderError("config", "API key save nahi hai. Key paste karo aur 'Save key' dabao.")
    return ProviderConfig(
        kind=kind,
        base_url=base,
        model=(settings.get("ai_remote_model") or "").strip(),
        api_key=api_key,
        label=label.split(" (")[0],
    )


def build_provider() -> Provider:
    return make_provider(current_config())


def model_hint(provider_key: str) -> str:
    return REMOTE_PRESETS.get(provider_key, REMOTE_PRESETS["custom"])[3]