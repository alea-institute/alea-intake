"""Privacy boundary shared by logs, traces, and error-report payloads."""
import re
from app import config

_SENSITIVE = re.compile(r'narrative|content|text|body|document|message|key|token|authorization|cookie|password|exception|stack|url|query|headers|input|error|detail', re.I)
_TOKEN = re.compile(r'(?:sk-|key[-_=])[\w.-]+|eyJ[\w-]+\.[\w-]+\.[\w-]+', re.I)
_REQUEST = re.compile(r'(?:GET|POST|PUT|PATCH|DELETE|HEAD|OPTIONS) /|https?://|(?:Authorization|Cookie|X-LLM-API-Key|X-Preview-Key):', re.I)


def scrub(value, key=''):
    """Preserve operational diagnostics while removing visitor content and secrets."""
    settings = config.get_settings()
    secrets = tuple(secret for secret in (
        settings.preview_passphrase, settings.secret_key, settings.db_password,
        settings.session_secret_key, settings.google_client_secret,
        settings.microsoft_client_secret) if secret)
    return _scrub(value, key, secrets)


def _scrub(value, key, secrets):
    if _SENSITIVE.search(key):
        return '[redacted]'
    if isinstance(value, dict):
        return {k: _scrub(v, str(k), secrets) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_scrub(v, "", secrets) for v in value]
    if isinstance(value, str):
        # Raw request log lines can contain query credentials and visitor text.
        if _REQUEST.search(value):
            return '[redacted]'
        for secret in secrets:
            value = value.replace(secret, '[redacted]')
        return _TOKEN.sub('[redacted]', value)
    if isinstance(value, (int, float, bool)) or value is None:
        return value
    return '[redacted]'


def redact_event(logger, method_name, event_dict):
    return scrub(event_dict)
