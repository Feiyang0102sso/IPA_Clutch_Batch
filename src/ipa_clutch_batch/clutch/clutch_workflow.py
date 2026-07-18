"""Run the dedicated Clutch device check workflow."""

from ipa_clutch_batch.clutch.clutch_manager import ensure_clutch_ready
from ipa_clutch_batch.device import (
    UsbSshConnection,
    get_single_connected_device_udid,
)
from ipa_clutch_batch.logger import logger


def run_clutch_check() -> int:
    """Connect to one USB device, check Clutch, and then exit."""
    device_udid = get_single_connected_device_udid()
    if device_udid is None:
        logger.error("Device connection check failed. Clutch check stopped.")
        return 1

    logger.info(f"Device connection ready: {device_udid}")
    ssh_connection = UsbSshConnection(device_udid)
    try:
        if not ssh_connection.connect():
            return 1

        clutch_result = ensure_clutch_ready(ssh_connection)
        if not clutch_result.success:
            return 1
    except KeyboardInterrupt:
        logger.info("Clutch check interrupted by user.")
        return 130
    finally:
        ssh_connection.close()

    return 0
