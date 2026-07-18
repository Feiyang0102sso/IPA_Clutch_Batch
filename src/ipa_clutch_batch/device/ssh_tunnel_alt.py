"""Keep a standalone USB SSH tunnel open for manual testing."""

import time

from ipa_clutch_batch.device.device_connector import (
    get_single_connected_device_udid,
)
from ipa_clutch_batch.device.ssh_connector import UsbSshConnection
from ipa_clutch_batch.logger import logger

SSH22_LOCAL_PORT = 22
TUNNEL_MONITOR_INTERVAL_SECONDS = 0.5


def run_ssh22_tunnel() -> int:
    """Open local port 22 to device port 22 until the user stops the process."""
    device_udid = get_single_connected_device_udid()
    if device_udid is None:
        logger.error("Device connection check failed. SSH tunnel stopped.")
        return 1

    logger.info(f"Device connection ready: {device_udid}")
    ssh_connection = UsbSshConnection(
        device_udid,
        local_port=SSH22_LOCAL_PORT,
    )
    try:
        if not ssh_connection.open_tunnel():
            return 1

        logger.info("SSH tunnel is open on 127.0.0.1:22. Press Ctrl+C to stop.")
        while ssh_connection.is_tunnel_active():
            time.sleep(TUNNEL_MONITOR_INTERVAL_SECONDS)

        logger.error("SSH tunnel closed unexpectedly.")
        return 1
    except KeyboardInterrupt:
        logger.info("SSH tunnel stopped by user.")
        return 0
    finally:
        ssh_connection.close()
