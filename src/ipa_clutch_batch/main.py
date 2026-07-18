"""
Command line entry point for IPA Clutch Batch.
"""
import argparse
from pathlib import Path

from ipa_clutch_batch.clutch import ensure_clutch_ready, run_clutch_check
from ipa_clutch_batch.config import get_cracked_dir, get_input_dir, init_app_env
from ipa_clutch_batch.device import (
    UsbSshConnection,
    get_device_info,
    get_single_connected_device_udid,
    run_ssh22_tunnel,
)
from ipa_clutch_batch.ipa_processing import run_ipa_pipeline
from ipa_clutch_batch.logger import (
    configure_console_logging,
    logger,
)
from ipa_clutch_batch.progress import WorkflowProgress
from ipa_clutch_batch.version import __app_name__, __version__


def main() -> int:
    """
    Initialize the project environment.
    """
    arguments = _parse_arguments()
    show_complete_console_logs = (
        arguments.verbose
        or arguments.clutch
        or arguments.ssh22
    )
    configure_console_logging(show_complete_console_logs)
    if arguments.ssh22:
        init_app_env()
        logger.info(f"{__app_name__} v{__version__}")
        return run_ssh22_tunnel()

    if arguments.clutch:
        init_app_env()
        logger.info(f"{__app_name__} v{__version__}")
        return run_clutch_check()

    input_dir = get_input_dir(arguments.input_path)
    init_app_env(input_dir)

    if not input_dir.is_dir():
        logger.error(f"Input path is not a directory: {input_dir}")
        return 2

    cracked_dir = get_cracked_dir(input_dir)

    logger.info(f"{__app_name__} v{__version__}")
    logger.info(f"Input directory: {input_dir}")
    logger.info(f"Cracked directory: {cracked_dir}")

    if not _contains_ipa_files(input_dir):
        logger.info("No IPA files found in input directory.")
        return 0

    progress_display = WorkflowProgress(enabled=not arguments.verbose)
    progress_display.open()
    ssh_connection = None
    try:
        progress_display.start_ssh_stage()

        device_udid = get_single_connected_device_udid()
        if device_udid is None:
            logger.error("Device connection check failed. Workflow stopped.")
            return 1

        logger.info(f"Device connection ready: {device_udid}")

        device_info = get_device_info(device_udid)
        if device_info is None:
            logger.error("Cannot read device information. Workflow stopped.")
            return 1

        ssh_connection = UsbSshConnection(device_udid)
        if not ssh_connection.connect():
            return 1

        progress_display.complete_ssh_stage()

        progress_display.start_clutch_stage()
        clutch_result = ensure_clutch_ready(ssh_connection)
        if not clutch_result.success:
            logger.error("Clutch environment check failed. Workflow stopped.")
            return 1
        progress_display.complete_clutch_stage()

        process_summary = run_ipa_pipeline(
            input_dir,
            cracked_dir,
            device_info,
            ssh_connection,
            progress_reporter=progress_display,
        )

        total_failed = process_summary.failed
        logger.info(
            f"Workflow completed: {process_summary.total} input, "
            f"{process_summary.cracked} cracked, {process_summary.moved} moved, "
            f"{total_failed} failed, {process_summary.skipped} skipped."
        )
        progress_display.show_all_tasks_finished()
        if total_failed > 0:
            return 1
    except KeyboardInterrupt:
        logger.info("Workflow interrupted by user.")
        return 130
    finally:
        if ssh_connection is not None:
            ssh_connection.close()
        progress_display.close()

    return 0


def _parse_arguments() -> argparse.Namespace:
    """Read command line options."""
    # Initial development versions provided three manual hardware test modes:
    # -s / --ssh-test: open USB SSH, run a probe, and wait until Ctrl+C.
    # -c / --crack-test: install and crack each IPA without moving dump files.
    # -m / --move-test: move and rename all IPA files already in the dump directory.
    # They were removed from the initial release CLI to keep one clear workflow.
    # Keep this record because these diagnostic modes may be restored during
    # future device compatibility and workflow optimization work.
    argument_parser = argparse.ArgumentParser(
        description="Batch install IPA files and run Clutch through USB SSH."
    )
    argument_parser.add_argument(
        "input_path",
        type=Path,
        nargs="?",
        help="Directory containing IPA files to install and crack.",
    )
    argument_parser.add_argument(
        "--verbose",
        action="store_true",
        help=(
            "Show complete console logs instead of progress bars during "
            "normal batch processing."
        ),
    )
    argument_parser.add_argument(
        "--clutch",
        action="store_true",
        help="Only check the Clutch environment; do nothing else.",
    )
    argument_parser.add_argument(
        "--ssh22",
        action="store_true",
        help=(
            "Open local port 22 for testing. It cannot be combined with any "
            "other argument; press Ctrl+C to close the connection."
        ),
    )
    arguments = argument_parser.parse_args()
    ssh22_has_other_arguments = (
        arguments.clutch
        or arguments.verbose
        or arguments.input_path is not None
    )
    if arguments.ssh22 and ssh22_has_other_arguments:
        argument_parser.error(
            "--ssh22 cannot be combined with any other argument"
        )
    if arguments.input_path is None and not arguments.clutch and not arguments.ssh22:
        argument_parser.error(
            "input_path is required unless --clutch or --ssh22 is used"
        )
    return arguments


def _contains_ipa_files(input_dir: Path) -> bool:
    """Return whether the input directory contains at least one IPA file."""
    for ipa_path in input_dir.glob("*.ipa"):
        if ipa_path.is_file():
            return True
    return False

# !!! for test only !!!
# ipa-clutch-batch input
# ipa-clutch-batch kill9
# ipa-clutch-batch already_crack
if __name__ == "__main__":
    raise SystemExit(main())
