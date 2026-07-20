"""Unit tests for command-line workflow selection and exclusivity."""

import argparse
from dataclasses import dataclass
import sys

import pytest

from ipa_clutch_batch import main


def test_batch_checks_clutch_after_ssh_before_ipa_pipeline(
    monkeypatch,
    tmp_path,
):
    """Repair Clutch after connecting and before processing any IPA file."""
    ipa_path = tmp_path / "app.ipa"
    ipa_path.touch()
    arguments = argparse.Namespace(
        input_path=tmp_path,
        clutch=False,
        ssh22=False,
        verbose=False,
    )
    workflow_events = []
    fake_connection = FakeBatchSshConnection(workflow_events)
    fake_progress_display = FakeProgressDisplay(workflow_events)

    def parse_batch_arguments():
        return arguments

    def configure_batch_console_logs(verbose: bool):
        workflow_events.append(f"logging:{verbose}")

    def initialize_environment(input_dir=None):
        assert input_dir == tmp_path

    def get_mock_device_udid():
        return "mock-udid"

    def get_mock_device_info(device_udid: str):
        assert device_udid == "mock-udid"
        return object()

    def create_fake_connection(device_udid: str):
        assert device_udid == "mock-udid"
        return fake_connection

    def check_mock_clutch(ssh_connection):
        assert ssh_connection is fake_connection
        workflow_events.append("clutch")
        return FakeClutchResult(success=True)

    def run_mock_ipa_pipeline(
        input_dir,
        cracked_dir,
        device_info,
        ssh_connection,
        progress_reporter=None,
    ):
        assert input_dir == tmp_path
        assert cracked_dir == tmp_path / "cracked"
        assert device_info is not None
        assert ssh_connection is fake_connection
        assert progress_reporter is fake_progress_display
        workflow_events.append("pipeline")
        return FakeProcessSummary()

    monkeypatch.setattr(main, "_parse_arguments", parse_batch_arguments)
    monkeypatch.setattr(
        main,
        "configure_console_logging",
        configure_batch_console_logs,
    )
    monkeypatch.setattr(main, "init_app_env", initialize_environment)
    monkeypatch.setattr(main, "get_single_connected_device_udid", get_mock_device_udid)
    monkeypatch.setattr(main, "get_device_info", get_mock_device_info)
    monkeypatch.setattr(main, "UsbSshConnection", create_fake_connection)
    monkeypatch.setattr(
        main,
        "WorkflowProgress",
        lambda enabled: fake_progress_display,
    )
    monkeypatch.setattr(main, "ensure_clutch_ready", check_mock_clutch)
    monkeypatch.setattr(main, "run_ipa_pipeline", run_mock_ipa_pipeline)

    exit_code = main.main()

    assert exit_code == 0
    assert workflow_events == [
        "logging:False",
        "progress:ssh_started",
        "connect",
        "progress:ssh_completed",
        "progress:clutch_started",
        "clutch",
        "progress:clutch_completed",
        "pipeline",
        "progress:summary:1:1:0",
        "progress:finished",
        "close",
        "progress:closed",
    ]


def test_clutch_mode_remains_available(monkeypatch):
    """Keep --clutch as a dedicated check-and-repair workflow."""
    arguments = argparse.Namespace(
        input_path=None,
        clutch=True,
        ssh22=False,
        verbose=False,
    )
    recorded_calls = []

    def parse_clutch_arguments():
        return arguments

    def configure_complete_console_logs(verbose: bool):
        recorded_calls.append(f"logging:{verbose}")

    def initialize_environment():
        recorded_calls.append("init")

    def run_mock_clutch_check():
        recorded_calls.append("clutch")
        return 0

    monkeypatch.setattr(main, "_parse_arguments", parse_clutch_arguments)
    monkeypatch.setattr(
        main,
        "configure_console_logging",
        configure_complete_console_logs,
    )
    monkeypatch.setattr(main, "init_app_env", initialize_environment)
    monkeypatch.setattr(main, "run_clutch_check", run_mock_clutch_check)

    exit_code = main.main()

    assert exit_code == 0
    assert recorded_calls == ["logging:True", "init", "clutch"]


def test_ssh22_mode_runs_without_an_input_directory(monkeypatch):
    """Select only the standalone port 22 tunnel workflow."""
    arguments = argparse.Namespace(
        input_path=None,
        clutch=False,
        ssh22=True,
        verbose=False,
    )
    recorded_calls = []

    def parse_ssh22_arguments():
        return arguments

    def configure_complete_console_logs(verbose: bool):
        recorded_calls.append(f"logging:{verbose}")

    def initialize_environment():
        recorded_calls.append("init")

    def run_mock_ssh22_tunnel():
        recorded_calls.append("ssh22")
        return 0

    monkeypatch.setattr(main, "_parse_arguments", parse_ssh22_arguments)
    monkeypatch.setattr(
        main,
        "configure_console_logging",
        configure_complete_console_logs,
    )
    monkeypatch.setattr(main, "init_app_env", initialize_environment)
    monkeypatch.setattr(main, "run_ssh22_tunnel", run_mock_ssh22_tunnel)

    exit_code = main.main()

    assert exit_code == 0
    assert recorded_calls == ["logging:True", "init", "ssh22"]


@pytest.mark.parametrize(
    "command_arguments",
    [
        ["ipa-clutch-batch", "--ssh22", "--clutch"],
        ["ipa-clutch-batch", "--ssh22", "--verbose"],
        ["ipa-clutch-batch", "--ssh22", "input"],
    ],
)
def test_ssh22_rejects_other_workflow_arguments(
    monkeypatch,
    command_arguments,
):
    """Reject Clutch checks and IPA paths when -ssh22 is selected."""
    monkeypatch.setattr(sys, "argv", command_arguments)

    with pytest.raises(SystemExit) as system_exit:
        main._parse_arguments()

    assert system_exit.value.code == 2


def test_verbose_argument_enables_complete_console_logs(monkeypatch, tmp_path):
    """Accept verbose mode together with the normal batch input path."""
    monkeypatch.setattr(
        sys,
        "argv",
        ["ipa-clutch-batch", "--verbose", str(tmp_path)],
    )

    arguments = main._parse_arguments()

    assert arguments.verbose
    assert arguments.input_path == tmp_path


def test_final_summary_logs_counts_and_failed_input_names(monkeypatch):
    """Write the same plain final summary lines to the complete log."""
    logged_messages = []
    process_summary = FakeProcessSummary(
        total=4,
        moved=2,
        failed=2,
        failed_ipa_names=(
            "Gun Bros. 1.0.0.ipa",
            "Second App.ipa",
        ),
    )

    monkeypatch.setattr(main, "log_file_only", logged_messages.append)

    main._log_final_summary(process_summary)

    assert logged_messages == [
        "input:4 success:2 fail:2",
        "fail: Gun Bros. 1.0.0.ipa",
        "fail: Second App.ipa",
    ]


@dataclass(frozen=True)
class FakeClutchResult:
    """Expose the Clutch success state used by the main workflow."""

    success: bool


@dataclass(frozen=True)
class FakeProcessSummary:
    """Expose the successful counters logged by the main workflow."""

    total: int = 1
    cracked: int = 1
    moved: int = 1
    failed: int = 0
    skipped: int = 0
    failed_ipa_names: tuple[str, ...] = ()


class FakeBatchSshConnection:
    """Record the SSH lifecycle used by the batch workflow."""

    def __init__(self, workflow_events: list[str]):
        self.workflow_events = workflow_events

    def connect(self) -> bool:
        """Record a successful SSH connection."""
        self.workflow_events.append("connect")
        return True

    def close(self):
        """Record SSH cleanup."""
        self.workflow_events.append("close")


class FakeProgressDisplay:
    """Record main workflow progress events without terminal output."""

    def __init__(self, workflow_events: list[str]):
        self.workflow_events = workflow_events

    def open(self):
        """Provide the progress lifecycle method used by the application."""

    def start_ssh_stage(self):
        """Record the start of the SSH stage."""
        self.workflow_events.append("progress:ssh_started")

    def complete_ssh_stage(self):
        """Record successful SSH completion."""
        self.workflow_events.append("progress:ssh_completed")

    def start_clutch_stage(self):
        """Record the start of the Clutch stage."""
        self.workflow_events.append("progress:clutch_started")

    def complete_clutch_stage(self):
        """Record successful Clutch completion."""
        self.workflow_events.append("progress:clutch_completed")

    def show_all_tasks_finished(self):
        """Record the final message before SSH cleanup."""
        self.workflow_events.append("progress:finished")

    def show_final_summary(
        self,
        input_count: int,
        success_count: int,
        fail_count: int,
        failed_ipa_names: tuple[str, ...],
    ):
        """Record the final summary values."""
        assert len(failed_ipa_names) == fail_count
        self.workflow_events.append(
            f"progress:summary:{input_count}:{success_count}:{fail_count}"
        )

    def close(self):
        """Record progress cleanup."""
        self.workflow_events.append("progress:closed")
