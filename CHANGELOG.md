# Changelog

All notable changes to this project are documented here.
The format follows [Keep a Changelog](https://keepachangelog.com/) and the project
uses [Semantic Versioning](https://semver.org/).

## [0.1.0] - 2026-10-02

First release.

### Added
- Label-based UI automation of the tennis-court booking flow: every button is located
  at runtime by its accessibility label, with no hard-coded coordinates.
- Consent checkbox located as the small clickable node beside and level with its caption.
- Lag-tolerant navigation: tap as soon as a button appears, retry if the next screen
  does not show.
- Scroll-into-view for time slots below the fold; a slot is tapped only when fully
  visible and not covered by the sticky bottom button.
- Multiple booking rounds; each round after the first starts from the utilities list.
- Success verified by leaving the confirmation screen.
- Step logger with millisecond timing.
- `config.toml` for all settings and UI labels; command-line overrides.
- `tools/inspect_screen.py` to dump and inspect the UI tree.
- Unit tests with a fake device and GitHub Actions CI.
