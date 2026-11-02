"""How a process starts the engine, from the sources and from the packaged app."""

import sys

from court_booker import cli, engine, schedule
from court_booker.api import runs


def test_from_the_sources_the_engine_is_a_python_module(monkeypatch, tmp_path):
    python = tmp_path / "python.exe"
    monkeypatch.setattr(sys, "executable", str(python))
    assert engine.engine_command() == [str(python), "-m", "court_booker"]


def test_windowless_prefers_pythonw_when_it_is_there(monkeypatch, tmp_path):
    python = tmp_path / "python.exe"
    monkeypatch.setattr(sys, "executable", str(python))
    assert engine.engine_command(windowless=True)[0] == str(python)

    (tmp_path / "pythonw.exe").touch()
    assert engine.engine_command(windowless=True) == [
        str(tmp_path / "pythonw.exe"),
        "-m",
        "court_booker",
    ]


def test_the_packaged_app_starts_itself(monkeypatch, tmp_path):
    app = tmp_path / "court-booker.exe"
    (tmp_path / "pythonw.exe").touch()  # never used: there is no Python in the app
    monkeypatch.setattr(sys, "executable", str(app))
    monkeypatch.setattr(sys, "frozen", True, raising=False)

    assert engine.engine_command() == [str(app)]
    assert engine.engine_command(windowless=True) == [str(app)]


def test_every_starter_of_the_engine_uses_the_command():
    assert cli.engine_command is schedule.engine_command is runs.engine_command
