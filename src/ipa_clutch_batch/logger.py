"""
Universal log config for IPA Clutch Batch.
"""
import logging
from pathlib import Path
import sys

LOGGER_NAME = "ipa_clutch_batch"


class ColoredFormatter(logging.Formatter):
    """
    Provide different colors based on log levels.
    """

    COLORS = {
        logging.DEBUG: "\033[36m",
        logging.INFO: "\033[32m",
        logging.WARNING: "\033[33m",
        logging.ERROR: "\033[31m",
        logging.CRITICAL: "\033[41m",
    }
    RESET = "\033[0m"

    def format(self, record):
        color = self.COLORS.get(record.levelno, "")
        log_fmt = f"{color}[%(asctime)s.%(msecs)03d] [%(levelname)s]"

        if record.levelno >= logging.ERROR:
            log_fmt += " [%(name)s - %(filename)s:%(lineno)d]"

        log_fmt += f" %(message)s{self.RESET}"

        formatter = logging.Formatter(log_fmt, datefmt="%Y-%m-%d %H:%M:%S")
        return formatter.format(record)


def setup_logger() -> logging.Logger:
    """
    Initialize a logger with console handlers for stdout and stderr.
    """
    project_logger = logging.getLogger(LOGGER_NAME)
    project_logger.setLevel(logging.DEBUG)
    project_logger.propagate = False

    if not project_logger.handlers:
        stdout_handler = logging.StreamHandler(sys.stdout)
        stdout_handler.setLevel(logging.DEBUG)
        stdout_handler.addFilter(lambda record: record.levelno < logging.ERROR)
        stdout_handler.setFormatter(ColoredFormatter())

        stderr_handler = logging.StreamHandler(sys.stderr)
        stderr_handler.setLevel(logging.ERROR)
        stderr_handler.setFormatter(ColoredFormatter())

        project_logger.addHandler(stdout_handler)
        project_logger.addHandler(stderr_handler)

    return project_logger


logger: logging.Logger = setup_logger()


def add_file_handler(log_path: Path):
    """
    Add a file handler and remove any old file handler first.
    """
    log_path.parent.mkdir(parents=True, exist_ok=True)

    project_logger = logging.getLogger(LOGGER_NAME)

    for handler in project_logger.handlers[:]:
        if isinstance(handler, logging.FileHandler):
            handler.close()
            project_logger.removeHandler(handler)

    file_handler = logging.FileHandler(log_path, mode="w", encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_formatter = logging.Formatter(
        "[%(asctime)s.%(msecs)03d] [%(levelname)s] [%(filename)s:%(lineno)d] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    file_handler.setFormatter(file_formatter)
    project_logger.addHandler(file_handler)
