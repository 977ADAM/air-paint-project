import cv2
import time
import logging

try:
    from cli_args import AppCli
    from camera import Camera, CameraConfig
    from hand_tracker import HandTracker, HandTrackerConfig
    from gesture_controller import GestureController
    from painter import Painter, PainterConfig
except ImportError:
    from .cli_args import AppCli
    from .camera import Camera, CameraConfig
    from .hand_tracker import HandTracker, HandTrackerConfig
    from .gesture_controller import GestureController
    from .painter import Painter, PainterConfig

def main():
    args = AppCli().parse()
    logging.basicConfig(level=logging.INFO)

    target_fps = max(1.0, float(args.target_fps))
    target_frame_time = 1.0 / target_fps
    detect_every = max(1, int(args.detect_every))
    prev_time = 0.0
    fps = 0.0

    cam_cfg = CameraConfig(device_index=args.camera, width=args.width, height=args.height, mirror=(not args.no_mirror))
    painter_cfg = PainterConfig(snapshots_dir=args.snapshots_dir)
    tracker_cfg = HandTrackerConfig(
        max_hands=args.max_hands,
        model_complexity=args.model_complexity,
        min_detection_confidence=args.min_detection_confidence,
        min_tracking_confidence=args.min_tracking_confidence,
        input_scale=args.tracker_scale,
    )

    with Camera(cam_cfg) as camera, HandTracker(tracker_cfg) as tracker:
        gestures = GestureController()
        gestures.set_global_cooldown(args.cooldown)
        if args.gesture_map:
            try:
                gestures.load_pattern_overrides_from_file(args.gesture_map)
                logging.info("Loaded gesture overrides from: %s", args.gesture_map)
            except Exception as e:
                logging.error("Failed to load --gesture-map '%s': %s", args.gesture_map, e)
                return
        painter = Painter(painter_cfg)

        help_text = "ESC: exit | Q: exit | U: undo | S: save snapshot | C: clear"
        frame_idx = 0
        cached_detection = None

        while True:
            frame_start = time.monotonic()
            try:
                frame = camera.get_frame()
            except RuntimeError as e:
                logging.error(str(e))
                break
            if frame is None:
                time.sleep(0.01)
                continue

            painter.init_canvas(frame)

            frame_idx += 1
            if frame_idx % detect_every == 0:
                cached_detection = tracker.detect(frame)
            detection = cached_detection

            if detection:
                landmarks, handedness = detection
                fingers = tracker.fingers_up(landmarks, handedness)

                painter.draw(frame, landmarks, fingers)
                gestures.handle(fingers, painter)
                if args.draw_landmarks:
                    tracker.draw_landmarks(frame, landmarks)

            frame = painter.merge(frame)
            painter.draw_hud(frame)

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
                    logging.info("Saved snapshot: %s", path)

            frame_elapsed = time.monotonic() - frame_start
            sleep_for = target_frame_time - frame_elapsed
            if sleep_for > 0:
                time.sleep(sleep_for)

            current_time = time.monotonic()
            if prev_time > 0:
                dt = current_time - prev_time
                if dt > 0:
                    instant_fps = 1.0 / dt
                    fps = fps * 0.9 + instant_fps * 0.1
            prev_time = current_time

    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
