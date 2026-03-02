from __future__ import annotations

from dataclasses import dataclass

import cv2
import mediapipe as mp  # type: ignore[import-untyped]


@dataclass(frozen=True)
class HandTrackerConfig:
    max_hands: int = 1
    model_complexity: int = 0
    min_detection_confidence: float = 0.5
    min_tracking_confidence: float = 0.5
    input_scale: float = 1.0


class HandTracker:
    def __init__(self, config: HandTrackerConfig | None = None):
        self.config = config or HandTrackerConfig()
        self.mp_hands = mp.solutions.hands
        self.hands = self.mp_hands.Hands(
            static_image_mode=False,
            max_num_hands=self.config.max_hands,
            model_complexity=self.config.model_complexity,
            min_detection_confidence=self.config.min_detection_confidence,
            min_tracking_confidence=self.config.min_tracking_confidence,
        )
        self.mp_draw = mp.solutions.drawing_utils

    def __enter__(self) -> HandTracker:
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()

    def close(self) -> None:
        if self.hands is not None:
            try:
                self.hands.close()
            finally:
                self.hands = None

    def detect(self, frame) -> tuple[object, object] | None:
        if self.hands is None:
            return None
        scale = min(1.0, max(0.2, float(self.config.input_scale)))
        src = frame
        if scale < 1.0:
            src = cv2.resize(frame, None, fx=scale, fy=scale, interpolation=cv2.INTER_LINEAR)
        rgb = cv2.cvtColor(src, cv2.COLOR_BGR2RGB)
        result = self.hands.process(rgb)

        if result.multi_hand_landmarks and result.multi_handedness:
            return result.multi_hand_landmarks[0], result.multi_handedness[0]

        return None

    def draw_landmarks(self, frame, landmarks) -> None:
        self.mp_draw.draw_landmarks(
            frame,
            landmarks,
            self.mp_hands.HAND_CONNECTIONS
        )

    def fingers_up(self, hand_landmarks, handedness) -> list[int]:
        fingers = []
        tip_ids = [4, 8, 12, 16, 20]

        label = getattr(handedness.classification[0], "label", "Right")
        is_right = (label == "Right")

        if (hand_landmarks.landmark[4].x > hand_landmarks.landmark[3].x) == is_right:
            fingers.append(1)
        else:
            fingers.append(0)

        for i in range(1, 5):
            if hand_landmarks.landmark[tip_ids[i]].y < \
               hand_landmarks.landmark[tip_ids[i] - 2].y:
                fingers.append(1)
            else:
                fingers.append(0)

        return fingers
