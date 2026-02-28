import logging
import time
from dataclasses import dataclass
from typing import Optional, Protocol

import cv2

from .camera import Camera, CameraConfig
from .cli_args import AppCli, AppConfig
from .gesture_controller import GestureController
from .hand_tracker import HandTracker, HandTrackerConfig
from .logging_utils import setup_logging
from .painter import Painter, PainterConfig


class CameraLike(Protocol):
    def get_frame(self):
        ...


class TrackerLike(Protocol):
    def detect(self, frame):
        ...

    def fingers_up(self, landmarks, handedness):
        ...

    def draw_landmarks(self, frame, landmarks) -> None:
        ...


class PainterLike(Protocol):
    def init_canvas(self, frame) -> None:
        ...

    def draw(self, frame, landmarks, fingers) -> None:
        ...

    def merge(self, frame):
        ...

    def draw_hud(self, frame) -> None:
        ...

    def clear(self) -> None:
        ...

    def undo(self) -> None:
        ...

    def save_snapshot(self, merged: bool = True):
        ...


class GesturesLike(Protocol):
    def handle(self, fingers, painter: PainterLike, landmarks=None) -> Optional[str]:
        ...
    def get_live_feedback(self) -> Optional[tuple[str, Optional[float]]]:
        ...


class UiLike(Protocol):
    def show(self, frame, fps: float, help_text: str, window_title: str) -> None:
        ...

    def wait_key(self, delay_ms: int) -> int:
        ...

    def close(self) -> None:
        ...


@dataclass
class RuntimeDeps:
    camera: CameraLike
    tracker: TrackerLike
    gestures: GesturesLike
    painter: PainterLike


class OpenCvUi:
    def show(self, frame, fps: float, help_text: str, window_title: str) -> None:
        cv2.putText(
            frame,
            f"FPS: {int(fps)}",
            (10, 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            1,
            (0, 255, 0),
            2,
        )
        cv2.putText(
            frame,
            help_text,
            (10, frame.shape[0] - 10),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (255, 255, 255),
            2,
        )
        cv2.imshow(window_title, frame)

    def wait_key(self, delay_ms: int) -> int:
        return cv2.waitKey(delay_ms)

    def close(self) -> None:
        cv2.destroyAllWindows()


class RuntimeService:
    def __init__(
        self,
        config: AppConfig,
        deps: RuntimeDeps,
        ui: Optional[UiLike] = None,
        *,
        clock=time.monotonic,
        sleeper=time.sleep,
    ):
        self.config = config
        self.deps = deps
        self.ui = ui or OpenCvUi()
        self.clock = clock
        self.sleeper = sleeper
        self.logger = logging.getLogger("airpaint.runtime")

        self.window_title = "Air Paint - Portfolio Version"
        self.help_text = "ESC: exit | Q: exit | U: undo | S: save snapshot | C: clear"
        self.target_fps = max(1.0, float(config.target_fps))
        self.target_frame_time = 1.0 / self.target_fps
        self.detect_every = max(1, int(config.detect_every))

        self.prev_time = 0.0
        self.fps = 0.0
        self.stats_window_start = self.clock()
        self.stats_frames = 0
        self.stats_detect_calls = 0
        self.stats_detect_hits = 0
        self.stats_gesture_hits = 0
        self.frame_idx = 0
        self.cached_detection = None

    def run(self) -> None:
        while True:
            frame_start = self.clock()
            self.stats_frames += 1

            frame = self._get_frame(self.deps.camera)
            if frame is None:
                continue

            self._process_frame(
                frame,
                tracker=self.deps.tracker,
                gestures=self.deps.gestures,
                painter=self.deps.painter,
            )
            self.ui.show(frame, self.fps, self.help_text, self.window_title)

            key = self.ui.wait_key(1) & 0xFF
            if self._handle_hotkeys(key, self.deps.painter):
                break

            self._finish_frame(frame_start)
            self._debug_stats_tick()

        self.ui.close()

    def _get_frame(self, camera: CameraLike):
        frame = camera.get_frame()
        if frame is None:
            self.sleeper(0.01)
            return None
        return frame

    def _process_frame(self, frame, tracker: TrackerLike, gestures: GesturesLike, painter: PainterLike) -> None:
        painter.init_canvas(frame)

        self.frame_idx += 1
        if self.frame_idx % self.detect_every == 0:
            self.stats_detect_calls += 1
            self.cached_detection = tracker.detect(frame)
            if self.cached_detection:
                self.stats_detect_hits += 1

        if self.cached_detection:
            landmarks, handedness = self.cached_detection
            fingers = tracker.fingers_up(landmarks, handedness)
            painter.draw(frame, landmarks, fingers)
            triggered = gestures.handle(fingers, painter, landmarks=landmarks)
            if triggered:
                self.stats_gesture_hits += 1
            self._draw_gesture_hint(frame, landmarks, gestures.get_live_feedback())
            if self.config.draw_landmarks:
                tracker.draw_landmarks(frame, landmarks)

        merged = painter.merge(frame)
        painter.draw_hud(merged)
        frame[:] = merged

    def _draw_gesture_hint(self, frame, landmarks, feedback: Optional[tuple[str, Optional[float]]]) -> None:
        if not feedback:
            return
        h, w = frame.shape[:2]
        x = int(landmarks.landmark[8].x * w)
        y = int(landmarks.landmark[8].y * h)
        x = max(0, min(w - 1, x))
        y = max(0, min(h - 1, y))

        label, progress = feedback
        if progress is None:
            text = label
        else:
            text = f"{label} {int(progress * 100)}%"

        pos_x = min(max(10, x + 12), max(10, w - 220))
        pos_y = min(max(30, y - 12), max(30, h - 10))

        cv2.rectangle(frame, (pos_x - 4, pos_y - 20), (min(w - 1, pos_x + 210), pos_y + 6), (0, 0, 0), -1)
        cv2.putText(
            frame,
            text,
            (pos_x, pos_y),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            (0, 255, 255) if progress is not None and progress < 1.0 else (0, 255, 0),
            2,
        )

    def _handle_hotkeys(self, key: int, painter: PainterLike) -> bool:
        if key in (27, ord("q"), ord("Q")):
            return True
        if key in (ord("c"), ord("C")):
            painter.clear()
        if key in (ord("u"), ord("U")):
            painter.undo()
        if key in (ord("s"), ord("S")):
            path = painter.save_snapshot(merged=True)
            if path is not None:
                logging.info("Saved snapshot: %s", path)
        return False

    def _finish_frame(self, frame_start: float) -> None:
        frame_elapsed = self.clock() - frame_start
        sleep_for = self.target_frame_time - frame_elapsed
        if sleep_for > 0:
            self.sleeper(sleep_for)

        current_time = self.clock()
        if self.prev_time > 0:
            dt = current_time - self.prev_time
            if dt > 0:
                instant_fps = 1.0 / dt
                self.fps = self.fps * 0.9 + instant_fps * 0.1
        self.prev_time = current_time

    def _debug_stats_tick(self) -> None:
        if not self.logger.isEnabledFor(logging.DEBUG):
            return
        now = self.clock()
        window_s = now - self.stats_window_start
        if window_s < 1.0:
            return

        self.logger.debug(
            "loop_stats",
            extra={
                "event": "loop_stats",
                "fps": round(self.fps, 2),
                "frames": self.stats_frames,
                "detect_every": self.detect_every,
                "detect_calls": self.stats_detect_calls,
                "detect_hits": self.stats_detect_hits,
                "gesture_hits": self.stats_gesture_hits,
                "window_s": round(window_s, 3),
            },
        )
        self.stats_window_start = now
        self.stats_frames = 0
        self.stats_detect_calls = 0
        self.stats_detect_hits = 0
        self.stats_gesture_hits = 0


class AppRunner:
    def __init__(self, config: AppConfig):
        self.config = config

    def run(self) -> None:
        cam_cfg, painter_cfg, tracker_cfg = self._build_configs()

        with Camera(cam_cfg) as camera, HandTracker(tracker_cfg) as tracker:
            gestures = self._build_gestures()
            painter = Painter(painter_cfg)
            deps = RuntimeDeps(
                camera=camera,
                tracker=tracker,
                gestures=gestures,
                painter=painter,
            )
            service = RuntimeService(config=self.config, deps=deps, ui=OpenCvUi())
            service.run()

    def _build_configs(self) -> tuple[CameraConfig, PainterConfig, HandTrackerConfig]:
        cam_cfg = CameraConfig(
            device_index=self.config.camera,
            width=self.config.width,
            height=self.config.height,
            mirror=(not self.config.no_mirror),
        )
        painter_cfg = PainterConfig(snapshots_dir=self.config.snapshots_dir)
        tracker_cfg = HandTrackerConfig(
            max_hands=self.config.max_hands,
            model_complexity=self.config.model_complexity,
            min_detection_confidence=self.config.min_detection_confidence,
            min_tracking_confidence=self.config.min_tracking_confidence,
            input_scale=self.config.tracker_scale,
        )
        return cam_cfg, painter_cfg, tracker_cfg

    def _build_gestures(self) -> GestureController:
        gestures = GestureController()
        gestures.set_global_cooldown(self.config.cooldown)
        if self.config.gesture_map:
            try:
                gestures.load_pattern_overrides_from_file(self.config.gesture_map)
                logging.info("Loaded gesture overrides from: %s", self.config.gesture_map)
            except Exception as e:
                raise RuntimeError(
                    f"Failed to load --gesture-map '{self.config.gesture_map}': {e}"
                ) from e
        return gestures


def main():
    args = AppCli().parse()
    setup_logging("DEBUG" if args.debug else args.log_level)
    logger = logging.getLogger("airpaint.runtime")
    logger.info(
        "app_start",
        extra={
            "event": "app_start",
            "target_fps": args.target_fps,
            "detect_every": args.detect_every,
            "tracker_scale": args.tracker_scale,
            "log_level": "DEBUG" if args.debug else args.log_level,
        },
    )

    runner = AppRunner(args)
    try:
        runner.run()
    except RuntimeError as e:
        logger.error(str(e))


if __name__ == "__main__":
    main()
