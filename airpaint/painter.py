from __future__ import annotations

import cv2
import time
import numpy as np
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

@dataclass
class PainterConfig:
    default_color: Tuple[int, int, int] = (255, 0, 255)
    brush_thickness: int = 5
    smooth_factor: float = 0.4
    undo_depth: int = 20
    snapshots_dir: str = "snapshots"


class Painter:
    def __init__(self, config: Optional[PainterConfig] = None):
        self.config = config or PainterConfig()
        self.canvas: Optional[np.ndarray] = None
        self._mask: Optional[np.ndarray] = None
        self._dirty: bool = True
        self.color = self.config.default_color
        self.brush_thickness = int(self.config.brush_thickness)
        self.prev_x: Optional[int] = None
        self.prev_y: Optional[int] = None
        self.smooth_factor = float(max(0.0, min(1.0, self.config.smooth_factor)))
        self._undo_stack: List[np.ndarray] = []
        self._last_saved_frame_idx = 0
        self._last_merged: Optional[np.ndarray] = None
        self._stroke_points: List[Tuple[int, int]] = []
        self.last_shape_snap: Optional[str] = None

    def init_canvas(self, frame):
        if self.canvas is None or self.canvas.shape != frame.shape:
            self.canvas = np.zeros_like(frame)
            self._mask = np.zeros(frame.shape[:2], dtype=np.uint8)
            self._dirty = True
            self.prev_x = None
            self.prev_y = None

    def set_color(self, color):
        self.color = color

    def set_brush_thickness(self, value: int) -> None:
        self.brush_thickness = int(max(1, min(50, value)))

    def clear(self):
        if self.canvas is not None:
            self._push_undo()
            self.canvas[:] = 0
            self.prev_x = None
            self.prev_y = None
            self._dirty = True

 
    def undo(self) -> None:
        if not self._undo_stack or self.canvas is None:
            return
        self.canvas = self._undo_stack.pop()
        self.prev_x = None
        self.prev_y = None
        self._dirty = True

    def _push_undo(self, *, allow_empty: bool = False) -> None:
        if self.canvas is None:
            return
        if not allow_empty and not np.any(self.canvas):
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
        ts = time.strftime("%Y%m%d_%H%M%S")
        path = out_dir / f"airpaint_{ts}_{self._last_saved_frame_idx:04d}.png"
        img = self._last_merged if (merged and self._last_merged is not None) else self.canvas
        cv2.imwrite(str(path), img)
        return path

    def draw(self, frame, landmarks, fingers):
        h, w, _ = frame.shape

        if not isinstance(fingers, (list, tuple)) or len(fingers) != 5:
            return

        x = int(landmarks.landmark[8].x * w)
        y = int(landmarks.landmark[8].y * h)

        x = max(0, min(w - 1, x))
        y = max(0, min(h - 1, y))

        if self.prev_x is not None and self.prev_y is not None:
            x = int(self.prev_x * (1 - self.smooth_factor) + x * self.smooth_factor)
            y = int(self.prev_y * (1 - self.smooth_factor) + y * self.smooth_factor)

        if fingers[1] == 1 and sum(fingers) == 1:
            cv2.circle(frame, (x, y), 10, (0, 255, 0), -1)

            if self.prev_x is None or self.prev_y is None:
                self.prev_x, self.prev_y = x, y
                self._push_undo(allow_empty=True)
                self._stroke_points = [(x, y)]
                self.last_shape_snap = None

            cv2.line(
                self.canvas,
                (self.prev_x, self.prev_y),
                (x, y),
                self.color,
                self.brush_thickness
            )
            self._dirty = True

            self._stroke_points.append((x, y))
            self.prev_x, self.prev_y = x, y
        else:
            if self.prev_x is not None and self.prev_y is not None:
                self._finalize_stroke_shape()
            self.prev_x, self.prev_y = None, None
            self._stroke_points = []

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

    def _finalize_stroke_shape(self) -> None:
        if self.canvas is None or len(self._stroke_points) < 8 or not self._undo_stack:
            return

        shape = self._detect_shape(self._stroke_points)
        if not shape:
            return

        base = self._undo_stack[-1].copy()
        self._draw_ideal_shape(base, shape)
        self.canvas = base
        self._dirty = True
        self.last_shape_snap = str(shape["kind"])

    def _detect_shape(self, points: List[Tuple[int, int]]) -> Optional[Dict[str, object]]:
        pts = np.array(points, dtype=np.float32)
        if pts.shape[0] < 8:
            return None

        x_min, y_min = np.min(pts, axis=0)
        x_max, y_max = np.max(pts, axis=0)
        bbox_w = float(x_max - x_min)
        bbox_h = float(y_max - y_min)
        diag = float(np.hypot(bbox_w, bbox_h))
        if diag < 20:
            return None

        seg = pts[1:] - pts[:-1]
        path_len = float(np.sum(np.linalg.norm(seg, axis=1)))
        if path_len < diag * 1.1:
            return None

        start = pts[0]
        end = pts[-1]
        closed = float(np.linalg.norm(end - start)) <= max(12.0, diag * 0.12)

        if closed:
            candidates: List[Dict[str, object]] = []
            circle = self._detect_circle(pts)
            if circle:
                candidates.append(circle)
            rect = self._detect_rectangle(pts)
            if rect:
                candidates.append(rect)
            if not candidates:
                return None
            return min(candidates, key=lambda c: float(c["score"]))

        return self._detect_arrow(pts)

    def _detect_circle(self, pts: np.ndarray) -> Optional[Dict[str, object]]:
        (cx, cy), r = cv2.minEnclosingCircle(pts)
        if r < 8:
            return None
        center = np.array([cx, cy], dtype=np.float32)
        dists = np.linalg.norm(pts - center, axis=1)
        radial_error = float(np.sqrt(np.mean((dists - r) ** 2)) / r)
        if radial_error > 0.18:
            return None
        return {
            "kind": "circle",
            "center": (int(round(cx)), int(round(cy))),
            "radius": int(round(r)),
            "score": radial_error,
        }

    def _detect_rectangle(self, pts: np.ndarray) -> Optional[Dict[str, object]]:
        contour = pts.reshape(-1, 1, 2)
        peri = float(cv2.arcLength(contour, True))
        if peri < 40:
            return None
        approx = cv2.approxPolyDP(contour, 0.04 * peri, True)
        if len(approx) != 4:
            return None

        corners = approx.reshape(-1, 2).astype(np.int32)
        area = abs(float(cv2.contourArea(corners)))
        x, y, w, h = cv2.boundingRect(corners)
        if w < 14 or h < 14:
            return None
        rect_area = float(w * h)
        fill_ratio = area / rect_area if rect_area > 0 else 0.0
        if fill_ratio < 0.55:
            return None
        return {
            "kind": "rectangle",
            "corners": corners,
            "score": 1.0 - fill_ratio,
        }

    def _detect_arrow(self, pts: np.ndarray) -> Optional[Dict[str, object]]:
        if pts.shape[0] < 8:
            return None
        start = pts[0]
        end = pts[-1]
        vec = end - start
        length = float(np.linalg.norm(vec))
        if length < 30:
            return None

        unit = vec / max(1e-6, length)
        rel = pts - start
        proj = rel[:, 0] * unit[0] + rel[:, 1] * unit[1]
        perp = np.abs(rel[:, 0] * unit[1] - rel[:, 1] * unit[0])

        shaft_mask = proj <= 0.75 * length
        head_mask = proj >= 0.75 * length
        if int(np.sum(shaft_mask)) < 4 or int(np.sum(head_mask)) < 2:
            return None

        shaft_dev = float(np.percentile(perp[shaft_mask], 75))
        head_dev = float(np.max(perp[head_mask]))
        if shaft_dev > 0.06 * length:
            return None
        if head_dev < 0.06 * length:
            return None

        return {
            "kind": "arrow",
            "start": (int(round(start[0])), int(round(start[1]))),
            "end": (int(round(end[0])), int(round(end[1]))),
            "score": shaft_dev / max(1e-6, length),
        }

    def _draw_ideal_shape(self, canvas: np.ndarray, shape: Dict[str, object]) -> None:
        kind = str(shape["kind"])
        if kind == "circle":
            center = shape["center"]
            radius = int(shape["radius"])
            cv2.circle(canvas, center, radius, self.color, self.brush_thickness)
            return
        if kind == "rectangle":
            corners = np.array(shape["corners"], dtype=np.int32).reshape(-1, 1, 2)
            cv2.polylines(canvas, [corners], True, self.color, self.brush_thickness)
            return
        if kind == "arrow":
            start = shape["start"]
            end = shape["end"]
            cv2.arrowedLine(canvas, start, end, self.color, self.brush_thickness, tipLength=0.24)
