import cv2
import numpy as np


class Painter:
    def __init__(self):
        self.canvas = None
        self.color = (255, 0, 255)
        self.brush_thickness = 5
        self.prev_x = None
        self.prev_y = None
        self.smooth_factor = 0.4

    def init_canvas(self, frame):
        if self.canvas is None:
            self.canvas = np.zeros_like(frame)

    def set_color(self, color):
        self.color = color

    def clear(self):
        if self.canvas is not None:
            self.canvas[:] = 0

    def draw(self, frame, landmarks, fingers):
        h, w, _ = frame.shape

        x = int(landmarks.landmark[8].x * w)
        y = int(landmarks.landmark[8].y * h)

        if self.prev_x is not None and self.prev_y is not None:
            x = int(self.prev_x * (1 - self.smooth_factor) + x * self.smooth_factor)
            y = int(self.prev_y * (1 - self.smooth_factor) + y * self.smooth_factor)

        if fingers[1] == 1 and sum(fingers) == 1:
            cv2.circle(frame, (x, y), 10, (0, 255, 0), -1)

            if self.prev_x is None or self.prev_y is None:
                self.prev_x, self.prev_y = x, y

            cv2.line(
                self.canvas,
                (self.prev_x, self.prev_y),
                (x, y),
                self.color,
                self.brush_thickness
            )

            self.prev_x, self.prev_y = x, y
        else:
            self.prev_x, self.prev_y = None, None

    def merge(self, frame):
        return cv2.addWeighted(frame, 1.0, self.canvas, 1.0, 0)