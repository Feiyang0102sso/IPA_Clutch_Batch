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
from ipa_clutch_batch.logger import logger
from ipa_clutch_batch.version import __app_name__, __version__


def main() -> int:
    """
    Initialize the project environment.
    """
    arguments = _parse_arguments()
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
    try:
        if not ssh_connection.connect():
            return 1

        clutch_result = ensure_clutch_ready(ssh_connection)
        if not clutch_result.success:
            logger.error("Clutch environment check failed. Workflow stopped.")
            return 1

        process_summary = run_ipa_pipeline(
            input_dir,
            cracked_dir,
            device_info,
            ssh_connection,
        )

        total_failed = process_summary.failed
        logger.info(
            f"Workflow completed: {process_summary.total} input, "
            f"{process_summary.cracked} cracked, {process_summary.moved} moved, "
            f"{total_failed} failed, {process_summary.skipped} skipped."
        )
        if total_failed > 0:
            return 1
    except KeyboardInterrupt:
        logger.info("Workflow interrupted by user.")
        return 130
    finally:
        ssh_connection.close()

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
        "--clutch",
        action="store_true",
        help="Check and repair Clutch on the connected device, then exit.",
    )
    argument_parser.add_argument(
        "--ssh22",
        action="store_true",
        help="Open local port 22 to device SSH until Ctrl+C, then exit.",
    )
    arguments = argument_parser.parse_args()
    if arguments.ssh22 and arguments.clutch:
        argument_parser.error("--ssh22 cannot be combined with --clutch")
    if arguments.ssh22 and arguments.input_path is not None:
        argument_parser.error("--ssh22 cannot accept an input path")
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
