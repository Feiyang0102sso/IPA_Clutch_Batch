"""Unit tests for IPA installation path handling."""

from pathlib import Path
import plistlib
import subprocess

from ipa_clutch_batch.device import DeviceInfo
from ipa_clutch_batch.ipa_info import IpaInfo
from ipa_clutch_batch.ipa_processing import ipa_installer


def test_install_ipa_uses_temporary_ascii_hard_link_for_chinese_name(
    monkeypatch,
    tmp_path: Path,
):
    """Hide a Chinese IPA filename from tools that only accept ASCII paths."""
    ipa_path = tmp_path / "僵尸之城2_2.0.2.ipa"
    installer_path = tmp_path / "ideviceinstaller.exe"
    ipa_path.touch()
    installer_path.touch()
    captured_install_path = None

    def fake_run_command(command):
        nonlocal captured_install_path
        captured_install_path = Path(command[-1])

        # The link must exist while ideviceinstaller is running.
        assert captured_install_path.is_file()
        assert captured_install_path.name.isascii()
        assert captured_install_path.samefile(ipa_path)

        return subprocess.CompletedProcess(
            args=command,
            returncode=0,
            stdout="Complete",
            stderr="",
        )

    monkeypatch.setattr(ipa_installer, "run_command", fake_run_command)

    install_result = ipa_installer.install_ipa(
        ipa_path,
        udid="mock-udid",
        ideviceinstaller_path=installer_path,
    )

    assert install_result is not None
    assert install_result.success
    assert install_result.ipa_path == ipa_path.resolve()
    assert captured_install_path is not None
    assert not captured_install_path.exists()
    assert list(tmp_path.glob("*.ipa")) == [ipa_path]


def test_install_ipa_keeps_ascii_path_unchanged(monkeypatch, tmp_path: Path):
    """Avoid creating a hard link when the IPA filename is already ASCII."""
    ipa_path = tmp_path / "app_2.0.2.ipa"
    installer_path = tmp_path / "ideviceinstaller.exe"
    ipa_path.touch()
    installer_path.touch()
    captured_install_path = None

    def fake_run_command(command):
        nonlocal captured_install_path
        captured_install_path = Path(command[-1])
        return subprocess.CompletedProcess(
            args=command,
            returncode=0,
            stdout="Complete",
            stderr="",
        )

    monkeypatch.setattr(ipa_installer, "run_command", fake_run_command)

    install_result = ipa_installer.install_ipa(
        ipa_path,
        udid="mock-udid",
        ideviceinstaller_path=installer_path,
    )

    assert install_result is not None
    assert install_result.success
    assert captured_install_path == ipa_path.resolve()
    assert list(tmp_path.glob("*.ipa")) == [ipa_path]


def test_query_installed_ipa_writes_cache_and_reuses_memory(
    monkeypatch,
    tmp_path: Path,
):
    """Query installed apps once, write a local cache, and reuse memory afterwards."""
    installer_path = tmp_path / "ideviceinstaller.exe"
    cache_path = tmp_path / "installed_ipa_cache.xml"
    installer_path.touch()
    query_count = 0
    captured_command = None
    fake_logger = FakeLogger()

    installed_apps = {
        "com.example.test": {
            "CFBundleVersion": "100",
            "CFBundleShortVersionString": "1.2.3",
        },
    }
    plist_output = plistlib.dumps(installed_apps).decode("utf-8")

    def fake_run_command(command):
        nonlocal query_count
        nonlocal captured_command
        query_count += 1
        captured_command = command
        return subprocess.CompletedProcess(
            args=command,
            returncode=0,
            stdout=plist_output,
            stderr="",
        )

    monkeypatch.setattr(ipa_installer, "run_command", fake_run_command)
    monkeypatch.setattr(ipa_installer, "INSTALLED_IPA_CACHE_PATH", cache_path)
    monkeypatch.setattr(ipa_installer, "logger", fake_logger)
    ipa_installer._installed_ipa_cache_by_udid.clear()

    first_result = ipa_installer.query_installed_ipa(
        "mock-udid",
        ideviceinstaller_path=installer_path,
    )
    second_result = ipa_installer.query_installed_ipa(
        "mock-udid",
        ideviceinstaller_path=installer_path,
    )

    assert query_count == 1
    assert captured_command == [
        str(installer_path),
        "--udid",
        "mock-udid",
        "list",
        "--xml",
    ]
    assert first_result is second_result
    assert first_result["com.example.test"].version == "1.2.3"
    assert cache_path.read_text(encoding="utf-8") == plist_output
    assert fake_logger.debugs == [
        f"Installed IPA XML saved: {cache_path}",
    ]
    assert fake_logger.infos == [
        "Query installed IPA list from device.",
        f"Use cached installed IPA XML: {cache_path}",
    ]


def test_failed_query_installed_ipa_is_not_retried_for_same_device(
    monkeypatch,
    tmp_path: Path,
):
    """Avoid repeating a broken installed-app query for every IPA in the batch."""
    installer_path = tmp_path / "ideviceinstaller.exe"
    installer_path.touch()
    query_count = 0

    def fake_run_command(command):
        nonlocal query_count
        query_count += 1
        return subprocess.CompletedProcess(
            args=command,
            returncode=2,
            stdout="",
            stderr="unknown option",
        )

    monkeypatch.setattr(ipa_installer, "run_command", fake_run_command)
    ipa_installer._installed_ipa_cache_by_udid.clear()

    first_result = ipa_installer.query_installed_ipa(
        "mock-udid",
        ideviceinstaller_path=installer_path,
    )
    second_result = ipa_installer.query_installed_ipa(
        "mock-udid",
        ideviceinstaller_path=installer_path,
    )

    assert query_count == 1
    assert first_result == {}
    assert second_result == {}


def test_parse_installed_ipa_xml_accepts_app_array_root():
    """Parse old ideviceinstaller XML where the root plist is an app array."""
    installed_apps = [
        {
            "CFBundleIdentifier": "com.example.first",
            "CFBundleVersion": "1.0",
        },
        {
            "CFBundleIdentifier": "com.example.second",
            "CFBundleVersion": "200",
            "CFBundleShortVersionString": "2.0",
        },
    ]
    plist_output = plistlib.dumps(installed_apps).decode("utf-8")

    installed_ipa_by_bundle_id = ipa_installer._parse_installed_ipa_xml(
        plist_output,
    )

    assert installed_ipa_by_bundle_id["com.example.first"].version == "1.0"
    assert installed_ipa_by_bundle_id["com.example.second"].version == "2.0"


def test_parse_installed_ipa_xml_accepts_single_app_dict_root():
    """Parse one installed app dict returned by a filtered query."""
    installed_app = {
        "CFBundleIdentifier": "com.example.single",
        "CFBundleVersion": "1.0",
    }
    plist_output = plistlib.dumps(installed_app).decode("utf-8")

    installed_ipa_by_bundle_id = ipa_installer._parse_installed_ipa_xml(
        plist_output,
    )

    assert installed_ipa_by_bundle_id["com.example.single"].version == "1.0"


def test_is_already_installed_current_ipa_requires_same_bundle_and_version(
    monkeypatch,
    tmp_path: Path,
):
    """Match only when the installed bundle ID and selected version are identical."""
    installed_ipa_info = ipa_installer.InstalledIpaInfo(
        bundle_identifier="com.example.test",
        version="1.0",
        bundle_version="1.0",
        short_version="1.0",
    )

    def fake_query(udid: str, ideviceinstaller_path=None):
        return {"com.example.test": installed_ipa_info}

    monkeypatch.setattr(ipa_installer, "query_installed_ipa", fake_query)

    same_ipa_info = _create_ipa_info(tmp_path, device_families=[1])
    different_version_ipa_info = IpaInfo(
        ipa_path=tmp_path / "Test.ipa",
        display_name="Test",
        version="2.0.0",
        bundle_version="200",
        short_version="2.0.0",
        bundle_identifier="com.example.test",
        device_families=[1],
        minimum_os_version="6.0",
    )

    assert ipa_installer.is_already_installed_current_ipa(
        same_ipa_info,
        "mock-udid",
    )
    assert not ipa_installer.is_already_installed_current_ipa(
        different_version_ipa_info,
        "mock-udid",
    )


def test_skip_current_ipa_returns_successful_skipped_result(
    monkeypatch,
    tmp_path: Path,
):
    """Represent a skipped reinstall without treating the IPA as failed."""
    ipa_path = tmp_path / "Test.ipa"
    ipa_path.touch()
    ipa_info = _create_ipa_info(tmp_path, device_families=[1])
    fake_logger = FakeLogger()
    monkeypatch.setattr(ipa_installer, "logger", fake_logger)

    install_result = ipa_installer.skip_current_ipa(
        ipa_path,
        ipa_info,
        "mock-udid",
    )

    assert install_result.success
    assert install_result.skipped
    assert install_result.failure_reason is None
    assert fake_logger.infos == [
        "Skip install and crack installed app directly: Test.ipa",
    ]


def test_iphone_only_app_is_compatible_with_ipad(tmp_path: Path):
    """iPad can install iPhone-only apps in compatibility mode."""
    ipa_info = _create_ipa_info(tmp_path, device_families=[1])
    device_info = _create_device_info(device_family=2)

    compatibility_error = ipa_installer.get_ipa_compatibility_error(
        ipa_info,
        device_info,
    )

    assert compatibility_error is None


def test_ipad_only_app_is_not_compatible_with_iphone(tmp_path: Path):
    """iPhone cannot install iPad-only apps."""
    ipa_info = _create_ipa_info(tmp_path, device_families=[2])
    device_info = _create_device_info(device_family=1)

    compatibility_error = ipa_installer.get_ipa_compatibility_error(
        ipa_info,
        device_info,
    )

    assert compatibility_error == (
        "App supports iPad, but connected device is iPhone/iPod."
    )


def _create_ipa_info(
    tmp_path: Path,
    device_families: list[int],
) -> IpaInfo:
    """Create stable IPA metadata for compatibility checks."""
    return IpaInfo(
        ipa_path=tmp_path / "Test.ipa",
        display_name="Test",
        version="1.0",
        bundle_version="1.0",
        short_version="1.0",
        bundle_identifier="com.example.test",
        device_families=device_families,
        minimum_os_version="6.0",
    )


def _create_device_info(device_family: int) -> DeviceInfo:
    """Create stable device metadata for compatibility checks."""
    return DeviceInfo(
        udid="mock-udid",
        name="Mock Device",
        product_type="iPad3,1",
        product_version="6.1.3",
        cpu_architecture="armv7",
        device_family=device_family,
    )


class FakeLogger:
    """Collect logger output for assertions."""

    def __init__(self):
        self.debugs = []
        self.infos = []
        self.warnings = []
        self.errors = []

    def debug(self, message: str):
        """Collect debug output."""
        self.debugs.append(message)

    def info(self, message: str):
        """Collect info output."""
        self.infos.append(message)

    def warning(self, message: str):
        """Collect warning output."""
        self.warnings.append(message)

    def error(self, message: str):
        """Collect error output."""
        self.errors.append(message)
