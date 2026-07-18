"""Unit tests for shared IPA path helpers."""

from pathlib import Path

from ipa_clutch_batch.common.ipa_utils import ipa_sort_key


def test_ipa_sort_key_orders_filenames_without_case_sensitivity():
    """Sort IPA paths alphabetically regardless of filename casing."""
    ipa_paths = [
        Path("Zebra.ipa"),
        Path("alpha.ipa"),
        Path("Beta.ipa"),
    ]

    sorted_ipa_paths = sorted(ipa_paths, key=ipa_sort_key)

    assert sorted_ipa_paths == [
        Path("alpha.ipa"),
        Path("Beta.ipa"),
        Path("Zebra.ipa"),
    ]
