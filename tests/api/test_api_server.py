"""Tests for ``court-booker serve`` with uvicorn replaced."""

import pytest
import uvicorn
from fastapi.testclient import TestClient

from court_booker.api import server
from court_booker.config import Config, load_config


@pytest.fixture
def served(monkeypatch):
    """Record what uvicorn would serve instead of serving it."""
    calls = []
    monkeypatch.setattr(uvicorn, "run", lambda app, **options: calls.append((app, options)))
    return calls


def test_serves_on_this_pc_only(served, tmp_path):
    config_path = tmp_path / "config.toml"

    assert server.main(["--config", str(config_path), "--port", "9000"]) == 0

    ((app, options),) = served
    assert options["host"] == "127.0.0.1"
    assert options["port"] == 9000
    assert app.state.context.config_path == config_path.resolve()


def test_the_built_ui_beside_the_code_is_served(served, monkeypatch, tmp_path):
    (tmp_path / "index.html").write_text("<!doctype html>", encoding="utf-8")
    monkeypatch.setattr(server, "UI_FOLDER", tmp_path)

    server.main(["--config", str(tmp_path / "config.toml")])

    ((app, _),) = served
    with TestClient(app) as client:
        assert client.get("/").text == "<!doctype html>"


def test_development_without_a_build_serves_the_api_only(served, monkeypatch, tmp_path):
    monkeypatch.setattr(server, "UI_FOLDER", tmp_path / "missing")

    server.main(["--config", str(tmp_path / "config.toml")])

    ((app, _),) = served
    with TestClient(app) as client:
        assert client.get("/").status_code == 404
        assert client.get("/api/health").status_code == 200


def test_the_data_folder_config_is_created_when_none_is_given(served, data_home):
    server.main([])

    ((app, _),) = served
    assert app.state.context.config_path == data_home / "config.toml"
    assert load_config(data_home / "config.toml") == Config()
    assert app.state.context.data.root == data_home
