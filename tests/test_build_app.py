"""Tests for the packaged app's build tool; no npm or PyInstaller calls."""

import importlib.util
import subprocess
from pathlib import Path

TOOL = Path(__file__).resolve().parents[1] / "tools" / "build_app.py"
_spec = importlib.util.spec_from_file_location("build_app", TOOL)
build_app = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(build_app)


def fake_build(calls, *, make_files=True):
    def run(command, cwd, check):
        calls.append(command)
        output = Path(command[command.index("--distpath") + 1]) if "--distpath" in command else None
        if output is not None and make_files:
            for path in build_app.expected_files(output / build_app.APP_NAME):
                path.parent.mkdir(parents=True, exist_ok=True)
                path.touch()
        return subprocess.CompletedProcess(command, 0)

    return run


def test_the_ui_is_built_before_the_app(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(build_app.shutil, "which", lambda name: name)
    monkeypatch.setattr(build_app.subprocess, "run", fake_build(calls))

    assert build_app.main(["--output", str(tmp_path)]) == 0

    assert calls[0] == ["npm", "run", "build"]
    assert calls[1][1:4] == ["-m", "PyInstaller", str(build_app.SPEC)]


def test_a_missing_file_fails_the_build(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(build_app.shutil, "which", lambda name: name)
    monkeypatch.setattr(build_app.subprocess, "run", fake_build([], make_files=False))

    assert build_app.main(["--output", str(tmp_path)]) == 1
    assert "court-driver.apk" in capsys.readouterr().err


def test_no_npm_fails_with_a_message(monkeypatch, capsys):
    monkeypatch.setattr(build_app.shutil, "which", lambda name: None)

    assert build_app.main([]) == 1
    assert "npm not found" in capsys.readouterr().err
