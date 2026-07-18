"""Dump one installed iOS application with Clutch."""
from dataclasses import dataclass
from pathlib import PurePosixPath
import re

from ipa_clutch_batch.config import CLUTCH_DUMP_DIR
from ipa_clutch_batch.device import UsbSshConnection
from ipa_clutch_batch.ipa_processing.ipa_installer import (
    is_device_storage_full_error,
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
    device_storage_full: bool


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

    device_storage_full = is_device_storage_full_error(
        dump_result.stdout,
        dump_result.stderr,
    )
    if device_storage_full:
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
            device_storage_full=True,
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
        device_storage_full=False,
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

    if is_device_storage_full_error(stdout, stderr):
        return "The device does not have enough free storage."
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
    device_storage_full: bool = False,
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
        device_storage_full=device_storage_full,
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
