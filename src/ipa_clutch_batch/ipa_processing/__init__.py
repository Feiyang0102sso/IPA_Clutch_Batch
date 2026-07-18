"""
Install IPA files on one USB-connected iOS device.
"""
from ipa_clutch_batch.ipa_processing.ipa_cracker import (
    CrackResult,
    crack_installed_app,
    parse_clutch_installed_apps,
)
from ipa_clutch_batch.ipa_processing.ipa_installer import (
    BatchInstallSummary,
    InstallResult,
    get_ipa_compatibility_error,
    install_all_ipas,
    install_ipa,
)
from ipa_clutch_batch.ipa_processing.ipa_mover import move_single_dumped_ipa
from ipa_clutch_batch.ipa_processing.ipa_pipeline import (
    BatchProcessSummary,
    run_ipa_pipeline,
)

__all__ = [
    "BatchProcessSummary",
    "CrackResult",
    "crack_installed_app",
    "parse_clutch_installed_apps",
    "run_ipa_pipeline",
    "BatchInstallSummary",
    "InstallResult",
    "get_ipa_compatibility_error",
    "install_all_ipas",
    "install_ipa",
    "move_single_dumped_ipa",
]
