import logging
import time

import numpy as np
import pytest

from airpaint.cli_args import AppConfig
from airpaint.main import AppRunner, RuntimeDeps, RuntimeService


def _config(**overrides):
    base = {
        "camera": 0,
        "width": 320,
        "height": 240,
        "no_mirror": False,
        "max_hands": 1,
        "target_fps": 60.0,
        "detect_every": 2,
        "tracker_scale": 1.0,
        "draw_landmarks": False,
        "model_complexity": 0,
        "min_detection_confidence": 0.5,
        "min_tracking_confidence": 0.5,
        "cooldown": 0.0,
        "snapshots_dir": "snapshots",
        "gesture_map": None,
        "log_level": "INFO",
        "debug": False,
    }
    base.update(overrides)
    return AppConfig(**base)


class FakeTracker:
    def __init__(self):
        self.detect_calls = 0
        self.draw_landmarks_calls = 0

    def detect(self, frame):
        self.detect_calls += 1
        return ("landmarks", "right")

    def fingers_up(self, landmarks, handedness):
        return [0, 1, 0, 0, 0]

    def draw_landmarks(self, frame, landmarks):
        self.draw_landmarks_calls += 1


class FakeGestures:
    def __init__(self, return_name="clear"):
        self.return_name = return_name
        self.calls = 0

    def handle(self, fingers, painter, landmarks=None):
        self.calls += 1
        return self.return_name


class FakePainter:
    def __init__(self):
        self.clear_calls = 0
        self.undo_calls = 0
        self.save_calls = 0
        self.init_calls = 0
        self.draw_calls = 0
        self.hud_calls = 0

    def init_canvas(self, frame):
        self.init_calls += 1

    def draw(self, frame, landmarks, fingers):
        self.draw_calls += 1

    def merge(self, frame):
        return frame

    def draw_hud(self, frame):
        self.hud_calls += 1

    def clear(self):
        self.clear_calls += 1

    def undo(self):
        self.undo_calls += 1

    def save_snapshot(self, merged=True):
        self.save_calls += 1
        return "snapshots/ok.png"


def test_build_configs_maps_values_from_app_config():
    cfg = _config(width=640, height=360, tracker_scale=0.55, no_mirror=True)
    runner = AppRunner(cfg)

    cam_cfg, painter_cfg, tracker_cfg = runner._build_configs()

    assert cam_cfg.width == 640
    assert cam_cfg.height == 360
    assert cam_cfg.mirror is False
    assert tracker_cfg.input_scale == 0.55
    assert painter_cfg.snapshots_dir == "snapshots"


def test_build_gestures_raises_runtime_error_for_bad_map():
    runner = AppRunner(_config(gesture_map="missing-file.json"))
    with pytest.raises(RuntimeError):
        runner._build_gestures()


def test_process_frame_runs_detection_on_schedule_and_tracks_stats():
    tracker = FakeTracker()
    gestures = FakeGestures(return_name="clear")
    painter = FakePainter()
    service = RuntimeService(
        _config(detect_every=2, draw_landmarks=False),
        RuntimeDeps(camera=None, tracker=tracker, gestures=gestures, painter=painter),
    )
    frame = np.zeros((20, 20, 3), dtype=np.uint8)

    service._process_frame(frame, tracker, gestures, painter)
    assert tracker.detect_calls == 0
    assert service.stats_detect_calls == 0

    service._process_frame(frame, tracker, gestures, painter)
    assert tracker.detect_calls == 1
    assert service.stats_detect_calls == 1
    assert service.stats_detect_hits == 1
    assert service.stats_gesture_hits == 1
    assert painter.draw_calls == 1
    assert tracker.draw_landmarks_calls == 0


def test_process_frame_draws_landmarks_when_enabled():
    tracker = FakeTracker()
    gestures = FakeGestures()
    painter = FakePainter()
    service = RuntimeService(
        _config(detect_every=1, draw_landmarks=True),
        RuntimeDeps(camera=None, tracker=tracker, gestures=gestures, painter=painter),
    )
    frame = np.zeros((20, 20, 3), dtype=np.uint8)

    service._process_frame(frame, tracker, gestures, painter)
    assert tracker.draw_landmarks_calls == 1


def test_handle_hotkeys_dispatches_actions():
    service = RuntimeService(
        _config(),
        RuntimeDeps(camera=None, tracker=FakeTracker(), gestures=FakeGestures(), painter=FakePainter()),
    )
    painter = FakePainter()

    assert service._handle_hotkeys(ord("c"), painter) is False
    assert service._handle_hotkeys(ord("u"), painter) is False
    assert service._handle_hotkeys(ord("s"), painter) is False
    assert service._handle_hotkeys(ord("q"), painter) is True

    assert painter.clear_calls == 1
    assert painter.undo_calls == 1
    assert painter.save_calls == 1


def test_debug_stats_tick_logs_and_resets(caplog):
    service = RuntimeService(
        _config(),
        RuntimeDeps(camera=None, tracker=FakeTracker(), gestures=FakeGestures(), painter=FakePainter()),
    )
    service.logger.setLevel(logging.DEBUG)
    service.fps = 33.3
    service.stats_frames = 30
    service.stats_detect_calls = 10
    service.stats_detect_hits = 8
    service.stats_gesture_hits = 2
    service.stats_window_start = time.monotonic() - 1.2

    with caplog.at_level(logging.DEBUG, logger="airpaint.runtime"):
        service._debug_stats_tick()

    assert any(rec.msg == "loop_stats" for rec in caplog.records)
    assert service.stats_frames == 0
    assert service.stats_detect_calls == 0
    assert service.stats_detect_hits == 0
    assert service.stats_gesture_hits == 0
