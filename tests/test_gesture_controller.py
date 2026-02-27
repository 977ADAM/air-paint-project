import time

import pytest

from gesture_controller import GestureController


class FakePainter:
    def __init__(self):
        self.calls = []
        self.brush_thickness = 5

    def clear(self):
        self.calls.append("clear")

    def set_color(self, color):
        self.calls.append(("color", color))

    def undo(self):
        self.calls.append("undo")

    def save_snapshot(self, *args, **kwargs):
        self.calls.append("save")

    def set_brush_thickness(self, v):
        self.brush_thickness = v
        self.calls.append(("brush", v))


def test_register_validates_pattern_len():
    gc = GestureController()
    with pytest.raises(ValueError):
        gc.register("bad", [1, 2, 3], lambda p: None)


def test_global_cooldown(monkeypatch):
    t = 100.0

    def fake_monotonic():
        return t

    monkeypatch.setattr(time, "monotonic", fake_monotonic)

    gc = GestureController()
    gc.set_global_cooldown(0.5)

    painter = FakePainter()
    hits = {"n": 0}

    def handler(p):
        hits["n"] += 1

    gc.register("ping", [0, 0, 0, 0, 0], handler, cooldown=0.0)

    gc.handle([0, 0, 0, 0, 0], painter)
    assert hits["n"] == 1

    t = 100.1
    gc.handle([0, 0, 0, 0, 0], painter)
    assert hits["n"] == 1  # blocked by global cooldown

    t = 100.6
    gc.handle([0, 0, 0, 0, 0], painter)
    assert hits["n"] == 2