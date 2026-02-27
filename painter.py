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
        self._mask: Optional[np.ndarray] = None
        self._dirty: bool = True
        self.color = config.default_color
        self.brush_thickness = int(config.brush_thickness)
        self.prev_x: Optional[int] = None
        self.prev_y: Optional[int] = None
        self.smooth_factor = float(config.smooth_factor)
        self._undo_stack: List[np.ndarray] = []
        self._last_saved_frame_idx = 0
        self._last_merged: Optional[np.ndarray] = None

    def init_canvas(self, frame):
        if self.canvas is None:
            self.canvas = np.zeros_like(frame)
            self._mask = np.zeros(frame.shape[:2], dtype=np.uint8)
            self._dirty = True

    def set_color(self, color):
        self.color = color

    def set_brush_thickness(self, value: int) -> None:
        self.brush_thickness = int(max(1, min(50, value)))

    def clear(self):
        if self.canvas is not None:
            self._push_undo()
            self.canvas[:] = 0
            self._dirty = True

 
    def undo(self) -> None:
        if not self._undo_stack or self.canvas is None:
            return
        self.canvas = self._undo_stack.pop()
        self._dirty = True

    def _push_undo(self) -> None:
        if self.canvas is None:
            return
        self._undo_stack.append(self.canvas.copy())
        if len(self._undo_stack) > self.config.undo_depth:
            self._undo_stack.pop(0)

    def save_snapshot(self, *, merged: bool = True) -> Optional[Path]:
        if self.canvas is None:
            return None
        out_dir = Path(self.config.snapshots_dir)
        out_dir.mkdir(parents=True, exist_ok=True)

        self._last_saved_frame_idx += 1
        path = out_dir / f"airpaint_{self._last_saved_frame_idx:04d}.png"
        img = self._last_merged if (merged and self._last_merged is not None) else self.canvas
        cv2.imwrite(str(path), img)
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
            self._dirty = True

            self.prev_x, self.prev_y = x, y
        else:
            self.prev_x, self.prev_y = None, None

    def merge(self, frame):
        if self.canvas is None:
            return frame
        # Recompute mask only when canvas changed
        if self._dirty:
            gray = cv2.cvtColor(self.canvas, cv2.COLOR_BGR2GRAY)
            _, self._mask = cv2.threshold(gray, 1, 255, cv2.THRESH_BINARY)
            self._dirty = False

        inv = cv2.bitwise_not(self._mask)
        bg = cv2.bitwise_and(frame, frame, mask=inv)
        fg = cv2.bitwise_and(self.canvas, self.canvas, mask=self._mask)
        merged = cv2.add(bg, fg)
        self._last_merged = merged
        return merged

    def draw_hud(self, frame) -> None:
        # Small UX: show brush + color
        cv2.rectangle(frame, (10, 40), (220, 95), (0, 0, 0), -1)
        cv2.putText(frame, f"Brush: {self.brush_thickness}",
                    (20, 65), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
        cv2.putText(frame, "Color:",
                    (20, 88), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
        cv2.rectangle(frame, (95, 75), (210, 92), self.color, -1)