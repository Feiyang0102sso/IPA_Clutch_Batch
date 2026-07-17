"""
Install IPA files on one USB-connected iOS device.
"""
from ipa_clutch_batch.ipa_installer.ipa_cracker import (
    CrackResult,
    InstallAndCrackSummary,
    crack_installed_app,
    install_and_crack_all_ipas,
    parse_clutch_installed_apps,
)
from ipa_clutch_batch.ipa_installer.ipa_installer import (
    BatchInstallSummary,
    InstallResult,
    get_ipa_compatibility_error,
    install_all_ipas,
    install_ipa,
)
from ipa_clutch_batch.ipa_installer.ipa_mover import (
    MoveIpaSummary,
    move_and_rename_dumped_ipas,
)

__all__ = [
    "CrackResult",
    "InstallAndCrackSummary",
    "crack_installed_app",
    "install_and_crack_all_ipas",
    "parse_clutch_installed_apps",
    "BatchInstallSummary",
    "InstallResult",
    "get_ipa_compatibility_error",
    "install_all_ipas",
    "install_ipa",
    "MoveIpaSummary",
    "move_and_rename_dumped_ipas",
]
