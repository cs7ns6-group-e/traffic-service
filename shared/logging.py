import logging
import sys
from typing import Any


def setup_logging(service_name: str, debug: bool = False) -> None:
    """Configure structured logging for a service."""
    level = logging.DEBUG if debug else logging.INFO

    formatter = logging.Formatter(
        fmt='{"time": "%(asctime)s", "level": "%(levelname)s", "service": "'
        + service_name
        + '", "logger": "%(name)s", "message": "%(message)s"}',
        datefmt="%Y-%m-%dT%H:%M:%S",
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    root_logger.handlers.clear()
    root_logger.addHandler(handler)

    # Silence noisy third-party loggers
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING if not debug else logging.INFO)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
