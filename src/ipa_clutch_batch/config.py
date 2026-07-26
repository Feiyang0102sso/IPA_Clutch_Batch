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
    Return the external resources directory beside the project or packaged EXE.
    """
    return app_root / "resources"


ROOT_DIR = get_app_root()
RESOURCE_ROOT = get_resource_root(ROOT_DIR)
LOG_FILE_NAME = "IPAClutchBatch.log"
LOG_FILE_PATH = ROOT_DIR / LOG_FILE_NAME
INSTALLED_IPA_CACHE_PATH = ROOT_DIR / "installed_ipa_cache.xml"

INPUT_DIR = ROOT_DIR / "input"
CRACKED_DIR = INPUT_DIR / "cracked"
LIBIMOBILE_DIR = RESOURCE_ROOT / "libimobile"
IDEVICE_ID_PATH = LIBIMOBILE_DIR / "idevice_id.exe"
IDEVICEINFO_PATH = LIBIMOBILE_DIR / "ideviceinfo.exe"
IDEVICEINSTALLER_PATH = LIBIMOBILE_DIR / "ideviceinstaller.exe"
IPROXY_PATH = LIBIMOBILE_DIR / "iproxy.exe"

CLUTCH_DIR = RESOURCE_ROOT / "clutch"
CLUTCH_BINARY_PATH = CLUTCH_DIR / "Clutch"

SSH_HOST = "127.0.0.1"
SSH_LOCAL_PORT = 2222
SSH_DEVICE_PORT = 22
SSH_USERNAME = "root"
SSH_PASSWORD = "alpine"
SSH_CONNECT_TIMEOUT_SECONDS = 10

CLUTCH_DUMP_DIR = "/private/var/mobile/Documents/Dumped"
CRACKED_FILENAME_SUFFIX = "_cracked"


def get_input_dir(input_path: Path | None = None) -> Path:
    """
    Verify and return the IPA input directory.
    """
    resolved_input_dir = INPUT_DIR
    if input_path is not None:
        resolved_input_dir = input_path.expanduser().resolve()

    if not resolved_input_dir.exists():
        logger.warning(f"Input directory not found at: {resolved_input_dir}")
    return resolved_input_dir


def get_cracked_dir(input_dir: Path | None = None) -> Path:
    """
    Return the final cracked IPA directory under the input directory.
    """
    resolved_input_dir = INPUT_DIR
    if input_dir is not None:
        resolved_input_dir = input_dir

    cracked_dir = resolved_input_dir / "cracked"
    cracked_dir.mkdir(parents=True, exist_ok=True)
    return cracked_dir


def get_ideviceinstaller_path() -> Path:
    """
    Return the expected ideviceinstaller executable path.
    """
    return IDEVICEINSTALLER_PATH


def get_idevice_id_path() -> Path:
    """
    Return the expected idevice_id executable path.
    """
    return IDEVICE_ID_PATH


def get_ideviceinfo_path() -> Path:
    """
    Return the expected ideviceinfo executable path.
    """
    return IDEVICEINFO_PATH


def get_iproxy_path() -> Path:
    """
    Return the expected iproxy executable path.
    """
    return IPROXY_PATH


def get_clutch_binary_path() -> Path:
    """
    Return the expected preset Clutch binary path.
    """
    return CLUTCH_BINARY_PATH


def init_app_env(input_dir: Path | None = None):
    """
    Initial bootstrap with default paths.
    """
    runtime_input_dir = INPUT_DIR
    if input_dir is not None:
        runtime_input_dir = input_dir
    runtime_cracked_dir = runtime_input_dir / "cracked"

    add_file_handler(LOG_FILE_PATH)
    _clear_previous_installed_ipa_cache()
    logger.debug(get_runtime_mode_message())
    logger.debug(f"Root Path: {ROOT_DIR}")
    logger.debug(f"Resource Root Path: {RESOURCE_ROOT}")
    logger.debug(f"Log File Path: {LOG_FILE_PATH}")
    logger.debug(f"Installed IPA Cache Path: {INSTALLED_IPA_CACHE_PATH}")
    logger.debug(f"Input Path: {runtime_input_dir}")
    logger.debug(f"Cracked Path: {runtime_cracked_dir}")
    logger.debug(f"Clutch Dump Path: {CLUTCH_DUMP_DIR}")
    logger.debug(f"Device ID Tool Path: {IDEVICE_ID_PATH}")
    logger.debug(f"Device Info Tool Path: {IDEVICEINFO_PATH}")
    logger.debug(f"Installer Tool Path: {IDEVICEINSTALLER_PATH}")
    logger.debug(f"USB Proxy Tool Path: {IPROXY_PATH}")
    logger.debug(f"Preset Clutch Path: {CLUTCH_BINARY_PATH}")
    logger.debug(
        f"Default SSH Tunnel: {SSH_HOST}:{SSH_LOCAL_PORT} "
        f"-> device:{SSH_DEVICE_PORT}"
    )


def _clear_previous_installed_ipa_cache():
    """Clear stale installed-app XML from the previous app run."""
    try:
        INSTALLED_IPA_CACHE_PATH.unlink(missing_ok=True)
    except OSError as error:
        logger.warning(f"Cannot clear installed IPA cache: {error}")
        return

    logger.debug("Previous installed IPA cache cleared.")
