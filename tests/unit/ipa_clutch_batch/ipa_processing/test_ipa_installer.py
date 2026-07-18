"""Unit tests for IPA installation path handling."""

from pathlib import Path
import subprocess

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
