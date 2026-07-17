"""
Universal log config for IPA Clutch Batch.
"""
import logging
import sys
from pathlib import Path

LOGGER_NAME = "ipa_clutch_batch"

class ColoredFormatter(logging.Formatter):
    """
    provide different colors based on log levels.
    """
    # ANSI Color Codes
    COLORS = {
        logging.DEBUG: "\033[36m",  # Cyan
        logging.INFO: "\033[32m",  # Green
        logging.WARNING: "\033[33m",  # Yellow
        logging.ERROR: "\033[31m",  # Red
        logging.CRITICAL: "\033[41m",  # Red Background
    }
    RESET = "\033[0m"

    def format(self, record):
        # Pick color based on level
        color = self.COLORS.get(record.levelno, "")

        # Build precision timestamp
        log_fmt = f"{color}[%(asctime)s.%(msecs)03d] [%(levelname)s]"

        # Add source info (filename and line) only for ERROR and above
        if record.levelno >= logging.ERROR:
            log_fmt += " [%(name)s - %(filename)s:%(lineno)d]"

        log_fmt += f" %(message)s{self.RESET}"

        # Create a temporary formatter with the defined date format
        formatter = logging.Formatter(log_fmt, datefmt='%Y-%m-%d %H:%M:%S')
        return formatter.format(record)


def setup_logger() -> logging.Logger:
    """
    Initializes a logger with console handlers for both stdout and stderr.
    """
    _logger = logging.getLogger(LOGGER_NAME)
    _logger.setLevel(logging.DEBUG)
    _logger.propagate = False

    if not _logger.handlers:
        # Standard Output, Handler for regular logs (DEBUG, INFO, WARNING)
        stdout_h = logging.StreamHandler(sys.stdout)
        stdout_h.setLevel(logging.DEBUG)
        stdout_h.addFilter(lambda r: r.levelno < logging.ERROR)
        stdout_h.setFormatter(ColoredFormatter())

        # Standard Error, Handler for error logs (ERROR, CRITICAL)
        stderr_h = logging.StreamHandler(sys.stderr)
        stderr_h.setLevel(logging.ERROR)
        stderr_h.setFormatter(ColoredFormatter())

        _logger.addHandler(stdout_h)
        _logger.addHandler(stderr_h)

    return _logger


# Global logger instance for other modules
logger: logging.Logger = setup_logger()


def add_file_handler(log_path: Path):
    """
    Adds a file handler. If one exists, removes it first to avoid duplicates or
    writing to the wrong location after a path update.
    """
    log_path.parent.mkdir(parents=True, exist_ok=True)

    # Get the global logger
    _logger = logging.getLogger(LOGGER_NAME)

    # 1. Remove existing FileHandlers to avoid duplication or path conflicts
    for h in _logger.handlers[:]:
        if isinstance(h, logging.FileHandler):
            h.close()
            _logger.removeHandler(h)

    # 2. Add the new handler
    file_h = logging.FileHandler(log_path, mode='w', encoding='utf-8')
    file_h.setLevel(logging.DEBUG)
    # no need color format gor .log
    file_fmt = logging.Formatter(
        '[%(asctime)s.%(msecs)03d] [%(levelname)s] [%(filename)s:%(lineno)d] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    file_h.setFormatter(file_fmt)
    _logger.addHandler(file_h)
