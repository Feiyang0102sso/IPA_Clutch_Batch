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
    )
    workflow_events = []
    fake_connection = FakeBatchSshConnection(workflow_events)

    def parse_batch_arguments():
        return arguments

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
    ):
        assert input_dir == tmp_path
        assert cracked_dir == tmp_path / "cracked"
        assert device_info is not None
        assert ssh_connection is fake_connection
        workflow_events.append("pipeline")
        return FakeProcessSummary()

    monkeypatch.setattr(main, "_parse_arguments", parse_batch_arguments)
    monkeypatch.setattr(main, "init_app_env", initialize_environment)
    monkeypatch.setattr(main, "get_single_connected_device_udid", get_mock_device_udid)
    monkeypatch.setattr(main, "get_device_info", get_mock_device_info)
    monkeypatch.setattr(main, "UsbSshConnection", create_fake_connection)
    monkeypatch.setattr(main, "ensure_clutch_ready", check_mock_clutch)
    monkeypatch.setattr(main, "run_ipa_pipeline", run_mock_ipa_pipeline)

    exit_code = main.main()

    assert exit_code == 0
    assert workflow_events == ["connect", "clutch", "pipeline", "close"]


def test_clutch_mode_remains_available(monkeypatch):
    """Keep --clutch as a dedicated check-and-repair workflow."""
    arguments = argparse.Namespace(input_path=None, clutch=True, ssh22=False)
    recorded_calls = []

    def parse_clutch_arguments():
        return arguments

    def initialize_environment():
        recorded_calls.append("init")

    def run_mock_clutch_check():
        recorded_calls.append("clutch")
        return 0

    monkeypatch.setattr(main, "_parse_arguments", parse_clutch_arguments)
    monkeypatch.setattr(main, "init_app_env", initialize_environment)
    monkeypatch.setattr(main, "run_clutch_check", run_mock_clutch_check)

    exit_code = main.main()

    assert exit_code == 0
    assert recorded_calls == ["init", "clutch"]


def test_ssh22_mode_runs_without_an_input_directory(monkeypatch):
    """Select only the standalone port 22 tunnel workflow."""
    arguments = argparse.Namespace(input_path=None, clutch=False, ssh22=True)
    recorded_calls = []

    def parse_ssh22_arguments():
        return arguments

    def initialize_environment():
        recorded_calls.append("init")

    def run_mock_ssh22_tunnel():
        recorded_calls.append("ssh22")
        return 0

    monkeypatch.setattr(main, "_parse_arguments", parse_ssh22_arguments)
    monkeypatch.setattr(main, "init_app_env", initialize_environment)
    monkeypatch.setattr(main, "run_ssh22_tunnel", run_mock_ssh22_tunnel)

    exit_code = main.main()

    assert exit_code == 0
    assert recorded_calls == ["init", "ssh22"]


@pytest.mark.parametrize(
    "command_arguments",
    [
        ["ipa-clutch-batch", "--ssh22", "--clutch"],
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
