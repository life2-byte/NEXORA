import faulthandler
import os
import sys
import threading
import traceback
from datetime import datetime
from pathlib import Path

# pip wale Qt ko system ki fonts config batao (sirf Linux par, warning band)
if sys.platform.startswith("linux") and os.path.isdir("/etc/fonts"):
    os.environ.setdefault("FONTCONFIG_PATH", "/etc/fonts")

# spellcheck ki dictionary files (.bdic) is folder se uthai jati hain
os.environ.setdefault("QTWEBENGINE_DICTIONARIES_PATH", str(Path(__file__).resolve().parent / "frontend" / "assets" / "dictionaries"))

CONFIG_DIR = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "agentic-browser"
CRASH_LOG = CONFIG_DIR / "crash.log"
CONFIG_DIR.mkdir(parents=True, exist_ok=True)


def _log_exception(exc_type, exc, tb) -> None:
    """PyQt6 mein slot ke error par app abort hoti hai; ye hook usay rokta hai aur log likhta hai."""
    text = "".join(traceback.format_exception(exc_type, exc, tb))
    sys.stderr.write(text)
    try:
        with open(CRASH_LOG, "a", encoding="utf-8") as f:
            f.write(f"\n--- {datetime.now():%Y-%m-%d %H:%M:%S} ---\n{text}")
    except OSError:
        pass


sys.excepthook = _log_exception
threading.excepthook = lambda args: _log_exception(args.exc_type, args.exc_value, args.exc_traceback)

# native crash (segfault) par bhi Python ka stack crash.log mein likha jaye
_fault_file = open(CRASH_LOG, "a")
faulthandler.enable(file=_fault_file, all_threads=True)



def _take_profile_arg() -> None:
    """`--profile <id>` ko argv se nikal kar env var mein rakhta hai (settings import hone se pehle)."""
    argv = sys.argv
    for i, arg in enumerate(argv[1:], start=1):
        if arg == "--profile" and i + 1 < len(argv):
            os.environ["NEXORA_PROFILE"] = argv[i + 1]
            del argv[i : i + 2]
            return
        if arg.startswith("--profile="):
            os.environ["NEXORA_PROFILE"] = arg.split("=", 1)[1]
            del argv[i]
            return


_take_profile_arg()

from frontend.app import create_app  # noqa: E402


def main():
    app, window = create_app("dark")
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()