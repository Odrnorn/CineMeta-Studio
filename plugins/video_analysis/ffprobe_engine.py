from __future__ import annotations
from typing import Any


class FfprobeEngine:
    """Extracts video metadata via ffprobe subprocess."""

    def extract(self, source_path: str) -> dict[str, Any]:
        """Return {fps, duration, width, height, codec} for source_path.
        Returns {} on any error including ffprobe not installed."""
        try:
            return self._run(source_path)
        except Exception:
            return {}

    def _run(self, source_path: str) -> dict[str, Any]:
        import json
        import subprocess

        result = subprocess.run(
            [
                "ffprobe", "-v", "quiet",
                "-print_format", "json",
                "-show_streams", "-show_format",
                source_path,
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        data = json.loads(result.stdout)
        video_stream = next(
            s for s in data["streams"] if s["codec_type"] == "video"
        )
        num, den = video_stream["r_frame_rate"].split("/")
        return {
            "fps": round(int(num) / int(den), 3),
            "duration": float(data["format"]["duration"]),
            "width": int(video_stream["width"]),
            "height": int(video_stream["height"]),
            "codec": video_stream["codec_name"],
        }
