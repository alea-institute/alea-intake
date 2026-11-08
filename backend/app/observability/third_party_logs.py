"""Content-free records for third-party loggers on the LLM path.

``alea_llm_client`` builds its log messages with f-strings that embed model
replies (``Invalid JSON or JSONL response: {cleaned}``) and retry tracebacks
(``Attempt N failed: {e!s}\\n{traceback}``). The structlog bridge keeps a
record's message template in showcase mode, but an f-string message *is* the
content, so template-only redaction cannot help. The HTTP transport stack
(httpcore, h2, hpack, urllib3) does the same at DEBUG, logging reprs of
requests, responses, and headers.

A log-record factory rewrites those records at creation time, before any
handler sees them. That covers the root handlers, pytest's capture, and the
console/file handlers ``alea_llm_client`` attaches to its own loggers each time
a model is constructed (which happens after app logging setup). The rewritten
record keeps its logger name, level, and the exception TYPE, so operators still
see that a failure happened.

Policy:
- Showcase mode: every ``alea``/``alea_llm_client`` record and every transport
  DEBUG record becomes a fixed message; traceback and stack text are dropped
  because exception text can carry the reply.
- Other modes: only the known content-bearing ``alea_llm_client`` messages are
  rewritten; any traceback ``alea_llm_client`` attached is kept for debugging.
"""

from __future__ import annotations

import logging
import sys

from app import config

LLM_CLIENT_LOGGERS = ("alea", "alea_llm_client")
TRANSPORT_LOGGERS = ("httpcore", "httpx", "h2", "hpack", "urllib3", "requests")

# alea_llm_client message prefixes that interpolate prompt, reply, or exception text.
CONTENT_BEARING_PREFIXES = (
    "Invalid JSON or JSONL response",
    "Attempt ",
    "Error parsing JSON data",
    "Model error",
    "Model response",
    "JSON model response",
    "Formatted messages",
    "Error in request",
    "Error in asynchronous request",
    "Error connecting to the API",
)

WITHHELD_MESSAGE = "Third-party log content withheld"

_GUARD_MARK = "_third_party_content_guard"


def _matches(name: str, prefixes: tuple[str, ...]) -> bool:
    return any(name == prefix or name.startswith(prefix + ".") for prefix in prefixes)


def _showcase_mode() -> bool:
    try:
        return bool(config.get_settings().showcase_mode)
    except Exception:  # noqa: BLE001 - fail closed: treat unknown config as showcase
        return True


def _content_bearing(record: logging.LogRecord) -> bool:
    return isinstance(record.msg, str) and record.msg.startswith(CONTENT_BEARING_PREFIXES)


def sanitize_record(record: logging.LogRecord) -> None:
    """Rewrite a third-party record in place so it carries no prompt/reply text."""
    name = record.name
    if not isinstance(name, str):  # logging.makeLogRecord() fills fields after the factory
        return
    is_client = _matches(name, LLM_CLIENT_LOGGERS)
    is_transport_debug = (
        not is_client and record.levelno < logging.INFO and _matches(name, TRANSPORT_LOGGERS)
    )
    if not (is_client or is_transport_debug):
        return

    showcase = _showcase_mode()
    if not showcase and not (is_client and _content_bearing(record)):
        return

    exc = record.exc_info[1] if isinstance(record.exc_info, tuple) else None
    if exc is None:
        # alea's retry warning formats the active exception into the message
        # without passing exc_info; the record is created inside that handler.
        exc = sys.exc_info()[1]

    message = f"{WITHHELD_MESSAGE}: logger={name} level={record.levelname}"
    if exc is not None:
        message += f" exception={type(exc).__name__}"
    record.msg = message
    record.args = ()
    record.withheld_exception_type = type(exc).__name__ if exc is not None else None
    if showcase:
        record.exc_info = None
        record.exc_text = None
        record.stack_info = None


def install_third_party_log_guard() -> None:
    """Install the record factory once; repeated setup calls are no-ops."""
    current = logging.getLogRecordFactory()
    if getattr(current, _GUARD_MARK, False):
        return

    def factory(*args, **kwargs):
        record = current(*args, **kwargs)
        sanitize_record(record)
        return record

    setattr(factory, _GUARD_MARK, True)
    logging.setLogRecordFactory(factory)
