"""Privacy boundary shared by logs, traces, and error-report payloads."""
import re
from app import config

_SENSITIVE = re.compile(r'narrative|content|text|body|document|message|key|token|authorization|cookie|password|exception|stack|url|query|headers|input|error|detail', re.I)
_TOKEN = re.compile(r'(?:sk-|key[-_=])[\w.-]+|eyJ[\w-]+\.[\w-]+\.[\w-]+', re.I)
_SAFE = {'level', 'log_level', 'timestamp', 'trace_id', 'span_id', 'http.method', 'http.request.method'}


def scrub(value, key=''):
    """Drop content-bearing fields; in showcase discard all free-form strings.

    Free-form exception/log messages can interpolate a story without a field
    name. Keeping numeric diagnostics and trace IDs avoids that leak entirely.
    """
    if _SENSITIVE.search(key):
        return '[redacted]'
    if isinstance(value, dict):
        return {k: scrub(v, str(k)) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [scrub(v) for v in value]
    if isinstance(value, str):
        if config.get_settings().showcase_mode and key not in _SAFE:
            return '[redacted]'
        return _TOKEN.sub('[redacted]', value)
    if isinstance(value, (int, float, bool)) or value is None:
        return value
    return '[redacted]'


def redact_event(logger, method_name, event_dict):
    return scrub(event_dict)
