import json
import logging

from logging_utils import JsonFormatter, setup_logging


def test_json_formatter_includes_standard_and_extra_fields():
    formatter = JsonFormatter()
    record = logging.LogRecord(
        name="airpaint.test",
        level=logging.INFO,
        pathname=__file__,
        lineno=10,
        msg="hello %s",
        args=("world",),
        exc_info=None,
    )
    record.event = "unit_test"
    record.value = 123

    payload = json.loads(formatter.format(record))
    assert payload["message"] == "hello world"
    assert payload["level"] == "INFO"
    assert payload["logger"] == "airpaint.test"
    assert payload["event"] == "unit_test"
    assert payload["value"] == 123
    assert "ts" in payload


def test_setup_logging_applies_level_and_json_formatter():
    setup_logging("DEBUG")
    root = logging.getLogger()

    assert root.level == logging.DEBUG
    assert len(root.handlers) == 1
    assert isinstance(root.handlers[0].formatter, JsonFormatter)
