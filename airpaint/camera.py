from __future__ import annotations

from dataclasses import dataclass
from typing import Final

import cv2


@dataclass(frozen=True)
class CameraConfig:
    device_index: int = 0
    width: int = 1024
    height: int = 480
    warmup_frames: int = 5
    max_read_failures: int = 30
    mirror: bool = True


class Camera:
    def __init__(self, config: CameraConfig = CameraConfig()):
        self.config = config
        self.cap: cv2.VideoCapture | None = cv2.VideoCapture(config.device_index)
        self._read_failures = 0
        self._flip_code: Final[int] = 1  # horizontal

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

    def get_frame(self) -> cv2.Mat | None:
        if not self.cap:
            return None
        ret, frame = self.cap.read()
        if not ret or frame is None:
            self._read_failures += 1
            if self._read_failures >= self.config.max_read_failures:
                raise RuntimeError(
                    f"Camera read failed {self._read_failures} times подряд "
                    f"(device_index={self.config.device_index})."
                )
            return None
        self._read_failures = 0
        if self.config.mirror:
            return cv2.flip(frame, self._flip_code)
        return frame

    def release(self):
        if self.cap is not None:
            try:
                if self.cap.isOpened():
                    self.cap.release()
            finally:
                self.cap = None