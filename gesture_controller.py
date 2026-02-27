from dataclasses import dataclass, field
import time
from typing import Callable, Dict, List, Optional, Sequence, Tuple, Mapping

@dataclass
class Gesture:
    name: str
    pattern: Sequence[int]
    handler: Callable[["Painter"], None]
    cooldown: float = 0.8  # seconds (monotonic)

class GestureController:
    def __init__(self):
        self.last_gesture_time = 0.0
        self.default_cooldown = 0.8  # seconds (monotonic)
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
        self.register("brush+", [0, 1, 0, 0, 0], self._brush_plus, cooldown=0.2)
        self.register("brush-", [0, 1, 0, 0, 1], self._brush_minus, cooldown=0.2)

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
        g = Gesture(name=name, pattern=p, handler=handler, cooldown=float(cooldown or self.default_cooldown))
        self._gestures_by_name[name] = g
        self._gestures_by_pattern[p] = g

    def handle(self, fingers: Sequence[int], painter: "Painter") -> None:
        gesture = self._detect_gesture(fingers)
        if not gesture:
            return

        now = time.monotonic()
        if now - self.last_gesture_time < gesture.cooldown:
            return

        gesture.handler(painter)

        self.last_gesture_time = now

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