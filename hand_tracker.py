from __future__ import annotations

import cv2
import mediapipe as mp
from dataclasses import dataclass
from typing import Optional, Tuple

@dataclass(frozen=True)
class HandTrackerConfig:
    max_hands: int = 1
    model_complexity: int = 1
    min_detection_confidence: float = 0.7
    min_tracking_confidence: float = 0.7


class HandTracker:
    def __init__(self, config: HandTrackerConfig = HandTrackerConfig()):
        self.config = config
        self.mp_hands = mp.solutions.hands
        self.hands = self.mp_hands.Hands(
            static_image_mode=False,
            max_num_hands=config.max_hands,
            model_complexity=config.model_complexity,
            min_detection_confidence=config.min_detection_confidence,
            min_tracking_confidence=config.min_tracking_confidence,
        )
        self.mp_draw = mp.solutions.drawing_utils

    def __enter__(self) -> "HandTracker":
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()

    def close(self) -> None:
        if self.hands is not None:
            try:
                self.hands.close()
            finally:
                self.hands = None

    def detect(self, frame) -> Optional[Tuple[object, object]]:
        if self.hands is None:
            return None
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
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