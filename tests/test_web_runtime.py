import base64

import cv2
import numpy as np
import pytest

from airpaint.web_painter import WebPainterState
from airpaint.web_runtime import WebRuntimeConfig, WebSessionRuntime, decode_base64_frame, serialize_feedback


class FakePoint:
    def __init__(self, x: float, y: float, z: float = 0.0):
        self.x = x
        self.y = y
        self.z = z


class FakeLandmarks:
    def __init__(self, points):
        self.landmark = points


class FakeClass:
    def __init__(self, label: str, score: float):
        self.label = label
        self.score = score


class FakeHandedness:
    def __init__(self, label: str = "Right", score: float = 0.99):
        self.classification = [FakeClass(label, score)]


def make_landmarks(x: float, y: float) -> FakeLandmarks:
    points = [FakePoint(0.0, 0.0, 0.0) for _ in range(21)]
    points[4] = FakePoint(max(0.0, x - 0.05), y, 0.0)
    points[8] = FakePoint(x, y, 0.0)
    return FakeLandmarks(points)


class FakeTracker:
    def detect(self, frame):
        del frame
        return make_landmarks(0.3, 0.4), FakeHandedness()

    def fingers_up(self, landmarks, handedness):
        del landmarks, handedness
        return [0, 1, 0, 0, 0]

    def close(self):
        return None


class FakeGestures:
    colors = [(255, 0, 255), (0, 255, 0)]

    def __init__(self):
        self.color_index = 0

    def set_global_cooldown(self, seconds: float) -> None:
        self.cooldown = seconds

    def handle(self, fingers, painter, landmarks=None):
        del fingers, painter, landmarks
        return "draw"

    def get_live_feedback(self):
        return ("draw", 1.0)


def test_decode_base64_frame_roundtrip():
    frame = np.zeros((24, 32, 3), dtype=np.uint8)
    frame[:, :] = (10, 140, 220)
    ok, encoded = cv2.imencode(".jpg", frame)
    assert ok

    payload = base64.b64encode(encoded.tobytes()).decode("ascii")
    decoded = decode_base64_frame(f"data:image/jpeg;base64,{payload}")

    assert decoded is not None
    assert decoded.shape == frame.shape


def test_web_painter_draw_then_undo_and_clear():
    painter = WebPainterState()

    painter.update_from_landmarks(make_landmarks(0.10, 0.10), [0, 1, 0, 0, 0])
    painter.update_from_landmarks(make_landmarks(0.20, 0.15), [0, 1, 0, 0, 0])
    painter.end_stroke()

    snap = painter.snapshot()
    assert len(snap["strokes"]) == 1
    assert len(snap["strokes"][0]["points"]) >= 2

    painter.undo()
    assert painter.snapshot()["strokes"] == []

    painter.update_from_landmarks(make_landmarks(0.5, 0.5), [0, 1, 0, 0, 0])
    painter.clear()
    assert painter.snapshot()["strokes"] == []


def test_web_session_runtime_process_and_commands():
    runtime = WebSessionRuntime(
        WebRuntimeConfig(),
        tracker=FakeTracker(),
        gestures=FakeGestures(),
    )
    frame = np.zeros((20, 30, 3), dtype=np.uint8)

    payload = runtime.process_frame(frame)

    assert payload["frame"]["width"] == 30
    assert payload["frame"]["height"] == 20
    assert payload["gesture"] == "draw"
    assert payload["fingers"] == [0, 1, 0, 0, 0]
    assert payload["pointer"]["drawing"] is True
    assert len(payload["canvas"]["strokes"]) == 1

    current_color = tuple(runtime.painter.color)
    runtime.handle_command("color-next")
    assert tuple(runtime.painter.color) != current_color

    runtime.handle_command("undo")
    assert runtime.snapshot_state()["canvas"]["strokes"] == []

    with pytest.raises(ValueError):
        runtime.handle_command("unsupported")


def test_serialize_feedback_optional_progress():
    assert serialize_feedback(("pinch", 0.5)) == {"label": "pinch", "progress": 0.5}
    assert serialize_feedback(("swipe", None)) == {"label": "swipe"}
