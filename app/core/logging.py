import contextvars
import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from app.core.config import settings

_CONFIGURED = False

# backend/logs
LOG_DIR = Path(__file__).resolve().parent.parent.parent / "logs"

request_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="-")


class _RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get()
        return True


def configure_logging() -> None:
    """Configures application/system logging. Kept entirely separate from audit
    logging, which is persisted to the audit_logs table via app.services.audit_service.
    """
    global _CONFIGURED
    if _CONFIGURED:
        return

    root_logger = logging.getLogger()
    root_logger.setLevel(settings.LOG_LEVEL)

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | [%(request_id)s] | %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S%z",
    )
    request_id_filter = _RequestIdFilter()

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(formatter)
    stream_handler.addFilter(request_id_filter)

    LOG_DIR.mkdir(parents=True, exist_ok=True)
    file_handler = RotatingFileHandler(
        LOG_DIR / "app.log",
        maxBytes=5 * 1024 * 1024,  # 5 MB per file
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    file_handler.addFilter(request_id_filter)

    root_logger.handlers.clear()
    root_logger.addHandler(stream_handler)
    root_logger.addHandler(file_handler)

    # Keep noisy third-party loggers at a sane level.
    logging.getLogger("uvicorn.access").setLevel(logging.INFO)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
