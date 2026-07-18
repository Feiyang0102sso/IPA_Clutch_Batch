"""
Unit tests for IPA info directory scan.
"""
from pathlib import Path
import plistlib
import zipfile

from ipa_clutch_batch.ipa_info import ipa_info_reader


def test_get_single_ipa_info_reads_required_metadata(tmp_path: Path):
    """Read the complete IPA metadata required by the main workflow."""
    ipa_path = tmp_path / "normal.ipa"
    create_ipa(ipa_path, "Normal App", "1.0.0")

    ipa_info = ipa_info_reader.get_single_ipa_info(ipa_path)

    assert ipa_info is not None
    assert ipa_info.ipa_path == ipa_path.resolve()
    assert ipa_info.display_name == "Normal App"
    assert ipa_info.version == "1.0.0"
    assert ipa_info.bundle_version == "1.0.0"
    assert ipa_info.short_version is None
    assert ipa_info.bundle_identifier == "com.example.mock"
    assert ipa_info.device_families == [1]
    assert ipa_info.minimum_os_version == "12.0"


def test_get_all_ipa_info_from_directory(monkeypatch, tmp_path: Path):
    """Scan 5 mock IPA files and report only 1 valid result."""
    create_ipa(tmp_path / "normal.ipa", "Normal App", "1.0.0")
    create_ipa_without_info(tmp_path / "without_info.ipa")
    create_ipa(tmp_path / "missing_name.ipa", None, "2.0.0")
    create_ipa(tmp_path / "missing_version.ipa", "Missing Version App", None)
    create_ipa(tmp_path / "missing_name_and_version.ipa", None, None)

    fake_logger = FakeLogger()
    monkeypatch.setattr(ipa_info_reader, "logger", fake_logger)

    ipa_info_reader.get_all_ipa_info_from_directory(tmp_path)

    assert fake_logger.infos == [
        "Found 5 IPA file(s) in input directory.",
        "IPA display name: Normal App (normal.ipa)",
        "IPA version: 1.0.0 (normal.ipa)",
        "IPA bundle ID: com.example.mock (normal.ipa)",
        "Scan completed: 5 total, 1 succeeded, 4 failed.",
    ]
    assert fake_logger.errors == [
        "Cannot find 'CFBundleDisplayName' in Info.plist (missing_name.ipa)",
        "Cannot find 'CFBundleDisplayName' in Info.plist (missing_name_and_version.ipa)",
        "Cannot find 'CFBundleVersion' or 'CFBundleShortVersionString' in Info.plist "
        "(missing_name_and_version.ipa)",
        "Cannot find 'CFBundleVersion' or 'CFBundleShortVersionString' in Info.plist "
        "(missing_version.ipa)",
        "Cannot find Info.plist in without_info.ipa",
    ]


class FakeLogger:
    """Collect logger output for assertions."""

    def __init__(self):
        self.infos = []
        self.errors = []

    def info(self, message: str):
        self.infos.append(message)

    def error(self, message: str):
        self.errors.append(message)


def create_ipa(ipa_path: Path, display_name: str | None, version: str | None):
    """Create a minimal IPA file with Info.plist."""
    plist_content = {
        ipa_info_reader.BUNDLE_IDENTIFIER_KEY: "com.example.mock",
        ipa_info_reader.DEVICE_FAMILY_KEY: [1],
        ipa_info_reader.MINIMUM_OS_VERSION_KEY: "12.0",
    }

    if display_name is not None:
        plist_content[ipa_info_reader.DISPLAY_NAME_KEY] = display_name

    if version is not None:
        plist_content[ipa_info_reader.BUNDLE_VERSION_KEY] = version

    plist_data = plistlib.dumps(plist_content)

    with zipfile.ZipFile(ipa_path, "w") as zip_file:
        zip_file.writestr("Payload/Mock.app/Info.plist", plist_data)


def create_ipa_without_info(ipa_path: Path):
    """Create a minimal IPA file without Info.plist."""
    with zipfile.ZipFile(ipa_path, "w") as zip_file:
        zip_file.writestr("Payload/Mock.app/placeholder.txt", "empty")
