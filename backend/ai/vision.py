"""Kya ye model tasveer (screenshot) dekh sakta hai? Naam se andaza; user Memory page mein On/Off kar sakta hai."""

import re

_VISION_HINTS = re.compile(
    r"(vision|llava|bakllava|moondream|minicpm-v|pixtral|qwen[\w.\-]*-?vl|qwen2\.5vl|qwen3-vl|gemma-?3|"
    r"llama-?4|llama-?3\.2-\d+b-vision|gpt-4o|gpt-4\.1|gpt-4-turbo|gpt-5|o4-mini|o3|claude|gemini|"
    r"mistral-(small|medium)-3|grok-(2-vision|4)|internvl|phi-?3\.5-vision|phi-?4-multimodal|molmo|scout|maverick)",
    re.I,
)


def supports_vision(model: str, mode: str = "auto") -> bool:
    """mode: auto | on | off"""
    if mode == "on":
        return True
    if mode == "off":
        return False
    return bool(_VISION_HINTS.search(model or ""))