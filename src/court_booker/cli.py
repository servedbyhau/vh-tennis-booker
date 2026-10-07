"""Command-line entry point."""

from __future__ import annotations

import argparse
import logging

from court_booker import __version__
from court_booker.config import Config, load_config
from court_booker.errors import AppNotReadyError, CourtBookerError, DeviceError, RequestError
from court_booker.logging_setup import LOGGER_NAME, configure_logging
from court_booker.runner import RoundResult, connect_device, run_booking

logger = logging.getLogger(LOGGER_NAME)

EXIT_OK = 0
EXIT_ROUND_FAILED = 1
EXIT_BAD_REQUEST = 2
EXIT_DEVICE = 3
EXIT_APP_NOT_READY = 4
EXIT_INTERRUPTED = 130


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="court-booker",
        description="Book tennis-court slots in the Vinhomes Resident app via UI automation.",
    )
    parser.add_argument(
        "--config", default="config.toml", help="config file (default: %(default)s)"
    )
    parser.add_argument("--dry-run", action="store_true", help="stop before the final confirmation")
    parser.add_argument("--days", type=int, help="days ahead of today to book")
    parser.add_argument("--slots", nargs="+", metavar="SLOT", help='e.g. "18:00 - 19:00"')
    parser.add_argument("--device", help='ADB serial, e.g. 127.0.0.1:16384, or "auto"')
    parser.add_argument("-v", "--verbose", action="store_true", help="show debug output")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return parser


def apply_overrides(config: Config, args: argparse.Namespace) -> Config:
    if args.days is not None:
        config.days_ahead = args.days
    if args.slots:
        config.slots = args.slots
    if args.device:
        config.device = args.device
    return config


def print_summary(results: list[RoundResult]) -> None:
    """Log one line per finished round."""
    if not results:
        return
    logger.info("Summary")
    for result in results:
        status = "OK  " if result.ok else "FAIL"
        logger.info("  %s %s  %s  (%.1fs)", status, result.slot, result.detail, result.seconds)


def exit_code(error: CourtBookerError) -> int:
    """Map a run-level error to the process exit code."""
    if isinstance(error, RequestError):
        return EXIT_BAD_REQUEST
    if isinstance(error, DeviceError):
        return EXIT_DEVICE
    if isinstance(error, AppNotReadyError):
        return EXIT_APP_NOT_READY
    return EXIT_ROUND_FAILED


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    configure_logging(verbose=args.verbose)
    results: list[RoundResult] = []
    try:
        config = apply_overrides(load_config(args.config), args)
        logger.info("court-booker %s", __version__)
        device = connect_device(config)
        run_booking(device, config, dry_run=args.dry_run, results=results)
    except KeyboardInterrupt:
        logger.warning("Interrupted")
        print_summary(results)
        return EXIT_INTERRUPTED
    except CourtBookerError as exc:
        logger.error("%s", exc)
        print_summary(results)
        return exit_code(exc)
    print_summary(results)
    return EXIT_OK if all(result.ok for result in results) else EXIT_ROUND_FAILED
