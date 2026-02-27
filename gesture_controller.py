import time
from dataclasses import dataclass
from typing import Callable, List

@dataclass
class Gesture:
    name: str
    pattern: List[int]
    handler: Callable

class GestureController:
    def __init__(self):
        self.last_gesture_time = 0
        self.cooldown = 0.8  # seconds
        self.colors = [
            (255, 0, 255),
            (0, 255, 0),
            (0, 0, 255),
            (255, 255, 0)
        ]
        self.color_index = 0
        self.gestures = [
            Gesture("clear", [1,1,0,0,0], self._clear),
            Gesture("color", [0,1,1,0,0], self._next_color),
        ]

    def handle(self, fingers, painter):
        gesture = self._detect_gesture(fingers)
        if not gesture:
            return

        now = time.time()
        if now - self.last_gesture_time < self.cooldown:
            return

        gesture.handler(painter)

        self.last_gesture_time = now

    def _detect_gesture(self, fingers):
        for gesture in self.gestures:
            if fingers == gesture.pattern:
                return gesture
        return None

    def _clear(self, painter):
        painter.clear()

    def _next_color(self, painter):
        self.color_index = (self.color_index + 1) % len(self.colors)
        painter.set_color(self.colors[self.color_index])