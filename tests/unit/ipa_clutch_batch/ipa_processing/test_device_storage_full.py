"""Unit tests for stopping a batch when device storage is full."""

from dataclasses import dataclass
from pathlib import Path
import subprocess

from ipa_clutch_batch.device import DeviceInfo, SshCommandResult
from ipa_clutch_batch.ipa_processing import ipa_cracker, ipa_installer, ipa_pipeline
from ipa_clutch_batch.ipa_processing.ipa_cracker import CrackResult
from ipa_clutch_batch.ipa_processing.ipa_installer import InstallResult


def test_device_storage_error_detection_matches_common_messages():
    """Recognize common storage errors without matching unrelated memory errors."""
    assert ipa_installer.is_device_storage_full_error(
        "",
        "write failed: No space left on device",
    )
    assert ipa_installer.is_device_storage_full_error(
        "Installation failed: not enough free space",
        "",
    )
    assert ipa_installer.is_device_storage_full_error(
        "",
        "Insufficient storage available",
    )
    assert not ipa_installer.is_device_storage_full_error(
        "not enough memory",
        "",
    )


def test_install_result_marks_device_storage_error(monkeypatch, tmp_path: Path):
    """Expose an installer storage error as a structured result flag."""
    ipa_path = tmp_path / "app.ipa"
    installer_path = tmp_path / "ideviceinstaller.exe"
    ipa_path.touch()
    installer_path.touch()

    completed_process = subprocess.CompletedProcess(
        args=[str(installer_path)],
        returncode=1,
        stdout="",
        stderr="Installation failed: No space left on device",
    )

    def fake_run_command(command):
        return completed_process

    monkeypatch.setattr(ipa_installer, "run_command", fake_run_command)

    install_result = ipa_installer.install_ipa(
        ipa_path,
        udid="mock-udid",
        ideviceinstaller_path=installer_path,
    )

    assert install_result is not None
    assert not install_result.success
    assert install_result.device_storage_full
    assert install_result.failure_reason == (
        "The device does not have enough free storage."
    )


def test_install_storage_error_stops_remaining_ipa_files(monkeypatch, tmp_path: Path):
    """Stop installing new IPA files after an installer storage error."""
    ipa_paths = _create_ipa_files(tmp_path, 3)
    installed_names = []
    cracked_bundle_identifiers = []
    fake_logger = FakeLogger()

    def fake_install(ipa_path: Path, udid: str):
        installed_names.append(ipa_path.name)
        if ipa_path == ipa_paths[1]:
            return _create_install_result(
                ipa_path,
                udid,
                success=False,
                device_storage_full=True,
            )
        return _create_install_result(
            ipa_path,
            udid,
            success=True,
            device_storage_full=False,
        )

    def fake_crack(bundle_identifier: str, ssh_connection):
        cracked_bundle_identifiers.append(bundle_identifier)
        return _create_crack_result(bundle_identifier, success=True)

    _mock_batch_dependencies(monkeypatch, fake_logger, fake_install, fake_crack)

    ssh_connection = FakePipelineSshConnection()
    summary = ipa_pipeline.run_ipa_pipeline(
        tmp_path,
        tmp_path / "cracked",
        _create_device_info(),
        ssh_connection,
    )

    assert installed_names == ["app_1.ipa", "app_2.ipa"]
    assert cracked_bundle_identifiers == ["com.example.app_1"]
    assert summary.total == 3
    assert summary.cracked == 1
    assert summary.install_failed == 1
    assert summary.crack_failed == 0
    assert summary.move_failed == 0
    assert summary.moved == 1
    assert summary.skipped == 1
    assert ssh_connection.open_sftp_count == 1
    assert ssh_connection.sftp_client.closed
    assert fake_logger.warnings == [
        "Device storage is full. Batch processing stopped; 1 IPA file(s) skipped."
    ]


def test_normal_install_failure_does_not_stop_batch(monkeypatch, tmp_path: Path):
    """Continue with later IPA files when an install failure is unrelated to storage."""
    ipa_paths = _create_ipa_files(tmp_path, 2)
    installed_names = []
    cracked_bundle_identifiers = []
    fake_logger = FakeLogger()

    def fake_install(ipa_path: Path, udid: str):
        installed_names.append(ipa_path.name)
        if ipa_path == ipa_paths[0]:
            return _create_install_result(
                ipa_path,
                udid,
                success=False,
                device_storage_full=False,
            )
        return _create_install_result(
            ipa_path,
            udid,
            success=True,
            device_storage_full=False,
        )

    def fake_crack(bundle_identifier: str, ssh_connection):
        cracked_bundle_identifiers.append(bundle_identifier)
        return _create_crack_result(bundle_identifier, success=True)

    _mock_batch_dependencies(monkeypatch, fake_logger, fake_install, fake_crack)

    summary = ipa_pipeline.run_ipa_pipeline(
        tmp_path,
        tmp_path / "cracked",
        _create_device_info(),
        FakePipelineSshConnection(),
    )

    assert installed_names == ["app_1.ipa", "app_2.ipa"]
    assert cracked_bundle_identifiers == ["com.example.app_2"]
    assert summary.cracked == 1
    assert summary.moved == 1
    assert summary.install_failed == 1
    assert summary.move_failed == 0
    assert summary.skipped == 0
    assert fake_logger.warnings == []


def test_clutch_storage_error_stops_remaining_ipa_files(monkeypatch, tmp_path: Path):
    """Stop processing new IPA files after a Clutch storage error."""
    _create_ipa_files(tmp_path, 2)
    installed_names = []
    cracked_bundle_identifiers = []
    fake_logger = FakeLogger()

    def fake_install(ipa_path: Path, udid: str):
        installed_names.append(ipa_path.name)
        return _create_install_result(
            ipa_path,
            udid,
            success=True,
            device_storage_full=False,
        )

    def fake_crack(bundle_identifier: str, ssh_connection):
        cracked_bundle_identifiers.append(bundle_identifier)
        return _create_crack_result(
            bundle_identifier,
            success=False,
            device_storage_full=True,
        )

    _mock_batch_dependencies(monkeypatch, fake_logger, fake_install, fake_crack)

    ssh_connection = FakePipelineSshConnection()
    summary = ipa_pipeline.run_ipa_pipeline(
        tmp_path,
        tmp_path / "cracked",
        _create_device_info(),
        ssh_connection,
    )

    assert installed_names == ["app_1.ipa"]
    assert cracked_bundle_identifiers == ["com.example.app_1"]
    assert summary.total == 2
    assert summary.cracked == 0
    assert summary.install_failed == 0
    assert summary.crack_failed == 1
    assert summary.move_failed == 0
    assert summary.moved == 0
    assert summary.skipped == 1
    assert ssh_connection.open_sftp_count == 0


def test_crack_result_marks_clutch_storage_error():
    """Expose a Clutch storage error as a structured result flag."""
    ssh_connection = FakeSshConnection()

    crack_result = ipa_cracker.crack_installed_app(
        "com.example.app",
        ssh_connection,
    )

    assert not crack_result.success
    assert crack_result.device_storage_full
    assert crack_result.failure_reason == (
        "The device does not have enough free storage."
    )


def _mock_batch_dependencies(
    monkeypatch,
    fake_logger,
    fake_install,
    fake_crack,
):
    """Replace device operations while keeping the batch loop under test."""
    monkeypatch.setattr(ipa_pipeline, "logger", fake_logger)
    monkeypatch.setattr(ipa_pipeline, "get_single_ipa_info", _get_fake_ipa_info)
    monkeypatch.setattr(
        ipa_pipeline,
        "get_ipa_compatibility_error",
        _get_no_compatibility_error,
    )
    monkeypatch.setattr(ipa_pipeline, "install_ipa", fake_install)
    monkeypatch.setattr(
        ipa_pipeline,
        "is_already_installed_current_ipa",
        _is_not_already_installed,
    )
    monkeypatch.setattr(ipa_pipeline, "crack_installed_app", fake_crack)
    monkeypatch.setattr(
        ipa_pipeline,
        "move_single_dumped_ipa",
        _move_dump_successfully,
    )


def _create_ipa_files(input_dir: Path, count: int) -> list[Path]:
    """Create alphabetically ordered placeholder IPA files."""
    ipa_paths = []
    for ipa_number in range(1, count + 1):
        ipa_path = input_dir / f"app_{ipa_number}.ipa"
        ipa_path.touch()
        ipa_paths.append(ipa_path)
    return ipa_paths


def _get_fake_ipa_info(ipa_path: Path):
    """Return the metadata field required by the batch loop."""
    return FakeIpaInfo(bundle_identifier=f"com.example.{ipa_path.stem}")


def _get_no_compatibility_error(ipa_info, device_info):
    """Report that the placeholder IPA is compatible with the mock device."""
    return None


def _is_not_already_installed(ipa_info, udid: str):
    """Report that the mock IPA still needs installation."""
    return False


def _move_dump_successfully(remote_ipa_path, cracked_dir, sftp_client):
    """Report a successful move for storage-related batch tests."""
    return True


def _create_device_info() -> DeviceInfo:
    """Create stable device information for batch tests."""
    return DeviceInfo(
        udid="mock-udid",
        name="Mock iPhone",
        product_type="iPhone5,1",
        product_version="6.1.6",
        cpu_architecture="armv7",
        device_family=1,
    )


def _create_install_result(
    ipa_path: Path,
    udid: str,
    success: bool,
    device_storage_full: bool,
) -> InstallResult:
    """Create one installer result for the requested test state."""
    failure_reason = None
    return_code = 0
    if not success:
        failure_reason = "Mock install failure."
        if device_storage_full:
            failure_reason = "The device does not have enough free storage."
        return_code = 1

    return InstallResult(
        ipa_path=ipa_path,
        udid=udid,
        success=success,
        return_code=return_code,
        stdout="",
        stderr="",
        failure_reason=failure_reason,
        device_storage_full=device_storage_full,
    )


def _create_crack_result(
    bundle_identifier: str,
    success: bool,
    device_storage_full: bool = False,
) -> CrackResult:
    """Create one Clutch result for the requested test state."""
    failure_reason = None
    remote_ipa_path = (
        f"/private/var/mobile/Documents/Dumped/{bundle_identifier.rsplit('.', 1)[-1]}.ipa"
    )
    exit_code = 0

    if not success:
        failure_reason = "The device does not have enough free storage."
        remote_ipa_path = None
        exit_code = 1

    return CrackResult(
        bundle_identifier=bundle_identifier,
        app_number=1,
        success=success,
        exit_code=exit_code,
        failure_reason=failure_reason,
        remote_ipa_path=remote_ipa_path,
        device_storage_full=device_storage_full,
    )


@dataclass(frozen=True)
class FakeIpaInfo:
    """Minimal IPA metadata required by the batch loop."""

    bundle_identifier: str


class FakeLogger:
    """Collect batch log messages for assertions."""

    def __init__(self):
        self.infos = []
        self.errors = []
        self.warnings = []

    def info(self, message: str):
        """Collect an info message."""
        self.infos.append(message)

    def error(self, message: str):
        """Collect an error message."""
        self.errors.append(message)

    def warning(self, message: str):
        """Collect a warning message."""
        self.warnings.append(message)


class FakeSshConnection:
    """Return a Clutch listing followed by a storage failure."""

    def __init__(self):
        self.command_count = 0

    def execute_command(self, command: str, use_pty: bool = False):
        """Return stable command output for the Clutch workflow."""
        self.command_count += 1
        if self.command_count == 1:
            return SshCommandResult(
                command=command,
                exit_code=0,
                stdout="1: Mock App <com.example.app>",
                stderr="",
            )

        return SshCommandResult(
            command=command,
            exit_code=1,
            stdout="",
            stderr="zip error: No space left on device",
        )


class FakePipelineSshConnection:
    """Provide one reusable SFTP connection to the batch pipeline."""

    def __init__(self):
        self.open_sftp_count = 0
        self.sftp_client = FakeSftpClient()

    def open_sftp(self):
        """Return the same SFTP client and count connection requests."""
        self.open_sftp_count += 1
        return self.sftp_client


class FakeSftpClient:
    """Record whether the pipeline closes its SFTP connection."""

    def __init__(self):
        self.closed = False

    def close(self):
        """Record SFTP connection cleanup."""
        self.closed = True
