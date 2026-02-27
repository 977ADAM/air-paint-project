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


def test_global_cooldown():
    t = {"now": 100.0}
    gc = GestureController(clock=lambda: t["now"])
    gc.set_global_cooldown(0.5)

    painter = FakePainter()
    hits = {"n": 0}

    def handler(p):
        hits["n"] += 1

    gc.register("ping", [0, 0, 0, 0, 0], handler, cooldown=0.0)

    gc.handle([0, 0, 0, 0, 0], painter)
    assert hits["n"] == 1

    t["now"] = 100.1
    gc.handle([0, 0, 0, 0, 0], painter)
    assert hits["n"] == 1  # blocked by global cooldown

    t["now"] = 100.6
    gc.handle([0, 0, 0, 0, 0], painter)
    assert hits["n"] == 2


def test_per_gesture_cooldown_is_independent():
    t = {"now": 100.0}
    gc = GestureController(clock=lambda: t["now"])

    painter = FakePainter()
    hits = {"a": 0, "b": 0}

    gc.register("a", [0, 0, 0, 0, 0], lambda p: hits.__setitem__("a", hits["a"] + 1), cooldown=1.0)
    gc.register("b", [1, 0, 0, 0, 0], lambda p: hits.__setitem__("b", hits["b"] + 1), cooldown=1.0)

    gc.handle([0, 0, 0, 0, 0], painter)
    assert hits["a"] == 1
    assert hits["b"] == 0

    # 'a' is on cooldown, but 'b' should still work.
    t["now"] = 100.2
    gc.handle([0, 0, 0, 0, 0], painter)
    gc.handle([1, 0, 0, 0, 0], painter)
    assert hits["a"] == 1
    assert hits["b"] == 1


def test_pattern_overrides_from_dict():
    gc = GestureController()

    # default "clear" is [1,1,0,0,0], after override becomes [0,0,0,0,0]
    gc.apply_pattern_overrides({"clear": [0, 0, 0, 0, 0]})
    g = gc._detect_gesture([0, 0, 0, 0, 0])  # internal check for registry mapping
    assert g is not None
    assert g.name == "clear"


def test_pattern_overrides_reject_collision():
    gc = GestureController()
    with pytest.raises(ValueError):
        # "undo" cannot share "clear" pattern
        gc.apply_pattern_overrides({"undo": [1, 1, 0, 0, 0]})


def test_default_brush_plus_does_not_conflict_with_draw_pattern():
    gc = GestureController()
    draw_pattern = [0, 1, 0, 0, 0]
    detected = gc._detect_gesture(draw_pattern)
    assert detected is None or detected.name != "brush+"
