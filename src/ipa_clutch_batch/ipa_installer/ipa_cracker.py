"""
Install each IPA and dump it with Clutch before processing the next IPA.
"""
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
import re

from ipa_clutch_batch.config import CLUTCH_DUMP_DIR
from ipa_clutch_batch.device_connector import DeviceInfo, UsbSshConnection
from ipa_clutch_batch.ipa_info import get_single_ipa_info
from ipa_clutch_batch.ipa_installer.ipa_installer import (
    get_ipa_compatibility_error,
    install_ipa,
)
from ipa_clutch_batch.logger import logger

CLUTCH_LIST_COMMAND = "Clutch -i -n"
CLUTCH_DUMP_COMMAND = "Clutch -d {app_number}"
CLUTCH_APP_PATTERN = re.compile(r"^\s*(\d+):.*<([^<>]+)>\s*$")
CLUTCH_DONE_PATTERN = re.compile(r"^DONE:\s*(.+\.ipa)\s*$", re.MULTILINE)


@dataclass(frozen=True)
class CrackResult:
    """Result of one Clutch dump command."""

    bundle_identifier: str
    app_number: int | None
    success: bool
    exit_code: int | None
    failure_reason: str | None
    remote_ipa_path: str | None


@dataclass(frozen=True)
class InstallAndCrackSummary:
    """Summary of one sequential install-and-crack batch."""

    total: int
    cracked: int
    install_failed: int
    crack_failed: int
    remote_ipa_paths: tuple[str, ...]

    @property
    def failed(self) -> int:
        """Return the total number of failed IPA files."""
        return self.install_failed + self.crack_failed


def install_and_crack_all_ipas(
    input_dir: Path,
    device_info: DeviceInfo,
    ssh_connection: UsbSshConnection,
) -> InstallAndCrackSummary:
    """Install and crack IPA files one at a time in alphabetical order."""
    ipa_paths = sorted(input_dir.glob("*.ipa"), key=_ipa_sort_key)
    total_count = len(ipa_paths)

    if total_count == 0:
        logger.info("No IPA files found in input directory.")
        return InstallAndCrackSummary(
            total=0,
            cracked=0,
            install_failed=0,
            crack_failed=0,
            remote_ipa_paths=(),
        )

    logger.info(f"Found {total_count} IPA file(s) to install and crack.")
    cracked_count = 0
    install_failed_count = 0
    crack_failed_count = 0
    remote_ipa_paths = []

    for process_index, ipa_path in enumerate(ipa_paths, start=1):
        logger.info(f"Process [{process_index}/{total_count}]: {ipa_path.name}")

        ipa_info = get_single_ipa_info(ipa_path)
        if ipa_info is None:
            install_failed_count += 1
            continue

        logger.info(f"Target bundle ID: {ipa_info.bundle_identifier}")
        compatibility_error = get_ipa_compatibility_error(ipa_info, device_info)
        if compatibility_error is not None:
            install_failed_count += 1
            logger.error(f"Compatibility check failed: {compatibility_error}")
            continue

        install_result = install_ipa(ipa_path, udid=device_info.udid)
        if install_result is None or not install_result.success:
            install_failed_count += 1
            if install_result is not None and install_result.failure_reason is not None:
                logger.error(f"Failure reason: {install_result.failure_reason}")
            continue

        crack_result = crack_installed_app(
            ipa_info.bundle_identifier,
            ssh_connection,
        )
        if crack_result.success:
            cracked_count += 1
            if crack_result.remote_ipa_path is not None:
                remote_ipa_paths.append(crack_result.remote_ipa_path)
            continue

        crack_failed_count += 1

    summary = InstallAndCrackSummary(
        total=total_count,
        cracked=cracked_count,
        install_failed=install_failed_count,
        crack_failed=crack_failed_count,
        remote_ipa_paths=tuple(remote_ipa_paths),
    )
    logger.info(
        f"Install and crack completed: {summary.total} total, "
        f"{summary.cracked} cracked, {summary.install_failed} install failed, "
        f"{summary.crack_failed} crack failed."
    )
    return summary


def crack_installed_app(
    bundle_identifier: str,
    ssh_connection: UsbSshConnection,
) -> CrackResult:
    """Resolve the current Clutch number by bundle ID and dump the app."""
    list_result = ssh_connection.execute_command(CLUTCH_LIST_COMMAND)
    if list_result is None:
        return _log_crack_failure(
            bundle_identifier,
            None,
            None,
            "Cannot execute Clutch app listing command.",
        )

    if list_result.exit_code != 0:
        return _log_crack_failure(
            bundle_identifier,
            None,
            list_result.exit_code,
            "Clutch failed to list installed applications.",
        )

    clutch_apps = parse_clutch_installed_apps(list_result.stdout)
    app_number = clutch_apps.get(bundle_identifier)
    if app_number is None:
        return _log_crack_failure(
            bundle_identifier,
            None,
            list_result.exit_code,
            "Bundle ID is not present in Clutch installed app list.",
        )

    logger.info(
        f"Clutch target resolved: {bundle_identifier} -> number {app_number}"
    )
    dump_command = CLUTCH_DUMP_COMMAND.format(app_number=app_number)
    # Match the successful interactive invocation used on the legacy device.
    dump_result = ssh_connection.execute_command(dump_command, use_pty=True)
    if dump_result is None:
        return _log_crack_failure(
            bundle_identifier,
            app_number,
            None,
            "Cannot start the Clutch dump command.",
        )

    if dump_result.exit_code != 0:
        failure_reason = classify_clutch_failure(
            dump_result.exit_code,
            dump_result.stdout,
            dump_result.stderr,
        )
        return _log_crack_failure(
            bundle_identifier,
            app_number,
            dump_result.exit_code,
            failure_reason,
        )

    remote_ipa_path = _get_clutch_output_path(dump_result.stdout)
    if remote_ipa_path is None:
        return _log_crack_failure(
            bundle_identifier,
            app_number,
            dump_result.exit_code,
            "Clutch finished without reporting the generated IPA path.",
        )
    if not _is_valid_clutch_output_path(remote_ipa_path):
        return _log_crack_failure(
            bundle_identifier,
            app_number,
            dump_result.exit_code,
            f"Clutch reported an unexpected output path: {remote_ipa_path}",
        )

    logger.info(f"Clutch dump succeeded: {bundle_identifier}")
    logger.info(f"Clutch output file: {remote_ipa_path}")
    return CrackResult(
        bundle_identifier=bundle_identifier,
        app_number=app_number,
        success=True,
        exit_code=dump_result.exit_code,
        failure_reason=None,
        remote_ipa_path=remote_ipa_path,
    )


def parse_clutch_installed_apps(clutch_output: str) -> dict[str, int]:
    """Map exact Bundle IDs to the numbers from the latest Clutch output."""
    installed_apps = {}

    for output_line in clutch_output.splitlines():
        app_match = CLUTCH_APP_PATTERN.match(output_line)
        if app_match is None:
            continue

        app_number = int(app_match.group(1))
        bundle_identifier = app_match.group(2).strip()
        installed_apps[bundle_identifier] = app_number

    return installed_apps


def classify_clutch_failure(
    exit_code: int,
    stdout: str,
    stderr: str,
) -> str:
    """Classify known Clutch failures while preserving its raw output in logs."""
    combined_output = f"{stdout}\n{stderr}".lower()

    if exit_code in (9, 137) or "killed: 9" in combined_output:
        return (
            "Clutch was terminated by SIGKILL (9). Check App Store account "
            "authorization, available memory, and jailbreak environment."
        )
    if exit_code == 255 and not combined_output.strip():
        return (
            "Clutch exited with code 255 without diagnostic output. Use the "
            "exact dump command 'Clutch -d <number>' without '-n'."
        )
    if "not found" in combined_output or "no such" in combined_output:
        return "Clutch could not find a required application file or path."
    if "permission denied" in combined_output:
        return "Clutch does not have permission to access a required file."
    if "segmentation fault" in combined_output:
        return "Clutch crashed with a segmentation fault."
    return f"Clutch failed with exit code {exit_code}."


def _log_crack_failure(
    bundle_identifier: str,
    app_number: int | None,
    exit_code: int | None,
    failure_reason: str,
) -> CrackResult:
    """Log and return one failed crack result."""
    logger.error(f"Clutch dump failed for {bundle_identifier}: {failure_reason}")
    return CrackResult(
        bundle_identifier=bundle_identifier,
        app_number=app_number,
        success=False,
        exit_code=exit_code,
        failure_reason=failure_reason,
        remote_ipa_path=None,
    )


def _get_clutch_output_path(clutch_output: str) -> str | None:
    """Read the generated remote IPA path from Clutch's DONE line."""
    done_match = CLUTCH_DONE_PATTERN.search(clutch_output)
    if done_match is None:
        return None
    return done_match.group(1).strip()


def _is_valid_clutch_output_path(remote_ipa_path: str) -> bool:
    """Limit generated IPA paths to the configured Clutch dump directory."""
    output_path = PurePosixPath(remote_ipa_path)
    dump_dir = PurePosixPath(CLUTCH_DUMP_DIR)
    if output_path.parent != dump_dir:
        return False
    return output_path.suffix.lower() == ".ipa"


def _ipa_sort_key(ipa_path: Path) -> str:
    """Return a stable case-insensitive alphabetical filename key."""
    return ipa_path.name.casefold()
