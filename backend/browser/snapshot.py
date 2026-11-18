import re
from typing import Any

_TOKEN = re.compile(r"[a-z0-9]+")
_STOP = {
    "the", "and", "for", "with", "from", "that", "this", "are", "you", "your",
    "find", "search", "open", "click", "get", "show", "please", "into", "about",
}
_INPUT_KINDS = {"input", "textarea", "select"}
_HEADING_BONUS = {"h1": 3, "h2": 2, "h3": 1, "h4": 0}


def _tokens(text: str) -> set:
    return {t for t in _TOKEN.findall((text or "").lower()) if len(t) > 2 and t not in _STOP}


def _score(el: dict, goal_tokens: set) -> int:
    score = 0
    kind = el["kind"]
    if el.get("inView"):
        score += 2
    if el.get("region") == "dialog":
        score += 6                       # popups/cookie banners hamesha chahiye
    if kind in _INPUT_KINDS:
        score += 3                       # search boxes/forms hamesha chahiye
    if kind == "canvas":
        score += 8                       # agent ko pata chalna chahiye ke ye canvas page hai
    if kind in ("link", "button", "tab", "menuitem"):
        score += 1
    score += _HEADING_BONUS.get(kind, 0)
    if el.get("region") == "footer":
        score -= 2
    elif el.get("region") == "nav":
        score -= 1

    blob = " ".join(str(el.get(k, "")) for k in ("text", "href", "placeholder", "value"))
    score += 4 * len(goal_tokens & _tokens(blob))
    return score


def _line(el: dict) -> str:
    kind = el["kind"]
    text = el.get("text", "")
    region = el.get("region", "main")
    tag = "" if region == "main" else f" ({region})"

    if kind == "text":
        return f"[text]{tag} {text}"
    if re.fullmatch(r"h[1-4]", kind):
        return f"[{kind}]{tag} {text}"

    if kind == "canvas":
        return f"[canvas {el['id']}] {text}  <- drawn pixels, no DOM: use screenshot + click_at"
    head = f"{kind} {el['id']}"
    if kind in _INPUT_KINDS:
        if el.get("inputType") not in (None, "text"):
            head += f" type={el['inputType']}"
        if el.get("placeholder"):
            head += f' placeholder="{el["placeholder"]}"'
    if el.get("disabled"):
        head += " disabled"
    if kind in ("checkbox", "radio"):
        head += " checked" if el.get("checked") else " unchecked"
    if el.get("state"):
        head += " " + ",".join(el["state"])

    line = f"[{head}]{tag}"
    if text:
        line += f" {text}"
    if el.get("secret"):
        line += " = (hidden)"
    elif el.get("value"):
        line += f' = "{el["value"]}"'
    if el.get("href"):
        line += f" -> {el['href']}"
    return line


def build_snapshot(raw: dict[str, Any], goal: str = "", scope: str = "viewport", budget: int = 6000) -> str:
    """scope: 'viewport' (jo abhi screen pe hai) ya 'page' (poora page).
    budget: output ki max characters (~4 chars = 1 token)."""
    goal_tokens = _tokens(goal)
    elements = list(raw.get("elements", []))
    total = len(elements)

    note = ""
    if scope == "viewport" and raw.get("viewportHeight", 0) < 50:
        scope = "page"  # is tab ka viewport hi nahi (hidden), to poora page do
        note = "\nNOTE: this tab has no visible viewport, showing the whole page instead"

    if scope == "viewport":
        elements = [e for e in elements if e.get("inView") or e.get("region") == "dialog"]

    header = (
        f"PAGE: {raw.get('title', '')} | {raw.get('url', '')}\n"
        f"SCROLL: {raw.get('scrollY', 0)}/{raw.get('scrollHeight', 0)}"
        f" (viewport {raw.get('viewportHeight', 0)}px)"
    )
    if goal.strip():
        header += f"\nGOAL: {goal.strip()}"
    if raw.get("selection"):
        header += f"\nSELECTED TEXT: {raw['selection']}"
    header += note

    ranked = sorted(elements, key=lambda e: (-_score(e, goal_tokens), e["i"]))
    used = len(header) + 120  # footer ke liye jagah
    chosen = []
    for el in ranked:
        line = _line(el)
        if used + len(line) + 1 > budget:
            continue
        chosen.append((el["i"], line))
        used += len(line) + 1

    chosen.sort()  # document ka asli order
    body = "\n".join(line for _, line in chosen)

    footer = f"(showing {len(chosen)} of {total} elements, scope={scope}"
    if raw.get("truncated"):
        footer += ", page bohot bara hai: baqi elements kaate gaye"
    footer += ")"
    return f"{header}\n\n{body}\n\n{footer}"


def format_found(items: list, query: str) -> str:
    if not items:
        return f'FIND "{query}": no matches (try other words, or scroll and read the page again)'
    lines = "\n".join(_line(it) for it in items)
    return f'FIND "{query}": {len(items)} match(es)\n{lines}'