import pytest

from airpaint.gesture_controller import GestureController


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


class _LM:
    def __init__(self, x=0.0, y=0.0):
        self.x = x
        self.y = y


class _Landmarks:
    def __init__(self, thumb_x, thumb_y, index_x, index_y):
        self.landmark = [_LM() for _ in range(21)]
        self.landmark[4] = _LM(thumb_x, thumb_y)
        self.landmark[8] = _LM(index_x, index_y)


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


def test_handle_returns_triggered_gesture_name():
    t = {"now": 100.0}
    gc = GestureController(clock=lambda: t["now"])
    painter = FakePainter()

    name = gc.handle([1, 1, 0, 0, 0], painter)
    assert name == "clear"


def test_temporal_pinch_hold_triggers_save():
    t = {"now": 100.0}
    gc = GestureController(clock=lambda: t["now"])
    painter = FakePainter()
    pinch = _Landmarks(0.5, 0.5, 0.52, 0.5)

    assert gc.handle([0, 0, 0, 0, 0], painter, landmarks=pinch) is None
    t["now"] = 100.31
    assert gc.handle([0, 0, 0, 0, 0], painter, landmarks=pinch) == "pinch-hold"
    assert "save" in painter.calls


def test_temporal_pinch_hold_reports_progress_feedback():
    t = {"now": 120.0}
    gc = GestureController(clock=lambda: t["now"])
    painter = FakePainter()
    pinch = _Landmarks(0.5, 0.5, 0.52, 0.5)

    gc.handle([0, 0, 0, 0, 0], painter, landmarks=pinch)
    t["now"] = 120.21
    gc.handle([0, 0, 0, 0, 0], painter, landmarks=pinch)
    feedback = gc.get_live_feedback()

    assert feedback is not None
    label, progress = feedback
    assert label == "pinch-hold"
    assert progress is not None
    assert 0.65 <= progress <= 0.75


def test_temporal_double_tap_triggers_color():
    t = {"now": 200.0}
    gc = GestureController(clock=lambda: t["now"])
    painter = FakePainter()
    pinch = _Landmarks(0.5, 0.5, 0.52, 0.5)
    open_hand = _Landmarks(0.2, 0.2, 0.8, 0.8)

    gc.handle([0, 0, 0, 0, 0], painter, landmarks=pinch)
    t["now"] = 200.05
    gc.handle([0, 0, 0, 0, 0], painter, landmarks=open_hand)
    t["now"] = 200.15
    gc.handle([0, 0, 0, 0, 0], painter, landmarks=pinch)
    t["now"] = 200.20
    assert gc.handle([0, 0, 0, 0, 0], painter, landmarks=open_hand) == "double-tap"
    assert any(call for call in painter.calls if isinstance(call, tuple) and call[0] == "color")


def test_temporal_swipe_left_triggers_undo():
    t = {"now": 300.0}
    gc = GestureController(clock=lambda: t["now"])
    painter = FakePainter()

    l1 = _Landmarks(0.1, 0.1, 0.82, 0.5)
    l2 = _Landmarks(0.1, 0.1, 0.56, 0.52)
    assert gc.handle([0, 1, 0, 0, 0], painter, landmarks=l1) is None
    t["now"] = 300.12
    assert gc.handle([0, 1, 0, 0, 0], painter, landmarks=l2) == "swipe-left"
    assert "undo" in painter.calls
