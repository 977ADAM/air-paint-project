import numpy as np

from painter import Painter, PainterConfig


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