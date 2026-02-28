import numpy as np
import math

from airpaint.painter import Painter, PainterConfig


class LM:
    def __init__(self, x, y):
        self.x = x
        self.y = y


class Landmarks:
    def __init__(self, x, y):
        self.landmark = [LM(0.0, 0.0) for _ in range(21)]
        self.landmark[8] = LM(x, y)


def test_draw_and_undo():
    frame = np.zeros((100, 100, 3), dtype=np.uint8)
    p = Painter(PainterConfig())
    p.init_canvas(frame)

    p.draw(frame, Landmarks(0.2, 0.2), [0, 1, 0, 0, 0])
    p.draw(frame, Landmarks(0.3, 0.3), [0, 1, 0, 0, 0])
    assert np.count_nonzero(p.canvas) > 0

    p.undo()
    assert np.count_nonzero(p.canvas) == 0


def test_clamps_out_of_range_coords():
    frame = np.zeros((100, 100, 3), dtype=np.uint8)
    p = Painter(PainterConfig())
    p.init_canvas(frame)

    # Should not crash even if MediaPipe returns coords outside [0..1]
    p.draw(frame, Landmarks(1.2, -0.1), [0, 1, 0, 0, 0])


def _run_stroke(p: Painter, frame, points):
    for x, y in points:
        p.draw(frame, Landmarks(x, y), [0, 1, 0, 0, 0])
    p.draw(frame, Landmarks(points[-1][0], points[-1][1]), [0, 0, 0, 0, 0])


def test_shape_snap_circle():
    frame = np.zeros((220, 220, 3), dtype=np.uint8)
    p = Painter(PainterConfig(smooth_factor=1.0, brush_thickness=2))
    p.init_canvas(frame)

    points = []
    for i in range(24):
        t = (2 * math.pi * i) / 24
        points.append((0.5 + 0.20 * math.cos(t), 0.5 + 0.20 * math.sin(t)))
    points.append(points[0])
    _run_stroke(p, frame, points)
    assert p.last_shape_snap == "circle"


def test_shape_snap_rectangle():
    frame = np.zeros((220, 220, 3), dtype=np.uint8)
    p = Painter(PainterConfig(smooth_factor=1.0, brush_thickness=2))
    p.init_canvas(frame)

    points = [
        (0.30, 0.30), (0.50, 0.30), (0.70, 0.30),
        (0.70, 0.50), (0.70, 0.70),
        (0.50, 0.70), (0.30, 0.70),
        (0.30, 0.50), (0.30, 0.30),
    ]
    _run_stroke(p, frame, points)
    assert p.last_shape_snap == "rectangle"


def test_shape_snap_arrow():
    frame = np.zeros((220, 220, 3), dtype=np.uint8)
    p = Painter(PainterConfig(smooth_factor=1.0, brush_thickness=2))
    p.init_canvas(frame)

    points = [
        (0.20, 0.50), (0.32, 0.50), (0.44, 0.50), (0.56, 0.50), (0.68, 0.50), (0.78, 0.50),
        (0.70, 0.44), (0.78, 0.50), (0.70, 0.56), (0.78, 0.50),
    ]
    _run_stroke(p, frame, points)
    assert p.last_shape_snap == "arrow"
