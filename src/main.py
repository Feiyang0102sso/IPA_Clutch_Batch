"""
Command line entry point for IPA Clutch Batch.
"""
from config import get_cracked_dir, get_input_dir, init_app_env
from logger import logger
from version import __app_name__, __version__


def main() -> int:
    """
    Initialize the project environment.
    """
    init_app_env()
    input_dir = get_input_dir()
    cracked_dir = get_cracked_dir()

    logger.info(f"{__app_name__} v{__version__}")
    logger.info(f"Input directory: {input_dir}")
    logger.info(f"Cracked directory: {cracked_dir}")
    logger.info("Batch clutch workflow is not implemented yet.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
