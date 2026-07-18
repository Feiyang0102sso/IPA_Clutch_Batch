"""Unit tests for Clutch installation and verification."""

import hashlib
import io
from pathlib import Path
import stat

from ipa_clutch_batch.clutch import clutch_manager

PRESET_CONTENT = b"known clutch binary"
OTHER_CONTENT = b"different clutch binary"


def test_missing_local_preset_stops_before_opening_sftp(tmp_path: Path):
    """Fail clearly when the ignored preset resource was not downloaded."""
    ssh_connection = FakeSshConnection(FakeSftpClient())
    missing_path = tmp_path / "Clutch"

    result = clutch_manager.ensure_clutch_ready(
        ssh_connection,
        missing_path,
    )

    assert not result.success
    assert result.failure_reason == f"Preset Clutch binary not found: {missing_path}"
    assert ssh_connection.open_sftp_count == 0


def test_missing_remote_clutch_is_installed_with_mode_0755(
    monkeypatch,
    tmp_path: Path,
):
    """Upload the preset and give owner, group, and others execute permission."""
    fake_logger = FakeLogger()
    preset_path = _create_preset(tmp_path)
    sftp_client = FakeSftpClient()
    ssh_connection = FakeSshConnection(sftp_client)
    monkeypatch.setattr(clutch_manager, "logger", fake_logger)

    result = clutch_manager.ensure_clutch_ready(
        ssh_connection,
        preset_path,
    )

    assert result.success
    assert result.installed
    assert not result.permissions_fixed
    assert sftp_client.files[clutch_manager.REMOTE_CLUTCH_PATH] == PRESET_CONTENT
    assert sftp_client.modes[clutch_manager.REMOTE_CLUTCH_PATH] == 0o755
    assert sftp_client.closed
    assert (
        f"Clutch is not installed at: {clutch_manager.REMOTE_CLUTCH_PATH}"
        in fake_logger.warnings
    )


def test_existing_clutch_permissions_are_changed_to_0755(
    monkeypatch,
    tmp_path: Path,
):
    """Replace incomplete execute permissions with the documented mode."""
    fake_logger = FakeLogger()
    preset_path = _create_preset(tmp_path)
    sftp_client = FakeSftpClient(
        remote_content=PRESET_CONTENT,
        remote_mode=0o744,
    )
    ssh_connection = FakeSshConnection(sftp_client)
    monkeypatch.setattr(clutch_manager, "logger", fake_logger)

    result = clutch_manager.ensure_clutch_ready(
        ssh_connection,
        preset_path,
    )

    assert result.success
    assert not result.installed
    assert result.permissions_fixed
    assert sftp_client.modes[clutch_manager.REMOTE_CLUTCH_PATH] == 0o755
    assert "Current Clutch mode: 0744" in fake_logger.infos
    assert "Clutch mode changed to: 0755" in fake_logger.infos
    assert (
        "Clutch mode is incorrect: 0744. Changing to 0755."
        in fake_logger.warnings
    )


def test_existing_clutch_with_correct_mode_logs_mode_ok(
    monkeypatch,
    tmp_path: Path,
):
    """Report that mode 0755 already satisfies the requirement."""
    fake_logger = FakeLogger()
    preset_path = _create_preset(tmp_path)
    sftp_client = FakeSftpClient(
        remote_content=PRESET_CONTENT,
        remote_mode=0o755,
    )
    ssh_connection = FakeSshConnection(sftp_client)
    monkeypatch.setattr(clutch_manager, "logger", fake_logger)

    result = clutch_manager.ensure_clutch_ready(
        ssh_connection,
        preset_path,
    )

    assert result.success
    assert not result.permissions_fixed
    assert "Current Clutch mode: 0755" in fake_logger.infos
    assert "Clutch mode OK: 0755" in fake_logger.infos


def test_existing_clutch_with_different_hash_is_replaced(
    monkeypatch,
    tmp_path: Path,
):
    """Replace an unexpected binary with the verified local preset."""
    fake_logger = FakeLogger()
    preset_path = _create_preset(tmp_path)
    sftp_client = FakeSftpClient(
        remote_content=OTHER_CONTENT,
        remote_mode=0o755,
    )
    ssh_connection = FakeSshConnection(sftp_client)
    monkeypatch.setattr(clutch_manager, "logger", fake_logger)

    result = clutch_manager.ensure_clutch_ready(
        ssh_connection,
        preset_path,
    )

    assert result.success
    assert result.installed
    assert result.local_sha256 == hashlib.sha256(PRESET_CONTENT).hexdigest()
    assert result.remote_sha256 == hashlib.sha256(PRESET_CONTENT).hexdigest()
    assert sftp_client.files[clutch_manager.REMOTE_CLUTCH_PATH] == PRESET_CONTENT
    assert sftp_client.modes[clutch_manager.REMOTE_CLUTCH_PATH] == 0o755
    assert (
        "Remote Clutch SHA-256 does not match the preset binary. "
        "Replacing the remote binary."
        in fake_logger.warnings
    )


def _create_preset(tmp_path: Path) -> Path:
    """Create one known local Clutch binary."""
    preset_path = tmp_path / "Clutch"
    preset_path.write_bytes(PRESET_CONTENT)
    return preset_path


class FakeSshConnection:
    """Return one fake SFTP client and record whether it was requested."""

    def __init__(self, sftp_client):
        self.sftp_client = sftp_client
        self.open_sftp_count = 0

    def open_sftp(self):
        """Return the configured fake SFTP client."""
        self.open_sftp_count += 1
        return self.sftp_client


class FakeSftpClient:
    """Provide the SFTP operations required by the Clutch manager."""

    def __init__(
        self,
        remote_content: bytes | None = None,
        remote_mode: int = 0o755,
    ):
        self.files = {}
        self.modes = {}
        self.closed = False
        if remote_content is not None:
            self.files[clutch_manager.REMOTE_CLUTCH_PATH] = remote_content
            self.modes[clutch_manager.REMOTE_CLUTCH_PATH] = remote_mode

    def stat(self, remote_path: str):
        """Return file size and mode, or report a missing remote file."""
        if remote_path not in self.files:
            raise FileNotFoundError(2, "No such file", remote_path)

        file_mode = stat.S_IFREG | self.modes[remote_path]
        return FakeSftpAttributes(file_mode)

    def put(self, local_path: str, remote_path: str):
        """Copy local bytes into the fake remote file map."""
        self.files[remote_path] = Path(local_path).read_bytes()
        self.modes[remote_path] = 0o600

    def chmod(self, remote_path: str, file_mode: int):
        """Record the requested remote permission mode."""
        self.modes[remote_path] = file_mode

    def rename(self, old_path: str, new_path: str):
        """Move one fake remote file and its mode."""
        self.files[new_path] = self.files.pop(old_path)
        self.modes[new_path] = self.modes.pop(old_path)

    def remove(self, remote_path: str):
        """Remove one fake remote file and its mode."""
        del self.files[remote_path]
        del self.modes[remote_path]

    def open(self, remote_path: str, file_mode: str):
        """Open remote bytes for hash calculation."""
        assert file_mode == "rb"
        return io.BytesIO(self.files[remote_path])

    def close(self):
        """Record SFTP cleanup."""
        self.closed = True


class FakeSftpAttributes:
    """Expose the remote mode used by the manager."""

    def __init__(self, file_mode: int):
        self.st_mode = file_mode


class FakeLogger:
    """Collect Clutch check messages for log assertions."""

    def __init__(self):
        self.infos = []
        self.warnings = []
        self.errors = []

    def info(self, message: str):
        """Collect an informational message."""
        self.infos.append(message)

    def warning(self, message: str):
        """Collect a warning message."""
        self.warnings.append(message)

    def error(self, message: str):
        """Collect an error message."""
        self.errors.append(message)
