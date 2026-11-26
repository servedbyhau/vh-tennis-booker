"""Keep-on route: whether the PC stays on while plugged in, read from Windows and switched."""

# No `from __future__ import annotations`: FastAPI and Pydantic read the annotations at run
# time.
from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict

from court_booker import keep_on
from court_booker.api.activity import record
from court_booker.api.context import Context
from court_booker.events import EventKind

router = APIRouter(prefix="/api", tags=["setup"])


class KeepOnState(BaseModel):
    """Whether the PC is kept on while plugged in, and whether it has Modern Standby (its
    screen then stays on too)."""

    on: bool
    modern_standby: bool


class KeepOnSwitch(BaseModel):
    """Keep the PC on while plugged in, or give back the values it had."""

    model_config = ConfigDict(extra="forbid")

    on: bool


def answer(found: keep_on.KeepOn) -> KeepOnState:
    return KeepOnState(on=found.on, modern_standby=found.modern_standby)


@router.get("/keep-on", response_model=KeepOnState)
def read_keep_on() -> KeepOnState:
    """Read the power plan; ``on`` only while every plugged-in value keeps the PC on, so a
    value changed by hand shows it off. 503 ``power`` when ``powercfg`` cannot run."""
    return answer(keep_on.state())


@router.put("/keep-on", response_model=KeepOnState)
def switch_keep_on(context: Context, switch: KeepOnSwitch) -> KeepOnState:
    """Keep the PC on while plugged in (no sleep, no hibernation, nothing on closing the lid,
    the screen off after 5 minutes, Wi-Fi and USB at full power, wake timers allowed), or give
    back the values it had before; the values on battery stay. Records ``settings_saved``.
    503 ``power`` when ``powercfg`` fails."""
    saved = context.data.power_plan
    found = keep_on.switch_on(saved) if switch.on else keep_on.switch_off(saved)
    record(context, EventKind.SETTINGS_SAVED, changed=["keep_on"])
    return answer(found)
