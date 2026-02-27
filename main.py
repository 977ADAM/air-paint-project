import cv2
import time
import argparse

try:
    from camera import Camera, CameraConfig
    from hand_tracker import HandTracker, HandTrackerConfig
    from gesture_controller import GestureController
    from painter import Painter, PainterConfig
except ImportError:
    from .camera import Camera, CameraConfig
    from .hand_tracker import HandTracker, HandTrackerConfig
    from .gesture_controller import GestureController
    from .painter import Painter, PainterConfig

def parse_args():
    p = argparse.ArgumentParser(description="Air Paint - Gesture Based Drawing")
    p.add_argument("--camera", type=int, default=0, help="Camera device index")
    p.add_argument("--width", type=int, default=640)
    p.add_argument("--height", type=int, default=480)
    p.add_argument("--no-mirror", action="store_true", help="Disable mirrored preview")
    p.add_argument("--max-hands", type=int, default=1)
    p.add_argument("--cooldown", type=float, default=0.0, help="Global min gesture cooldown seconds (in addition to per-gesture cooldown)")
    p.add_argument("--snapshots-dir", type=str, default="snapshots")
    return p.parse_args()

def main():
    args = parse_args()

    prev_time = 0.0
    fps = 0.0

    cam_cfg = CameraConfig(device_index=args.camera, width=args.width, height=args.height, mirror=(not args.no_mirror))
    painter_cfg = PainterConfig(snapshots_dir=args.snapshots_dir)
    tracker_cfg = HandTrackerConfig(max_hands=args.max_hands)

    with Camera(cam_cfg) as camera, HandTracker(tracker_cfg) as tracker:
        gestures = GestureController()
        gestures.set_global_cooldown(args.cooldown)
        painter = Painter(painter_cfg)

        help_text = "ESC: exit | Q: exit | U: undo | S: save snapshot | C: clear"

        while True:
            try:
                frame = camera.get_frame()
            except RuntimeError as e:
                print(f"[ERROR] {e}")
                break
            if frame is None:
                time.sleep(0.01)
                continue

            painter.init_canvas(frame)

            detection = tracker.detect(frame)

            if detection:
                landmarks, handedness = detection
                fingers = tracker.fingers_up(landmarks, handedness)

                painter.draw(frame, landmarks, fingers)
                gestures.handle(fingers, painter)
                tracker.draw_landmarks(frame, landmarks)

            frame = painter.merge(frame)
            painter.draw_hud(frame)

            current_time = time.monotonic()
            if prev_time > 0:
                dt = current_time - prev_time
                if dt > 0:
                    instant_fps = 1.0 / dt
                    fps = fps * 0.9 + instant_fps * 0.1
            prev_time = current_time

            cv2.putText(frame, f"FPS: {int(fps)}",
                        (10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        1,
                        (0, 255, 0),
                        2)
            cv2.putText(frame, help_text,
                        (10, frame.shape[0] - 10),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.6,
                        (255, 255, 255),
                        2)
            
            cv2.imshow("Air Paint - Portfolio Version", frame)

            key = cv2.waitKey(1) & 0xFF
            if key in (27, ord("q"), ord("Q")):
                break
            if key in (ord("c"), ord("C")):
                painter.clear()
            if key in (ord("u"), ord("U")):
                painter.undo()
            if key in (ord("s"), ord("S")):
                path = painter.save_snapshot(merged=True)
                if path is not None:
                    print(f"[OK] Saved: {path}")

    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()