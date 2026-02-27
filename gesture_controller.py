from dataclasses import dataclass
import time
from typing import Callable, Dict, List, Optional, Sequence, Tuple

@dataclass
class Gesture:
    name: str
    pattern: Sequence[int]
    handler: Callable[["Painter"], None]

class GestureController:
    def __init__(self):
        self.last_gesture_time = 0.0
        self.cooldown = 0.8  # seconds (monotonic)
        self.colors: List[Tuple[int, int, int]] = [
            (255, 0, 255),
            (0, 255, 0),
            (0, 0, 255),
            (255, 255, 0)
        ]
        self.color_index = 0
        self._gestures: Dict[str, Gesture] = {}

        # Default registry
        self.register("clear", [1, 1, 0, 0, 0], self._clear)
        self.register("color", [0, 1, 1, 0, 0], self._next_color)
        self.register("undo",  [1, 1, 1, 0, 0], self._undo)
        self.register("save",  [0, 1, 1, 1, 0], self._save)
        self.register("brush+", [0, 1, 0, 0, 0], self._brush_plus)
        self.register("brush-", [0, 1, 0, 0, 1], self._brush_minus)

    def register(self, name: str, pattern: Sequence[int], handler: Callable[["Painter"], None]) -> None:
        self._gestures[name] = Gesture(name=name, pattern=list(pattern), handler=handler)

    def handle(self, fingers, painter):
        gesture = self._detect_gesture(fingers)
        if not gesture:
            return

        now = time.monotonic()
        if now - self.last_gesture_time < self.cooldown:
            return

        gesture.handler(painter)

        self.last_gesture_time = now

    def _detect_gesture(self, fingers: Sequence[int]) -> Optional[Gesture]:
        for gesture in self._gestures.values():
            if list(fingers) == list(gesture.pattern):
                return gesture
        return None

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