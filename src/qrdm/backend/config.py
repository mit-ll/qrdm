# Copyright 2024, Massachusetts Institute of Technology
# Subject to FAR 52.227-11 - Patent Rights - Ownership by the Contractor (May 2014).
# SPDX-License-Identifier: MIT
"""Configuration of the QRDM FastAPI Application."""
import logging
import sys
from enum import Enum
from functools import lru_cache

import structlog
from pydantic_settings import BaseSettings
from structlog.types import EventDict, Processor

from qrdm.models import ECSettingValues

__all__ = ["BackendSettings", "get_backend_settings", "configure_app_logging"]


class LogLevelValues(str, Enum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class BackendSettings(BaseSettings):
    """Pydantic-settings object for QRDM FastAPI Application."""

    QRDM_ERROR_TOLERANCE: ECSettingValues = ECSettingValues.M
    QRDM_ENCODE_EC_CODES: bool = True
    QRDM_LOG_LEVEL: LogLevelValues = LogLevelValues.INFO
    QRDM_JSON_LOGS: bool = False


@lru_cache
def get_backend_settings() -> BackendSettings:
    """Return a cached instance of the application settings."""
    return BackendSettings()


# Adapted from https://gist.github.com/nymous/f138c7f06062b7c43c060bf03759c29e
# MIT License - Copyright (c) 2023 Thomas GAUDIN
def drop_color_message_key(_, __, event_dict: EventDict) -> EventDict:
    """Drop the `color_message` key from an EventDict.

    Uvicorn logs the message a second time in the extra `color_message`, but we don't
    need it. This processor drops the key from the event dict if it exists.
    """
    event_dict.pop("color_message", None)
    return event_dict


def configure_app_logging() -> None:
    """Configure the `structlog` logging pipeline of the FastAPI Application."""
    app_settings = get_backend_settings()

    timestamper = structlog.processors.TimeStamper(fmt="iso")

    shared_processors: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.stdlib.ExtraAdder(),
        drop_color_message_key,
        timestamper,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.UnicodeDecoder(),
    ]

    if app_settings.QRDM_JSON_LOGS:
        # Format the exception only for JSON logs, as we want to pretty-print them when
        # using the ConsoleRenderer
        shared_processors.append(structlog.processors.format_exc_info)

    structlog.configure(
        processors=[
            *shared_processors,
            # Prepare event dict for `ProcessorFormatter`.
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    log_renderer: structlog.types.Processor
    if app_settings.QRDM_JSON_LOGS:
        log_renderer = structlog.processors.JSONRenderer()
        handler = logging.StreamHandler(sys.stdout)
    else:
        log_renderer = structlog.dev.ConsoleRenderer()
        handler = logging.StreamHandler(sys.stderr)

    formatter = structlog.stdlib.ProcessorFormatter(
        # These run ONLY on `logging` entries that do NOT originate within structlog.
        foreign_pre_chain=shared_processors,
        # These run on ALL entries after the pre_chain is done.
        processors=[
            # Remove _record & _from_structlog.
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            log_renderer,
        ],
    )

    # Use OUR `ProcessorFormatter` to format all `logging` entries.
    handler.setFormatter(formatter)
    root_logger = logging.getLogger()
    root_logger.addHandler(handler)
    root_logger.setLevel(app_settings.QRDM_LOG_LEVEL.value)

    for _log in ["uvicorn", "uvicorn.error"]:
        # Clear the log handlers for uvicorn loggers, and enable propagation so the
        # messages are caught by our root logger and formatted correctly by structlog
        logging.getLogger(_log).handlers.clear()
        logging.getLogger(_log).propagate = True

    # Since we re-create the access logs ourselves, to add all information in the
    # structured log (see the `logging_middleware` in main.py), we clear the handlers
    # and prevent the logs to propagate to a logger higher up in the hierarchy
    # (effectively rendering them silent).
    logging.getLogger("uvicorn.access").handlers.clear()
    logging.getLogger("uvicorn.access").propagate = False

    def handle_exception(exc_type, exc_value, exc_traceback):
        """Log any uncaught exception instead of letting it be printed by Python.

        Leaves KeyboardInterrupt untouched to allow users to Ctrl+C to stop
        See https://stackoverflow.com/a/16993115/3641865
        """
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return

        root_logger.error(
            "Uncaught exception", exc_info=(exc_type, exc_value, exc_traceback)
        )

    sys.excepthook = handle_exception
