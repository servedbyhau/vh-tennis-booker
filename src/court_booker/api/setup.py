"""Device setup route: what the Setup page shows; runs and the schedule fix what they can."""

# No `from __future__ import annotations`: FastAPI and Pydantic read the annotations at run
# time.
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Request
from pydantic import BaseModel

from court_booker import device_setup
from court_booker.adb import Adb, find_adb
from court_booker.api.context import Context
from court_booker.api.tasks import check_free
from court_booker.device_setup import Status
from court_booker.emulator import MuMu, instance_indexes
from court_booker.errors import AdbNotFoundError, EmulatorError, LockHeldError, RequestError
from court_booker.lock import check_quiet_time

router = APIRouter(prefix="/api", tags=["setup"])


class MachineSetup(BaseModel):
    """The setup items of one MuMu instance on the PC; each status is a message key."""

    mumu_index: int
    screen: Status
    """540x1600 at 220 DPI; ``fixable``: each run sets it before starting the instance."""
    performance: Status
    """2 cores and 2 GB; ``fixable`` as for the screen."""
    app: Status
    """The Vinhomes app: read while the instance runs, else as last seen (``unknown``: never)."""


class SetupReport(BaseModel):
    """What the PC has of what the booking needs."""

    mumu: Status
    """MuMu Player: ``user`` while it is not installed."""
    wake_timers: Status
    """Whether Windows lets the daily task wake the PC (``fixable``: keeping it on allows them)."""
    machines: list[MachineSetup]
    """Every MuMu instance on the PC, lowest index first."""


@router.get("/setup", response_model=SetupReport)
def check_setup(request: Request, context: Context) -> SetupReport:
    """Check the PC and every MuMu instance on it; nothing is changed.

    The checks ask MuMu, so they are refused (409 ``lock_held``) around the scheduled run and
    while a run or a task uses MuMu.
    """
    config = context.config()
    try:
        check_quiet_time(datetime.now(), config.wake_at, config.start_at, "setup check")
    except RequestError as exc:
        raise LockHeldError(str(exc)) from exc
    manager = device_setup.find_mumu_manager(config.mumu_manager)
    indexes: list[int] = []
    if manager is not None:
        try:
            indexes = instance_indexes(manager)
        except EmulatorError:  # MuMu answers nothing: no machine to tell of
            indexes = []
    for index in indexes or [config.mumu_index]:
        check_free(request, context, index)
    machines = []
    if manager is not None and indexes:
        try:
            adb: Optional[Adb] = Adb(find_adb(config.adb_path, [manager.parent]))
        except AdbNotFoundError:
            adb = None
        for index in indexes:
            checks = device_setup.check_machine(
                MuMu(manager, index), adb, config.package, context.data.apps_seen
            )
            machines.append(
                MachineSetup(
                    mumu_index=checks.index,
                    screen=checks.screen,
                    performance=checks.performance,
                    app=checks.app,
                )
            )
    return SetupReport(
        mumu=device_setup.check_mumu(manager, config.mumu_manager).status,
        wake_timers=device_setup.check_wake_timers().status,
        machines=machines,
    )
