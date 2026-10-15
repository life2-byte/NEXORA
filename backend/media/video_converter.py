import shutil
import subprocess
from pathlib import Path
from typing import Callable, Optional

# Ye formats Chromium seedha chala leta hai, convert nahi karne
NATIVE_VIDEO_EXTS = {".webm", ".ogv", ".ogg"}


class ConversionError(Exception):
    pass


def needs_conversion(path: str) -> bool:
    return Path(path).suffix.lower() not in NATIVE_VIDEO_EXTS


def ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None


def _duration_seconds(src: Path) -> float:
    try:
        out = subprocess.run(
            [
                "ffprobe", "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=nw=1:nk=1",
                str(src),
            ],
            capture_output=True,
            text=True,
            timeout=15,
        )
        return float(out.stdout.strip())
    except (OSError, ValueError, subprocess.SubprocessError):
        return 0.0


def convert_to_webm(
    src: str,
    dest: str,
    on_progress: Optional[Callable[[int], None]] = None,
    should_cancel: Optional[Callable[[], bool]] = None,
) -> Path:
    """Koi bhi video -> VP9 .webm (no audio, max 1280px wide). Progress 0-100 deta hai."""
    if not ffmpeg_available():
        raise ConversionError("ffmpeg nahi mila. Terminal mein chala: sudo apt install ffmpeg")

    src_path, dest_path = Path(src), Path(dest)
    duration = _duration_seconds(src_path)

    cmd = [
        "ffmpeg", "-y", "-i", str(src_path),
        "-an",
        "-vf", "scale='min(1280,iw)':-2",
        "-c:v", "libvpx-vp9", "-b:v", "0", "-crf", "34", "-r", "30",
        "-deadline", "good", "-cpu-used", "4",
        "-progress", "pipe:1", "-nostats",
        str(dest_path),
    ]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)

    cancelled = False
    try:
        for line in proc.stdout:
            if should_cancel and should_cancel():
                cancelled = True
                proc.terminate()
                break
            if on_progress and duration > 0 and line.startswith(("out_time_us=", "out_time_ms=")):
                try:
                    micro = int(line.split("=", 1)[1])
                except ValueError:
                    continue  # shuru mein "N/A" aata hai
                on_progress(max(0, min(99, int(micro / 1_000_000 / duration * 100))))
    finally:
        proc.stdout.close()
        code = proc.wait()

    if cancelled or code != 0:
        dest_path.unlink(missing_ok=True)
        raise ConversionError("Cancelled" if cancelled else "Video convert nahi ho saki")

    if on_progress:
        on_progress(100)
    return dest_path