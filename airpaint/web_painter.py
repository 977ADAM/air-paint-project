from __future__ import annotations

import json
import time
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

Color = tuple[int, int, int]
Point = tuple[float, float]


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


@dataclass
class Stroke:
    id: int
    color: Color
    thickness: int
    points: list[Point] = field(default_factory=list)


class WebPainterState:
    """State container for browser canvas rendering."""

    def __init__(self, snapshots_dir: str = "snapshots") -> None:
        self.snapshots_dir = snapshots_dir
        self.color: Color = (255, 0, 255)
        self.brush_thickness = 5

        self._strokes: list[Stroke] = []
        self._next_stroke_id = 1
        self._active_stroke_id: int | None = None
        self._revision = 0

    @property
    def revision(self) -> int:
        return self._revision

    def set_color(self, color: Sequence[int]) -> None:
        next_color = (
            int(max(0, min(255, int(color[0])))),
            int(max(0, min(255, int(color[1])))),
            int(max(0, min(255, int(color[2])))),
        )
        if next_color == self.color:
            return
        self.color = next_color
        self._touch()

    def set_brush_thickness(self, value: int) -> None:
        next_value = int(max(1, min(50, int(value))))
        if next_value == self.brush_thickness:
            return
        self.brush_thickness = next_value
        self._touch()

    def clear(self) -> None:
        if not self._strokes and self._active_stroke_id is None:
            return
        self._strokes = []
        self._active_stroke_id = None
        self._touch()

    def undo(self) -> None:
        if self._active_stroke_id is not None:
            self._active_stroke_id = None
        if not self._strokes:
            return
        self._strokes.pop()
        self._touch()

    def save_snapshot(self, *, merged: bool = True) -> Path | None:
        del merged
        out_dir = Path(self.snapshots_dir)
        out_dir.mkdir(parents=True, exist_ok=True)

        ts = time.strftime("%Y%m%d_%H%M%S")
        path = out_dir / f"airpaint_web_{ts}_{self._revision:04d}.json"
        payload = {
            "version": 1,
            "saved_at": ts,
            "canvas": self.snapshot(),
        }
        path.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
        return path

    def end_stroke(self) -> None:
        if self._active_stroke_id is None:
            return
        self._active_stroke_id = None
        self._touch()

    def update_from_landmarks(self, landmarks, fingers: Sequence[int]) -> dict[str, Any]:
        index_tip = landmarks.landmark[8]
        x = _clamp01(index_tip.x)
        y = _clamp01(index_tip.y)

        is_drawing = (
            isinstance(fingers, (list, tuple))
            and len(fingers) == 5
            and int(fingers[1]) == 1
            and sum(int(v) for v in fingers) == 1
        )

        if is_drawing:
            self._append_point(x, y)
        else:
            self.end_stroke()

        return {"x": x, "y": y, "drawing": is_drawing}

    def hud_state(self) -> dict[str, Any]:
        return {
            "color": list(self.color),
            "brush_thickness": self.brush_thickness,
            "stroke_count": len(self._strokes),
            "revision": self._revision,
        }

    def snapshot(self) -> dict[str, Any]:
        return {
            "revision": self._revision,
            "active_stroke_id": self._active_stroke_id,
            "color": list(self.color),
            "brush_thickness": self.brush_thickness,
            "strokes": [
                {
                    "id": stroke.id,
                    "color": list(stroke.color),
                    "thickness": stroke.thickness,
                    "points": [{"x": x, "y": y} for x, y in stroke.points],
                }
                for stroke in self._strokes
            ],
        }

    def _append_point(self, x: float, y: float) -> None:
        stroke = self._ensure_active_stroke()
        if stroke.points:
            last_x, last_y = stroke.points[-1]
            if abs(last_x - x) < 0.0015 and abs(last_y - y) < 0.0015:
                return
        stroke.points.append((x, y))
        self._touch()

    def _ensure_active_stroke(self) -> Stroke:
        if self._active_stroke_id is not None:
            for stroke in self._strokes:
                if stroke.id == self._active_stroke_id:
                    return stroke

        stroke = Stroke(
            id=self._next_stroke_id,
            color=self.color,
            thickness=self.brush_thickness,
            points=[],
        )
        self._next_stroke_id += 1
        self._active_stroke_id = stroke.id
        self._strokes.append(stroke)
        self._touch()
        return stroke

    def _touch(self) -> None:
        self._revision += 1
