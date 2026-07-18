"""Validate and prepare the Clutch binary on an iOS device."""

from dataclasses import dataclass
import hashlib
from pathlib import Path
import stat
from typing import BinaryIO

import paramiko

from ipa_clutch_batch.config import get_clutch_binary_path
from ipa_clutch_batch.device import UsbSshConnection
from ipa_clutch_batch.logger import logger

REMOTE_CLUTCH_PATH = "/usr/bin/Clutch"
REMOTE_CLUTCH_TEMP_PATH = "/usr/bin/.Clutch.tmp"
CLUTCH_FILE_MODE = 0o755
HASH_CHUNK_SIZE = 64 * 1024


@dataclass(frozen=True)
class ClutchCheckResult:
    """Final state of the local preset and remote Clutch binary."""

    success: bool
    installed: bool
    permissions_fixed: bool
    local_sha256: str | None
    remote_sha256: str | None
    failure_reason: str | None


def ensure_clutch_ready(
    ssh_connection: UsbSshConnection,
    local_clutch_path: Path | None = None,
) -> ClutchCheckResult:
    """Install a missing Clutch, enforce mode 0755, and verify SHA-256."""
    preset_path = local_clutch_path
    if preset_path is None:
        preset_path = get_clutch_binary_path()

    logger.info("Checking Clutch environment...")
    if not preset_path.is_file():
        return _log_failure(f"Preset Clutch binary not found: {preset_path}")

    local_sha256 = _calculate_local_sha256(preset_path)
    logger.info(f"Preset Clutch SHA-256: {local_sha256}")

    sftp_client = ssh_connection.open_sftp()
    if sftp_client is None:
        return _log_failure(
            "Cannot open SFTP for the Clutch check.",
            local_sha256=local_sha256,
        )

    installed = False
    permissions_fixed = False
    try:
        remote_attributes = _get_remote_attributes(sftp_client)
        if remote_attributes is None:
            logger.warning(f"Clutch is not installed at: {REMOTE_CLUTCH_PATH}")
            _install_clutch(sftp_client, preset_path)
            installed = True
            remote_attributes = sftp_client.stat(REMOTE_CLUTCH_PATH)
        else:
            logger.info(f"Clutch found at: {REMOTE_CLUTCH_PATH}")

        if not stat.S_ISREG(remote_attributes.st_mode):
            return _log_failure(
                f"Remote Clutch path is not a regular file: {REMOTE_CLUTCH_PATH}",
                installed=installed,
                local_sha256=local_sha256,
            )

        current_mode = stat.S_IMODE(remote_attributes.st_mode)
        logger.info(f"Current Clutch mode: {current_mode:04o}")
        if current_mode != CLUTCH_FILE_MODE:
            logger.warning(
                f"Clutch mode is incorrect: {current_mode:04o}. "
                f"Changing to {CLUTCH_FILE_MODE:04o}."
            )
            sftp_client.chmod(REMOTE_CLUTCH_PATH, CLUTCH_FILE_MODE)
            permissions_fixed = True

        verified_mode = stat.S_IMODE(
            sftp_client.stat(REMOTE_CLUTCH_PATH).st_mode
        )
        if verified_mode != CLUTCH_FILE_MODE:
            return _log_failure(
                f"Clutch mode verification failed: {verified_mode:04o}",
                installed=installed,
                permissions_fixed=permissions_fixed,
                local_sha256=local_sha256,
            )

        if permissions_fixed:
            logger.info(f"Clutch mode changed to: {verified_mode:04o}")
        else:
            logger.info(f"Clutch mode OK: {verified_mode:04o}")

        remote_sha256 = _calculate_remote_sha256(sftp_client)
        logger.info(f"Remote Clutch SHA-256: {remote_sha256}")
        if remote_sha256 != local_sha256:
            logger.warning(
                "Remote Clutch SHA-256 does not match the preset binary. "
                "Replacing the remote binary."
            )
            _replace_clutch(sftp_client, preset_path)
            installed = True

            replaced_mode = stat.S_IMODE(
                sftp_client.stat(REMOTE_CLUTCH_PATH).st_mode
            )
            if replaced_mode != CLUTCH_FILE_MODE:
                return _log_failure(
                    f"Replaced Clutch mode verification failed: "
                    f"{replaced_mode:04o}",
                    installed=installed,
                    permissions_fixed=permissions_fixed,
                    local_sha256=local_sha256,
                    remote_sha256=remote_sha256,
                )

            remote_sha256 = _calculate_remote_sha256(sftp_client)
            logger.info(f"Replaced Clutch SHA-256: {remote_sha256}")
            if remote_sha256 != local_sha256:
                return _log_failure(
                    "Replaced Clutch SHA-256 verification failed.",
                    installed=installed,
                    permissions_fixed=permissions_fixed,
                    local_sha256=local_sha256,
                    remote_sha256=remote_sha256,
                )

            logger.info("Remote Clutch replaced successfully.")
    except OSError as error:
        return _log_failure(
            f"Clutch check failed: {error}",
            installed=installed,
            permissions_fixed=permissions_fixed,
            local_sha256=local_sha256,
        )
    finally:
        sftp_client.close()

    logger.info("Clutch check completed successfully.")
    return ClutchCheckResult(
        success=True,
        installed=installed,
        permissions_fixed=permissions_fixed,
        local_sha256=local_sha256,
        remote_sha256=remote_sha256,
        failure_reason=None,
    )


def _get_remote_attributes(
    sftp_client: paramiko.SFTPClient,
) -> paramiko.SFTPAttributes | None:
    """Return remote Clutch attributes, or None when the file is missing."""
    try:
        return sftp_client.stat(REMOTE_CLUTCH_PATH)
    except FileNotFoundError:
        return None
    except OSError as error:
        if error.errno == 2:
            return None
        raise


def _install_clutch(
    sftp_client: paramiko.SFTPClient,
    local_clutch_path: Path,
) -> None:
    """Upload the preset through a temporary path and install it atomically."""
    logger.info(f"Uploading preset Clutch to: {REMOTE_CLUTCH_PATH}")
    sftp_client.put(str(local_clutch_path), REMOTE_CLUTCH_TEMP_PATH)
    sftp_client.chmod(REMOTE_CLUTCH_TEMP_PATH, CLUTCH_FILE_MODE)
    sftp_client.rename(REMOTE_CLUTCH_TEMP_PATH, REMOTE_CLUTCH_PATH)
    logger.info("Preset Clutch installed on the device.")


def _replace_clutch(
    sftp_client: paramiko.SFTPClient,
    local_clutch_path: Path,
) -> None:
    """Replace an unexpected remote Clutch with the preset binary."""
    sftp_client.put(str(local_clutch_path), REMOTE_CLUTCH_TEMP_PATH)
    sftp_client.chmod(REMOTE_CLUTCH_TEMP_PATH, CLUTCH_FILE_MODE)
    sftp_client.remove(REMOTE_CLUTCH_PATH)
    sftp_client.rename(REMOTE_CLUTCH_TEMP_PATH, REMOTE_CLUTCH_PATH)


def _calculate_local_sha256(local_clutch_path: Path) -> str:
    """Calculate the SHA-256 digest of the local preset binary."""
    with local_clutch_path.open("rb") as local_file:
        return _calculate_sha256(local_file)


def _calculate_remote_sha256(sftp_client: paramiko.SFTPClient) -> str:
    """Calculate the SHA-256 digest of the remote binary over SFTP."""
    with sftp_client.open(REMOTE_CLUTCH_PATH, "rb") as remote_file:
        return _calculate_sha256(remote_file)


def _calculate_sha256(binary_file: BinaryIO) -> str:
    """Calculate SHA-256 by reading a binary file in fixed-size chunks."""
    sha256 = hashlib.sha256()
    while True:
        file_chunk = binary_file.read(HASH_CHUNK_SIZE)
        if not file_chunk:
            break
        sha256.update(file_chunk)
    return sha256.hexdigest()


def _log_failure(
    failure_reason: str,
    installed: bool = False,
    permissions_fixed: bool = False,
    local_sha256: str | None = None,
    remote_sha256: str | None = None,
) -> ClutchCheckResult:
    """Log and return one failed Clutch check result."""
    logger.error(failure_reason)
    return ClutchCheckResult(
        success=False,
        installed=installed,
        permissions_fixed=permissions_fixed,
        local_sha256=local_sha256,
        remote_sha256=remote_sha256,
        failure_reason=failure_reason,
    )
