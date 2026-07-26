"""Unit tests for app environment initialization."""

from pathlib import Path

from ipa_clutch_batch import config


def test_init_app_env_clears_previous_installed_ipa_cache(
    monkeypatch,
    tmp_path: Path,
):
    """Remove stale installed-app XML only when a new app run starts."""
    log_path = tmp_path / "IPAClutchBatch.log"
    cache_path = tmp_path / "installed_ipa_cache.xml"
    input_dir = tmp_path / "input"
    cache_path.write_text("<plist></plist>", encoding="utf-8")

    monkeypatch.setattr(config, "LOG_FILE_PATH", log_path)
    monkeypatch.setattr(config, "INSTALLED_IPA_CACHE_PATH", cache_path)

    config.init_app_env(input_dir)

    assert not cache_path.exists()
