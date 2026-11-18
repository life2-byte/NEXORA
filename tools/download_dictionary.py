
import sys
import urllib.request
from pathlib import Path

TARGET = Path(__file__).resolve().parents[1] / "frontend" / "assets" / "dictionaries"
BASES = [
    "https://redirector.gvt1.com/edgedl/chrome/dict/",
    "https://dl.google.com/chrome/dict/",
]
VERSIONS = ["10-1", "9-0", "8-0", "7-1", "3-0"]


def fetch(url: str) -> bytes | None:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = resp.read()
        return data if data[:4] == b"BDic" and len(data) > 50_000 else None  # asli dictionary ki pehchan
    except Exception:
        return None


def main() -> int:
    lang = sys.argv[1] if len(sys.argv) > 1 else "en-US"
    TARGET.mkdir(parents=True, exist_ok=True)
    names = {lang.lower(), lang}  # kuch mirrors lowercase naam rakhte hain
    for base in BASES:
        for version in VERSIONS:
            for name in sorted(names):
                url = f"{base}{name}-{version}.bdic"
                data = fetch(url)
                if data:
                    out = TARGET / f"{lang}.bdic"
                    out.write_bytes(data)
                    print(f"OK: {url}\n -> {out} ({len(data) // 1024} KB)")
                    return 0
                print(f"nahi mili: {url}")
    print("\nKoi dictionary nahi mili. Net check karo ya kisi aur language code se try karo (jese en-GB).")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())