"""
Build IPA Clutch Batch with Nuitka.
"""

import shutil
import subprocess
import sys
from pathlib import Path


APP_PROCESS_NAME = "IPAClutchBatch.exe"
APP_OUTPUT_NAME = "IPAClutchBatch"
APP_PRODUCT_NAME = "IPA Clutch Batch"
PROJECT_ROOT = Path(__file__).resolve().parent
DIST_DIR = PROJECT_ROOT / "dist"
VERSION_FILE = PROJECT_ROOT / "src" / "ipa_clutch_batch" / "version.py"
ENTRY_FILE = PROJECT_ROOT / "src" / "ipa_clutch_batch" / "main.py"
RESOURCES_SOURCE = PROJECT_ROOT / "resources"
RESOURCES_TARGET = DIST_DIR / "resources"


def main() -> int:
    """Run a clean Nuitka one-file build."""
    print("=========================================")
    print(" IPA Clutch Batch - Nuitka Pack ")
    print("=========================================")

    stop_old_app_process()

    version = read_version()
    if version is None:
        return 1

    print(f"[Prep] Detected app version: {version}")
    command = build_nuitka_command(version)

    print("[Nuitka] Compiling Python code...")
    result = subprocess.run(command, check=False)
    if result.returncode != 0:
        print(f"[Nuitka] Error: compilation failed with code {result.returncode}")
        return result.returncode

    copy_resources_directory()
    print("[Finish] Nuitka packaging completed successfully.")
    return 0


def stop_old_app_process() -> None:
    """Stop the old app process so Nuitka can overwrite the executable."""
    command = ["taskkill", "/f", "/im", APP_PROCESS_NAME]
    result = subprocess.run(command, check=False, capture_output=True, text=True)
    if result.returncode == 0:
        print(f"[Prep] Stopped old process: {APP_PROCESS_NAME}")


def read_version() -> str | None:
    """Read __version__ from the app version module."""
    if not VERSION_FILE.exists():
        print(f"[Prep] Error: version file not found: {VERSION_FILE}")
        return None

    version_globals = {}
    version_text = VERSION_FILE.read_text(encoding="utf-8")
    exec(version_text, version_globals)
    return version_globals.get("__version__", "0.0.0")


def build_nuitka_command(version: str) -> list[str]:
    """Build the Nuitka command line."""
    command = [
        sys.executable,
        "-m",
        "nuitka",
        "--onefile",
        "--nofollow-import-to=pytest,unittest,tests",
        "--company-name=Feiyang",
        f"--product-name={APP_PRODUCT_NAME}",
        f"--file-version={version}",
        f"--product-version={version}",
        "--file-description=Batch install and crack IPA files",
        "--copyright=Copyright (c) 2026 Feiyang. All rights reserved.",
        f"--output-dir={DIST_DIR}",
        f"--output-filename={APP_OUTPUT_NAME}",
        str(ENTRY_FILE),
    ]

    # The project has no icon yet. Add --windows-icon-from-ico here in the future.
    return command


def copy_resources_directory() -> None:
    """Copy all external runtime resources beside the generated executable."""
    print("[Post-Build] Copying runtime resources...")
    if not RESOURCES_SOURCE.is_dir():
        print(f"[Post-Build] Warning: directory not found: {RESOURCES_SOURCE}")
        return

    shutil.copytree(
        RESOURCES_SOURCE,
        RESOURCES_TARGET,
        dirs_exist_ok=True,
    )
    print(f"[Post-Build] Copied resources to: {RESOURCES_TARGET}")


if __name__ == "__main__":
    raise SystemExit(main())
