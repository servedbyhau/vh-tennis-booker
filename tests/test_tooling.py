"""The Ruff version: pinned once in pyproject.toml, used by pre-commit and CI."""

import re
import sys
from pathlib import Path

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib

REPO = Path(__file__).resolve().parents[1]


def test_pyproject_pins_ruff_once():
    data = tomllib.loads((REPO / "pyproject.toml").read_text(encoding="utf-8"))
    pins = [pin for pin in data["project"]["optional-dependencies"]["dev"] if "ruff" in pin]

    assert len(pins) == 1 and pins[0].startswith("ruff=="), pins


def test_pre_commit_runs_the_installed_ruff():
    text = (REPO / ".pre-commit-config.yaml").read_text(encoding="utf-8")

    # A hook repo would pin a second version, which Dependabot does not bump.
    assert "ruff-pre-commit" not in text
    assert "python -m ruff check" in text
    assert "python -m ruff format" in text


def test_ci_installs_ruff_from_pyproject():
    text = (REPO / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")

    # CI reads the pin from pyproject.toml; a version of its own would drift from it.
    assert "grep -o 'ruff==[0-9.]*' pyproject.toml" in text
    assert re.search(r"ruff==\d", text) is None
