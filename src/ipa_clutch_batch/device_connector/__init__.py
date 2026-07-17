"""
Detect and select an iOS device connected through USB.
"""
from ipa_clutch_batch.device_connector.device_connector import (
    DeviceInfo,
    get_connected_device_udids,
    get_device_info,
    get_single_connected_device_udid,
)
from ipa_clutch_batch.device_connector.ssh_connector import (
    SshCommandResult,
    UsbSshConnection,
)

__all__ = [
    "DeviceInfo",
    "get_connected_device_udids",
    "get_device_info",
    "get_single_connected_device_udid",
    "SshCommandResult",
    "UsbSshConnection",
]
