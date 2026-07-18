"""Shared helpers for working with IPA file paths."""

from pathlib import Path


def _ipa_sort_key(ipa_path: Path) -> str:
    """Return a stable case-insensitive alphabetical filename key."""
    return ipa_path.name.casefold()
