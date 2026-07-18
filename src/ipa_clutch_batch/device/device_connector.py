"""
Detect one iOS device connected through USB.
"""
from dataclasses import dataclass
from pathlib import Path
import plistlib

from ipa_clutch_batch.common.command_runner import (
    log_command_output,
    run_command,
)
from ipa_clutch_batch.config import get_idevice_id_path, get_ideviceinfo_path
from ipa_clutch_batch.logger import logger


@dataclass(frozen=True)
class DeviceInfo:
    """Information required to check IPA compatibility."""

    udid: str
    name: str
    product_type: str
    product_version: str
    cpu_architecture: str
    device_family: int


def get_connected_device_udids(idevice_id_path: Path | None = None) -> list[str]:
    """Return UDIDs of all iOS devices connected through USB."""
    tool_path = idevice_id_path
    if tool_path is None:
        tool_path = get_idevice_id_path()

    if not tool_path.is_file():
        logger.error(f"Device detection tool not found: {tool_path}")
        return []

    command = [str(tool_path), "--list"]
    completed_process = run_command(command)
    if completed_process is None:
        return []

    if completed_process.returncode != 0:
        logger.error(
            f"Failed to detect USB devices. Exit code: {completed_process.returncode}"
        )
        log_command_output(completed_process, is_error=True)
        return []

    device_udids = []
    for output_line in completed_process.stdout.splitlines():
        device_udid = output_line.strip()
        if device_udid:
            device_udids.append(device_udid)

    return device_udids


def get_single_connected_device_udid(
    idevice_id_path: Path | None = None,
) -> str | None:
    """Return the UDID when exactly one USB device is connected."""
    logger.info("Checking USB device connection...")
    device_udids = get_connected_device_udids(idevice_id_path)

    if not device_udids:
        logger.error("No USB device detected. Connect one iOS device and try again.")
        return None

    if len(device_udids) > 1:
        logger.error(
            f"Multiple USB devices detected: {len(device_udids)}. "
            "Connect only one device."
        )
        return None

    device_udid = device_udids[0]
    logger.info(f"USB device detected: {device_udid}")
    return device_udid


def get_device_info(
    udid: str,
    ideviceinfo_path: Path | None = None,
) -> DeviceInfo | None:
    """Read device information required by the installer."""
    tool_path = ideviceinfo_path
    if tool_path is None:
        tool_path = get_ideviceinfo_path()

    if not tool_path.is_file():
        logger.error(f"Device information tool not found: {tool_path}")
        return None

    command = [str(tool_path), "--udid", udid, "--xml"]
    completed_process = run_command(command)
    if completed_process is None:
        return None

    if completed_process.returncode != 0:
        logger.error(
            f"Failed to read device information. Exit code: "
            f"{completed_process.returncode}"
        )
        log_command_output(completed_process, is_error=True)
        return None

    try:
        device_data = plistlib.loads(completed_process.stdout.encode("utf-8"))
    except plistlib.InvalidFileException as error:
        logger.error(f"Cannot parse device information: {error}")
        return None

    product_type = str(device_data.get("ProductType", ""))
    product_version = str(device_data.get("ProductVersion", ""))
    if not product_type or not product_version:
        logger.error("Device information is missing product type or system version.")
        return None

    device_family = _get_device_family(product_type)
    if device_family is None:
        logger.error(f"Unsupported device product type: {product_type}")
        return None

    device_info = DeviceInfo(
        udid=udid,
        name=str(device_data.get("DeviceName", "Unknown Device")),
        product_type=product_type,
        product_version=product_version,
        cpu_architecture=str(device_data.get("CPUArchitecture", "Unknown")),
        device_family=device_family,
    )
    logger.info(
        f"Device: {device_info.name}, {device_info.product_type}, "
        f"iOS {device_info.product_version}, {device_info.cpu_architecture}"
    )
    return device_info


def _get_device_family(product_type: str) -> int | None:
    """Map the Apple product type to UIDeviceFamily values."""
    if product_type.startswith("iPhone") or product_type.startswith("iPod"):
        return 1
    if product_type.startswith("iPad"):
        return 2
    return None
