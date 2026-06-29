"""Structured JSON logging with automatic correlation ID injection.

Every log line emitted anywhere in the process includes:
  - ts        ISO-8601 timestamp (UTC)
  - level     DEBUG / INFO / WARNING / ERROR
  - logger    dotted logger name (e.g. "worker.ingest")
  - msg       the log message
  - request_id  current correlation ID if one is set (HTTP request or RQ job)

Additional fields can be injected per-call via extra={"extra_fields": {...}}.
"""
import json
import logging
import sys
from datetime import datetime, timezone


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        from app.context import request_id_var  # late import avoids circular at startup

        payload: dict = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        if rid := request_id_var.get(""):
            payload["request_id"] = rid
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        for key, value in getattr(record, "extra_fields", {}).items():
            payload[key] = value
        return json.dumps(payload)


def configure_logging(level: str = "INFO") -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level.upper())
