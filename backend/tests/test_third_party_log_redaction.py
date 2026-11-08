"""alea_llm_client and transport loggers never carry visitor text into logs."""

import io
import json
import logging
import traceback

import pytest

SECRET = "SECRET-VISITOR-TEXT"
JSON_LOGGER = "alea_llm_client.llms.utils.json"
MODEL_LOGGER = "alea_llm_client.llms.models.anthropic_model.AnthropicModel"


@pytest.fixture
def capture(monkeypatch):
    """Configure app logging for a mode and capture root output via the structlog formatter."""
    from app import config
    from app.observability.logging import setup_logging

    handlers = []

    def _configure(showcase: bool, log_level: str = "INFO") -> io.StringIO:
        settings = config.Settings(_env_file=None, secret_key="test-key",
                                   showcase_mode=showcase, log_level=log_level, log_format="json")
        monkeypatch.setattr(config, "get_settings", lambda: settings)
        # alea attaches its own console and ~/.alea file handlers; keep tests off them.
        for name in (JSON_LOGGER, MODEL_LOGGER):
            monkeypatch.setattr(logging.getLogger(name), "handlers", [])
        previous_level = logging.getLogger().level
        monkeypatch.setattr(logging.getLogger(), "level", previous_level)
        setup_logging()
        stream = io.StringIO()
        handler = logging.StreamHandler(stream)
        handler.setFormatter(logging.getLogger().handlers[0].formatter)
        logging.getLogger().addHandler(handler)
        handlers.append(handler)
        return stream

    yield _configure
    for handler in handlers:
        logging.getLogger().removeHandler(handler)


def _emit_json_failure():
    try:
        raise ValueError(f"The cleaned response is not a valid JSON or JSONL object: {SECRET}")
    except ValueError:
        logging.getLogger(JSON_LOGGER).exception(f"Invalid JSON or JSONL response: {SECRET}")


def _emit_retry_failure():
    try:
        raise ValueError(SECRET)
    except ValueError as e:
        logging.getLogger(MODEL_LOGGER).warning(f"Attempt 1 failed: {e!s}\n{traceback.format_exc()}")


def test_showcase_alea_json_failure_records_event_without_content(capture, caplog):
    stream = capture(showcase=True)
    with caplog.at_level(logging.WARNING):
        _emit_json_failure()
    output = stream.getvalue() + caplog.text
    assert SECRET not in output
    assert "Traceback" not in output
    event = json.loads(stream.getvalue().strip().splitlines()[-1])
    assert event["level"] == "error"
    assert "withheld" in event["event"]
    assert JSON_LOGGER in event["event"]
    assert "exception=ValueError" in event["event"]
    record = [r for r in caplog.records if r.name == JSON_LOGGER][-1]
    assert record.exc_info is None and record.exc_text is None


def test_showcase_alea_retry_attempt_records_event_without_content(capture, caplog):
    stream = capture(showcase=True)
    with caplog.at_level(logging.WARNING):
        _emit_retry_failure()
    output = stream.getvalue() + caplog.text
    assert SECRET not in output
    assert "Traceback" not in output
    event = json.loads(stream.getvalue().strip().splitlines()[-1])
    assert event["level"] == "warning"
    assert "withheld" in event["event"] and "exception=ValueError" in event["event"]


def test_showcase_transport_debug_traces_withheld(capture):
    stream = capture(showcase=True, log_level="DEBUG")
    logging.getLogger("httpcore.http11").debug(f"send_request_body.started request=<{SECRET}>")
    logging.getLogger("hpack.hpack").debug("Encoding %s", SECRET)
    assert SECRET not in stream.getvalue()
    assert "logger=httpcore.http11" in stream.getvalue()


def test_showcase_app_logs_unaffected(capture):
    import structlog
    stream = capture(showcase=True)
    logging.getLogger("app.services.example").warning("Operation failed: %s", "detail")
    structlog.get_logger().warning("Health check: database down")
    output = stream.getvalue()
    assert "Operation failed: %s" in output
    assert "Health check: database down" in output
    assert "withheld" not in output


def test_non_showcase_strips_alea_json_failure_content(capture, caplog):
    stream = capture(showcase=False)
    payload = SECRET
    with caplog.at_level(logging.WARNING):
        try:
            json.loads(payload)
        except json.JSONDecodeError:
            logging.getLogger(JSON_LOGGER).exception(f"Invalid JSON or JSONL response: {payload}")
        _emit_retry_failure()
        logging.getLogger("app.services.example").warning(f"App detail {payload}")
    assert SECRET not in stream.getvalue().replace(f"App detail {SECRET}", "")
    records = {r.name: r for r in caplog.records}
    assert "exception=JSONDecodeError" in records[JSON_LOGGER].getMessage()
    # Outside showcase the traceback alea attached stays for debugging.
    assert records[JSON_LOGGER].exc_info is not None
    assert SECRET not in records[MODEL_LOGGER].getMessage()
    # Non-alea app logs keep their message as written.
    assert records["app.services.example"].getMessage() == f"App detail {SECRET}"


def test_non_showcase_keeps_benign_alea_messages(capture, caplog):
    capture(showcase=False)
    with caplog.at_level(logging.INFO):
        logging.getLogger(MODEL_LOGGER).warning("Failed to load dynamic model configuration: x")
    assert "Failed to load dynamic model configuration: x" in caplog.text


def test_guard_installs_once(capture):
    capture(showcase=True)
    factory = logging.getLogRecordFactory()
    capture(showcase=True)
    assert logging.getLogRecordFactory() is factory
