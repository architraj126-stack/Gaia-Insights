import json
import logging
from backend.app.config import settings
from backend.app.logging import redact_sensitive_value, StructuredJsonFormatter

def test_config_defaults():
    assert settings.APP_NAME == "Earth Science Explorer API"
    assert "http://localhost:5173" in settings.CORS_ORIGINS
    assert settings.LOG_LEVEL in ["DEBUG", "INFO", "WARNING", "ERROR"]

def test_secret_redaction():
    payload = {
        "user": "test_user",
        "api_key": "super_secret_api_key_123",
        "nested": {
            "password": "my_db_password",
            "normal_value": 42
        },
        "url": "postgresql://postgres:secretpass123@localhost:5432/db",
        "auth_header": "Bearer secret_jwt_token_here"
    }

    cleaned = redact_sensitive_value(payload)

    assert cleaned["user"] == "test_user"
    assert cleaned["api_key"] == "***REDACTED***"
    assert cleaned["nested"]["password"] == "***REDACTED***"
    assert cleaned["nested"]["normal_value"] == 42
    assert "secretpass123" not in cleaned["url"]
    assert "***REDACTED***" in cleaned["url"]
    assert "secret_jwt_token_here" not in cleaned["auth_header"]
    assert "***REDACTED***" in cleaned["auth_header"]

def test_json_formatter_never_leaks_secrets():
    formatter = StructuredJsonFormatter()
    record = logging.LogRecord(
        name="test_logger",
        level=logging.INFO,
        pathname=__file__,
        lineno=10,
        msg="Connecting with password: super_secret_pw_999",
        args=(),
        exc_info=None
    )
    formatted = formatter.format(record)
    parsed = json.loads(formatted)

    assert "super_secret_pw_999" not in formatted
    assert parsed["level"] == "INFO"
    assert parsed["logger"] == "test_logger"
    assert "***REDACTED***" in parsed["message"]
