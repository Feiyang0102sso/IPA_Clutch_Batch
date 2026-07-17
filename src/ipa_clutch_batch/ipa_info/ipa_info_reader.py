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

# -- IPA zip structure constants --
PAYLOAD_PREFIX = "Payload/"
INFO_PLIST_SUFFIX = ".app/Info.plist"

# -- Info.plist key constants --
DISPLAY_NAME_KEY = "CFBundleDisplayName"
BUNDLE_VERSION_KEY = "CFBundleVersion"
SHORT_VERSION_KEY = "CFBundleShortVersionString"
BUNDLE_IDENTIFIER_KEY = "CFBundleIdentifier"
DEVICE_FAMILY_KEY = "UIDeviceFamily"
MINIMUM_OS_VERSION_KEY = "MinimumOSVersion"

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
    device_families: list[int]
    minimum_os_version: str | None

# initially designed... but not widely used now
# keep it in case it will be used
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
    Universal Reader to get infos from an IPA archive.

    Logs an error and returns None when the archive or required metadata is invalid.
    """
    resolved_path = ipa_path.expanduser().resolve()
    plist_data = _read_info_plist(resolved_path)
    if plist_data is None:
        return None

    display_name = plist_data.get(DISPLAY_NAME_KEY)
    bundle_version = normalize_version_value(plist_data.get(BUNDLE_VERSION_KEY))
    short_version = normalize_version_value(plist_data.get(SHORT_VERSION_KEY))
    version = select_preferred_version(bundle_version, short_version)
    bundle_identifier = plist_data.get(BUNDLE_IDENTIFIER_KEY)
    device_families = _parse_device_families(plist_data)
    minimum_os_version = normalize_version_value(
        plist_data.get(MINIMUM_OS_VERSION_KEY)
    )

    missing_keys = []

    if not isinstance(display_name, str) or not display_name:
        missing_keys.append(DISPLAY_NAME_KEY)
    if version is None:
        missing_keys.append(f"{BUNDLE_VERSION_KEY}' or '{SHORT_VERSION_KEY}")
    if not isinstance(bundle_identifier, str) or not bundle_identifier:
        missing_keys.append(BUNDLE_IDENTIFIER_KEY)
    if not device_families:
        missing_keys.append(DEVICE_FAMILY_KEY)
    if minimum_os_version is None:
        missing_keys.append(MINIMUM_OS_VERSION_KEY)

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
        device_families=device_families,
        minimum_os_version=minimum_os_version,
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


def _read_info_plist(resolved_path: Path) -> dict | None:
    """Read and validate the main Info.plist from an IPA archive."""
    try:
        with zipfile.ZipFile(resolved_path, "r") as ipa_archive:
            # locate Info.plist
            plist_entry = _find_info_plist(ipa_archive)
            if plist_entry is None:
                logger.error(f"Cannot find Info.plist in {resolved_path.name}")
                # logger.error(f"IPA path: {resolved_path}")
                return None

            # parse plist and extract infos
            plist_bytes = ipa_archive.read(plist_entry)
            plist_data = plistlib.loads(plist_bytes)

    except zipfile.BadZipFile as error:
        logger.error(f"Invalid IPA archive ({resolved_path.name}): {error}")
        return None
    except plistlib.InvalidFileException as error:
        logger.error(f"Invalid Info.plist ({resolved_path.name}): {error}")
        return None
    except (OSError, RuntimeError, NotImplementedError) as error:
        logger.error(f"Cannot read IPA file ({resolved_path.name}): {error}")
        return None

    if not isinstance(plist_data, dict):
        logger.error(
            f"Info.plist root is not a dictionary ({resolved_path.name})"
        )
        return None
    return plist_data


def _find_info_plist(ipa_archive: zipfile.ZipFile) -> str | None:
    """
    Find Payload/*.app/Info.plist in the IPA zip.
    Returns None if not found.
    """
    for archive_path in ipa_archive.namelist():
        if archive_path.startswith(PAYLOAD_PREFIX) and archive_path.endswith(
            INFO_PLIST_SUFFIX
        ):
            return archive_path
    return None


def _parse_device_families(plist_data: dict) -> list[int]:
    """Read UIDeviceFamily as a normalized integer list."""
    raw_families = plist_data.get(DEVICE_FAMILY_KEY, [])
    families = []

    if isinstance(raw_families, int):
        families.append(raw_families)
        return families

    if not isinstance(raw_families, list):
        return families

    for raw_family in raw_families:
        if isinstance(raw_family, int):
            families.append(raw_family)

    return families
