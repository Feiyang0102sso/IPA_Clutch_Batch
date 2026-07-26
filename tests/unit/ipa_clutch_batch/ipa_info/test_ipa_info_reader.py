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


def test_get_single_ipa_info_falls_back_to_bundle_name(monkeypatch, tmp_path: Path):
    """Use CFBundleName when old IPA metadata has no display name."""
    ipa_path = tmp_path / "bundle_name_only.ipa"
    create_ipa(
        ipa_path,
        None,
        "1.0.0",
        bundle_name="Bundle Name App",
    )
    fake_logger = FakeLogger()
    monkeypatch.setattr(ipa_info_reader, "logger", fake_logger)

    ipa_info = ipa_info_reader.get_single_ipa_info(ipa_path)

    assert ipa_info is not None
    assert ipa_info.display_name == "Bundle Name App"
    assert fake_logger.debugs == [
        "Cannot find 'CFBundleDisplayName' in Info.plist (bundle_name_only.ipa); "
        "using 'CFBundleName' instead",
    ]
    assert fake_logger.warnings == []
    assert fake_logger.errors == []


def test_get_single_ipa_info_falls_back_to_executable_name(monkeypatch, tmp_path: Path):
    """Use CFBundleExecutable when old IPA metadata has no user-facing name keys."""
    ipa_path = tmp_path / "executable_name_only.ipa"
    create_ipa(
        ipa_path,
        None,
        "1.0.0",
        executable_name="OndineiPhone",
    )
    fake_logger = FakeLogger()
    monkeypatch.setattr(ipa_info_reader, "logger", fake_logger)

    ipa_info = ipa_info_reader.get_single_ipa_info(ipa_path)

    assert ipa_info is not None
    assert ipa_info.display_name == "OndineiPhone"
    assert fake_logger.debugs == [
        "Cannot find 'CFBundleDisplayName' in Info.plist (executable_name_only.ipa); "
        "using 'CFBundleExecutable' instead",
    ]
    assert fake_logger.warnings == []
    assert fake_logger.errors == []


def test_get_single_ipa_info_reads_string_device_families(
    monkeypatch,
    tmp_path: Path,
):
    """Accept old malformed UIDeviceFamily string values with a warning."""
    ipa_path = tmp_path / "string_device_family.ipa"
    create_ipa(
        ipa_path,
        "String Family App",
        "1.0.0",
        device_families=["1", "2"],
    )
    fake_logger = FakeLogger()
    monkeypatch.setattr(ipa_info_reader, "logger", fake_logger)

    ipa_info = ipa_info_reader.get_single_ipa_info(ipa_path)

    assert ipa_info is not None
    assert ipa_info.device_families == [1, 2]
    assert fake_logger.warnings == [
        "Invalid string value in 'UIDeviceFamily': 1; treating it as an integer",
        "Invalid string value in 'UIDeviceFamily': 2; treating it as an integer",
    ]
    assert fake_logger.errors == []


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
        "Cannot find a usable app name in Info.plist (missing_name.ipa): "
        "'CFBundleDisplayName', 'CFBundleName', and 'CFBundleExecutable' "
        "are all missing or empty",
        "Cannot find a usable app name in Info.plist (missing_name_and_version.ipa): "
        "'CFBundleDisplayName', 'CFBundleName', and 'CFBundleExecutable' "
        "are all missing or empty",
        "Cannot find 'CFBundleVersion' or 'CFBundleShortVersionString' in Info.plist "
        "(missing_name_and_version.ipa)",
        "Cannot find 'CFBundleVersion' or 'CFBundleShortVersionString' in Info.plist "
        "(missing_version.ipa)",
        "Cannot find Info.plist in without_info.ipa",
    ]


class FakeLogger:
    """Collect logger output for assertions."""

    def __init__(self):
        self.debugs = []
        self.infos = []
        self.warnings = []
        self.errors = []

    def debug(self, message: str):
        self.debugs.append(message)

    def info(self, message: str):
        self.infos.append(message)

    def warning(self, message: str):
        self.warnings.append(message)

    def error(self, message: str):
        self.errors.append(message)


def create_ipa(
    ipa_path: Path,
    display_name: str | None,
    version: str | None,
    *,
    bundle_name: str | None = None,
    executable_name: str | None = None,
    device_families: list[object] | None = None,
):
    """Create a minimal IPA file with Info.plist."""
    if device_families is None:
        device_families = [1]

    plist_content = {
        ipa_info_reader.BUNDLE_IDENTIFIER_KEY: "com.example.mock",
        ipa_info_reader.DEVICE_FAMILY_KEY: device_families,
        ipa_info_reader.MINIMUM_OS_VERSION_KEY: "12.0",
    }

    if display_name is not None:
        plist_content[ipa_info_reader.DISPLAY_NAME_KEY] = display_name

    if bundle_name is not None:
        plist_content[ipa_info_reader.BUNDLE_NAME_KEY] = bundle_name

    if executable_name is not None:
        plist_content[ipa_info_reader.EXECUTABLE_NAME_KEY] = executable_name

    if version is not None:
        plist_content[ipa_info_reader.BUNDLE_VERSION_KEY] = version

    plist_data = plistlib.dumps(plist_content)

    with zipfile.ZipFile(ipa_path, "w") as zip_file:
        zip_file.writestr("Payload/Mock.app/Info.plist", plist_data)


def create_ipa_without_info(ipa_path: Path):
    """Create a minimal IPA file without Info.plist."""
    with zipfile.ZipFile(ipa_path, "w") as zip_file:
        zip_file.writestr("Payload/Mock.app/placeholder.txt", "empty")
