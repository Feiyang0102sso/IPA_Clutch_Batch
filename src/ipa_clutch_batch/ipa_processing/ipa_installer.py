"""
Install an IPA on an iOS device.
"""
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
import plistlib
import subprocess
from uuid import uuid4

from ipa_clutch_batch.common.command_runner import (
    log_command_output,
    run_command,
)
from ipa_clutch_batch.common.ipa_utils import ipa_sort_key
from ipa_clutch_batch.config import (
    INSTALLED_IPA_CACHE_PATH,
    get_ideviceinstaller_path,
)
from ipa_clutch_batch.device import (
    DeviceInfo,
    get_single_connected_device_udid,
)
from ipa_clutch_batch.ipa_info import (
    IpaInfo,
    get_single_ipa_info,
    select_preferred_version,
)
from ipa_clutch_batch.logger import logger


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
    device_storage_full: bool
    skipped: bool = False


@dataclass(frozen=True)
class InstalledIpaInfo:
    """Metadata for one app currently installed on the device."""

    bundle_identifier: str
    version: str
    bundle_version: str | None
    short_version: str | None


@dataclass(frozen=True)
class BatchInstallSummary:
    """Summary of one alphabetical IPA installation batch."""

    total: int
    succeeded: int
    failed: int


_installed_ipa_cache_by_udid: dict[str, dict[str, InstalledIpaInfo]] = {}
INSTALLED_IPA_QUERY_ATTRIBUTES = (
    "CFBundleIdentifier",
    "CFBundleVersion",
    "CFBundleShortVersionString",
)


@contextmanager
def use_ascii_ipa_path(ipa_path: Path) -> Iterator[Path]:
    """Provide an ASCII filename for installers that mishandle Chinese names."""
    if ipa_path.name.isascii():
        yield ipa_path
        return

    temporary_name = f".ipa_install_{uuid4().hex}.ipa"
    temporary_path = ipa_path.with_name(temporary_name)

    # A hard link exposes the same IPA data without copying a large file.
    temporary_path.hardlink_to(ipa_path)
    logger.debug(f"Created temporary ASCII IPA path: {temporary_path.name}")

    try:
        yield temporary_path
    finally:
        temporary_path.unlink(missing_ok=True)
        logger.debug(f"Removed temporary ASCII IPA path: {temporary_path.name}")


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
    with use_ascii_ipa_path(resolved_ipa_path) as installer_ipa_path:
        command = [
            str(installer_path),
            "--udid",
            target_udid,
            "install",
            str(installer_ipa_path),
        ]
        completed_process = run_command(command)
    if completed_process is None:
        return None

    success = _is_successful_install_output(completed_process)
    device_storage_full = False
    if not success:
        device_storage_full = is_device_storage_full_error(
            completed_process.stdout,
            completed_process.stderr,
        )

    log_command_output(completed_process, is_error=not success)

    if success:
        logger.info(f"IPA installed successfully: {resolved_ipa_path.name}")
        ipa_info = get_single_ipa_info(resolved_ipa_path)
        if ipa_info is not None:
            _remember_installed_ipa(target_udid, ipa_info)
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
        failure_reason=_classify_install_failure(
            completed_process,
            device_storage_full,
        ),
        device_storage_full=device_storage_full,
    )


def query_installed_ipa(
    udid: str,
    ideviceinstaller_path: Path | None = None,
) -> dict[str, InstalledIpaInfo]:
    """Query installed apps once per device and save the result locally."""
    if udid in _installed_ipa_cache_by_udid:
        logger.info(f"Use cached installed IPA XML: {INSTALLED_IPA_CACHE_PATH}")
        return _installed_ipa_cache_by_udid[udid]

    installer_path = ideviceinstaller_path
    if installer_path is None:
        installer_path = get_ideviceinstaller_path()

    if not installer_path.is_file():
        logger.error(f"IPA installer tool not found: {installer_path}")
        return _cache_empty_installed_ipa_result(udid)

    command = [
        str(installer_path),
        "--udid",
        udid,
        "list",
        "--xml",
    ]
    for attribute_name in INSTALLED_IPA_QUERY_ATTRIBUTES:
        command.extend(["-a", attribute_name])

    logger.info("Query installed IPA list from device.")
    completed_process = run_command(command)
    if completed_process is None:
        return _cache_empty_installed_ipa_result(udid)

    if completed_process.returncode != 0:
        logger.error(
            f"Failed to query installed IPA list. Exit code: "
            f"{completed_process.returncode}"
        )
        log_command_output(completed_process, is_error=True)
        return _cache_empty_installed_ipa_result(udid)

    installed_ipa_by_bundle_id = _parse_installed_ipa_xml(
        completed_process.stdout,
    )
    _installed_ipa_cache_by_udid[udid] = installed_ipa_by_bundle_id
    _write_installed_ipa_xml_cache(completed_process.stdout)
    return installed_ipa_by_bundle_id


def is_already_installed_current_ipa(
    ipa_info: IpaInfo,
    udid: str,
    ideviceinstaller_path: Path | None = None,
) -> bool:
    """Return whether the same bundle ID and version are installed already."""
    installed_ipa_by_bundle_id = query_installed_ipa(
        udid,
        ideviceinstaller_path=ideviceinstaller_path,
    )
    installed_ipa_info = installed_ipa_by_bundle_id.get(
        ipa_info.bundle_identifier,
    )
    if installed_ipa_info is None:
        return False

    if installed_ipa_info.version != ipa_info.version:
        logger.debug(
            f"Installed version mismatch for {ipa_info.bundle_identifier}: "
            f"device={installed_ipa_info.version}, ipa={ipa_info.version}"
        )
        return False

    logger.info(
        f"Same IPA already installed: {ipa_info.bundle_identifier} "
        f"v{ipa_info.version}"
    )
    return True


def skip_current_ipa(ipa_path: Path, ipa_info: IpaInfo, udid: str) -> InstallResult:
    """Create a successful install result for an IPA that does not need reinstalling."""
    resolved_ipa_path = ipa_path.expanduser().resolve()
    logger.info(
        f"Skip install and crack installed app directly: {resolved_ipa_path.name}"
    )
    return InstallResult(
        ipa_path=resolved_ipa_path,
        udid=udid,
        success=True,
        return_code=0,
        stdout="Already installed with the same bundle ID and version.",
        stderr="",
        failure_reason=None,
        device_storage_full=False,
        skipped=True,
    )


def install_all_ipas(input_dir: Path, device_info: DeviceInfo) -> BatchInstallSummary:
    """Install all IPA files in alphabetical filename order."""
    ipa_paths = sorted(input_dir.glob("*.ipa"), key=ipa_sort_key)
    total_count = len(ipa_paths)

    if total_count == 0:
        logger.info("No IPA files found in input directory.")
        return BatchInstallSummary(total=0, succeeded=0, failed=0)

    logger.info(f"Found {total_count} IPA file(s) to install.")
    succeeded_count = 0
    failed_count = 0

    for install_index, ipa_path in enumerate(ipa_paths, start=1):
        logger.info(f"Install [{install_index}/{total_count}]: {ipa_path.name}")

        ipa_info = get_single_ipa_info(ipa_path)
        if ipa_info is None:
            failed_count += 1
            continue

        compatibility_error = get_ipa_compatibility_error(ipa_info, device_info)
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
    ipa_info: IpaInfo,
    device_info: DeviceInfo,
) -> str | None:
    """Return a clear compatibility error before installation when possible."""
    if ipa_info.device_families:
        is_family_compatible = _is_device_family_compatible(
            ipa_info.device_families,
            device_info.device_family,
        )
        if not is_family_compatible:
            supported_names = _format_device_families(ipa_info.device_families)
            current_name = _format_device_families([device_info.device_family])
            return f"App supports {supported_names}, but connected device is {current_name}."

    minimum_os_version = ipa_info.minimum_os_version
    if isinstance(minimum_os_version, str) and minimum_os_version:
        if _compare_versions(device_info.product_version, minimum_os_version) < 0:
            return (
                f"App requires iOS {minimum_os_version} or later, but connected "
                f"device runs iOS {device_info.product_version}."
            )

    return None


def _parse_installed_ipa_xml(xml_output: str) -> dict[str, InstalledIpaInfo]:
    """Parse ideviceinstaller XML output into installed IPA metadata."""
    try:
        installed_data = plistlib.loads(xml_output.encode("utf-8"))
    except plistlib.InvalidFileException as error:
        logger.error(f"Cannot parse installed IPA list: {error}")
        return {}

    if isinstance(installed_data, list):
        return _parse_installed_ipa_list(installed_data)

    if not isinstance(installed_data, dict):
        logger.error("Installed IPA list root is not a dictionary or list.")
        return {}

    bundle_identifier = _normalize_bundle_identifier(
        installed_data.get("CFBundleIdentifier")
    )
    if bundle_identifier is not None:
        return _parse_single_installed_ipa_dict(installed_data)

    installed_ipa_by_bundle_id = {}
    for bundle_identifier, raw_app_info in installed_data.items():
        if not isinstance(bundle_identifier, str):
            continue
        if not isinstance(raw_app_info, dict):
            continue

        installed_ipa_info = _create_installed_ipa_info(
            bundle_identifier,
            raw_app_info,
        )
        if installed_ipa_info is None:
            continue

        installed_ipa_by_bundle_id[bundle_identifier] = installed_ipa_info

    return installed_ipa_by_bundle_id


def _parse_installed_ipa_list(
    installed_app_items: list,
) -> dict[str, InstalledIpaInfo]:
    """Parse ideviceinstaller XML when the root plist is an array."""
    installed_ipa_by_bundle_id = {}

    for raw_app_info in installed_app_items:
        if not isinstance(raw_app_info, dict):
            continue

        bundle_identifier = _normalize_bundle_identifier(
            raw_app_info.get("CFBundleIdentifier")
        )
        if bundle_identifier is None:
            continue

        installed_ipa_info = _create_installed_ipa_info(
            bundle_identifier,
            raw_app_info,
        )
        if installed_ipa_info is None:
            continue

        installed_ipa_by_bundle_id[bundle_identifier] = installed_ipa_info

    return installed_ipa_by_bundle_id


def _parse_single_installed_ipa_dict(
    raw_app_info: dict,
) -> dict[str, InstalledIpaInfo]:
    """Parse one installed app dict returned by a filtered query."""
    bundle_identifier = _normalize_bundle_identifier(
        raw_app_info.get("CFBundleIdentifier")
    )
    if bundle_identifier is None:
        return {}

    installed_ipa_info = _create_installed_ipa_info(
        bundle_identifier,
        raw_app_info,
    )
    if installed_ipa_info is None:
        return {}

    return {bundle_identifier: installed_ipa_info}


def _create_installed_ipa_info(
    bundle_identifier: str,
    raw_app_info: dict,
) -> InstalledIpaInfo | None:
    """Create installed app metadata from one ideviceinstaller item."""
    bundle_version = _normalize_installed_version(
        raw_app_info.get("CFBundleVersion")
    )
    short_version = _normalize_installed_version(
        raw_app_info.get("CFBundleShortVersionString")
    )
    version = select_preferred_version(bundle_version, short_version)
    if version is None:
        logger.debug(f"Skip installed app without version: {bundle_identifier}")
        return None

    return InstalledIpaInfo(
        bundle_identifier=bundle_identifier,
        version=version,
        bundle_version=bundle_version,
        short_version=short_version,
    )


def _normalize_bundle_identifier(bundle_identifier: object) -> str | None:
    """Normalize an installed app bundle identifier."""
    if not isinstance(bundle_identifier, str):
        return None

    normalized_identifier = bundle_identifier.strip()
    if not normalized_identifier:
        return None
    return normalized_identifier


def _normalize_installed_version(version_value: object) -> str | None:
    """Normalize installed app version values."""
    if isinstance(version_value, bool):
        return None
    if isinstance(version_value, int):
        return str(version_value)
    if not isinstance(version_value, str):
        return None

    normalized_version = version_value.strip()
    if not normalized_version:
        return None
    return normalized_version


def _write_installed_ipa_xml_cache(xml_output: str):
    """Write the raw installed IPA XML query result to an app-local file."""
    try:
        INSTALLED_IPA_CACHE_PATH.write_text(xml_output, encoding="utf-8")
    except OSError as error:
        logger.warning(f"Cannot write installed IPA cache: {error}")
        return

    logger.debug(f"Installed IPA XML saved: {INSTALLED_IPA_CACHE_PATH}")


def _cache_empty_installed_ipa_result(
    udid: str,
) -> dict[str, InstalledIpaInfo]:
    """Remember an empty query result so one broken query does not repeat per IPA."""
    installed_ipa_by_bundle_id: dict[str, InstalledIpaInfo] = {}
    _installed_ipa_cache_by_udid[udid] = installed_ipa_by_bundle_id
    return installed_ipa_by_bundle_id


def _remember_installed_ipa(udid: str, ipa_info: IpaInfo):
    """Update the query cache after a successful install."""
    installed_ipa_by_bundle_id = _installed_ipa_cache_by_udid.get(udid)
    if installed_ipa_by_bundle_id is None:
        return

    installed_ipa_by_bundle_id[ipa_info.bundle_identifier] = InstalledIpaInfo(
        bundle_identifier=ipa_info.bundle_identifier,
        version=ipa_info.version,
        bundle_version=ipa_info.bundle_version,
        short_version=ipa_info.short_version,
    )


def _is_device_family_compatible(
    supported_device_families: list[int],
    connected_device_family: int,
) -> bool:
    """Return whether iOS allows this app family on the connected device."""
    if connected_device_family in supported_device_families:
        return True

    # iPad can install iPhone/iPod apps in compatibility mode.
    if connected_device_family == 2 and 1 in supported_device_families:
        logger.warning(
            "App only declares iPhone/iPod support, but iPad installation is "
            "allowed in iOS compatibility mode."
        )
        return True

    return False


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
    device_storage_full: bool,
) -> str | None:
    """Classify common installation errors without hiding raw tool output."""
    combined_output = f"{completed_process.stdout}\n{completed_process.stderr}".lower()

    if device_storage_full:
        return "The device does not have enough free storage."
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
    if "device removed" in combined_output:
        return "The device disconnected before installation completed."
    return None


def _is_successful_install_output(
    completed_process: subprocess.CompletedProcess[str],
) -> bool:
    """Return whether ideviceinstaller really completed installation."""
    combined_output = f"{completed_process.stdout}\n{completed_process.stderr}".lower()

    if completed_process.returncode != 0:
        return False
    if "device removed" in combined_output:
        return False
    if "error" in combined_output:
        return False
    if "failed" in combined_output:
        return False

    return "install: complete" in combined_output or "complete" in combined_output


def is_device_storage_full_error(stdout: str, stderr: str) -> bool:
    """Return whether command output reports insufficient device storage."""
    combined_output = f"{stdout}\n{stderr}".lower()

    if "no space left on device" in combined_output:
        return True
    if "not enough" in combined_output and "space" in combined_output:
        return True
    if "insufficient storage" in combined_output:
        return True
    if "disk full" in combined_output:
        return True
    return False
