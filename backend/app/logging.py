import json
import logging
import re
import sys
from datetime import datetime, timezone
from typing import Any, Dict

SENSITIVE_KEY_PATTERNS = [
    re.compile(r"password", re.IGNORECASE),
    re.compile(r"secret", re.IGNORECASE),
    re.compile(r"token", re.IGNORECASE),
    re.compile(r"api[_-]?key", re.IGNORECASE),
    re.compile(r"auth(orization)?", re.IGNORECASE),
    re.compile(r"credential", re.IGNORECASE),
    re.compile(r"cookie", re.IGNORECASE),
    re.compile(r"private[_-]?key", re.IGNORECASE),
]

SENSITIVE_VALUE_PATTERNS = [
    (re.compile(r"(Bearer\s+)[A-Za-z0-9\-\._~\+\/]+=*", re.IGNORECASE), r"\1***REDACTED***"),
    (re.compile(r"(://[^:]+:)([^@]+)(@)"), r"\1***REDACTED***\3"),  # URLs with credentials
    (re.compile(r"((?:password|secret|token|api[_-]?key|auth(?:orization)?)\s*[:=]\s*)(['\"][^'\"]+['\"]|\S+)", re.IGNORECASE), r"\1***REDACTED***"),
]


def redact_sensitive_value(value: Any) -> Any:
    """Recursively scrub sensitive keys and regex patterns from values."""
    if isinstance(value, str):
        redacted = value
        for pattern, replacement in SENSITIVE_VALUE_PATTERNS:
            redacted = pattern.sub(replacement, redacted)
        return redacted
    elif isinstance(value, dict):
        new_dict: Dict[str, Any] = {}
        for k, v in value.items():
            str_key = str(k)
            if any(pattern.search(str_key) for pattern in SENSITIVE_KEY_PATTERNS):
                new_dict[k] = "***REDACTED***"
            else:
                new_dict[k] = redact_sensitive_value(v)
        return new_dict
    elif isinstance(value, (list, tuple, set)):
        return [redact_sensitive_value(item) for item in value]
    return value


class StructuredJsonFormatter(logging.Formatter):
    """
    JSON log formatter with automated secret redaction ensuring
    no credentials, tokens, or sensitive configuration values are leaked into logs.
    """

    def format(self, record: logging.LogRecord) -> str:
        # Format the basic log record
        message = record.getMessage()
        redacted_message = redact_sensitive_value(message)

        log_entry: Dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": redacted_message,
        }

        # Include exceptions if present
        if record.exc_info:
            log_entry["exception"] = redact_sensitive_value(self.formatException(record.exc_info))

        # Include extra attributes attached to the record
        standard_attrs = {
            "name", "msg", "args", "levelname", "levelno", "pathname", "filename",
            "module", "exc_info", "exc_text", "stack_info", "lineno", "funcName",
            "created", "msecs", "relativeCreated", "thread", "threadName",
            "processName", "process", "message"
        }
        extras = {k: v for k, v in record.__dict__.items() if k not in standard_attrs}
        if extras:
            log_entry["extra"] = redact_sensitive_value(extras)

        return json.dumps(log_entry, default=str)


def setup_logging(log_level: str = "INFO") -> None:
    """Configures structured logging on root logger."""
    root_logger = logging.getLogger()
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)
    root_logger.setLevel(numeric_level)

    # Avoid duplicate handlers
    for handler in list(root_logger.handlers):
        root_logger.removeHandler(handler)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(StructuredJsonFormatter())
    root_logger.addHandler(console_handler)

    # Silence overly verbose external loggers
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
