import pytest

from court_booker.config import load_config


def test_defaults_when_file_missing(tmp_path):
    cfg = load_config(tmp_path / "missing.toml")
    assert cfg.labels.home == "Tiện ích"


def test_override(tmp_path):
    p = tmp_path / "c.toml"
    p.write_text('slots = ["18:00 - 19:00"]\n[labels]\ncontinue = "Next"\n', encoding="utf-8")
    cfg = load_config(p)
    assert cfg.slots == ["18:00 - 19:00"]
    assert cfg.labels.continue_ == "Next"


def test_unknown_key_rejected(tmp_path):
    p = tmp_path / "c.toml"
    p.write_text("slot = 1\n", encoding="utf-8")
    with pytest.raises(ValueError):
        load_config(p)
