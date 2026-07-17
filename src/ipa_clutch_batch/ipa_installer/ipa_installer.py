"""
Install an IPA on an iOS device.
"""
from dataclasses import dataclass
from pathlib import Path
import plistlib
import subprocess
import zipfile

from ipa_clutch_batch.config import get_ideviceinstaller_path
from ipa_clutch_batch.device_connector import (
    DeviceInfo,
    get_single_connected_device_udid,
)
from ipa_clutch_batch.logger import logger

PAYLOAD_PREFIX = "Payload/"
INFO_PLIST_SUFFIX = ".app/Info.plist"
DEVICE_FAMILY_KEY = "UIDeviceFamily"
MINIMUM_OS_VERSION_KEY = "MinimumOSVersion"


@dataclass(frozen=True)
class InstallResult:
    """Result returned by an ideviceinstaller command."""

    ipa_path: Path
    udid: str
    success: bool
    return_code: int
    stdout: str
    stderr: str
    failure_reason: str | None


@dataclass(frozen=True)
class BatchInstallSummary:
    """Summary of one alphabetical IPA installation batch."""

    total: int
    succeeded: int
    failed: int


def install_ipa(
    ipa_path: Path,
    udid: str | None = None,
    ideviceinstaller_path: Path | None = None,
    idevice_id_path: Path | None = None,
) -> InstallResult | None:
    """Install one IPA on a specified or automatically detected USB device."""
    resolved_ipa_path = ipa_path.expanduser().resolve()
    if not resolved_ipa_path.is_file():
        logger.error(f"IPA file not found: {resolved_ipa_path}")
        return None

    if resolved_ipa_path.suffix.lower() != ".ipa":
        logger.error(f"File is not an IPA: {resolved_ipa_path}")
        return None

    installer_path = ideviceinstaller_path
    if installer_path is None:
        installer_path = get_ideviceinstaller_path()

    if not installer_path.is_file():
        logger.error(f"IPA installer tool not found: {installer_path}")
        return None

    target_udid = udid
    if target_udid is None:
        target_udid = get_single_connected_device_udid(
            idevice_id_path=idevice_id_path
        )
    if target_udid is None:
        return None

    logger.info(f"Installing IPA: {resolved_ipa_path.name}")
    command = [
        str(installer_path),
        "--udid",
        target_udid,
        "install",
        str(resolved_ipa_path),
    ]
    completed_process = _run_command(command)
    if completed_process is None:
        return None

    success = completed_process.returncode == 0
    _log_command_output(completed_process, is_error=not success)

    if success:
        logger.info(f"IPA installed successfully: {resolved_ipa_path.name}")
    else:
        logger.error(
            f"Failed to install {resolved_ipa_path.name}. "
            f"Exit code: {completed_process.returncode}"
        )

    return InstallResult(
        ipa_path=resolved_ipa_path,
        udid=target_udid,
        success=success,
        return_code=completed_process.returncode,
        stdout=completed_process.stdout,
        stderr=completed_process.stderr,
        failure_reason=_classify_install_failure(completed_process),
    )


def install_all_ipas(input_dir: Path, device_info: DeviceInfo) -> BatchInstallSummary:
    """Install all IPA files in alphabetical filename order."""
    ipa_paths = sorted(input_dir.glob("*.ipa"), key=_ipa_sort_key)
    total_count = len(ipa_paths)

    if total_count == 0:
        logger.info("No IPA files found in input directory.")
        return BatchInstallSummary(total=0, succeeded=0, failed=0)

    logger.info(f"Found {total_count} IPA file(s) to install.")
    succeeded_count = 0
    failed_count = 0

    for install_index, ipa_path in enumerate(ipa_paths, start=1):
        logger.info(f"Install [{install_index}/{total_count}]: {ipa_path.name}")

        compatibility_error = get_ipa_compatibility_error(ipa_path, device_info)
        if compatibility_error is not None:
            failed_count += 1
            logger.error(f"Compatibility check failed: {compatibility_error}")
            continue

        install_result = install_ipa(ipa_path, udid=device_info.udid)
        if install_result is None:
            failed_count += 1
            continue

        if install_result.success:
            succeeded_count += 1
            continue

        failed_count += 1
        if install_result.failure_reason is not None:
            logger.error(f"Failure reason: {install_result.failure_reason}")

    logger.info(
        f"Installation completed: {total_count} total, "
        f"{succeeded_count} succeeded, {failed_count} failed."
    )
    return BatchInstallSummary(
        total=total_count,
        succeeded=succeeded_count,
        failed=failed_count,
    )


def get_ipa_compatibility_error(
    ipa_path: Path,
    device_info: DeviceInfo,
) -> str | None:
    """Return a clear compatibility error before installation when possible."""
    info_plist = _read_info_plist(ipa_path)
    if info_plist is None:
        return "Cannot read Payload/*.app/Info.plist."

    supported_families = _get_supported_device_families(info_plist)
    if supported_families and device_info.device_family not in supported_families:
        supported_names = _format_device_families(supported_families)
        current_name = _format_device_families([device_info.device_family])
        return f"App supports {supported_names}, but connected device is {current_name}."

    minimum_os_version = info_plist.get(MINIMUM_OS_VERSION_KEY)
    if isinstance(minimum_os_version, str) and minimum_os_version:
        if _compare_versions(device_info.product_version, minimum_os_version) < 0:
            return (
                f"App requires iOS {minimum_os_version} or later, but connected "
                f"device runs iOS {device_info.product_version}."
            )

    return None


def _read_info_plist(ipa_path: Path) -> dict | None:
    """Read the main application Info.plist from an IPA archive."""
    try:
        with zipfile.ZipFile(ipa_path, "r") as ipa_archive:
            info_plist_path = None
            for archive_path in ipa_archive.namelist():
                if archive_path.startswith(PAYLOAD_PREFIX) and archive_path.endswith(
                    INFO_PLIST_SUFFIX
                ):
                    info_plist_path = archive_path
                    break

            if info_plist_path is None:
                return None

            info_plist_data = ipa_archive.read(info_plist_path)
            return plistlib.loads(info_plist_data)
    except zipfile.BadZipFile:
        return None
    except plistlib.InvalidFileException:
        return None


def _get_supported_device_families(info_plist: dict) -> list[int]:
    """Read UIDeviceFamily as a normalized integer list."""
    raw_families = info_plist.get(DEVICE_FAMILY_KEY, [])
    supported_families = []

    if isinstance(raw_families, int):
        supported_families.append(raw_families)
        return supported_families

    if not isinstance(raw_families, list):
        return supported_families

    for raw_family in raw_families:
        if isinstance(raw_family, int):
            supported_families.append(raw_family)

    return supported_families


def _format_device_families(device_families: list[int]) -> str:
    """Format UIDeviceFamily values for a user-facing log message."""
    family_names = []
    for device_family in device_families:
        if device_family == 1:
            family_names.append("iPhone/iPod")
        elif device_family == 2:
            family_names.append("iPad")
        else:
            family_names.append(f"device family {device_family}")
    return ", ".join(family_names)


def _compare_versions(left_version: str, right_version: str) -> int:
    """Compare dotted numeric iOS version strings."""
    left_parts = _parse_version(left_version)
    right_parts = _parse_version(right_version)
    part_count = max(len(left_parts), len(right_parts))

    while len(left_parts) < part_count:
        left_parts.append(0)
    while len(right_parts) < part_count:
        right_parts.append(0)

    if left_parts < right_parts:
        return -1
    if left_parts > right_parts:
        return 1
    return 0


def _parse_version(version: str) -> list[int]:
    """Convert a dotted version string to numeric parts."""
    version_parts = []
    for raw_part in version.split("."):
        numeric_part = ""
        for character in raw_part:
            if not character.isdigit():
                break
            numeric_part += character

        if numeric_part:
            version_parts.append(int(numeric_part))
        else:
            version_parts.append(0)
    return version_parts


def _classify_install_failure(
    completed_process: subprocess.CompletedProcess[str],
) -> str | None:
    """Classify common installation errors without hiding raw tool output."""
    combined_output = f"{completed_process.stdout}\n{completed_process.stderr}".lower()

    if "deviceosversiontoolow" in combined_output or "minimumosversion" in combined_output:
        return "The connected iOS version is below the app minimum requirement."
    if "incorrectarchitecture" in combined_output or "architecture" in combined_output:
        return "The app executable architecture is incompatible with this device."
    if "uidevicefamily" in combined_output or "device family" in combined_output:
        return "The app does not support this device family."
    if "applicationverificationfailed" in combined_output:
        return "iOS rejected application verification or signing."
    if "installprohibited" in combined_output:
        return "Application installation is prohibited by the device."
    if "not enough" in combined_output and "space" in combined_output:
        return "The device does not have enough free storage."
    return None


def _ipa_sort_key(ipa_path: Path) -> str:
    """Return a stable case-insensitive alphabetical filename key."""
    return ipa_path.name.casefold()


def _run_command(command: list[str]) -> subprocess.CompletedProcess[str] | None:
    """Run one libimobiledevice command and log operating-system errors."""
    try:
        return subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
    except OSError as error:
        logger.error(f"Cannot run command: {command[0]}")
        logger.error(f"Operating system error: {error}")
        return None


def _log_command_output(
    completed_process: subprocess.CompletedProcess[str],
    is_error: bool,
):
    """Write non-empty command output to the appropriate log level."""
    output_lines = []

    if completed_process.stdout.strip():
        output_lines.append(f"stdout: {completed_process.stdout.strip()}")
    if completed_process.stderr.strip():
        output_lines.append(f"stderr: {completed_process.stderr.strip()}")

    for output_line in output_lines:
        if is_error:
            logger.error(output_line)
        else:
            logger.debug(output_line)
