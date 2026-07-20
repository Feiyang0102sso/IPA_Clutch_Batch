"""Run the sequential install, crack, move, and cleanup pipeline."""

from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from ipa_clutch_batch.common.ipa_utils import ipa_sort_key
from ipa_clutch_batch.device import DeviceInfo, UsbSshConnection
from ipa_clutch_batch.ipa_info import get_single_ipa_info
from ipa_clutch_batch.ipa_processing.ipa_cracker import crack_installed_app
from ipa_clutch_batch.ipa_processing.ipa_installer import (
    get_ipa_compatibility_error,
    install_ipa,
)
from ipa_clutch_batch.ipa_processing.ipa_mover import move_single_dumped_ipa
from ipa_clutch_batch.logger import logger
from ipa_clutch_batch.progress import (
    BatchProgressReporter,
    IpaProcessingStep,
    NO_BATCH_PROGRESS,
)


@dataclass(frozen=True)
class BatchProcessSummary:
    """Summary of one sequential install, crack, and move batch."""

    total: int
    cracked: int
    moved: int
    install_failed: int
    crack_failed: int
    move_failed: int
    skipped: int
    failed_ipa_names: tuple[str, ...]

    @property
    def failed(self) -> int:
        """Return the total number of failed IPA files."""
        return self.install_failed + self.crack_failed + self.move_failed


def run_ipa_pipeline(
    input_dir: Path,
    cracked_dir: Path,
    device_info: DeviceInfo,
    ssh_connection: UsbSshConnection,
    progress_reporter: BatchProgressReporter = NO_BATCH_PROGRESS,
) -> BatchProcessSummary:
    """Complete one IPA lifecycle before processing the next IPA."""
    ipa_paths = sorted(input_dir.glob("*.ipa"), key=ipa_sort_key)
    total_count = len(ipa_paths)

    if total_count == 0:
        logger.info("No IPA files found in input directory.")
        return BatchProcessSummary(
            total=0,
            cracked=0,
            moved=0,
            install_failed=0,
            crack_failed=0,
            move_failed=0,
            skipped=0,
            failed_ipa_names=(),
        )

    logger.info(f"Found {total_count} IPA file(s) to process.")
    progress_reporter.start_ipa_processing(total_count)
    cracked_count = 0
    moved_count = 0
    install_failed_count = 0
    crack_failed_count = 0
    move_failed_count = 0
    skipped_count = 0
    failed_ipa_names = []
    sftp_client = None

    try:
        for process_index, ipa_path in enumerate(ipa_paths, start=1):
            with progress_reporter.track_ipa(ipa_path):
                with progress_reporter.track_ipa_step(
                    ipa_path,
                    IpaProcessingStep.INSTALL,
                ):
                    logger.info(
                        f"Process [{process_index}/{total_count}]: {ipa_path.name}"
                    )

                    ipa_info = get_single_ipa_info(ipa_path)
                    if ipa_info is None:
                        install_failed_count += 1
                        failed_ipa_names.append(ipa_path.name)
                        continue

                    logger.info(f"Target bundle ID: {ipa_info.bundle_identifier}")
                    compatibility_error = get_ipa_compatibility_error(
                        ipa_info,
                        device_info,
                    )
                    if compatibility_error is not None:
                        install_failed_count += 1
                        failed_ipa_names.append(ipa_path.name)
                        logger.error(
                            f"Compatibility check failed: {compatibility_error}"
                        )
                        continue

                    install_result = install_ipa(ipa_path, udid=device_info.udid)
                    if install_result is None:
                        install_failed_count += 1
                        failed_ipa_names.append(ipa_path.name)
                        continue

                    if not install_result.success:
                        install_failed_count += 1
                        failed_ipa_names.append(ipa_path.name)
                        if install_result.failure_reason is not None:
                            logger.error(
                                f"Failure reason: {install_result.failure_reason}"
                            )

                        if install_result.device_storage_full:
                            skipped_count = total_count - process_index
                            _log_device_storage_full_warning(skipped_count)
                            break
                        continue

                with progress_reporter.track_ipa_step(
                    ipa_path,
                    IpaProcessingStep.CRACK,
                ):
                    crack_result = crack_installed_app(
                        ipa_info.bundle_identifier,
                        ssh_connection,
                    )
                    if not crack_result.success:
                        crack_failed_count += 1
                        failed_ipa_names.append(ipa_path.name)
                        if crack_result.device_storage_full:
                            skipped_count = total_count - process_index
                            _log_device_storage_full_warning(skipped_count)
                            break
                        continue

                cracked_count += 1
                remote_ipa_path = crack_result.remote_ipa_path
                if remote_ipa_path is None:
                    move_failed_count += 1
                    failed_ipa_names.append(ipa_path.name)
                    skipped_count = total_count - process_index
                    logger.error(
                        "Clutch succeeded without a dump path. "
                        "Batch processing stopped."
                    )
                    break

                with progress_reporter.track_ipa_step(
                    ipa_path,
                    IpaProcessingStep.MOVE_AND_RENAME,
                ):
                    if sftp_client is None:
                        sftp_client = ssh_connection.open_sftp()
                        if sftp_client is None:
                            move_failed_count += 1
                            failed_ipa_names.append(ipa_path.name)
                            skipped_count = total_count - process_index
                            logger.error(
                                "Cannot open SFTP for the dumped IPA. "
                                "Batch processing stopped."
                            )
                            break

                    logger.info(
                        f"Move [{process_index}/{total_count}]: "
                        f"{PurePosixPath(remote_ipa_path).name}"
                    )
                    move_succeeded = move_single_dumped_ipa(
                        remote_ipa_path,
                        cracked_dir,
                        sftp_client,
                    )
                    if move_succeeded:
                        moved_count += 1
                        continue

                    move_failed_count += 1
                    failed_ipa_names.append(ipa_path.name)
                    skipped_count = total_count - process_index
                    logger.error(
                        "Dump move or remote cleanup failed. "
                        "Batch processing stopped."
                    )
                    break
    finally:
        if sftp_client is not None:
            sftp_client.close()
            logger.info("SFTP connection closed.")

    summary = BatchProcessSummary(
        total=total_count,
        cracked=cracked_count,
        moved=moved_count,
        install_failed=install_failed_count,
        crack_failed=crack_failed_count,
        move_failed=move_failed_count,
        skipped=skipped_count,
        failed_ipa_names=tuple(failed_ipa_names),
    )
    logger.info(
        f"Batch processing completed: {summary.total} total, "
        f"{summary.cracked} cracked, {summary.moved} moved, "
        f"{summary.install_failed} install failed, "
        f"{summary.crack_failed} crack failed, "
        f"{summary.move_failed} move failed, {summary.skipped} skipped."
    )
    return summary


def _log_device_storage_full_warning(skipped_count: int):
    """Warn that no more IPA files will be processed in this batch."""
    logger.warning(
        "Device storage is full. Batch processing stopped; "
        f"{skipped_count} IPA file(s) skipped."
    )
