from __future__ import annotations

import base64
import binascii
from dataclasses import dataclass
from typing import Any

import cv2
import numpy as np

from .gesture_controller import GestureController
from .hand_tracker import HandTracker, HandTrackerConfig
from .web_painter import WebPainterState

DEFAULT_COLORS = [
    (255, 0, 255),
    (0, 255, 0),
    (0, 0, 255),
    (255, 255, 0),
]


@dataclass(frozen=True)
class WebRuntimeConfig:
    snapshots_dir: str = "snapshots"
    cooldown: float = 0.0
    gesture_map: str | None = None
    max_hands: int = 1
    model_complexity: int = 0
    min_detection_confidence: float = 0.5
    min_tracking_confidence: float = 0.5
    tracker_scale: float = 0.6


class WebSessionRuntime:
    def __init__(
        self,
        config: WebRuntimeConfig | None = None,
        *,
        tracker=None,
        gestures=None,
        painter: WebPainterState | None = None,
    ) -> None:
        self.config = config or WebRuntimeConfig()
        self._owns_tracker = tracker is None

        self.tracker = tracker or HandTracker(
            HandTrackerConfig(
                max_hands=self.config.max_hands,
                model_complexity=self.config.model_complexity,
                min_detection_confidence=self.config.min_detection_confidence,
                min_tracking_confidence=self.config.min_tracking_confidence,
                input_scale=self.config.tracker_scale,
            )
        )
        self.gestures = gestures or GestureController()
        self.gestures.set_global_cooldown(self.config.cooldown)
        if self.config.gesture_map:
            self.gestures.load_pattern_overrides_from_file(self.config.gesture_map)

        self.painter = painter or WebPainterState(snapshots_dir=self.config.snapshots_dir)

    def close(self) -> None:
        if self._owns_tracker and hasattr(self.tracker, "close"):
            self.tracker.close()

    def snapshot_state(self) -> dict[str, Any]:
        return {
            "canvas": self.painter.snapshot(),
            "hud": self.painter.hud_state(),
        }

    def handle_command(self, command: str, value: Any = None) -> dict[str, Any]:
        saved_path = None
        if command == "clear":
            self.painter.clear()
        elif command == "undo":
            self.painter.undo()
        elif command == "save":
            path = self.painter.save_snapshot(merged=False)
            saved_path = str(path) if path else None
        elif command == "color-next":
            self._cycle_color()
        elif command == "brush-plus":
            self.painter.set_brush_thickness(self.painter.brush_thickness + 1)
        elif command == "brush-minus":
            self.painter.set_brush_thickness(self.painter.brush_thickness - 1)
        elif command == "brush-set":
            if value is None:
                raise ValueError("Command 'brush-set' requires numeric 'value'")
            self.painter.set_brush_thickness(int(value))
        else:
            raise ValueError(f"Unsupported command: {command}")

        return {
            "ok": True,
            "command": command,
            "saved_path": saved_path,
            **self.snapshot_state(),
        }

    def process_base64_frame(self, image_data: str) -> dict[str, Any]:
        frame = decode_base64_frame(image_data)
        if frame is None:
            raise ValueError("Invalid base64 image payload")
        return self.process_frame(frame)

    def process_frame(self, frame: np.ndarray) -> dict[str, Any]:
        detection = self.tracker.detect(frame)

        landmarks = None
        handedness = None
        fingers = None
        gesture = None
        feedback = None
        pointer = None

        if detection:
            landmarks, handedness = detection
            fingers = self.tracker.fingers_up(landmarks, handedness)
            gesture = self.gestures.handle(fingers, self.painter, landmarks=landmarks)
            feedback = self.gestures.get_live_feedback()
            pointer = self.painter.update_from_landmarks(landmarks, fingers)
        else:
            self.painter.end_stroke()

        return {
            "frame": {
                "width": int(frame.shape[1]),
                "height": int(frame.shape[0]),
            },
            "landmarks": serialize_landmarks(landmarks),
            "handedness": serialize_handedness(handedness),
            "fingers": [int(v) for v in fingers] if fingers is not None else None,
            "gesture": gesture,
            "feedback": serialize_feedback(feedback),
            "pointer": pointer,
            **self.snapshot_state(),
        }

    def _cycle_color(self) -> None:
        colors = [tuple(int(v) for v in c) for c in getattr(self.gestures, "colors", DEFAULT_COLORS)]
        if not colors:
            colors = DEFAULT_COLORS

        current = tuple(int(v) for v in self.painter.color)
        try:
            idx = colors.index(current)
        except ValueError:
            idx = -1

        next_idx = (idx + 1) % len(colors)
        self.painter.set_color(colors[next_idx])
        if hasattr(self.gestures, "color_index"):
            self.gestures.color_index = next_idx


def decode_base64_frame(image_data: str) -> np.ndarray | None:
    if not image_data:
        return None

    encoded = image_data
    if image_data.startswith("data:image") and "," in image_data:
        encoded = image_data.split(",", 1)[1]

    try:
        raw = base64.b64decode(encoded, validate=True)
    except (binascii.Error, ValueError):
        try:
            raw = base64.b64decode(encoded)
        except (binascii.Error, ValueError):
            return None

    array = np.frombuffer(raw, dtype=np.uint8)
    if array.size == 0:
        return None

    frame = cv2.imdecode(array, cv2.IMREAD_COLOR)
    return frame


def serialize_landmarks(landmarks) -> list[dict[str, float]] | None:
    if landmarks is None:
        return None
    return [
        {
            "x": float(lm.x),
            "y": float(lm.y),
            "z": float(getattr(lm, "z", 0.0)),
        }
        for lm in landmarks.landmark
    ]


def serialize_handedness(handedness) -> dict[str, Any] | None:
    if handedness is None:
        return None

    classification = getattr(handedness, "classification", None)
    if not classification:
        return None

    entry = classification[0]
    return {
        "label": str(getattr(entry, "label", "Unknown")),
        "score": float(getattr(entry, "score", 0.0)),
    }


def serialize_feedback(feedback: tuple[str, float | None] | None) -> dict[str, Any] | None:
    if not feedback:
        return None
    label, progress = feedback
    payload: dict[str, Any] = {"label": str(label)}
    if progress is not None:
        payload["progress"] = float(progress)
    return payload
