# Contributing

## Setup

```bash
pip install -e ".[dev]"
pre-commit install
```

`pre-commit` runs Ruff (lint and format) and basic file checks on every commit.

## Before opening a pull request

```bash
ruff check .
ruff format .
pytest
```

If the booking flow changed, also run `court-booker --dry-run --verbose` against the emulator.

## Conventions

- **Language:** code, comments, logs, commit messages and documentation are in English.
  Accessibility labels of the target app stay in Vietnamese and live in `config.toml`.
- **Style:** enforced by Ruff (line length 100). Public functions have type hints and a
  one-line docstring in the imperative mood. Comments explain *why*, not *what*.
- **Errors:** raise a subclass of `BookingError` for failures that should abort one round.
- **Logging:** use the module logger (`logging.getLogger(__name__)`), never `print`, except
  for the final summary in the CLI.
- **Commits:** follow [Conventional Commits](https://www.conventionalcommits.org/),
  e.g. `feat: add retry when a slot is not yet open`, `fix: wait for ticket screen`.
- **Branches:** `feat/<topic>`, `fix/<topic>`, `docs/<topic>`; merge into `main` via pull request.
- **Versioning:** [Semantic Versioning](https://semver.org/). Record changes in
  `CHANGELOG.md` under "Unreleased" and move them to a version section when releasing.
- **Privacy:** never commit screenshots, UI dumps or `config.toml`.

## Releasing

1. Update `__version__` in `src/court_booker/__init__.py` (`pyproject.toml` reads it from there).
2. Move "Unreleased" entries in `CHANGELOG.md` to a new version section.
3. Commit with `chore: release vX.Y.Z`, then tag and push:
   ```bash
   git tag -a vX.Y.Z -m "vX.Y.Z"
   git push origin main vX.Y.Z
   ```
4. Create a GitHub release from the tag using the changelog entry.
