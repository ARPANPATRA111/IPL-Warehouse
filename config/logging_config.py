import json
import logging
import sys
from datetime import datetime, timezone
from typing import Any

from config.settings import get_settings

class JSONFormatter(logging.Formatter):

    def format(self, record: logging.LogRecord) -> str:
        log_entry: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)

        if hasattr(record, "extra_data"):
            log_entry["data"] = record.extra_data

        return json.dumps(log_entry)

def setup_logging() -> logging.Logger:
    settings = get_settings()

    logger = logging.getLogger("ipl_dw")
    logger.setLevel(getattr(logging, settings.log_level.upper()))

    if logger.handlers:
        logger.handlers.clear()


    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, settings.log_level.upper()))
    console_handler.setFormatter(JSONFormatter())
    logger.addHandler(console_handler)


    logger.propagate = False

    return logger

def get_logger(name: str) -> logging.Logger:
    parent = logging.getLogger("ipl_dw")
    if not parent.handlers:
        setup_logging()
    return parent.getChild(name)
