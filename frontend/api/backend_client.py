from backend.media.video_converter import (
    convert_to_webm,
    ffmpeg_available,
    needs_conversion,
)


class BackendClient:
    """Frontend backend se sirf yahin se baat karta hai.
    Abhi seedha local function call hai, baad mein HTTP/WebSocket ban sakta hai."""

    def ffmpeg_available(self) -> bool:
        return ffmpeg_available()

    def needs_video_conversion(self, path: str) -> bool:
        return needs_conversion(path)

    def convert_video(self, src: str, dest: str, on_progress=None, should_cancel=None):
        return convert_to_webm(src, dest, on_progress, should_cancel)


backend_client = BackendClient()