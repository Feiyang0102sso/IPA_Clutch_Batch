"""
Project configuration and path helpers for IPA Clutch Batch.
"""
import __main__
import os
from pathlib import Path
import sys

from ipa_clutch_batch.logger import add_file_handler, logger


def get_app_root() -> Path:
    """
    Get project root or packaged application directory.
    """
    if is_packaged_app():
        return Path(sys.argv[0]).parent.resolve()

    if hasattr(__main__, "__file__"):
        main_file = Path(__main__.__file__).resolve()
        main_dir = main_file.parent

        if main_dir.name == "ipa_clutch_batch" and main_dir.parent.name == "src":
            return main_dir.parent.parent.resolve()

        if main_dir.name == "src":
            return main_dir.parent.resolve()

        if main_dir.is_dir():
            return main_dir.resolve()

    return Path.cwd().resolve()


def is_packaged_app() -> bool:
    """
    Return whether the app is running from a built executable.
    """
    if getattr(sys, "frozen", False):
        return True

    if os.environ.get("NUITKA_ONEFILE_PARENT"):
        return True

    return False


def get_runtime_mode_message() -> str:
    """
    Return a short runtime mode message for logging.
    """
    if is_packaged_app():
        return "currently running as a packaged EXE"

    if hasattr(__main__, "__file__"):
        main_file = Path(__main__.__file__).resolve()
        if main_file.parent.is_dir():
            return "currently running as a python script"

    return "currently running as a CLI Wrapper / Shim"


def get_resource_root(app_root: Path) -> Path:
    """
    Get resources root directory.
    """
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        return Path(meipass).resolve()

    if is_packaged_app():
        if hasattr(__main__, "__file__"):
            main_file = Path(__main__.__file__).resolve()
            return main_file.parent

        return app_root

    return app_root


ROOT_DIR = get_app_root()
RESOURCE_ROOT = get_resource_root(ROOT_DIR)
LOG_FILE_NAME = "ipa_clutch_batch.log"
LOG_FILE_PATH = ROOT_DIR / LOG_FILE_NAME

INPUT_DIR = ROOT_DIR / "input"
CRACKED_DIR = INPUT_DIR / "Cracked"
TOOLS_DIR = ROOT_DIR / "tools"
IDEVICEINSTALLER_PATH = TOOLS_DIR / "libimobiledevice" / "ideviceinstaller.exe"

SSH_HOST = "127.0.0.1"
SSH_PORT = 22
SSH_USERNAME = "root"
SSH_PASSWORD = "alpine"

CLUTCH_DUMP_DIR = "/var/mobile/Documents/Dumped"
CRACKED_FILENAME_SUFFIX = "_cracked"


def get_input_dir() -> Path:
    """
    Verify and return the IPA input directory.
    """
    if not INPUT_DIR.exists():
        logger.warning(f"Input directory not found at: {INPUT_DIR}")
    return INPUT_DIR


def get_cracked_dir() -> Path:
    """
    Return the final cracked IPA directory under the input directory.
    """
    CRACKED_DIR.mkdir(parents=True, exist_ok=True)
    return CRACKED_DIR


def get_ideviceinstaller_path() -> Path:
    """
    Return the expected ideviceinstaller executable path.
    """
    return IDEVICEINSTALLER_PATH


def init_app_env():
    """
    Initial bootstrap with default paths.
    """
    add_file_handler(LOG_FILE_PATH)
    logger.debug(get_runtime_mode_message())
    logger.debug(f"Root Path: {ROOT_DIR}")
    logger.debug(f"Log File Path: {LOG_FILE_PATH}")
    logger.debug(f"Input Path: {INPUT_DIR}")
    logger.debug(f"Cracked Path: {CRACKED_DIR}")
    logger.debug(f"Clutch Dump Path: {CLUTCH_DUMP_DIR}")
    logger.debug(f"Tool Path: {IDEVICEINSTALLER_PATH}")
