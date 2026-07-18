"""Run external commands and report their captured output."""

import subprocess

from ipa_clutch_batch.logger import logger


def run_command(command: list[str]) -> subprocess.CompletedProcess[str] | None:
    """Run one system command and log operating-system errors."""
    try:
        return subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
    except OSError as error:
        logger.error(f"Cannot run command: {command[0]}")
        logger.error(f"Operating system error: {error}")
        return None


def log_command_output(
    completed_process: subprocess.CompletedProcess[str],
    is_error: bool,
):
    """Write non-empty command output to the selected log level."""
    output_lines = []

    if completed_process.stdout.strip():
        output_lines.append(f"stdout: {completed_process.stdout.strip()}")
    if completed_process.stderr.strip():
        output_lines.append(f"stderr: {completed_process.stderr.strip()}")

    for output_line in output_lines:
        if is_error:
            logger.error(output_line)
        else:
            logger.debug(output_line)
