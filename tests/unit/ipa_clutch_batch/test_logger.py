"""Unit tests for console logging modes and progress coordination."""

import logging

from ipa_clutch_batch import logger as logger_module


def test_console_logging_defaults_to_warning_and_verbose_enables_debug():
    """Change only the stdout console threshold between the two modes."""
    logger_module.configure_console_logging(False)
    stdout_handler = _get_stdout_handler()
    assert stdout_handler.level == logging.WARNING

    logger_module.configure_console_logging(True)
    assert stdout_handler.level == logging.DEBUG

    # Restore the application default for tests that run afterwards.
    logger_module.configure_console_logging(False)


def test_file_logging_remains_complete_in_both_console_modes(tmp_path):
    """Keep the file handler at DEBUG regardless of the console selection."""
    log_path = tmp_path / "complete.log"
    logger_module.add_file_handler(log_path)
    file_handler = _get_file_handler()

    try:
        logger_module.configure_console_logging(False)
        assert file_handler.level == logging.DEBUG

        logger_module.configure_console_logging(True)
        assert file_handler.level == logging.DEBUG
    finally:
        file_handler.close()
        logger_module.logger.removeHandler(file_handler)
        logger_module.configure_console_logging(False)


def _get_stdout_handler() -> logging.Handler:
    """Return the named stdout handler configured by the application."""
    for handler in logger_module.logger.handlers:
        if handler.get_name() == logger_module.STDOUT_HANDLER_NAME:
            return handler
    raise AssertionError("stdout console handler was not configured")


def _get_file_handler() -> logging.FileHandler:
    """Return the active file handler configured by the application."""
    for handler in logger_module.logger.handlers:
        if isinstance(handler, logging.FileHandler):
            return handler
    raise AssertionError("file handler was not configured")
