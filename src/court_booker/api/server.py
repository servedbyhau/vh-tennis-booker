"""Run the backend: ``court-booker serve``."""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any

from court_booker import credentials, schedule
from court_booker.api.app import create_app
from court_booker.api.context import AppContext
from court_booker.config import Config, ensure_config, load_config
from court_booker.customers import adopt_saved_logins
from court_booker.errors import CourtBookerError
from court_booker.lock import RunLock, check_quiet_time
from court_booker.logging_setup import LOGGER_NAME, add_file_handler, configure_logging
from court_booker.notify import DEFAULT_LANGUAGE
from court_booker.paths import DataFolder, data_folder
from court_booker.tickets import forget_expired

logger = logging.getLogger(LOGGER_NAME)

HOST = "127.0.0.1"
"""Only this PC can reach the backend; it has no login."""
DEFAULT_PORT = 8765
CUSTOMER_NAMES = {"vi": "Khách hàng {}", "en": "Customer {}"}
"""Names the customer given to a login saved before there were customers."""
UI_FOLDER = Path(__file__).resolve().parent.parent / "ui"
"""The built UI, beside the code in the packaged app; absent from the sources."""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="court-booker serve", description="Run the local backend of the desktop app."
    )
    parser.add_argument(
        "--config", help="config file to edit (default: config.toml in the data folder)"
    )
    parser.add_argument(
        "--port", type=int, default=DEFAULT_PORT, help="port on 127.0.0.1 (default: %(default)s)"
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="show debug output")
    return parser


def built_ui(folder: Path) -> Path | None:
    """Return ``folder`` if it holds a built UI: in development Vite serves the UI instead."""
    return folder if (folder / "index.html").is_file() else None


def refresh_daily_task(
    config_path: Path, config: Config, data: DataFolder, packaged: bool | None = None
) -> None:
    """Install the daily task again in the installed app, so the task an older version made
    takes this one's settings; never from the sources (the task would run them), never while
    a run goes on or around the scheduled run, and only while the task is on."""
    if not (getattr(sys, "frozen", False) if packaged is None else packaged):
        return
    try:
        if not schedule.installed():
            return
        check_quiet_time(datetime.now(), config.wake_at, config.start_at, "task refresh")
        if RunLock(data.lock).running_holder() is not None:
            return
        schedule.install(config_path, config.wake_at)
        logger.info("Daily task installed again at %s", config.wake_at)
    except CourtBookerError as exc:
        logger.warning("Daily task not installed again: %s", exc)


def main(argv: list[str]) -> int:
    """Serve the backend on 127.0.0.1 until stopped."""
    import uvicorn  # imported here so the tests can replace uvicorn.run

    args = build_parser().parse_args(argv)
    configure_logging(verbose=args.verbose)
    data = data_folder().ensure()
    # The installed app keeps its config in the data folder; development points at the repo.
    config_path = Path(args.config).resolve() if args.config else ensure_config(data.config)
    config = load_config(config_path)
    if config.log_dir:
        logger.debug("Logging to %s", add_file_handler(config_path.parent / config.log_dir))
    logger.info(
        "Backend on http://%s:%d, config %s, data %s", HOST, args.port, config_path, data.root
    )
    forget_expired(data, date.today())
    # Logins saved before there were customers, which the app then shows as one's account.
    name = CUSTOMER_NAMES.get(config.notification_language, CUSTOMER_NAMES[DEFAULT_LANGUAGE])
    adopt_saved_logins(data.database, credentials.default_store(), name.format)
    refresh_daily_task(config_path, config, data)
    log_config: dict[str, Any] | None = uvicorn.config.LOGGING_CONFIG
    if sys.stdout is None:
        # The packaged app has no console: uvicorn's formatter would fail on it, and only the
        # log file can show the backend's errors.
        log_config = None
        logging.getLogger("uvicorn").handlers[:] = logger.handlers
    uvicorn.run(
        create_app(AppContext(config_path, data), ui_folder=built_ui(UI_FOLDER)),
        host=HOST,
        port=args.port,
        log_level="info" if args.verbose else "warning",
        log_config=log_config,
    )
    return 0
