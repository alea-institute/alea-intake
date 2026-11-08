"""Keep the provider library's import-time file logger out of the user's home."""
import logging
from unittest.mock import patch

with patch("logging.handlers.RotatingFileHandler", return_value=logging.NullHandler()):
    import app.services.llm_service  # noqa: F401
