"""Command-line entry point."""

from __future__ import annotations

import argparse
import logging
import time
from dataclasses import dataclass
from datetime import date, timedelta

from court_booker import __version__
from court_booker.config import Config, load_config
from court_booker.errors import BookingError
from court_booker.flow import Booker
from court_booker.logging_setup import LOGGER_NAME, configure_logging

logger = logging.getLogger(LOGGER_NAME)


@dataclass
class RoundResult:
    slot: str
    ok: bool
    detail: str
    seconds: float


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
    parser.add_argument("--device", help="ADB serial, e.g. 127.0.0.1:7555")
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


def run(config: Config, dry_run: bool) -> list[RoundResult]:
    import uiautomator2  # deferred so tests do not require the dependency

    logger.info("court-booker %s, connecting to %s", __version__, config.device)
    device = uiautomator2.connect(config.device)
    booker = Booker(device, config)

    if device.app_current().get("package") != config.package:
        logger.info("Launching %s", config.package)
        device.app_start(config.package)
        device(**booker.home).wait(timeout=config.timeout * 2)

    target = date.today() + timedelta(days=config.days_ahead)
    logger.info(
        "Target date %s, slots: %s%s",
        target.isoformat(),
        ", ".join(config.slots),
        " (dry run)" if dry_run else "",
    )

    results = []
    for index, slot in enumerate(config.slots, start=1):
        logger.info("Round %d/%d: %s", index, len(config.slots), slot)
        started = time.perf_counter()
        try:
            booker.book(slot, target, dry_run=dry_run)
        except BookingError as exc:
            logger.error("%s", exc)
            results.append(RoundResult(slot, False, str(exc), time.perf_counter() - started))
        except Exception as exc:  # keep later rounds running on device glitches
            logger.exception("Unexpected error")
            results.append(RoundResult(slot, False, repr(exc), time.perf_counter() - started))
        else:
            detail = "dry run passed" if dry_run else "booked"
            results.append(RoundResult(slot, True, detail, time.perf_counter() - started))
    return results


def print_summary(results: list[RoundResult]) -> None:
    print("\nSummary")
    for result in results:
        status = "OK  " if result.ok else "FAIL"
        print(f"  {status} {result.slot}  {result.detail}  ({result.seconds:.1f}s)")


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    configure_logging(verbose=args.verbose)
    config = apply_overrides(load_config(args.config), args)
    try:
        results = run(config, dry_run=args.dry_run)
    except KeyboardInterrupt:
        return 130
    print_summary(results)
    return 0 if all(result.ok for result in results) else 1
