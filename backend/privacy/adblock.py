"""Ad / tracker blocking ka engine (Qt ka koi code nahi). Filter lists EasyList format (||domain^) ya hosts format mein hoti hain.
Sirf network rules chalte hain (cosmetic rules '##' ignore). Read-only banne ke baad thread-safe hai."""

import re
from pathlib import Path
from typing import Optional

_ALLOWED_OPTIONS = {
    "third-party", "3p", "script", "image", "stylesheet", "css", "xmlhttprequest", "xhr",
    "subdocument", "media", "font", "ping", "other", "object", "popup",
}
_TYPE_ALIASES = {"css": "stylesheet", "xhr": "xmlhttprequest", "3p": "third-party"}
_HOSTS_LINE = re.compile(r"^(?:0\.0\.0\.0|127\.0\.0\.1)\s+([a-z0-9._-]+)\s*(?:#.*)?$", re.I)
_RULE = re.compile(r"^\|\|([a-z0-9._-]+)(\^|/[^\s$]*)?(?:\$(.*))?$", re.I)
_SECOND_LEVEL = {"co", "com", "org", "net", "gov", "ac", "edu"}


def site_of(host: str) -> str:
    """Third-party check ke liye mota andaza: example.com ya example.co.uk."""
    parts = host.lower().strip(".").split(".")
    if len(parts) <= 2:
        return ".".join(parts)
    if len(parts[-1]) == 2 and parts[-2] in _SECOND_LEVEL:
        return ".".join(parts[-3:])
    return ".".join(parts[-2:])


class FilterEngine:
    def __init__(self) -> None:
        # host -> [(path_prefix, third_party_only, types or None)]
        self._rules: dict[str, list[tuple[str, bool, Optional[frozenset]]]] = {}
        self.count = 0

    def add_line(self, line: str) -> None:
        line = line.strip()
        if not line or line[0] in "!#[" or "##" in line or "#@#" in line or line.startswith("@@"):
            return
        m = _HOSTS_LINE.match(line)
        if m:
            self._add(m.group(1).lower(), "", False, None)
            return
        m = _RULE.match(line)
        if not m:
            return
        host, tail, options = m.group(1).lower(), m.group(2) or "", m.group(3)
        path = tail if tail.startswith("/") else ""
        path = path.rstrip("^*")
        third_party, types = False, set()
        if options:
            for opt in options.lower().split(","):
                opt = opt.strip()
                if opt not in _ALLOWED_OPTIONS:  # $domain=, $~script, $important... chhod do (ghalat block ka khatra)
                    return
                opt = _TYPE_ALIASES.get(opt, opt)
                if opt == "third-party":
                    third_party = True
                else:
                    types.add(opt)
        self._add(host, path, third_party, frozenset(types) or None)

    def _add(self, host: str, path: str, third_party: bool, types: Optional[frozenset]) -> None:
        self._rules.setdefault(host, []).append((path, third_party, types))
        self.count += 1

    def load_text(self, text: str) -> None:
        for line in text.splitlines():
            self.add_line(line)

    def load_file(self, path: Path) -> None:
        try:
            self.load_text(path.read_text(encoding="utf-8", errors="ignore"))
        except OSError:
            pass

    def should_block(self, host: str, path_query: str, first_party_host: str, resource_type: str) -> bool:
        host = host.lower()
        if not host or not self._rules:
            return False
        third = bool(first_party_host) and site_of(host) != site_of(first_party_host)
        labels = host.split(".")
        for i in range(len(labels) - 1):  # a.b.example.com, b.example.com, example.com
            rules = self._rules.get(".".join(labels[i:]))
            if not rules:
                continue
            for path, third_only, types in rules:
                if third_only and not third:
                    continue
                if types is not None and resource_type not in types:
                    continue
                if path and not path_query.startswith(path):
                    continue
                return True
        return False