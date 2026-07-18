"""Move one dumped IPA from the iOS device to the computer."""
from pathlib import Path
import re
import tempfile

import paramiko

from ipa_clutch_batch.ipa_info import get_single_ipa_info
from ipa_clutch_batch.logger import logger

INVALID_WINDOWS_FILENAME_PATTERN = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def move_single_dumped_ipa(
    remote_ipa_path: str,
    cracked_dir: Path,
    sftp_client: paramiko.SFTPClient,
) -> bool:
    """Download, verify, rename, and remove one remote IPA file."""
    cracked_dir.mkdir(parents=True, exist_ok=True)
    temp_path = _create_temp_ipa_path(cracked_dir)
    try:
        sftp_client.get(remote_ipa_path, str(temp_path))
    except OSError as error:
        logger.error(f"Cannot download {remote_ipa_path}: {error}")
        temp_path.unlink(missing_ok=True)
        return False

    ipa_info = get_single_ipa_info(temp_path)
    if ipa_info is None:
        logger.error(f"Downloaded IPA metadata is incomplete or invalid: {remote_ipa_path}")
        temp_path.unlink(missing_ok=True)
        return False

    final_path = _get_available_destination_path(
        cracked_dir,
        ipa_info.display_name,
        ipa_info.version,
    )
    try:
        temp_path.rename(final_path)
    except OSError as error:
        logger.error(f"Cannot rename downloaded IPA: {error}")
        temp_path.unlink(missing_ok=True)
        return False

    if not final_path.is_file():
        logger.error(f"Moved IPA verification failed: {final_path}")
        return False

    try:
        sftp_client.remove(remote_ipa_path)
    except OSError as error:
        logger.error(
            f"IPA downloaded but remote file could not be removed: {error}"
        )
        return False

    logger.info(f"Moved IPA to: {final_path}")
    return True


def _create_temp_ipa_path(cracked_dir: Path) -> Path:
    """Create an empty temporary IPA path inside the destination directory."""
    temp_file = tempfile.NamedTemporaryFile(
        prefix="ipa_download_",
        suffix=".ipa",
        dir=cracked_dir,
        delete=False,
    )
    temp_path = Path(temp_file.name)
    temp_file.close()
    return temp_path


def _get_available_destination_path(
    cracked_dir: Path,
    display_name: str,
    version: str,
) -> Path:
    """Build DisplayName_Version_cracked.ipa without overwriting files."""
    safe_display_name = _sanitize_filename_part(display_name)
    safe_version = _sanitize_filename_part(version)
    base_name = f"{safe_display_name}_{safe_version}_cracked"
    destination_path = cracked_dir / f"{base_name}.ipa"
    duplicate_number = 2

    while destination_path.exists():
        destination_path = cracked_dir / f"{base_name}_{duplicate_number}.ipa"
        duplicate_number += 1

    return destination_path


def _sanitize_filename_part(filename_part: str) -> str:
    """Replace characters that are invalid in Windows filenames."""
    safe_part = INVALID_WINDOWS_FILENAME_PATTERN.sub("_", filename_part)
    safe_part = safe_part.strip().rstrip(".")
    if safe_part:
        return safe_part
    return "Unknown"
