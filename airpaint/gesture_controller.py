from __future__ import annotations

import json
import logging
import math
import time
from collections import deque
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .main import PainterLike
    from .painter import Painter


@dataclass
class Gesture:
    name: str
    pattern: Sequence[int]
    handler: Callable[[Painter], None]
    cooldown: float = 0.8  # seconds (monotonic)

class GestureController:
    def __init__(self, clock: Callable[[], float] = time.monotonic):
        self._clock = clock
        self.default_cooldown = 0.8  # seconds (monotonic)
        self.global_cooldown = 0.0  # global min cooldown (monotonic)
        self._last_global_trigger_time = 0.0
        self._last_trigger_by_name: dict[str, float] = {}
        self.colors: list[tuple[int, int, int]] = [
            (255, 0, 255),
            (0, 255, 0),
            (0, 0, 255),
            (255, 255, 0)
        ]
        self.color_index = 0
        self._gestures_by_name: dict[str, Gesture] = {}
        self._gestures_by_pattern: dict[tuple[int, ...], Gesture] = {}
        self._temporal_by_name: dict[str, Gesture] = {}

        # Temporal state machine
        self._pinch_active = False
        self._pinch_start_time = 0.0
        self._pinch_hold_fired = False
        self._last_tap_time = 0.0
        self._tap_count = 0
        self._index_history: deque[tuple[float, float, float]] = deque()
        self._live_feedback: tuple[str, float | None] | None = None

        # Default registry
        self.register("clear",  [1, 1, 0, 0, 0], self._clear, cooldown=1.2)
        self.register("color",  [0, 1, 1, 0, 0], self._next_color, cooldown=0.5)
        self.register("undo",   [1, 1, 1, 0, 0], self._undo, cooldown=0.8)
        self.register("save",   [0, 1, 1, 1, 0], self._save, cooldown=1.0)
        self.register("brush+", [1, 0, 0, 0, 1], self._brush_plus, cooldown=0.2)
        self.register("brush-", [1, 0, 0, 1, 1], self._brush_minus, cooldown=0.2)
        self.register_temporal("pinch-hold", self._save, cooldown=1.0)
        self.register_temporal("swipe-left", self._undo, cooldown=0.7)
        self.register_temporal("double-tap", self._next_color, cooldown=0.4)

    def register(
        self,
        name: str,
        pattern: Sequence[int],
        handler: Callable[[Painter], None],
        cooldown: float | None = None,
    ) -> None:
        p = tuple(int(x) for x in pattern)
        if len(p) != 5:
            raise ValueError("Gesture pattern must have 5 ints: [thumb,index,middle,ring,pinky]")

        if name in self._gestures_by_name:
            raise ValueError(f"Gesture '{name}' already registered")

        if p in self._gestures_by_pattern:
            raise ValueError(f"Gesture pattern {p} already registered")

        cd = float(self.default_cooldown if cooldown is None else cooldown)
        g = Gesture(name=name, pattern=p, handler=handler, cooldown=cd)
        self._gestures_by_name[name] = g
        self._gestures_by_pattern[p] = g

    def register_temporal(
        self,
        name: str,
        handler: Callable[[Painter], None],
        cooldown: float | None = None,
    ) -> None:
        if name in self._gestures_by_name or name in self._temporal_by_name:
            raise ValueError(f"Gesture '{name}' already registered")
        cd = float(self.default_cooldown if cooldown is None else cooldown)
        self._temporal_by_name[name] = Gesture(name=name, pattern=(), handler=handler, cooldown=cd)

    def set_global_cooldown(self, seconds: float) -> None:
        self.global_cooldown = max(0.0, float(seconds))

    def apply_pattern_overrides(self, overrides: dict[str, Sequence[int]]) -> None:
        if not isinstance(overrides, dict):
            raise ValueError("Gesture overrides must be a dict: {name: [thumb,index,middle,ring,pinky]}")

        next_patterns: dict[str, tuple[int, ...]] = {}
        for name, pattern in overrides.items():
            if name not in self._gestures_by_name:
                raise ValueError(f"Unknown gesture name in overrides: '{name}'")
            p = tuple(int(x) for x in pattern)
            if len(p) != 5:
                raise ValueError(
                    f"Gesture '{name}' must have 5 ints: [thumb,index,middle,ring,pinky]"
                )
            next_patterns[name] = p

        combined_patterns: dict[str, tuple[int, ...]] = {
            name: gesture.pattern for name, gesture in self._gestures_by_name.items()
        }
        combined_patterns.update(next_patterns)

        reverse: dict[tuple[int, ...], str] = {}
        for name, pattern in combined_patterns.items():
            other = reverse.get(pattern)
            if other is not None:
                raise ValueError(
                    f"Pattern collision: '{name}' and '{other}' share pattern {pattern}"
                )
            reverse[pattern] = name

        for name, pattern in next_patterns.items():
            gesture = self._gestures_by_name[name]
            self._gestures_by_name[name] = Gesture(
                name=gesture.name,
                pattern=pattern,
                handler=gesture.handler,
                cooldown=gesture.cooldown,
            )

        self._gestures_by_pattern = {
            gesture.pattern: gesture for gesture in self._gestures_by_name.values()
        }

    def load_pattern_overrides_from_file(self, path: str) -> None:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        self.apply_pattern_overrides(data)

    def handle(self, fingers: Sequence[int], painter: PainterLike, landmarks=None) -> str | None:
        self._live_feedback = None
        temporal = self._detect_temporal_gesture(fingers, landmarks)
        if temporal and self._can_trigger(temporal):
            temporal.handler(painter)
            self._after_trigger(temporal)
            self._live_feedback = (temporal.name, 1.0)
            return temporal.name

        gesture = self._detect_gesture(fingers)
        if not gesture:
            return None
        self._live_feedback = (gesture.name, None)
        if not self._can_trigger(gesture):
            return None

        gesture.handler(painter)
        self._after_trigger(gesture)
        self._live_feedback = (gesture.name, 1.0)
        return gesture.name

    def get_live_feedback(self) -> tuple[str, float | None] | None:
        return self._live_feedback

    def _can_trigger(self, gesture: Gesture) -> bool:
        now = self._clock()
        if now - self._last_global_trigger_time < self.global_cooldown:
            return False
        last_for_gesture = self._last_trigger_by_name.get(gesture.name, 0.0)
        return (now - last_for_gesture) >= gesture.cooldown

    def _after_trigger(self, gesture: Gesture) -> None:
        now = self._clock()
        self._last_global_trigger_time = now
        self._last_trigger_by_name[gesture.name] = now
        logging.getLogger("airpaint.gesture").debug(
            "gesture_triggered",
            extra={"event": "gesture_triggered", "gesture": gesture.name},
        )

    def _detect_temporal_gesture(self, fingers: Sequence[int], landmarks) -> Gesture | None:
        if landmarks is None:
            return None
        now = self._clock()

        pinch = self._update_pinch(now, landmarks)
        if pinch:
            return pinch
        return self._update_swipe(now, fingers, landmarks)

    def _update_pinch(self, now: float, landmarks) -> Gesture | None:
        pinch_distance_threshold = 0.045
        hold_seconds = 0.3
        tap_max_duration = 0.18
        double_tap_gap = 0.3

        thumb = landmarks.landmark[4]
        index = landmarks.landmark[8]
        distance = math.hypot(index.x - thumb.x, index.y - thumb.y)
        is_pinched = distance <= pinch_distance_threshold

        if is_pinched:
            if not self._pinch_active:
                self._pinch_active = True
                self._pinch_start_time = now
                self._pinch_hold_fired = False
            elif not self._pinch_hold_fired and (now - self._pinch_start_time) >= hold_seconds:
                self._pinch_hold_fired = True
                return self._temporal_by_name.get("pinch-hold")
            if not self._pinch_hold_fired:
                progress = min(1.0, max(0.0, (now - self._pinch_start_time) / hold_seconds))
                self._live_feedback = ("pinch-hold", progress)
            return None

        if not self._pinch_active:
            return None

        pinch_duration = now - self._pinch_start_time
        if (not self._pinch_hold_fired) and pinch_duration <= tap_max_duration:
            if now - self._last_tap_time <= double_tap_gap:
                self._tap_count += 1
            else:
                self._tap_count = 1
            self._last_tap_time = now
            if self._tap_count >= 2:
                self._tap_count = 0
                self._pinch_active = False
                return self._temporal_by_name.get("double-tap")

        self._pinch_active = False
        self._pinch_hold_fired = False
        return None

    def _update_swipe(self, now: float, fingers: Sequence[int], landmarks) -> Gesture | None:
        swipe_window_s = 0.22
        swipe_min_dx = 0.20
        swipe_max_dy = 0.12

        is_index_only = isinstance(fingers, (list, tuple)) and len(fingers) == 5 and fingers[1] == 1 and sum(fingers) == 1
        if not is_index_only:
            self._index_history.clear()
            return None

        index = landmarks.landmark[8]
        self._index_history.append((now, float(index.x), float(index.y)))
        while self._index_history and (now - self._index_history[0][0]) > swipe_window_s:
            self._index_history.popleft()

        if len(self._index_history) < 2:
            return None

        _, start_x, start_y = self._index_history[0]
        _, end_x, end_y = self._index_history[-1]
        dx = start_x - end_x
        dy = abs(end_y - start_y)
        if dx > 0 and dy <= swipe_max_dy:
            self._live_feedback = ("swipe-left", min(1.0, dx / swipe_min_dx))
        if dx >= swipe_min_dx and dy <= swipe_max_dy:
            self._index_history.clear()
            return self._temporal_by_name.get("swipe-left")
        return None

    def _detect_gesture(self, fingers: Sequence[int]) -> Gesture | None:
        try:
            key = tuple(int(x) for x in fingers)
        except Exception:
            return None
        return self._gestures_by_pattern.get(key)

    def _clear(self, painter):
        painter.clear()

    def _next_color(self, painter):
        self.color_index = (self.color_index + 1) % len(self.colors)
        painter.set_color(self.colors[self.color_index])

    def _undo(self, painter):
        painter.undo()

    def _save(self, painter):
        painter.save_snapshot()

    def _brush_plus(self, painter):
        painter.set_brush_thickness(painter.brush_thickness + 1)

    def _brush_minus(self, painter):
        painter.set_brush_thickness(painter.brush_thickness - 1)
