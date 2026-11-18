"""AI providers ke common types, errors aur HTTP helper. Qt ka koi code nahi.

Messages ka neutral format (har provider ke liye converters providers.py mein):
    {"role": "system" | "user", "content": str}
    {"role": "assistant", "content": str, "tool_calls": [{"id", "name", "arguments": dict}]}
    {"role": "tool", "tool_call_id": str, "name": str, "content": str}
"""

import json
import socket
import ssl
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Optional

DEFAULT_TIMEOUT = 60


# ---------- config / results ----------
@dataclass
class ProviderConfig:
    kind: str                 # "openai" | "ollama" | "anthropic"
    base_url: str
    model: str = ""
    api_key: str = ""
    label: str = ""           # user ko dikhane ka naam (jese "Groq")
    timeout: int = DEFAULT_TIMEOUT
    reasoning: str = ""        # '' ya 'low' (sirf agent ke liye; Test connection par nahi)


@dataclass
class Usage:
    prompt_tokens: int = 0
    completion_tokens: int = 0

    @property
    def total(self) -> int:
        return self.prompt_tokens + self.completion_tokens


@dataclass
class RateLimits:
    """Provider ke response headers se. None = provider ne nahi bataya."""

    requests_limit: Optional[int] = None
    requests_remaining: Optional[int] = None
    tokens_limit: Optional[int] = None
    tokens_remaining: Optional[int] = None
    reset_seconds: Optional[float] = None   # sab se qareebi reset

    def known(self) -> bool:
        return any(v is not None for v in (self.requests_remaining, self.tokens_remaining))


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict
    extra: dict = field(default_factory=dict)   # provider ka chhupa data (jese Gemini ka thought_signature) - wapas bhejna zaroori


@dataclass
class ChatResult:
    text: str = ""
    tool_calls: list = field(default_factory=list)
    usage: Usage = field(default_factory=Usage)
    limits: RateLimits = field(default_factory=RateLimits)
    stop_reason: str = ""


@dataclass
class ConnectionReport:
    ok: bool
    title: str
    message: str
    latency_ms: int = 0
    model: str = ""
    usage: Usage = field(default_factory=Usage)
    limits: RateLimits = field(default_factory=RateLimits)
    models: list = field(default_factory=list)   # provider ke batae hue model names (agar mile)


# ---------- errors ----------
class ProviderError(Exception):
    """kind: auth | not_found | rate_limit | bad_request | server | network | timeout | bad_response | config"""

    def __init__(self, kind: str, message: str, retry_after: Optional[float] = None, status: int = 0):
        super().__init__(message)
        self.kind = kind
        self.message = message
        self.retry_after = retry_after
        self.status = status


_HINTS = {
    "auth": "API key galat ya expire hai (ya is provider ki nahi hai). Settings mein key dobara save karo.",
    "not_found": "Model ka naam ya URL galat hai. Model name ko provider ki list se check karo.",
    "rate_limit": "Limit lag gayi (free plan par aam hai). Thori der baad dobara try karo.",
    "bad_request": "Provider ne request qabool nahi ki (model is tarah ke kaam ko support nahi karta ho sakta hai).",
    "server": "Provider ke server mein masla hai. Thori der baad try karo.",
    "network": "Server tak pahunch nahi paya. Internet, URL ya (local ke liye) Ollama/LM Studio chal raha hai ya nahi, check karo.",
    "timeout": "Jawab ka intezar karte karte time khatam. Model bara ya server slow ho sakta hai.",
    "bad_response": "Server ka jawab samajh nahi aaya. URL shayad is provider ka nahi hai.",
    "config": "Settings poori nahi hain.",
}


def hint_for(kind: str) -> str:
    return _HINTS.get(kind, "")


# ---------- HTTP ----------
def _scrub(text: str, secret: str) -> str:
    return text.replace(secret, "***") if secret and len(secret) > 6 else text


def _num(value) -> Optional[float]:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def parse_duration(text: Optional[str]) -> Optional[float]:
    """'1m30.5s', '250ms', '20s', '12' ya RFC3339 time nahi: sirf seconds wale formats."""
    if not text:
        return None
    text = text.strip()
    n = _num(text)
    if n is not None:
        return n
    total, num, i = 0.0, "", 0
    while i < len(text):
        ch = text[i]
        if ch.isdigit() or ch == ".":
            num += ch
            i += 1
            continue
        unit = "ms" if text[i:i + 2] == "ms" else ch
        i += 2 if unit == "ms" else 1
        value = _num(num)
        num = ""
        if value is None:
            return None
        total += value * {"ms": 0.001, "s": 1, "m": 60, "h": 3600}.get(unit, 0)
    return total or None


def request_json(
    method: str,
    url: str,
    headers: dict,
    body: Optional[dict] = None,
    timeout: int = DEFAULT_TIMEOUT,
    secret: str = "",
) -> tuple:
    """(json, response headers dict lowercase). Galti par ProviderError. Key kabhi error text mein nahi aati."""
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers={"User-Agent": "Nexora", **headers})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
            hdrs = {k.lower(): v for k, v in resp.headers.items()}
    except urllib.error.HTTPError as e:
        hdrs = {k.lower(): v for k, v in (e.headers or {}).items()}
        try:
            detail = e.read().decode("utf-8", "replace")[:400]
        except Exception:
            detail = ""
        detail = _scrub(detail, secret)
        try:  # provider ka apna error message nikalo
            parsed = json.loads(detail)
            err = parsed.get("error", parsed)
            detail = err.get("message", detail) if isinstance(err, dict) else str(err)
        except Exception:
            pass
        retry = parse_duration(hdrs.get("retry-after"))
        kind = (
            "auth" if e.code in (401, 403)
            else "not_found" if e.code == 404
            else "rate_limit" if e.code == 429
            else "bad_request" if 400 <= e.code < 500
            else "server"
        )
        raise ProviderError(kind, f"HTTP {e.code}: {detail}".strip(), retry_after=retry, status=e.code)
    except (socket.timeout, TimeoutError):
        raise ProviderError("timeout", "Timeout")
    except urllib.error.URLError as e:
        reason = e.reason
        if isinstance(reason, (socket.timeout, TimeoutError)):
            raise ProviderError("timeout", "Timeout")
        if isinstance(reason, ssl.SSLError):
            raise ProviderError("network", f"SSL masla: {_scrub(str(reason), secret)}")
        raise ProviderError("network", _scrub(str(reason), secret))
    except (ConnectionError, OSError) as e:
        raise ProviderError("network", _scrub(str(e), secret))
    try:
        return json.loads(raw.decode("utf-8")) if raw else {}, hdrs
    except ValueError:
        raise ProviderError("bad_response", "Jawab JSON nahi tha")


def timed(fn):
    start = time.monotonic()
    result = fn()
    return result, int((time.monotonic() - start) * 1000)