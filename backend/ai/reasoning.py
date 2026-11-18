"""Kuch models har step par pehle lamba 'sochte' hain (reasoning) - agent ke liye ye bohat dheema hai.
Jahan provider ka 'reasoning_effort' parameter pakka maloom hai wahan 'low' bhejte hain (user band kar sakta hai)."""

import re
from urllib.parse import urlsplit


def effort_for(base_url: str, model: str, mode: str = "low") -> str:
    """mode: low (default) | auto (kuch na bhejo, provider ka apna default)"""
    if mode != "low":
        return ""
    host = (urlsplit(base_url or "").hostname or "").lower()
    m = (model or "").lower()
    if host == "generativelanguage.googleapis.com" and m.startswith("gemini"):
        return "low"
    if host == "api.groq.com" and "gpt-oss" in m:
        return "low"
    if host == "api.openai.com" and re.match(r"(gpt-5|o\d)", m):
        return "low"
    return ""