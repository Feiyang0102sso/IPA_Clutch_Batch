"""Unit tests for the sequential install, crack, and move pipeline."""

from contextlib import contextmanager
from dataclasses import dataclass
from io import StringIO
from pathlib import Path, PurePosixPath

from ipa_clutch_batch.device import DeviceInfo
from ipa_clutch_batch.ipa_processing import ipa_mover, ipa_pipeline
from ipa_clutch_batch.ipa_processing.ipa_cracker import CrackResult
from ipa_clutch_batch.ipa_processing.ipa_installer import InstallResult
from ipa_clutch_batch.progress import IpaProcessingStep, WorkflowProgress


def test_pipeline_moves_each_dump_before_installing_next(monkeypatch, tmp_path: Path):
    """Complete one IPA lifecycle before starting the next installation."""
    _create_ipa_files(tmp_path, 2)
    pipeline_events = []
    progress_reporter = FakeProgressReporter()
    ssh_connection = FakePipelineSshConnection(pipeline_events)

    def fake_install(ipa_path: Path, udid: str):
        pipeline_events.append(f"install:{ipa_path.stem}")
        return _create_successful_install_result(ipa_path, udid)

    def fake_crack(bundle_identifier: str, connection):
        app_name = bundle_identifier.rsplit(".", 1)[-1]
        pipeline_events.append(f"crack:{app_name}")
        return _create_successful_crack_result(bundle_identifier)

    def fake_move(remote_ipa_path: str, cracked_dir: Path, sftp_client):
        remote_name = PurePosixPath(remote_ipa_path).stem
        pipeline_events.append(f"move:{remote_name}")
        return True

    _mock_pipeline_dependencies(monkeypatch, fake_install, fake_crack, fake_move)

    summary = ipa_pipeline.run_ipa_pipeline(
        tmp_path,
        tmp_path / "cracked",
        _create_device_info(),
        ssh_connection,
        progress_reporter=progress_reporter,
    )

    assert pipeline_events == [
        "install:app_1",
        "crack:app_1",
        "open_sftp",
        "move:app_1",
        "install:app_2",
        "crack:app_2",
        "move:app_2",
        "close_sftp",
    ]
    assert ssh_connection.open_sftp_count == 1
    assert summary.total == 2
    assert summary.cracked == 2
    assert summary.moved == 2
    assert summary.failed == 0
    assert summary.skipped == 0
    assert progress_reporter.events == [
        "start:2",
        "begin:Install:app_1.ipa",
        "complete:Install:app_1.ipa",
        "begin:Crack:app_1.ipa",
        "complete:Crack:app_1.ipa",
        "begin:Move & Rename:app_1.ipa",
        "complete:Move & Rename:app_1.ipa",
        "begin:Install:app_2.ipa",
        "complete:Install:app_2.ipa",
        "begin:Crack:app_2.ipa",
        "complete:Crack:app_2.ipa",
        "begin:Move & Rename:app_2.ipa",
        "complete:Move & Rename:app_2.ipa",
    ]


def test_pipeline_stops_when_move_or_remote_cleanup_fails(
    monkeypatch,
    tmp_path: Path,
):
    """Do not install another IPA when the current dump was not safely removed."""
    _create_ipa_files(tmp_path, 3)
    pipeline_events = []
    progress_reporter = FakeProgressReporter()
    ssh_connection = FakePipelineSshConnection(pipeline_events)

    def fake_install(ipa_path: Path, udid: str):
        pipeline_events.append(f"install:{ipa_path.stem}")
        return _create_successful_install_result(ipa_path, udid)

    def fake_crack(bundle_identifier: str, connection):
        app_name = bundle_identifier.rsplit(".", 1)[-1]
        pipeline_events.append(f"crack:{app_name}")
        return _create_successful_crack_result(bundle_identifier)

    def fake_move(remote_ipa_path: str, cracked_dir: Path, sftp_client):
        remote_name = PurePosixPath(remote_ipa_path).stem
        pipeline_events.append(f"move_failed:{remote_name}")
        return False

    _mock_pipeline_dependencies(monkeypatch, fake_install, fake_crack, fake_move)

    summary = ipa_pipeline.run_ipa_pipeline(
        tmp_path,
        tmp_path / "cracked",
        _create_device_info(),
        ssh_connection,
        progress_reporter=progress_reporter,
    )

    assert pipeline_events == [
        "install:app_1",
        "crack:app_1",
        "open_sftp",
        "move_failed:app_1",
        "close_sftp",
    ]
    assert summary.cracked == 1
    assert summary.moved == 0
    assert summary.move_failed == 1
    assert summary.failed == 1
    assert summary.skipped == 2
    assert progress_reporter.events == [
        "start:3",
        "begin:Install:app_1.ipa",
        "complete:Install:app_1.ipa",
        "begin:Crack:app_1.ipa",
        "complete:Crack:app_1.ipa",
        "begin:Move & Rename:app_1.ipa",
        "complete:Move & Rename:app_1.ipa",
    ]


def test_single_mover_deletes_remote_dump_after_local_verification(
    monkeypatch,
    tmp_path: Path,
):
    """Remove the exact remote dump only after creating the final local IPA."""
    remote_ipa_path = "/private/var/mobile/Documents/Dumped/mock.ipa"
    sftp_client = FakeTransferSftpClient()

    def fake_get_ipa_info(ipa_path: Path):
        return FakeDumpedIpaInfo(display_name="Mock App", version="1.0")

    monkeypatch.setattr(ipa_mover, "get_single_ipa_info", fake_get_ipa_info)

    move_succeeded = ipa_mover.move_single_dumped_ipa(
        remote_ipa_path,
        tmp_path,
        sftp_client,
    )

    final_path = tmp_path / "Mock App_1.0_cracked.ipa"
    assert move_succeeded
    assert final_path.is_file()
    assert sftp_client.removed_paths == [remote_ipa_path]


def test_compatibility_failure_skips_remaining_steps_and_fills_progress(
    monkeypatch,
    tmp_path: Path,
):
    """Reach nine of nine for two valid IPAs and one incompatible IPA."""
    _create_ipa_files(tmp_path, 3)
    progress_output = StringIO()
    progress_reporter = WorkflowProgress(stream=progress_output)
    ssh_connection = FakePipelineSshConnection([])

    def get_compatibility_error(ipa_info, device_info):
        if ipa_info.bundle_identifier.endswith("app_3"):
            return "App supports iPad, but connected device is iPhone/iPod."
        return None

    def install_compatible_ipa(ipa_path: Path, udid: str):
        if ipa_path.stem == "app_3":
            raise AssertionError("incompatible IPA must not be installed")
        return _create_successful_install_result(ipa_path, udid)

    def crack_compatible_ipa(bundle_identifier: str, connection):
        return _create_successful_crack_result(bundle_identifier)

    def move_compatible_ipa(remote_ipa_path: str, cracked_dir: Path, sftp_client):
        return True

    monkeypatch.setattr(ipa_pipeline, "get_single_ipa_info", _get_fake_ipa_info)
    monkeypatch.setattr(
        ipa_pipeline,
        "get_ipa_compatibility_error",
        get_compatibility_error,
    )
    monkeypatch.setattr(ipa_pipeline, "install_ipa", install_compatible_ipa)
    monkeypatch.setattr(
        ipa_pipeline,
        "crack_installed_app",
        crack_compatible_ipa,
    )
    monkeypatch.setattr(
        ipa_pipeline,
        "move_single_dumped_ipa",
        move_compatible_ipa,
    )

    summary = ipa_pipeline.run_ipa_pipeline(
        tmp_path,
        tmp_path / "cracked",
        _create_device_info(),
        ssh_connection,
        progress_reporter=progress_reporter,
    )

    assert summary.install_failed == 1
    assert summary.moved == 2
    assert summary.skipped == 0
    rendered_output = progress_output.getvalue()
    assert "IPA Processing - Skipped" in rendered_output
    assert "9/9" in rendered_output


def _mock_pipeline_dependencies(
    monkeypatch,
    fake_install,
    fake_crack,
    fake_move,
):
    """Replace external work while retaining the pipeline orchestration."""
    monkeypatch.setattr(ipa_pipeline, "get_single_ipa_info", _get_fake_ipa_info)
    monkeypatch.setattr(
        ipa_pipeline,
        "get_ipa_compatibility_error",
        _get_no_compatibility_error,
    )
    monkeypatch.setattr(ipa_pipeline, "install_ipa", fake_install)
    monkeypatch.setattr(ipa_pipeline, "crack_installed_app", fake_crack)
    monkeypatch.setattr(ipa_pipeline, "move_single_dumped_ipa", fake_move)


def _create_ipa_files(input_dir: Path, count: int):
    """Create alphabetically ordered placeholder IPA files."""
    for ipa_number in range(1, count + 1):
        ipa_path = input_dir / f"app_{ipa_number}.ipa"
        ipa_path.touch()


def _get_fake_ipa_info(ipa_path: Path):
    """Return the metadata field used by the pipeline."""
    return FakeIpaInfo(bundle_identifier=f"com.example.{ipa_path.stem}")


def _get_no_compatibility_error(ipa_info, device_info):
    """Report that the placeholder IPA is compatible with the mock device."""
    return None


def _create_device_info() -> DeviceInfo:
    """Create stable device information for pipeline tests."""
    return DeviceInfo(
        udid="mock-udid",
        name="Mock iPhone",
        product_type="iPhone5,1",
        product_version="6.1.6",
        cpu_architecture="armv7",
        device_family=1,
    )


def _create_successful_install_result(ipa_path: Path, udid: str) -> InstallResult:
    """Create a successful installer result."""
    return InstallResult(
        ipa_path=ipa_path,
        udid=udid,
        success=True,
        return_code=0,
        stdout="",
        stderr="",
        failure_reason=None,
        device_storage_full=False,
    )


def _create_successful_crack_result(bundle_identifier: str) -> CrackResult:
    """Create a successful Clutch result with one remote dump path."""
    app_name = bundle_identifier.rsplit(".", 1)[-1]
    remote_ipa_path = f"/private/var/mobile/Documents/Dumped/{app_name}.ipa"
    return CrackResult(
        bundle_identifier=bundle_identifier,
        app_number=1,
        success=True,
        exit_code=0,
        failure_reason=None,
        remote_ipa_path=remote_ipa_path,
        device_storage_full=False,
    )


@dataclass(frozen=True)
class FakeIpaInfo:
    """Minimal IPA metadata required by the pipeline."""

    bundle_identifier: str


@dataclass(frozen=True)
class FakeDumpedIpaInfo:
    """Minimal dumped IPA metadata required for the final filename."""

    display_name: str
    version: str


class FakePipelineSshConnection:
    """Provide one reusable SFTP client and record its lifecycle."""

    def __init__(self, pipeline_events: list[str]):
        self.pipeline_events = pipeline_events
        self.open_sftp_count = 0
        self.sftp_client = FakePipelineSftpClient(pipeline_events)

    def open_sftp(self):
        """Return the reusable SFTP client."""
        self.open_sftp_count += 1
        self.pipeline_events.append("open_sftp")
        return self.sftp_client


class FakePipelineSftpClient:
    """Record when the pipeline closes SFTP."""

    def __init__(self, pipeline_events: list[str]):
        self.pipeline_events = pipeline_events

    def close(self):
        """Record SFTP cleanup."""
        self.pipeline_events.append("close_sftp")


class FakeTransferSftpClient:
    """Simulate downloading and deleting one remote dump."""

    def __init__(self):
        self.removed_paths = []

    def get(self, remote_ipa_path: str, local_ipa_path: str):
        """Write placeholder IPA content to the requested local path."""
        Path(local_ipa_path).write_bytes(b"mock ipa content")

    def remove(self, remote_ipa_path: str):
        """Record the remote dump deletion."""
        self.removed_paths.append(remote_ipa_path)


class FakeProgressReporter:
    """Record progress events without writing to the terminal."""

    def __init__(self):
        self.events = []

    def start_ipa_processing(self, total_count: int):
        """Record the IPA total."""
        self.events.append(f"start:{total_count}")

    @contextmanager
    def track_ipa(self, ipa_path: Path):
        """Provide the outer IPA lifecycle context."""
        yield

    @contextmanager
    def track_ipa_step(
        self,
        ipa_path: Path,
        step: IpaProcessingStep,
    ):
        """Record one attempted IPA processing step."""
        self.events.append(f"begin:{step.value}:{ipa_path.name}")
        try:
            yield
        finally:
            self.events.append(f"complete:{step.value}:{ipa_path.name}")
