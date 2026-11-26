"""Keep the PC on while it is plugged in, so the morning run never finds it asleep.

Switched on, the active power plan's plugged-in values become: no sleep, no hibernation,
nothing on closing the lid, the screen off after 5 minutes, the Wi-Fi card and USB at full
power (a phone's hotspot or USB tethering stays up all night); wake timers are allowed too.
The values on battery are left alone. Switched off, each value goes back to what it was before
(saved in the data folder), else to Windows' own default.

On a PC with Modern Standby, Windows goes to standby when the screen turns off, whatever the
sleep timeout; there the screen stays on as well (close the lid to darken it).
"""

from __future__ import annotations

import json
import logging
import re
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from court_booker import device_setup
from court_booker.emulator import Run, run_command
from court_booker.errors import CourtBookerError

logger = logging.getLogger(__name__)

SCHEME = "SCHEME_CURRENT"
SCREEN_SECONDS = 300
"""The screen turns off after 5 minutes: the PC keeps running."""


class PowerPlanError(CourtBookerError):
    """``powercfg`` could not read or change the power plan."""


@dataclass(frozen=True)
class Setting:
    """A plugged-in value of the power plan, by its ``powercfg`` subgroup and setting."""

    name: str
    subgroup: str
    setting: str
    on: int
    """The value while the PC is kept on."""
    default: int
    """Windows' value in the Balanced plan, for a value saved nowhere."""


SLEEP = Setting("sleep", "SUB_SLEEP", "STANDBYIDLE", 0, 1800)
HIBERNATE = Setting("hibernate", "SUB_SLEEP", "HIBERNATEIDLE", 0, 10800)
LID = Setting("lid", "SUB_BUTTONS", "LIDACTION", 0, 1)
"""0 does nothing, 1 sleeps."""
SCREEN = Setting("screen", "SUB_VIDEO", "VIDEOIDLE", SCREEN_SECONDS, 600)
WIFI = Setting(
    "wifi", "19cbb8fa-5279-450e-9fac-8a3d5fedd0c1", "12bbebe6-58d6-4636-95bb-3217ef867c1a", 0, 0
)
"""Wireless adapter power saving: 0 is maximum performance."""
USB = Setting(
    "usb", "2a737441-1930-4402-8d77-b2bebba308a3", "48e6b7a6-50f5-4782-a5d4-53bb8f07e226", 0, 1
)
"""USB selective suspend: 0 is off."""
SETTINGS = (SLEEP, HIBERNATE, LID, SCREEN, WIFI, USB)


@dataclass(frozen=True)
class KeepOn:
    """Whether the PC is kept on, and whether it has Modern Standby."""

    on: bool
    modern_standby: bool


def has_modern_standby() -> bool:
    """Tell whether Windows uses Modern Standby (S0 low power idle); False outside Windows."""
    if sys.platform != "win32":
        return False
    import ctypes

    # SYSTEM_POWER_CAPABILITIES: 76 bytes; the BOOLEAN AoAc is at offset 20.
    capabilities = (ctypes.c_ubyte * 128)()
    try:
        if not ctypes.windll.powrprof.GetPwrCapabilities(ctypes.byref(capabilities)):
            return False
    except OSError:
        return False
    return bool(capabilities[20])


def wanted(setting: Setting, modern_standby: bool) -> int:
    """Return the value ``setting`` takes while the PC is kept on."""
    if setting is SCREEN and modern_standby:
        return 0  # the screen turning off would put the PC in standby
    return setting.on


def read(run: Run = run_command) -> dict[str, int]:
    """Read the plugged-in values of the active plan; a setting this PC lacks is left out.

    ``/qh`` also shows the hidden ones (the lid action of a desktop). Raises
    :class:`PowerPlanError` when ``powercfg`` cannot run.
    """
    values: dict[str, int] = {}
    for setting in SETTINGS:
        argv = ["powercfg", "/qh", SCHEME, setting.subgroup, setting.setting]
        try:
            result = run(argv)
        except (OSError, subprocess.SubprocessError) as exc:
            raise PowerPlanError(f"powercfg could not run: {exc}") from exc
        found = re.findall(r"0x([0-9a-fA-F]{8})", result.stdout) if result.returncode == 0 else []
        if len(found) >= 2:
            values[setting.name] = int(found[-2], 16)  # plugged in, then on battery
    return values


def state(
    run: Run = run_command, modern_standby: Callable[[], bool] = has_modern_standby
) -> KeepOn:
    """Tell whether every plugged-in value is the one that keeps the PC on."""
    return _state(run, modern_standby())


def _state(run: Run, standby: bool) -> KeepOn:
    values = read(run)
    on = bool(values) and all(
        values[setting.name] == wanted(setting, standby)
        for setting in SETTINGS
        if setting.name in values
    )
    return KeepOn(on=on, modern_standby=standby)


def _write(values: dict[str, int], run: Run) -> None:
    by_name = {setting.name: setting for setting in SETTINGS}
    commands = [
        ["powercfg", "/setacvalueindex", SCHEME, setting.subgroup, setting.setting, str(value)]
        for setting, value in ((by_name[name], value) for name, value in values.items())
    ]
    for argv in [*commands, ["powercfg", "/setactive", SCHEME]]:
        try:
            result = run(argv)
        except (OSError, subprocess.SubprocessError) as exc:
            raise PowerPlanError(f"powercfg could not run: {exc}") from exc
        if result.returncode != 0:
            detail = (result.stderr or result.stdout).strip()
            raise PowerPlanError(f"powercfg {' '.join(argv[1:])} failed: {detail}")


def switch_on(
    saved: Path,
    run: Run = run_command,
    modern_standby: Callable[[], bool] = has_modern_standby,
) -> KeepOn:
    """Keep the PC on while plugged in, and allow wake timers.

    The values found are saved in ``saved`` first, unless it holds some already (those are the
    PC's own, from before the switch was first on).
    """
    standby = modern_standby()
    values = read(run)
    if not saved.exists():
        saved.parent.mkdir(parents=True, exist_ok=True)
        saved.write_text(json.dumps(values, indent=2) + "\n", encoding="utf-8")
    _write({name: wanted(_named(name), standby) for name in values}, run)
    device_setup.ensure_wake_timers(run)
    logger.info("Kept on while plugged in (was %s)", values)
    return _state(run, standby)


def switch_off(
    saved: Path,
    run: Run = run_command,
    modern_standby: Callable[[], bool] = has_modern_standby,
) -> KeepOn:
    """Give back each plugged-in value saved by :func:`switch_on`, else Windows' default.

    Wake timers stay allowed: the daily task needs them.
    """
    try:
        before = json.loads(saved.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        before = {}
    values = read(run)
    _write({name: _before(before, name) for name in values}, run)
    saved.unlink(missing_ok=True)
    logger.info("No longer kept on (back to %s)", {name: _before(before, name) for name in values})
    return _state(run, modern_standby())


def _named(name: str) -> Setting:
    return next(setting for setting in SETTINGS if setting.name == name)


def _before(before: object, name: str) -> int:
    value = before.get(name) if isinstance(before, dict) else None
    return value if isinstance(value, int) else _named(name).default
