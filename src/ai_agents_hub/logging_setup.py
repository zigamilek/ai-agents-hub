from __future__ import annotations

import logging
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path

from ai_agents_hub.config import LoggingConfig

TRACE_LEVEL_NUM = 5


def _register_trace_level() -> None:
    if hasattr(logging, "TRACE"):
        return

    logging.addLevelName(TRACE_LEVEL_NUM, "TRACE")
    setattr(logging, "TRACE", TRACE_LEVEL_NUM)

    def trace(self: logging.Logger, message: str, *args: object, **kwargs: object) -> None:
        if self.isEnabledFor(TRACE_LEVEL_NUM):
            self._log(TRACE_LEVEL_NUM, message, args, **kwargs)

    setattr(logging.Logger, "trace", trace)


def _level_to_int(level: str) -> int:
    mapping = {
        "ERROR": logging.ERROR,
        "WARNING": logging.WARNING,
        "INFO": logging.INFO,
        "DEBUG": logging.DEBUG,
        "TRACE": TRACE_LEVEL_NUM,
    }
    return mapping.get(level.upper(), logging.INFO)


def _formatter() -> logging.Formatter:
    return logging.Formatter(
        fmt="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def _clear_handlers(root: logging.Logger) -> None:
    for handler in list(root.handlers):
        root.removeHandler(handler)
        try:
            handler.close()
        except Exception:
            pass


def configure_logging(config: LoggingConfig) -> None:
    _register_trace_level()

    root = logging.getLogger()
    _clear_handlers(root)
    root.setLevel(_level_to_int(config.level))

    fmt = _formatter()
    mode = config.output

    if mode in {"console", "both"}:
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(fmt)
        root.addHandler(console_handler)

    if mode in {"file", "both"}:
        log_dir = Path(config.directory)
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / config.filename
        if config.daily_rotation:
            file_handler = TimedRotatingFileHandler(
                filename=str(log_file),
                when="midnight",
                backupCount=config.retention_days,
                utc=config.utc,
                encoding="utf-8",
            )
        else:
            file_handler = logging.FileHandler(str(log_file), encoding="utf-8")
        file_handler.setFormatter(fmt)
        root.addHandler(file_handler)

    logger = logging.getLogger(__name__)
    logger.info(
        "Logging configured: level=%s output=%s file=%s/%s rotation=%s",
        config.level,
        config.output,
        config.directory,
        config.filename,
        config.daily_rotation,
    )


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
