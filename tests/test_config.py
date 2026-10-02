import pytest

from court_booker.config import ConfigError, load_config


def test_missing_file_uses_defaults(tmp_path):
    config = load_config(tmp_path / "missing.toml")
    assert config.labels.home == "Tiện ích"


def test_file_overrides_defaults(tmp_path):
    path = tmp_path / "config.toml"
    path.write_text('slots = ["18:00 - 19:00"]\n[labels]\ncontinue = "Next"\n', encoding="utf-8")
    config = load_config(path)
    assert config.slots == ["18:00 - 19:00"]
    assert config.labels.continue_ == "Next"


def test_unknown_key_is_rejected(tmp_path):
    path = tmp_path / "config.toml"
    path.write_text("slot = 1\n", encoding="utf-8")
    with pytest.raises(ConfigError):
        load_config(path)
