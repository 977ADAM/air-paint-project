from __future__ import annotations

import cv2
from dataclasses import dataclass
from typing import Optional

@dataclass(frozen=True)
class CameraConfig:
    device_index: int = 0
    width: int = 640
    height: int = 480
    warmup_frames: int = 5
    max_read_failures: int = 30


class Camera:
    def __init__(self, config: CameraConfig = CameraConfig()):
        self.config = config
        self.cap: Optional[cv2.VideoCapture] = cv2.VideoCapture(config.device_index)
        self._read_failures = 0

        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, config.width)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, config.height)

        if not self.cap.isOpened():
            raise RuntimeError(f"Camera not found (device_index={config.device_index})")

        for _ in range(max(0, config.warmup_frames)):
            _ = self.cap.read()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.release()

    def get_frame(self):
        if not self.cap:
            return None
        ret, frame = self.cap.read()
        if not ret or frame is None:
            self._read_failures += 1
            if self._read_failures >= self.config.max_read_failures:
                return None
            return None
        self._read_failures = 0
        return cv2.flip(frame, 1)

    def release(self):
        if self.cap is not None:
            try:
                if self.cap.isOpened():
                    self.cap.release()
            finally:
                self.cap = None