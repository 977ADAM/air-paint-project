import cv2
import mediapipe as mp


class HandTracker:
    def __init__(self, max_hands=1):
        self.mp_hands = mp.solutions.hands
        self.hands = self.mp_hands.Hands(
            static_image_mode=False,
            max_num_hands=max_hands,
            model_complexity=1,
            min_detection_confidence=0.7,
            min_tracking_confidence=0.7
        )
        self.mp_draw = mp.solutions.drawing_utils

    def detect(self, frame):
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        result = self.hands.process(rgb)

        if result.multi_hand_landmarks:
            return result.multi_hand_landmarks[0], result.multi_handedness[0]

        return None

    def draw_landmarks(self, frame, landmarks):
        self.mp_draw.draw_landmarks(
            frame,
            landmarks,
            self.mp_hands.HAND_CONNECTIONS
        )

    def fingers_up(self, hand_landmarks, handedness):
        fingers = []
        tip_ids = [4, 8, 12, 16, 20]

        is_right = handedness.classification[0].label == "Right"

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