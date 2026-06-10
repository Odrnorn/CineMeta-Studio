from __future__ import annotations


class FrameExtractorEngine:
    """Extracts individual frames from video files via OpenCV."""

    def extract_frame(
        self,
        source_path: str,
        timestamp_seconds: float,
        output_path: str,
    ) -> bool:
        """Seek to timestamp_seconds, write PNG to output_path.
        Creates parent directories. Returns True on success, False on any error."""
        try:
            import cv2
            from pathlib import Path

            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            cap = cv2.VideoCapture(source_path)
            cap.set(cv2.CAP_PROP_POS_MSEC, timestamp_seconds * 1000)
            ok, frame = cap.read()
            cap.release()
            if not ok:
                return False
            cv2.imwrite(output_path, frame)
            return True
        except Exception:
            return False
