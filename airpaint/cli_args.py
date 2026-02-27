from __future__ import annotations

import argparse
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class AppConfig:
    camera: int
    width: int
    height: int
    no_mirror: bool
    max_hands: int
    target_fps: float
    detect_every: int
    tracker_scale: float
    draw_landmarks: bool
    model_complexity: int
    min_detection_confidence: float
    min_tracking_confidence: float
    cooldown: float
    snapshots_dir: str
    gesture_map: Optional[str]
    log_level: str
    debug: bool


class AppCli:
    def __init__(self) -> None:
        self._parser = argparse.ArgumentParser(
            description="Air Paint - Gesture Based Drawing"
        )
        self._configure()

    def _configure(self) -> None:
        p = self._parser
        p.add_argument("--camera", type=int, default=0, help="Camera device index")
        p.add_argument("--width", type=int, default=480)
        p.add_argument("--height", type=int, default=270)
        p.add_argument("--no-mirror", action="store_true", help="Disable mirrored preview")
        p.add_argument("--max-hands", type=self._int_min(1), default=1)
        p.add_argument(
            "--target-fps",
            type=self._float_range(min_value=1.0, min_inclusive=True),
            default=60.0,
            help="Render FPS cap (>= 1.0)",
        )
        p.add_argument(
            "--detect-every",
            type=self._int_min(1),
            default=3,
            help="Run hand detection every N frames (higher = faster, less responsive)",
        )
        p.add_argument(
            "--tracker-scale",
            type=self._float_range(min_value=0.2, max_value=1.0, min_inclusive=True, max_inclusive=True),
            default=0.6,
            help="Scale frame before MediaPipe processing (0.2..1.0, lower is faster)",
        )
        p.add_argument(
            "--draw-landmarks",
            action="store_true",
            help="Draw MediaPipe hand landmarks (costs FPS)",
        )
        p.add_argument(
            "--model-complexity",
            type=int,
            default=0,
            choices=[0, 1],
            help="MediaPipe model complexity (0 faster, 1 more accurate)",
        )
        p.add_argument(
            "--min-detection-confidence",
            type=self._float_range(min_value=0.0, max_value=1.0, min_inclusive=True, max_inclusive=True),
            default=0.5,
        )
        p.add_argument(
            "--min-tracking-confidence",
            type=self._float_range(min_value=0.0, max_value=1.0, min_inclusive=True, max_inclusive=True),
            default=0.5,
        )
        p.add_argument(
            "--cooldown",
            type=self._float_range(min_value=0.0, min_inclusive=True),
            default=0.0,
            help="Global min gesture cooldown seconds (in addition to per-gesture cooldown)",
        )
        p.add_argument("--snapshots-dir", type=str, default="snapshots")
        p.add_argument(
            "--gesture-map",
            type=str,
            default=None,
            help="Path to JSON with gesture pattern overrides, e.g. {'clear':[1,1,0,0,0]}",
        )
        p.add_argument(
            "--log-level",
            type=str,
            default="INFO",
            choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
            help="Logging level",
        )
        p.add_argument(
            "--debug",
            action="store_true",
            help="Enable debug mode (equivalent to --log-level DEBUG)",
        )

    def parse(self) -> AppConfig:
        args = self._parser.parse_args()
        return AppConfig(
            camera=args.camera,
            width=args.width,
            height=args.height,
            no_mirror=args.no_mirror,
            max_hands=args.max_hands,
            target_fps=args.target_fps,
            detect_every=args.detect_every,
            tracker_scale=args.tracker_scale,
            draw_landmarks=args.draw_landmarks,
            model_complexity=args.model_complexity,
            min_detection_confidence=args.min_detection_confidence,
            min_tracking_confidence=args.min_tracking_confidence,
            cooldown=args.cooldown,
            snapshots_dir=args.snapshots_dir,
            gesture_map=args.gesture_map,
            log_level=args.log_level,
            debug=args.debug,
        )

    @staticmethod
    def _int_min(min_value: int):
        def _validator(raw: str) -> int:
            try:
                value = int(raw)
            except ValueError as e:
                raise argparse.ArgumentTypeError(f"Expected integer, got '{raw}'") from e
            if value < min_value:
                raise argparse.ArgumentTypeError(f"Expected integer >= {min_value}, got {value}")
            return value
        return _validator

    @staticmethod
    def _float_range(
        *,
        min_value: Optional[float] = None,
        max_value: Optional[float] = None,
        min_inclusive: bool = True,
        max_inclusive: bool = True,
    ):
        def _validator(raw: str) -> float:
            try:
                value = float(raw)
            except ValueError as e:
                raise argparse.ArgumentTypeError(f"Expected float, got '{raw}'") from e

            if min_value is not None:
                if min_inclusive and value < min_value:
                    raise argparse.ArgumentTypeError(f"Expected value >= {min_value}, got {value}")
                if not min_inclusive and value <= min_value:
                    raise argparse.ArgumentTypeError(f"Expected value > {min_value}, got {value}")

            if max_value is not None:
                if max_inclusive and value > max_value:
                    raise argparse.ArgumentTypeError(f"Expected value <= {max_value}, got {value}")
                if not max_inclusive and value >= max_value:
                    raise argparse.ArgumentTypeError(f"Expected value < {max_value}, got {value}")

            return value
        return _validator
