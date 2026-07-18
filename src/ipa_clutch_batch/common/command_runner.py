"""Run external commands and report their captured output."""

import re
import subprocess

import paramiko

from ipa_clutch_batch.logger import logger

ANSI_COLOR_PATTERN = re.compile(r"\x1b\[[0-9;]*m")


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


def log_ssh_output(
    stdout: paramiko.ChannelFile,
    stderr: paramiko.ChannelStderrFile,
) -> tuple[str, str, int]:
    """Read, clean, and log the output returned by an SSH command."""
    stdout_text = stdout.read().decode("utf-8", errors="replace")
    stderr_text = stderr.read().decode("utf-8", errors="replace")
    stdout_text = _clean_command_output(stdout_text)
    stderr_text = _clean_command_output(stderr_text)
    exit_code = stdout.channel.recv_exit_status()

    if stdout_text:
        logger.debug(f"SSH stdout: {stdout_text}")
    if stderr_text:
        logger.error(f"SSH stderr: {stderr_text}")

    if exit_code != 0:
        logger.error(f"SSH command exit code: {exit_code}")

    return stdout_text, stderr_text, exit_code


def _clean_command_output(command_output: str) -> str:
    """Remove terminal color codes and normalize command output."""
    clean_output = ANSI_COLOR_PATTERN.sub("", command_output)
    clean_output = clean_output.replace("\r", "")
    return clean_output.strip()
