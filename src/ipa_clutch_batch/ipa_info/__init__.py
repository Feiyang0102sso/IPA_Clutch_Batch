"""
Read basic metadata from IPA files.
"""
from ipa_clutch_batch.ipa_info.ipa_info_reader import (
    IpaInfo,
    get_single_ipa_info,
    get_all_ipa_info_from_directory,
)

__all__ = [
    "IpaInfo",
    "get_single_ipa_info",
    "get_all_ipa_info_from_directory",
]
