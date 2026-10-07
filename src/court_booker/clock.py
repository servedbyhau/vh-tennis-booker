"""Exact start time: parse it, measure the clock error and wait for it."""

from __future__ import annotations

import logging
import socket
import struct
import time
from datetime import datetime, timedelta
from typing import Callable

from court_booker.errors import RequestError

logger = logging.getLogger(__name__)

LATE_START_GRACE = timedelta(minutes=10)
"""A start time missed by less than this (e.g. the PC woke late) still runs at once."""

_TIME_FORMATS = ("%H:%M:%S", "%H:%M")
_NTP_PORT = 123
_NTP_TIMEOUT = 2.0
_NTP_EPOCH_OFFSET = 2_208_988_800  # seconds from 1900-01-01 to 1970-01-01
_NTP_PACKET_SIZE = 48
_COARSE_STEP = 30.0
_FINE_WINDOW = 1.0
_FINE_STEP = 0.001


def resolve_start(text: str, now: datetime, grace: timedelta = LATE_START_GRACE) -> datetime:
    """Return today's ``HH:MM[:SS]`` as a datetime.

    A time passed by less than ``grace`` is returned as is (the wait then ends at
    once); a later one raises ``RequestError``.
    """
    for fmt in _TIME_FORMATS:
        try:
            parsed = datetime.strptime(text, fmt).time()
            break
        except ValueError:
            continue
    else:
        raise RequestError(f"Invalid start time {text!r}; use HH:MM or HH:MM:SS")

    start = datetime.combine(now.date(), parsed)
    if start < now:
        late = now - start
        if late > grace:
            raise RequestError(f"Start time {start:%H:%M:%S} has already passed today")
        logger.warning("Started %.0f s after %s; booking now", late.total_seconds(), text)
    return start


def ntp_offset(server: str, timeout: float = _NTP_TIMEOUT) -> float | None:
    """Return seconds to add to the local clock to match ``server``, or ``None``."""
    request = b"\x1b" + bytes(_NTP_PACKET_SIZE - 1)  # version 3, client mode
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.settimeout(timeout)
            sent = time.time()
            sock.sendto(request, (server, _NTP_PORT))
            reply, _ = sock.recvfrom(_NTP_PACKET_SIZE)
            received = time.time()
    except OSError as exc:
        logger.warning("Clock check against %s failed (%s); using the local clock", server, exc)
        return None
    offset = offset_from_reply(reply, sent, received)
    if offset is None:
        logger.warning("Invalid reply from %s; using the local clock", server)
    return offset


def offset_from_reply(reply: bytes, sent: float, received: float) -> float | None:
    """Return the clock offset from an NTP reply and the local send/receive times."""
    if len(reply) < _NTP_PACKET_SIZE:
        return None
    server_received = _ntp_timestamp(reply, 32)
    server_sent = _ntp_timestamp(reply, 40)
    return ((server_received - sent) + (server_sent - received)) / 2


def wait_until(
    target: datetime,
    offset: float = 0.0,
    now: Callable[[], datetime] = datetime.now,
    sleep: Callable[[float], None] = time.sleep,
) -> None:
    """Block until the local clock corrected by ``offset`` reaches ``target``.

    Sleeps in long steps first, then in millisecond steps for the last second, so
    the start is late by about a millisecond at most.
    """
    remaining = _remaining(target, offset, now)
    if remaining > 0:
        logger.info("Waiting %.1f s until %s", remaining, f"{target:%H:%M:%S}")
    while remaining > 0:
        if remaining > _FINE_WINDOW:
            sleep(min(remaining - _FINE_WINDOW, _COARSE_STEP))
        else:
            sleep(min(remaining, _FINE_STEP))
        remaining = _remaining(target, offset, now)


def _remaining(target: datetime, offset: float, now: Callable[[], datetime]) -> float:
    return (target - now()).total_seconds() - offset


def _ntp_timestamp(packet: bytes, position: int) -> float:
    seconds, fraction = struct.unpack("!II", packet[position : position + 8])
    return seconds - _NTP_EPOCH_OFFSET + fraction / 2**32
