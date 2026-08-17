import json
import logging

from app.core.logging import JsonFormatter


def test_json_formatter_emits_structured_record():
    record = logging.LogRecord(
        name="test_logger",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="hello %(name)s",
        args=({"name": "docagent"},),
        exc_info=None,
    )
    formatted = JsonFormatter().format(record)
    parsed = json.loads(formatted)
    assert parsed["level"] == "INFO"
    assert parsed["logger"] == "test_logger"
    assert parsed["message"] == "hello docagent"
    assert parsed["timestamp"]
