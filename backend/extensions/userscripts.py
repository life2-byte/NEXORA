"""User scripts (apni chhoti extensions): .js ya .css file jo chuni hui sites par chalti hai.
Header format (Tampermonkey jaisa):
    // ==UserScript==
    // @name        Meri script
    // @match       https://*.example.com/*
    // @exclude     https://example.com/private/*
    // @run-at      document-end        (document-start | document-end | document-idle)
    // @world       isolated            (isolated | main)
    // ==/UserScript==
CSS files mein yehi header /* ... */ comment ke andar likho. Qt ka koi code nahi."""

import re
import urllib.request
from pathlib import Path
from typing import Optional
from urllib.parse import urlsplit

TEMPLATE_JS = """// ==UserScript==
// @name        Meri script
// @match       https://example.com/*
// @run-at      document-end
// @world       isolated
// ==/UserScript==

console.log("Meri script chal rahi hai:", location.href);
"""

_HEADER = re.compile(r"==UserScript==(.*?)==/UserScript==", re.S)
_LINE = re.compile(r"^\s*(?://|\*|/\*)?\s*@(\w[\w-]*)\s+(.*?)\s*(?:\*/)?$")
MAX_SIZE = 512 * 1024


def parse_header(text: str) -> dict:
    meta = {"name": "", "match": [], "exclude": [], "run-at": "document-end", "world": "isolated"}
    m = _HEADER.search(text[:8000])
    if not m:
        return meta
    for line in m.group(1).splitlines():
        lm = _LINE.match(line)
        if not lm:
            continue
        key, value = lm.group(1).lower(), lm.group(2).strip()
        if key in ("match", "include"):
            meta["match"].append(value)
        elif key == "exclude":
            meta["exclude"].append(value)
        elif key in ("name", "run-at", "world"):
            meta[key] = value
    if meta["run-at"] not in ("document-start", "document-end", "document-idle"):
        meta["run-at"] = "document-end"
    if meta["world"] not in ("isolated", "main"):
        meta["world"] = "isolated"
    return meta


def pattern_to_regex(pattern: str) -> Optional[str]:
    """Chrome-style match pattern -> JS/Python regex string. Sirf http/https; galat pattern par None."""
    pattern = pattern.strip()
    if pattern == "<all_urls>":
        return r"^https?://.*$"
    m = re.fullmatch(r"(\*|https?)://([^/]*)(/.*)", pattern)
    if not m:
        return None
    scheme, host, path = m.groups()
    scheme_re = "https?" if scheme == "*" else scheme
    if host == "*":
        host_re = r"[^/]+"
    elif host.startswith("*."):
        host_re = r"(?:[^/]+\.)?" + re.escape(host[2:])
    elif "*" in host or not host:
        return None
    else:
        host_re = re.escape(host)
    path_re = ".*".join(re.escape(part) for part in path.split("*"))
    return f"^{scheme_re}://{host_re}{path_re}$"


def _regexes(patterns: list) -> list:
    return [r for r in (pattern_to_regex(p) for p in patterns) if r]


class UserScript:
    def __init__(self, path: Path):
        self.path = path
        self.filename = path.name
        self.kind = "css" if path.suffix.lower() == ".css" else "js"
        self.text = path.read_text(encoding="utf-8", errors="replace")
        self.meta = parse_header(self.text)
        self.name = self.meta["name"] or path.stem
        self.includes = _regexes(self.meta["match"])
        self.excludes = _regexes(self.meta["exclude"])

    @property
    def valid(self) -> bool:
        return bool(self.includes)  # @match ke baghair kabhi nahi chalti (har site par galti se nahi)

    def wrapped_source(self) -> str:
        """Page mein chalne wala poora JS: pehle URL match check, phir user ka code."""
        import json

        guard = (
            f"const __inc={json.dumps(self.includes)},__exc={json.dumps(self.excludes)};"
            "const __u=location.href;"
            "if(!__inc.some(r=>new RegExp(r).test(__u))||__exc.some(r=>new RegExp(r).test(__u)))return;"
        )
        if self.kind == "css":
            body = (
                "const s=document.createElement('style');"
                f"s.textContent={json.dumps(self.text)};"
                "(document.head||document.documentElement).appendChild(s);"
            )
        else:
            body = self.text
        return f"(function(){{{guard}\n{body}\n}})();"


class ScriptStore:
    def __init__(self, folder: Path):
        self.folder = Path(folder)

    def list(self) -> list:
        if not self.folder.exists():
            return []
        files = [f for f in self.folder.iterdir() if f.suffix.lower() in (".js", ".css") and f.is_file()]
        scripts = []
        for f in sorted(files, key=lambda x: x.name.lower()):
            try:
                scripts.append(UserScript(f))
            except OSError:
                pass
        return scripts

    @staticmethod
    def safe_name(name: str, kind: str) -> str:
        stem = re.sub(r"[^\w\- ]+", "", Path(name).stem).strip()[:50] or "script"
        return f"{stem}.{kind}"

    def save(self, filename: str, text: str) -> str:
        if len(text.encode("utf-8")) > MAX_SIZE:
            raise ValueError("Script bohat bari hai (512 KB se zyada)")
        self.folder.mkdir(parents=True, exist_ok=True)
        filename = self.safe_name(filename, "css" if filename.lower().endswith(".css") else "js")
        (self.folder / filename).write_text(text, encoding="utf-8")
        return filename

    def delete(self, filename: str) -> None:
        target = self.folder / Path(filename).name  # sirf is folder ki file
        try:
            target.unlink()
        except OSError:
            pass

    def unique_name(self, wanted: str) -> str:
        wanted = self.safe_name(wanted, "css" if wanted.lower().endswith(".css") else "js")
        if not (self.folder / wanted).exists():
            return wanted
        p = Path(wanted)
        n = 2
        while (self.folder / f"{p.stem}-{n}{p.suffix}").exists():
            n += 1
        return f"{p.stem}-{n}{p.suffix}"


def _local(host: str) -> bool:
    return host in ("localhost", "127.0.0.1", "::1")


def fetch_script(url: str, timeout: int = 15) -> tuple:
    """Link se script download karo. (filename, text) deta hai, galti par ValueError.
    Sirf https (ya local testing ke liye localhost http); 512 KB tak."""
    parts = urlsplit(url.strip())
    if parts.scheme != "https" and not (parts.scheme == "http" and _local(parts.hostname or "")):
        raise ValueError("Sirf https:// link chalta hai")
    if not parts.hostname:
        raise ValueError("Link galat hai")
    req = urllib.request.Request(url.strip(), headers={"User-Agent": "Nexora"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            final = urlsplit(resp.geturl())
            if final.scheme != "https" and not _local(final.hostname or ""):
                raise ValueError("Link http par redirect hua, rok diya")
            data = resp.read(MAX_SIZE + 1)
    except ValueError:
        raise
    except Exception as e:  # net, DNS, 404 wagera
        raise ValueError(f"Download nahi hua: {e}")
    if len(data) > MAX_SIZE:
        raise ValueError("Script bohat bari hai (512 KB se zyada)")
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        raise ValueError("Ye text file nahi lagti")
    if "<html" in text[:500].lower() or "<!doctype" in text[:500].lower():
        raise ValueError("Ye web page hai, script ka seedha (raw) link do")
    last = Path(parts.path).name or "script"
    last = re.sub(r"\.user\.js$", ".js", last, flags=re.I)
    if not last.lower().endswith((".js", ".css")):
        last += ".js"
    return last, text