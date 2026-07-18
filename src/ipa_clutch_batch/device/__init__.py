"""
Detect and select an iOS device connected through USB.
"""
from ipa_clutch_batch.device.device_connector import (
    DeviceInfo,
    get_connected_device_udids,
    get_device_info,
    get_single_connected_device_udid,
)
from ipa_clutch_batch.device.ssh_connector import (
    SshCommandResult,
    UsbSshConnection,
)
from ipa_clutch_batch.device.ssh_tunnel_alt import run_ssh22_tunnel

__all__ = [
    "DeviceInfo",
    "get_connected_device_udids",
    "get_device_info",
    "get_single_connected_device_udid",
    "SshCommandResult",
    "UsbSshConnection",
    "run_ssh22_tunnel",
]
