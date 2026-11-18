"""Teen protocol: OpenAI-style (OpenAI, Groq, Gemini, OpenRouter, LM Studio, llama.cpp...), Ollama aur Anthropic.
Sab ek hi interface dete hain: chat(messages, tools) -> ChatResult, aur test_connection() -> ConnectionReport.
Qt ka koi code nahi (worker thread se chalao)."""

import dataclasses
import json
from typing import Optional

from backend.ai.base import (
    ChatResult,
    ConnectionReport,
    ProviderConfig,
    ProviderError,
    RateLimits,
    ToolCall,
    Usage,
    hint_for,
    parse_duration,
    request_json,
    timed,
)

ANTHROPIC_VERSION = "2023-06-01"


def _int(value) -> Optional[int]:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _json_args(value) -> dict:
    if isinstance(value, dict):
        return value
    try:
        parsed = json.loads(value or "{}")
        return parsed if isinstance(parsed, dict) else {}
    except ValueError:
        return {}


class Provider:
    def __init__(self, config: ProviderConfig):
        self.cfg = config
        self.base = config.base_url.rstrip("/")

    # ---- subclasses ----
    def chat(self, messages: list, tools: Optional[list] = None, max_tokens: int = 1024) -> ChatResult:
        raise NotImplementedError

    def list_models(self) -> list:
        return []

    # ---- common ----
    def test_connection(self) -> ConnectionReport:
        """Chhoti si request bhej kar dekhta hai: connect hua? key theek? model mil gaya? kitne tokens/limit?"""
        name = self.cfg.label or self.cfg.kind
        if not self.base:
            return ConnectionReport(False, "URL nahi hai", "Settings mein URL daalo.")
        if not self.cfg.model:
            models = self._safe_models()
            extra = ("\n\nIs server par ye models hain:\n" + "\n".join(models[:15])) if models else ""
            return ConnectionReport(False, "Model ka naam nahi hai", "Settings mein model name daalo." + extra, models=models)
        try:
            result, ms = timed(
                lambda: self.chat(
                    [{"role": "user", "content": "Reply with the single word OK."}], max_tokens=16
                )
            )
        except ProviderError as e:
            models = self._safe_models() if e.kind == "not_found" else []
            msg = f"{e.message}\n\n{hint_for(e.kind)}"
            if e.retry_after:
                msg += f"\n(Dobara try karne ka waqt: {e.retry_after:.0f} second)"
            if models:
                msg += "\n\nIs server par ye models hain:\n" + "\n".join(models[:15])
            return ConnectionReport(False, f"{name}: connect nahi hua", msg, model=self.cfg.model, models=models)
        return ConnectionReport(
            True,
            f"{name}: connect ho gaya",
            (result.text.strip() or "(khali jawab)")[:80],
            latency_ms=ms,
            model=self.cfg.model,
            usage=result.usage,
            limits=result.limits,
        )

    def _safe_models(self) -> list:
        try:
            return self.list_models()
        except ProviderError:
            return []


# =====================================================================
# OpenAI-style
# =====================================================================
class OpenAIProvider(Provider):
    def _headers(self) -> dict:
        headers = {"Content-Type": "application/json"}
        if self.cfg.api_key:
            headers["Authorization"] = f"Bearer {self.cfg.api_key}"
        return headers

    @staticmethod
    def _to_messages(messages: list) -> list:
        out = []
        for m in messages:
            role = m["role"]
            if role == "assistant" and m.get("tool_calls"):
                out.append({
                    "role": "assistant",
                    "content": m.get("content") or None,
                    "tool_calls": [
                        {"id": c["id"], "type": "function",
                         "function": {"name": c["name"], "arguments": json.dumps(c["arguments"])},
                         **(c.get("extra") or {})}
                        for c in m["tool_calls"]
                    ],
                })
            elif role == "tool":
                out.append({"role": "tool", "tool_call_id": m["tool_call_id"], "content": m["content"]})
            elif m.get("images"):
                parts = [{"type": "text", "text": m["content"]}] + [
                    {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64," + img}} for img in m["images"]
                ]
                out.append({"role": role, "content": parts})
            else:
                out.append({"role": role, "content": m["content"]})
        return out

    def chat(self, messages, tools=None, max_tokens=1024) -> ChatResult:
        body = {"model": self.cfg.model, "messages": self._to_messages(messages), "max_tokens": max_tokens}
        if tools:
            body["tools"] = [{"type": "function", "function": t} for t in tools]
        if self.cfg.reasoning:
            body["reasoning_effort"] = self.cfg.reasoning
        try:
            data, h = request_json("POST", f"{self.base}/chat/completions", self._headers(), body,
                                   self.cfg.timeout, self.cfg.api_key)
        except ProviderError as e:
            if not (self.cfg.reasoning and e.kind == "bad_request" and "reasoning" in e.message.lower()):
                raise
            body.pop("reasoning_effort", None)      # is model ko ye parameter pasand nahi: bina iske dobara
            self.cfg = dataclasses.replace(self.cfg, reasoning="")
            data, h = request_json("POST", f"{self.base}/chat/completions", self._headers(), body,
                                   self.cfg.timeout, self.cfg.api_key)
        try:
            choice = data["choices"][0]
            msg = choice.get("message", {})
        except (KeyError, IndexError, TypeError):
            raise ProviderError("bad_response", "Jawab mein 'choices' nahi mila")
        calls = [
            ToolCall(c.get("id") or f"call_{i}", c["function"]["name"], _json_args(c["function"].get("arguments")),
                     {"extra_content": c["extra_content"]} if c.get("extra_content") else {})
            for i, c in enumerate(msg.get("tool_calls") or [])
            if c.get("function", {}).get("name")
        ]
        u = data.get("usage") or {}
        return ChatResult(
            text=msg.get("content") or "",
            tool_calls=calls,
            usage=Usage(_int(u.get("prompt_tokens")) or 0, _int(u.get("completion_tokens")) or 0),
            limits=RateLimits(
                requests_limit=_int(h.get("x-ratelimit-limit-requests")),
                requests_remaining=_int(h.get("x-ratelimit-remaining-requests")),
                tokens_limit=_int(h.get("x-ratelimit-limit-tokens")),
                tokens_remaining=_int(h.get("x-ratelimit-remaining-tokens")),
                reset_seconds=min(
                    [r for r in (parse_duration(h.get("x-ratelimit-reset-tokens")),
                                 parse_duration(h.get("x-ratelimit-reset-requests"))) if r is not None],
                    default=None,
                ),
            ),
            stop_reason=choice.get("finish_reason") or "",
        )

    def list_models(self) -> list:
        data, _ = request_json("GET", f"{self.base}/models", self._headers(), None, 15, self.cfg.api_key)
        items = data.get("data", data) if isinstance(data, dict) else data
        names = [m.get("id") or m.get("name", "") for m in items if isinstance(m, dict)]
        return sorted(n.removeprefix("models/") for n in names if n)


# =====================================================================
# Ollama
# =====================================================================
class OllamaProvider(Provider):
    @staticmethod
    def _to_messages(messages: list) -> list:
        out = []
        for m in messages:
            role = m["role"]
            if role == "assistant" and m.get("tool_calls"):
                out.append({
                    "role": "assistant",
                    "content": m.get("content") or "",
                    "tool_calls": [{"function": {"name": c["name"], "arguments": c["arguments"]}} for c in m["tool_calls"]],
                })
            elif role == "tool":
                out.append({"role": "tool", "tool_name": m.get("name", ""), "content": m["content"]})
            elif m.get("images"):
                out.append({"role": role, "content": m["content"], "images": list(m["images"])})
            else:
                out.append({"role": role, "content": m["content"]})
        return out

    def chat(self, messages, tools=None, max_tokens=1024) -> ChatResult:
        body = {"model": self.cfg.model, "messages": self._to_messages(messages), "stream": False,
                "options": {"num_predict": max_tokens}}
        if tools:
            body["tools"] = [{"type": "function", "function": t} for t in tools]
        data, _ = request_json("POST", f"{self.base}/api/chat", {"Content-Type": "application/json"}, body,
                               self.cfg.timeout)
        if "message" not in data:
            raise ProviderError("bad_response", "Jawab mein 'message' nahi mila (Ollama ka URL sahi hai?)")
        msg = data["message"]
        calls = [
            ToolCall(f"call_{i}", c["function"]["name"], _json_args(c["function"].get("arguments")))
            for i, c in enumerate(msg.get("tool_calls") or [])
            if c.get("function", {}).get("name")
        ]
        return ChatResult(
            text=msg.get("content") or "",
            tool_calls=calls,
            usage=Usage(_int(data.get("prompt_eval_count")) or 0, _int(data.get("eval_count")) or 0),
            stop_reason=data.get("done_reason") or "",
        )

    def list_models(self) -> list:
        data, _ = request_json("GET", f"{self.base}/api/tags", {}, None, 10)
        return sorted(m.get("name", "") for m in data.get("models", []) if m.get("name"))


# =====================================================================
# Anthropic
# =====================================================================
class AnthropicProvider(Provider):
    def _headers(self) -> dict:
        return {"Content-Type": "application/json", "x-api-key": self.cfg.api_key,
                "anthropic-version": ANTHROPIC_VERSION}

    @staticmethod
    def _convert(messages: list) -> tuple:
        system = "\n\n".join(m["content"] for m in messages if m["role"] == "system")
        out: list = []
        for m in messages:
            role = m["role"]
            if role == "system":
                continue
            if role == "assistant":
                blocks = []
                if m.get("content"):
                    blocks.append({"type": "text", "text": m["content"]})
                for c in m.get("tool_calls") or []:
                    blocks.append({"type": "tool_use", "id": c["id"], "name": c["name"], "input": c["arguments"]})
                out.append({"role": "assistant", "content": blocks or [{"type": "text", "text": ""}]})
            elif role == "tool":
                block = {"type": "tool_result", "tool_use_id": m["tool_call_id"], "content": m["content"]}
                if out and out[-1]["role"] == "user" and isinstance(out[-1]["content"], list) \
                        and out[-1]["content"] and out[-1]["content"][0].get("type") == "tool_result":
                    out[-1]["content"].append(block)  # ek hi turn ke saare tool results ek message mein
                else:
                    out.append({"role": "user", "content": [block]})
            else:
                if m.get("images"):
                    blocks = [{"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": img}}
                              for img in m["images"]] + [{"type": "text", "text": m["content"]}]
                    if out and out[-1]["role"] == "user" and isinstance(out[-1]["content"], list):
                        out[-1]["content"].extend(blocks)   # tool_result ke baad usi turn mein
                    else:
                        out.append({"role": "user", "content": blocks})
                else:
                    out.append({"role": "user", "content": m["content"]})
        return system, out

    def chat(self, messages, tools=None, max_tokens=1024) -> ChatResult:
        system, converted = self._convert(messages)
        body = {"model": self.cfg.model, "max_tokens": max_tokens, "messages": converted}
        if system:
            body["system"] = system
        if tools:
            body["tools"] = [{"name": t["name"], "description": t["description"], "input_schema": t["parameters"]}
                             for t in tools]
        data, h = request_json("POST", f"{self.base}/v1/messages", self._headers(), body,
                               self.cfg.timeout, self.cfg.api_key)
        if "content" not in data:
            raise ProviderError("bad_response", "Jawab mein 'content' nahi mila")
        text = "".join(b.get("text", "") for b in data["content"] if b.get("type") == "text")
        calls = [ToolCall(b["id"], b["name"], b.get("input") or {}) for b in data["content"] if b.get("type") == "tool_use"]
        u = data.get("usage") or {}
        resets = [parse_duration(h.get(k)) for k in ("anthropic-ratelimit-tokens-reset",
                                                       "anthropic-ratelimit-requests-reset")]
        return ChatResult(
            text=text,
            tool_calls=calls,
            usage=Usage(_int(u.get("input_tokens")) or 0, _int(u.get("output_tokens")) or 0),
            limits=RateLimits(
                requests_limit=_int(h.get("anthropic-ratelimit-requests-limit")),
                requests_remaining=_int(h.get("anthropic-ratelimit-requests-remaining")),
                tokens_limit=_int(h.get("anthropic-ratelimit-tokens-limit")),
                tokens_remaining=_int(h.get("anthropic-ratelimit-tokens-remaining")),
                reset_seconds=min([r for r in resets if r is not None], default=None),
            ),
            stop_reason=data.get("stop_reason") or "",
        )

    def list_models(self) -> list:
        data, _ = request_json("GET", f"{self.base}/v1/models?limit=50", self._headers(), None, 15, self.cfg.api_key)
        return [m["id"] for m in data.get("data", []) if m.get("id")]


_KINDS = {"openai": OpenAIProvider, "ollama": OllamaProvider, "anthropic": AnthropicProvider}


def make_provider(config: ProviderConfig) -> Provider:
    cls = _KINDS.get(config.kind)
    if cls is None:
        raise ProviderError("config", f"Unknown provider type: {config.kind}")
    return cls(config)