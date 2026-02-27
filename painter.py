from __future__ import annotations

import cv2
import numpy as np
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple, List

@dataclass
class PainterConfig:
    default_color: Tuple[int, int, int] = (255, 0, 255)
    brush_thickness: int = 5
    smooth_factor: float = 0.4
    undo_depth: int = 20
    snapshots_dir: str = "snapshots"


class Painter:
    def __init__(self, config: PainterConfig = PainterConfig()):
        self.config = config
        self.canvas: Optional[np.ndarray] = None
        self.color = config.default_color
        self.brush_thickness = int(config.brush_thickness)
        self.prev_x: Optional[int] = None
        self.prev_y: Optional[int] = None
        self.smooth_factor = float(config.smooth_factor)
        self._undo_stack: List[np.ndarray] = []
        self._last_saved_frame_idx = 0

    def init_canvas(self, frame):
        if self.canvas is None:
            self.canvas = np.zeros_like(frame)

    def set_color(self, color):
        self.color = color

    def set_brush_thickness(self, value: int) -> None:
        self.brush_thickness = int(max(1, min(50, value)))

    def clear(self):
        if self.canvas is not None:
            self._push_undo()
            self.canvas[:] = 0

 
    def undo(self) -> None:
        if not self._undo_stack or self.canvas is None:
            return
        self.canvas = self._undo_stack.pop()

    def _push_undo(self) -> None:
        if self.canvas is None:
            return
        self._undo_stack.append(self.canvas.copy())
        if len(self._undo_stack) > self.config.undo_depth:
            self._undo_stack.pop(0)

    def save_snapshot(self) -> Optional[Path]:
        if self.canvas is None:
            return None
        out_dir = Path(self.config.snapshots_dir)
        out_dir.mkdir(parents=True, exist_ok=True)

        self._last_saved_frame_idx += 1
        path = out_dir / f"airpaint_{self._last_saved_frame_idx:04d}.png"
        # Save only the canvas (transparent bg would require PNG alpha; here keep black bg)
        cv2.imwrite(str(path), self.canvas)
        return path

    def draw(self, frame, landmarks, fingers):
        h, w, _ = frame.shape

        x = int(landmarks.landmark[8].x * w)
        y = int(landmarks.landmark[8].y * h)

        if self.prev_x is not None and self.prev_y is not None:
            x = int(self.prev_x * (1 - self.smooth_factor) + x * self.smooth_factor)
            y = int(self.prev_y * (1 - self.smooth_factor) + y * self.smooth_factor)

        if fingers[1] == 1 and sum(fingers) == 1:
            cv2.circle(frame, (x, y), 10, (0, 255, 0), -1)

            if self.prev_x is None or self.prev_y is None:
                self.prev_x, self.prev_y = x, y
                self._push_undo()

            cv2.line(
                self.canvas,
                (self.prev_x, self.prev_y),
                (x, y),
                self.color,
                self.brush_thickness
            )

            self.prev_x, self.prev_y = x, y
        else:
            self.prev_x, self.prev_y = None, None

    def merge(self, frame):
        if self.canvas is None:
            return frame
        # Where canvas has something -> take it, else take frame.
        gray = cv2.cvtColor(self.canvas, cv2.COLOR_BGR2GRAY)
        _, mask = cv2.threshold(gray, 1, 255, cv2.THRESH_BINARY)
        inv = cv2.bitwise_not(mask)

        bg = cv2.bitwise_and(frame, frame, mask=inv)
        fg = cv2.bitwise_and(self.canvas, self.canvas, mask=mask)
        return cv2.add(bg, fg)