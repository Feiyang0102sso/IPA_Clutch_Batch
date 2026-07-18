"""Unit tests for the shared external command helpers."""

import subprocess

from ipa_clutch_batch.common import command_runner


def test_run_command_uses_expected_subprocess_options(monkeypatch):
    """Run commands with stable text decoding and captured output."""
    expected_process = subprocess.CompletedProcess(
        args=["tool", "--version"],
        returncode=0,
        stdout="1.0\n",
        stderr="",
    )
    captured_arguments = {}

    def fake_run(command, **options):
        captured_arguments["command"] = command
        captured_arguments["options"] = options
        return expected_process

    monkeypatch.setattr(command_runner.subprocess, "run", fake_run)

    completed_process = command_runner.run_command(["tool", "--version"])

    assert completed_process is expected_process
    assert captured_arguments == {
        "command": ["tool", "--version"],
        "options": {
            "capture_output": True,
            "text": True,
            "encoding": "utf-8",
            "errors": "replace",
            "check": False,
        },
    }


def test_run_command_logs_operating_system_error(monkeypatch):
    """Return None and retain useful diagnostics when process startup fails."""
    fake_logger = FakeLogger()

    def raise_os_error(command, **options):
        raise OSError("mock failure")

    monkeypatch.setattr(command_runner.subprocess, "run", raise_os_error)
    monkeypatch.setattr(command_runner, "logger", fake_logger)

    completed_process = command_runner.run_command(["missing-tool"])

    assert completed_process is None
    assert fake_logger.errors == [
        "Cannot run command: missing-tool",
        "Operating system error: mock failure",
    ]


def test_log_command_output_uses_error_level(monkeypatch):
    """Log trimmed stdout and stderr as errors when a command fails."""
    fake_logger = FakeLogger()
    completed_process = subprocess.CompletedProcess(
        args=["tool"],
        returncode=1,
        stdout=" output \n",
        stderr=" failure \n",
    )
    monkeypatch.setattr(command_runner, "logger", fake_logger)

    command_runner.log_command_output(completed_process, is_error=True)

    assert fake_logger.errors == ["stdout: output", "stderr: failure"]
    assert fake_logger.debugs == []


def test_log_command_output_uses_debug_level_and_ignores_empty_output(monkeypatch):
    """Log successful output as debug and skip whitespace-only stderr."""
    fake_logger = FakeLogger()
    completed_process = subprocess.CompletedProcess(
        args=["tool"],
        returncode=0,
        stdout=" installed \n",
        stderr="  \n",
    )
    monkeypatch.setattr(command_runner, "logger", fake_logger)

    command_runner.log_command_output(completed_process, is_error=False)

    assert fake_logger.errors == []
    assert fake_logger.debugs == ["stdout: installed"]


def test_log_ssh_output_cleans_output_and_logs_failure(monkeypatch):
    """Return normalized SSH output and retain failure diagnostics."""
    fake_logger = FakeLogger()
    fake_channel = FakeSshChannel(exit_code=7)
    stdout = FakeSshStream(b"\x1b[32m output\r\n", fake_channel)
    stderr = FakeSshStream(b" failure\r\n", fake_channel)
    monkeypatch.setattr(command_runner, "logger", fake_logger)

    stdout_text, stderr_text, exit_code = command_runner.log_ssh_output(
        stdout,
        stderr,
    )

    assert stdout_text == "output"
    assert stderr_text == "failure"
    assert exit_code == 7
    assert fake_logger.infos == ["SSH stdout: output"]
    assert fake_logger.errors == [
        "SSH stderr: failure",
        "SSH command exit code: 7",
    ]


class FakeSshChannel:
    """Return a configured SSH command exit code."""

    def __init__(self, exit_code: int):
        self.exit_code = exit_code

    def recv_exit_status(self) -> int:
        """Return the configured exit code."""
        return self.exit_code


class FakeSshStream:
    """Provide byte output and the associated fake SSH channel."""

    def __init__(self, output: bytes, channel: FakeSshChannel):
        self.output = output
        self.channel = channel

    def read(self) -> bytes:
        """Return the configured stream output."""
        return self.output


class FakeLogger:
    """Collect error and debug messages for assertions."""

    def __init__(self):
        self.errors = []
        self.debugs = []
        self.infos = []

    def error(self, message: str):
        """Collect an error message."""
        self.errors.append(message)

    def debug(self, message: str):
        """Collect a debug message."""
        self.debugs.append(message)

    def info(self, message: str):
        """Collect an informational message."""
        self.infos.append(message)
