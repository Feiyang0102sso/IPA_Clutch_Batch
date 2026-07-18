"""Unit tests for the standalone port 22 tunnel workflow."""

from ipa_clutch_batch.device import ssh_tunnel_alt


def test_ssh22_opens_tunnel_only_and_closes_on_ctrl_c(monkeypatch):
    """Keep the tunnel open without creating an application SSH session."""
    captured_connection_arguments = {}
    fake_connection = FakeTunnelConnection()

    def get_mock_device_udid():
        return "mock-udid"

    def create_fake_connection(udid: str, local_port: int):
        captured_connection_arguments["udid"] = udid
        captured_connection_arguments["local_port"] = local_port
        return fake_connection

    def interrupt_monitoring(interval_seconds: float):
        assert interval_seconds == 0.5
        raise KeyboardInterrupt

    monkeypatch.setattr(
        ssh_tunnel_alt,
        "get_single_connected_device_udid",
        get_mock_device_udid,
    )
    monkeypatch.setattr(
        ssh_tunnel_alt,
        "UsbSshConnection",
        create_fake_connection,
    )
    monkeypatch.setattr(
        ssh_tunnel_alt.time,
        "sleep",
        interrupt_monitoring,
    )

    exit_code = ssh_tunnel_alt.run_ssh22_tunnel()

    assert exit_code == 0
    assert captured_connection_arguments == {
        "udid": "mock-udid",
        "local_port": 22,
    }
    assert fake_connection.tunnel_opened
    assert fake_connection.closed
    assert not fake_connection.ssh_connected


class FakeTunnelConnection:
    """Record tunnel-only operations performed by the workflow."""

    def __init__(self):
        self.tunnel_opened = False
        self.ssh_connected = False
        self.closed = False

    def open_tunnel(self) -> bool:
        """Record a successful iproxy start."""
        self.tunnel_opened = True
        return True

    def connect(self) -> bool:
        """Record an unexpected application SSH login."""
        self.ssh_connected = True
        return True

    def is_tunnel_active(self) -> bool:
        """Keep the fake tunnel active until monitoring is interrupted."""
        return True

    def close(self):
        """Record tunnel cleanup."""
        self.closed = True
