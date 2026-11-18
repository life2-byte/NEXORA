"""Action ke result ko agent ke liye ek saaf, verified line mein badalta hai."""


def format_action(name: str, args: str, result: dict) -> str:
    label = f"{name} {args}".strip()
    if not result.get("ok"):
        return f"FAILED {label}: {result.get('error', 'unknown error')}"

    parts = [f"OK {label}"]
    if result.get("note"):
        parts.append(result["note"])

    if result.get("url_changed"):
        parts.append(f"navigated to {result.get('url', '')}")
    elif result.get("page_changed"):
        parts.append("page content changed")
    elif "scrollY" not in result:
        parts.append("no visible change (check if it worked)")

    if "value" in result:
        parts.append(f'value now "{result["value"]}"')
    if "scrollY" in result:
        where = "bottom" if result.get("atBottom") else f"{result['scrollY']}/{result['scrollHeight']}"
        parts.append(f"scroll at {where}")
    return " | ".join(parts)