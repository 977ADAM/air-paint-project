import cv2
import time

try:
    from camera import Camera
    from hand_tracker import HandTracker
    from gesture_controller import GestureController
    from painter import Painter
except ImportError:
    from .camera import Camera
    from .hand_tracker import HandTracker
    from .gesture_controller import GestureController
    from .painter import Painter


def main():
    prev_time = 0
    fps = 0.0

    with Camera() as camera:
        tracker = HandTracker()
        gestures = GestureController()
        painter = Painter()

        while True:
            frame = camera.get_frame()
            if frame is None:
                break

            painter.init_canvas(frame)

            detection = tracker.detect(frame)

            if detection:
                landmarks, handedness = detection
                fingers = tracker.fingers_up(landmarks, handedness)

                painter.draw(frame, landmarks, fingers)
                gestures.handle(fingers, painter)
                tracker.draw_landmarks(frame, landmarks)

            frame = painter.merge(frame)

            current_time = time.time()
            if prev_time:
                instant_fps = 1 / (current_time - prev_time)
                fps = fps * 0.9 + instant_fps * 0.1
            prev_time = current_time

            cv2.putText(frame, f"FPS: {int(fps)}",
                        (10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        1,
                        (0, 255, 0),
                        2)
            
            cv2.imshow("Air Paint - Portfolio Version", frame)

            if cv2.waitKey(1) == 27:
                break

    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()