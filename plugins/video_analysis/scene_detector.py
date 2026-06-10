from __future__ import annotations


class SceneDetectorEngine:
    """Detects scene boundaries via PySceneDetect."""

    def detect(self, source_path: str) -> list[float]:
        """Return scene-start timestamps in seconds.
        Falls back to [0.0] if scenedetect is not installed or any error occurs."""
        try:
            from scenedetect import ContentDetector
            from scenedetect import detect as sd_detect

            scenes = sd_detect(source_path, ContentDetector())
            timestamps = [s[0].get_seconds() for s in scenes]
            return timestamps if timestamps else [0.0]
        except Exception:
            return [0.0]
