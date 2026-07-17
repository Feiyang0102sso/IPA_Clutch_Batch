"""
Move dumped IPA files from the iOS device and rename them on the computer.
"""
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
import re
import tempfile

import paramiko

from ipa_clutch_batch.config import CLUTCH_DUMP_DIR
from ipa_clutch_batch.device_connector import UsbSshConnection
from ipa_clutch_batch.ipa_info import get_single_ipa_info
from ipa_clutch_batch.logger import logger

INVALID_WINDOWS_FILENAME_PATTERN = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


@dataclass(frozen=True)
class MoveIpaSummary:
    """Summary of one remote IPA move and rename operation."""

    total: int
    moved: int
    failed: int


def move_and_rename_dumped_ipas(
    cracked_dir: Path,
    ssh_connection: UsbSshConnection,
    remote_ipa_paths: tuple[str, ...] | None = None,
) -> MoveIpaSummary:
    """Move every dumped IPA to the computer and rename it from metadata."""
    cracked_dir.mkdir(parents=True, exist_ok=True)
    sftp_client = ssh_connection.open_sftp()
    if sftp_client is None:
        return MoveIpaSummary(total=0, moved=0, failed=1)

    try:
        selected_remote_paths = remote_ipa_paths
        if selected_remote_paths is None:
            listed_remote_paths = _get_remote_ipa_paths(sftp_client)
            if listed_remote_paths is None:
                return MoveIpaSummary(total=0, moved=0, failed=1)
            selected_remote_paths = tuple(listed_remote_paths)

        total_count = len(selected_remote_paths)
        if total_count == 0:
            logger.info(f"No dumped IPA files found in: {CLUTCH_DUMP_DIR}")
            return MoveIpaSummary(total=0, moved=0, failed=0)

        logger.info(f"Found {total_count} dumped IPA file(s) to move.")
        moved_count = 0
        failed_count = 0

        for move_index, remote_ipa_path in enumerate(selected_remote_paths, start=1):
            logger.info(
                f"Move [{move_index}/{total_count}]: "
                f"{PurePosixPath(remote_ipa_path).name}"
            )
            if _move_single_ipa(
                remote_ipa_path,
                cracked_dir,
                sftp_client,
            ):
                moved_count += 1
            else:
                failed_count += 1

        logger.info(
            f"Move completed: {total_count} total, "
            f"{moved_count} moved, {failed_count} failed."
        )
        return MoveIpaSummary(
            total=total_count,
            moved=moved_count,
            failed=failed_count,
        )
    finally:
        sftp_client.close()
        logger.info("SFTP connection closed.")


def _get_remote_ipa_paths(
    sftp_client: paramiko.SFTPClient,
) -> list[str] | None:
    """Return all remote IPA paths in stable alphabetical order."""
    try:
        remote_names = sftp_client.listdir(CLUTCH_DUMP_DIR)
    except OSError as error:
        logger.error(f"Cannot list Clutch dump directory: {error}")
        return None

    remote_ipa_paths = []
    for remote_name in sorted(remote_names, key=str.casefold):
        if not remote_name.lower().endswith(".ipa"):
            continue
        remote_path = PurePosixPath(CLUTCH_DUMP_DIR) / remote_name
        remote_ipa_paths.append(str(remote_path))
    return remote_ipa_paths


def _move_single_ipa(
    remote_ipa_path: str,
    cracked_dir: Path,
    sftp_client: paramiko.SFTPClient,
) -> bool:
    """Download, verify, rename, and remove one remote IPA file."""
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
