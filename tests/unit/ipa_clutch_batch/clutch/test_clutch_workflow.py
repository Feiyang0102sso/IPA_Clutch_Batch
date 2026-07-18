"""Unit tests for the dedicated Clutch check workflow."""

from dataclasses import dataclass

from ipa_clutch_batch.clutch import clutch_workflow


def test_clutch_check_uses_shared_ssh_connection_defaults(monkeypatch):
    """Use the same configured SSH defaults as the normal workflow."""
    captured_connection_arguments = {}
    fake_connection = FakeUsbSshConnection()

    def get_mock_device_udid():
        return "mock-udid"

    def create_fake_connection(udid: str):
        captured_connection_arguments["udid"] = udid
        return fake_connection

    def get_successful_clutch_result(ssh_connection):
        assert ssh_connection is fake_connection
        return FakeClutchResult(success=True)

    monkeypatch.setattr(
        clutch_workflow,
        "get_single_connected_device_udid",
        get_mock_device_udid,
    )
    monkeypatch.setattr(
        clutch_workflow,
        "UsbSshConnection",
        create_fake_connection,
    )
    monkeypatch.setattr(
        clutch_workflow,
        "ensure_clutch_ready",
        get_successful_clutch_result,
    )

    exit_code = clutch_workflow.run_clutch_check()

    assert exit_code == 0
    assert captured_connection_arguments == {"udid": "mock-udid"}
    assert fake_connection.connected
    assert fake_connection.closed


@dataclass(frozen=True)
class FakeClutchResult:
    """Expose the success flag used by the workflow."""

    success: bool


class FakeUsbSshConnection:
    """Record the dedicated workflow connection lifecycle."""

    def __init__(self):
        self.connected = False
        self.closed = False

    def connect(self) -> bool:
        """Record a successful SSH connection."""
        self.connected = True
        return True

    def close(self):
        """Record SSH cleanup."""
        self.closed = True
