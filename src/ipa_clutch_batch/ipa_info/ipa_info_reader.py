"""
Read Info.plist metadata from IPA archives.
find plist -> read display_name & version -> log error if missing.
"""
from dataclasses import dataclass
from pathlib import Path
import plistlib
import re
import zipfile

from ipa_clutch_batch.logger import logger

INFO_PLIST_SUFFIX = ".app/Info.plist"
PAYLOAD_PREFIX = "Payload/"
DISPLAY_NAME_KEY = "CFBundleDisplayName"
BUNDLE_VERSION_KEY = "CFBundleVersion"  # CFBundleShortVersionString
SHORT_VERSION_KEY = "CFBundleShortVersionString"
BUNDLE_IDENTIFIER_KEY = "CFBundleIdentifier"
DOTTED_VERSION_PATTERN = re.compile(r"^\d+\.\d+(?:\.\d+)?$")


@dataclass(frozen=True)
class IpaInfo:
    """Basic metadata extracted from an IPA file."""

    ipa_path: Path
    display_name: str
    version: str
    bundle_version: str | None
    short_version: str | None
    bundle_identifier: str


def get_all_ipa_info_from_directory(input_dir: Path):
    """Scan all IPA files in the directory and log their metadata."""
    ipa_paths = sorted(input_dir.glob("*.ipa"))
    total_count = len(ipa_paths)

    if total_count == 0:
        logger.info("No IPA files found in input directory.")
        return

    logger.info(f"Found {total_count} IPA file(s) in input directory.")

    success_count = 0
    for ipa_path in ipa_paths:
        info = get_single_ipa_info(ipa_path)
        if info is None:
            continue
        success_count += 1
        logger.info(f"IPA display name: {info.display_name} ({ipa_path.name})")
        logger.info(f"IPA version: {info.version} ({ipa_path.name})")
        logger.info(f"IPA bundle ID: {info.bundle_identifier} ({ipa_path.name})")

    failed_count = total_count - success_count
    logger.info(
        f"Scan completed: {total_count} total, {success_count} succeeded, {failed_count} failed."
    )


def get_single_ipa_info(ipa_path: Path) -> IpaInfo | None:
    """
    Read display name, version, and bundle identifier from an IPA archive.

    Logs an error and returns None if anything is missing.
    """
    resolved_path = ipa_path.expanduser().resolve()

    # locate Info.plist
    plist_entry = _find_info_plist(resolved_path)
    if plist_entry is None:
        logger.error(f"Cannot find Info.plist in {ipa_path.name}")
        # logger.error(f"IPA path: {resolved_path}")
        return None

    # parse plist and extract infos
    with zipfile.ZipFile(resolved_path, "r") as zf:
        plist_data = plistlib.loads(zf.read(plist_entry))

    display_name = plist_data.get(DISPLAY_NAME_KEY)
    bundle_version = normalize_version_value(plist_data.get(BUNDLE_VERSION_KEY))
    short_version = normalize_version_value(plist_data.get(SHORT_VERSION_KEY))
    version = select_preferred_version(bundle_version, short_version)
    bundle_identifier = plist_data.get(BUNDLE_IDENTIFIER_KEY)

    missing_keys = []

    if not isinstance(display_name, str) or not display_name:
        missing_keys.append(DISPLAY_NAME_KEY)
    if version is None:
        missing_keys.append(f"{BUNDLE_VERSION_KEY}' or '{SHORT_VERSION_KEY}")
    if not isinstance(bundle_identifier, str) or not bundle_identifier:
        missing_keys.append(BUNDLE_IDENTIFIER_KEY)

    if missing_keys:
        for key in missing_keys:
            logger.error(f"Cannot find '{key}' in Info.plist ({ipa_path.name})")
        return None

    return IpaInfo(
        ipa_path=resolved_path,
        display_name=display_name,
        version=version,
        bundle_version=bundle_version,
        short_version=short_version,
        bundle_identifier=bundle_identifier,
    )


def select_preferred_version(
    bundle_version: str | None,
    short_version: str | None,
) -> str | None:
    """Select the most useful version while preserving both original values."""
    if bundle_version is None:
        return short_version
    if short_version is None:
        return bundle_version

    if bundle_version.isdigit():
        return short_version
    if is_dotted_version(short_version):
        return short_version
    if is_dotted_version(bundle_version):
        return bundle_version
    return short_version


def is_dotted_version(version: str) -> bool:
    """Return whether a version uses the x.x or x.x.x numeric form."""
    return DOTTED_VERSION_PATTERN.fullmatch(version) is not None


def normalize_version_value(version_value: object) -> str | None:
    """Normalize plist string and integer version values."""
    if isinstance(version_value, bool):
        return None
    if isinstance(version_value, int):
        return str(version_value)
    if not isinstance(version_value, str):
        return None

    normalized_version = version_value.strip()
    if not normalized_version:
        return None
    return normalized_version


def _find_info_plist(ipa_path: Path) -> str | None:
    """
    Find Payload/*.app/Info.plist in the IPA zip.
    Returns None if not found.
    """
    with zipfile.ZipFile(ipa_path, "r") as zf:
        for name in zf.namelist():
            if name.startswith(PAYLOAD_PREFIX) and name.endswith(INFO_PLIST_SUFFIX):
                return name
    return None
