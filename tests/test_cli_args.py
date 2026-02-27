import sys

from cli_args import AppCli


def test_parse_defaults(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["airpaint"])
    cfg = AppCli().parse()

    assert cfg.width == 480
    assert cfg.height == 270
    assert cfg.target_fps == 60.0
    assert cfg.detect_every == 3
    assert cfg.log_level == "INFO"
    assert cfg.debug is False


def test_parse_overrides(monkeypatch):
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "airpaint",
            "--debug",
            "--log-level",
            "ERROR",
            "--detect-every",
            "5",
            "--tracker-scale",
            "0.4",
        ],
    )
    cfg = AppCli().parse()

    assert cfg.debug is True
    assert cfg.log_level == "ERROR"
    assert cfg.detect_every == 5
    assert cfg.tracker_scale == 0.4
