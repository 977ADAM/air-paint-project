from dataclasses import dataclass
import json
import logging
import time
from pathlib import Path
from typing import Callable, Dict, List, Optional, Sequence, Tuple

@dataclass
class Gesture:
    name: str
    pattern: Sequence[int]
    handler: Callable[["Painter"], None]
    cooldown: float = 0.8  # seconds (monotonic)

class GestureController:
    def __init__(self, clock: Callable[[], float] = time.monotonic):
        self._clock = clock
        self.default_cooldown = 0.8  # seconds (monotonic)
        self.global_cooldown = 0.0  # global min cooldown (monotonic)
        self._last_global_trigger_time = 0.0
        self._last_trigger_by_name: Dict[str, float] = {}
        self.colors: List[Tuple[int, int, int]] = [
            (255, 0, 255),
            (0, 255, 0),
            (0, 0, 255),
            (255, 255, 0)
        ]
        self.color_index = 0
        self._gestures_by_name: Dict[str, Gesture] = {}
        self._gestures_by_pattern: Dict[Tuple[int, ...], Gesture] = {}

        # Default registry
        self.register("clear",  [1, 1, 0, 0, 0], self._clear, cooldown=1.2)
        self.register("color",  [0, 1, 1, 0, 0], self._next_color, cooldown=0.5)
        self.register("undo",   [1, 1, 1, 0, 0], self._undo, cooldown=0.8)
        self.register("save",   [0, 1, 1, 1, 0], self._save, cooldown=1.0)
        self.register("brush+", [1, 0, 0, 0, 1], self._brush_plus, cooldown=0.2)
        self.register("brush-", [1, 0, 0, 1, 1], self._brush_minus, cooldown=0.2)

    def register(
        self,
        name: str,
        pattern: Sequence[int],
        handler: Callable[["Painter"], None],
        cooldown: Optional[float] = None,
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

    def set_global_cooldown(self, seconds: float) -> None:
        self.global_cooldown = max(0.0, float(seconds))

    def apply_pattern_overrides(self, overrides: Dict[str, Sequence[int]]) -> None:
        if not isinstance(overrides, dict):
            raise ValueError("Gesture overrides must be a dict: {name: [thumb,index,middle,ring,pinky]}")

        next_patterns: Dict[str, Tuple[int, ...]] = {}
        for name, pattern in overrides.items():
            if name not in self._gestures_by_name:
                raise ValueError(f"Unknown gesture name in overrides: '{name}'")
            p = tuple(int(x) for x in pattern)
            if len(p) != 5:
                raise ValueError(
                    f"Gesture '{name}' must have 5 ints: [thumb,index,middle,ring,pinky]"
                )
            next_patterns[name] = p

        combined_patterns: Dict[str, Tuple[int, ...]] = {
            name: gesture.pattern for name, gesture in self._gestures_by_name.items()
        }
        combined_patterns.update(next_patterns)

        reverse: Dict[Tuple[int, ...], str] = {}
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

    def handle(self, fingers: Sequence[int], painter: "Painter") -> Optional[str]:
        gesture = self._detect_gesture(fingers)
        if not gesture:
            return None
        
        now = self._clock()
        if now - self._last_global_trigger_time < self.global_cooldown:
            return None
        last_for_gesture = self._last_trigger_by_name.get(gesture.name, 0.0)
        if now - last_for_gesture < gesture.cooldown:
            return None

        gesture.handler(painter)
        self._last_global_trigger_time = now
        self._last_trigger_by_name[gesture.name] = now
        logging.getLogger("airpaint.gesture").debug(
            "gesture_triggered",
            extra={"event": "gesture_triggered", "gesture": gesture.name},
        )
        return gesture.name

    def _detect_gesture(self, fingers: Sequence[int]) -> Optional[Gesture]:
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
