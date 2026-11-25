"""Get MuMu, ADB, the driver and the app ready before the start time, repairing what fails.

A run rests on four layers, each on the one below (:class:`Layer`): the MuMu instance, its
ADB connection, the driver that reads and taps the screen, and the app on its home screen.
:meth:`Supervisor.prepare` checks them from the bottom up, each pass skipping a layer that
works, and repairs the first one that fails. A layer that fails :data:`ESCALATE_AFTER` times
in a row gets the layer below repaired too, as a person would restart the emulator once
restarting the app no longer helps.

Every failure is taken for a passing one, unknown ones included, except those no repair can
change (:func:`permanent`): MuMu or adb missing, the app not installed, a logout without a
saved login, a refused login, a config that names several devices. Those end the run at once
with what to do. The others are repaired until the deadline, a minute before the warm-up
(:func:`setup_deadline`); one still failing then ends the run as it did before.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Sequence
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Callable

from court_booker.adb import Adb, find_adb, resolve_device
from court_booker.clock import format_time
from court_booker.config import Config
from court_booker.device_setup import find_mumu_manager, prepare_performance, prepare_screen
from court_booker.driver import PACKAGE as DRIVER_PACKAGE
from court_booker.driver import connect_driver
from court_booker.emulator import CALL_ATTEMPTS, MuMu
from court_booker.errors import (
    AdbNotFoundError,
    AppMissingError,
    DeviceConnectionError,
    DeviceError,
    DeviceNotRespondingError,
    ElementNotFoundError,
    EmulatorError,
    LoggedOutError,
    LoginFailedError,
    MultipleDevicesError,
    MuMuNotFoundError,
    RequestError,
    WrongAccountError,
)
from court_booker.events import EventKind, Reporter
from court_booker.flow import Booker, log_screen
from court_booker.watchdog import GuardedDevice, Watchdog

logger = logging.getLogger(__name__)

AUTO_DRIVER = "auto"
INSTRUMENTATION = "instrumentation"
UIAUTOMATOR2 = "uiautomator2"
DRIVERS = (AUTO_DRIVER, INSTRUMENTATION, UIAUTOMATOR2)
"""How the run drives the device: the driver (:mod:`court_booker.driver`), else uiautomator2
when it does not start (``auto``), or only one of them (for tests by hand)."""

BOOT_RETRY_WAIT = 90.0
"""Seconds a restarted MuMu instance may take to boot Android: 19-37 s after a launch on
2026-11-10 to 19, 42-48 s from cold. The first boot of a run waits ``boot_timeout``, as the PC
has just woken."""
SHUTDOWN_WAIT = 20.0
"""Seconds a MuMu instance may take to stop: 4 s (2026-11-19), 18 s at most (2026-10-13)."""
KILL_WAIT = 15.0
"""Seconds MuMuManager may take to see an ended process stopped: 0.8-3 s (2026-11-19)."""
ADB_CONNECT_WAIT = 15.0
"""Seconds a connection to a booted instance may take: under a second on every run."""
DRIVER_STARTS = 2
"""Starts of the driver that fail before ``auto`` drives the device with uiautomator2."""
ESCALATE_AFTER = 3
"""Failures of a layer in a row before the layer below it is repaired too."""
MUMU_RESTARTS = 2
"""Restarts of the MuMu instance a run makes at most; each takes about a minute and a half."""
REPAIRS_MAX = 20
"""Repairs a run makes at most, for a failure that comes back the same however it is repaired;
the deadline ends the others. Twenty app restarts with :data:`APP_BACKOFF` take over ten
minutes, more than a run has before its warm-up."""
RETRY_PAUSE = 1.0
"""Seconds before a pass that repairs MuMu, ADB or the driver."""
APP_BACKOFF = (0.0, 5.0, 10.0, 20.0, 30.0)
"""Seconds before each restart of the app, the last one repeated: a PC just woken may join its
network a minute late, and the app shows nothing known until then."""
READY_MARGIN = timedelta(seconds=60)
"""How long before the warm-up the run must be ready: repairs stop then."""
MIN_BUDGET = timedelta(minutes=2)
"""Least time for repairs, for a run started close to the start time."""
UNTIMED_BUDGET = timedelta(minutes=5)
"""Time for repairs of a run without a start time, such as a dry run."""
LAUNCH_TURN = timedelta(seconds=75)
"""Longest a machine waits for each machine before it in the run to boot before it launches its
own MuMu instance: Android booted in 42-54 s with five or six booting together (2026-11-23)."""
TURN_POLL = 3.0
"""Seconds between two looks at the machines before: one MuMuManager call each."""
WATCH_INTERVAL = timedelta(seconds=60)
"""How often a run waiting on the home screen checks that it is still ready, until the
deadline: two commands a minute, far from the bursts of reads that froze MuMu in tests."""

PERMANENT_ERRORS: tuple[type[BaseException], ...] = (
    RequestError,
    AdbNotFoundError,
    MuMuNotFoundError,
    MultipleDevicesError,
    LoggedOutError,
    LoginFailedError,
    WrongAccountError,
    AppMissingError,
)
"""Failures no repair can change; a person must act."""


class Layer(str, Enum):
    """What the run rests on, from the bottom up; the value names it in the history."""

    MUMU = "mumu"
    ADB = "adb"
    DRIVER = "driver"
    APP = "app"


_BELOW = {Layer.APP: Layer.DRIVER, Layer.DRIVER: Layer.ADB, Layer.ADB: Layer.MUMU}
_NAMES = {
    Layer.MUMU: "MuMu",
    Layer.ADB: "The ADB connection",
    Layer.DRIVER: "The driver",
    Layer.APP: "The app",
}
_ACTIONS = {
    Layer.MUMU: ("restart_mumu", "restarting MuMu"),
    Layer.ADB: ("reconnect_adb", "connecting ADB again"),
    Layer.DRIVER: ("restart_driver", "starting the driver again"),
    Layer.APP: ("restart_app", "restarting the app"),
}
"""The ``action`` of a ``repaired`` event, and its words in the log."""


def pause(seconds: float) -> None:
    """Sleep between two passes; the tests make it return at once."""
    time.sleep(seconds)


def permanent(error: BaseException) -> bool:
    """Tell whether ``error`` is one no repair can change."""
    return isinstance(error, PERMANENT_ERRORS)


def _booted(mumu: MuMu) -> bool:
    """Return whether ``mumu`` has booted; one that MuMuManager cannot tell of counts as not."""
    try:
        return mumu.is_started()
    except EmulatorError:
        return False


def setup_deadline(start: datetime | None, warm_up_seconds: float, now: datetime) -> datetime:
    """Return when repairs stop: :data:`READY_MARGIN` before the warm-up of a timed run."""
    if start is None:
        return now + UNTIMED_BUDGET
    ready_by = start - timedelta(seconds=warm_up_seconds) - READY_MARGIN
    return max(ready_by, now + MIN_BUDGET)


class QuickTap:
    """Pass every call on to ``device``, except taps, sent as a bare touch down and up.

    uiautomator2's ``click`` holds the touch for about 100 ms (Android ``UiDevice.click``):
    151-165 ms a tap on MuMu, against 83-91 ms for a touch down and up, which the app took
    every time (2026-10-16).
    """

    driver = UIAUTOMATOR2

    def __init__(self, device: Any) -> None:
        self._device = device

    def click(self, x: int, y: int, label: str = "") -> None:
        """Tap ``(x, y)``; both events in one call, so the watchdog limits the whole tap.

        ``label`` is for the driver, which clicks by label; a tap here goes by position only.
        """
        self._device.touch.down(x, y).up(x, y)

    def set_text(self, x: int, y: int, text: str) -> None:
        """Type ``text`` into the field at ``(x, y)``: tap it, then set the focused field."""
        self._device.touch.down(x, y).up(x, y)
        time.sleep(0.3)  # the field takes the focus a few frames after the tap
        field = self._device(focused=True)
        if not field.exists:
            raise ElementNotFoundError("No field took the focus to type into")
        field.set_text(text)

    def close(self) -> None:
        """Leave the uiautomator2 server running, as runs always did."""

    def __getattr__(self, name: str) -> Any:
        return getattr(self._device, name)


def find_manager(configured: str) -> Path:
    """Return MuMuManager.exe: the configured one, else one found where MuMu is installed.

    The config is not rewritten (that would drop its comments); every run looks again.
    """
    found = find_mumu_manager(configured)
    if found is None:
        return Path(configured)  # starting MuMu fails with the configured path in the error
    if found != Path(configured):
        logger.info("MuMu found at %s; the config has %s", found, configured)
    return found


def connect_uiautomator2(serial: str, watchdog: Watchdog) -> Any:
    """Return a uiautomator2 device on ``serial``."""
    import uiautomator2  # deferred so tests do not require the dependency

    try:
        device = watchdog.run("connect", lambda: uiautomator2.connect(serial))
    except DeviceNotRespondingError:
        raise
    except Exception as exc:  # uiautomator2 raises several unrelated types
        raise DeviceConnectionError(f"Could not connect to {serial}: {exc}") from exc
    return device


class DeviceHandle:
    """The device the booking flow drives; a repair puts a newly connected one in its place.

    Every attribute but its own is read from the device of the moment, so the flow keeps
    one handle for the whole run. Without a device, a call raises
    :class:`DeviceConnectionError`.
    """

    def __init__(self, device: Any = None) -> None:
        self._device = device
        self.ever_hung = False
        """Whether a device given up on had a call that never ended: its thread still waits."""

    @property
    def connected(self) -> bool:
        return self._device is not None

    @property
    def hung(self) -> bool:
        """Whether a call on the device of the moment did not end in time."""
        return bool(getattr(self._device, "hung", False))

    def replace(self, device: Any) -> None:
        """Drive ``device`` from now on."""
        self.drop()
        self._device = device

    def drop(self, stop: bool = True) -> None:
        """Give the device up; ``stop`` ends its driver first, unless a call on it hung."""
        device, self._device = self._device, None
        if device is None:
            return
        if getattr(device, "hung", False):
            self.ever_hung = True
            return
        if not stop:
            return
        try:
            device.close()
        except Exception:  # the device is given up already
            logger.debug("Could not stop the device given up", exc_info=True)

    def close(self) -> None:
        """Stop the driver of the device of the moment, if any answers; may raise."""
        if self._device is not None and not self.hung:
            self._device.close()

    def __getattr__(self, name: str) -> Any:
        if name.startswith("_"):
            raise AttributeError(name)
        device = self.__dict__.get("_device")
        if device is None:
            raise DeviceConnectionError("No device is connected")
        return getattr(device, name)


class Supervisor:
    """Bring MuMu, ADB, the driver and the app up, and keep repairing them until a deadline.

    With ``device`` given, the run drives it as it is (tests, a device the run does not
    manage): only the app is repaired, and a device failure ends the run.
    """

    def __init__(
        self,
        config: Config,
        driver: str = AUTO_DRIVER,
        report: Reporter | None = None,
        *,
        device: Any = None,
        now: Callable[[], datetime] = datetime.now,
        sleep: Callable[[float], None] | None = None,
        launch_after: Sequence[int] = (),
    ) -> None:
        self.config = config
        self.launch_after = tuple(launch_after)
        """The MuMu instances of the machines before this one in the run: each is launched once
        those have booted (:meth:`_wait_for_turn`)."""
        self._deadline: datetime | None = None
        self.driver_mode = driver
        self.report = Reporter() if report is None else report
        self.now = now
        self.sleep = pause if sleep is None else sleep
        self.device = DeviceHandle(device)
        self.managed = device is None
        """Whether the supervisor starts MuMu, ADB and the driver itself."""
        self.repairs = 0
        """Repairs made so far, for the notification."""
        self.mumu: MuMu | None = None
        self.adb: Adb | None = None
        self.serial: str | None = None
        self._failures = dict.fromkeys(Layer, 0)
        self._pending: set[Layer] = set()
        """Layers the next pass restarts, not only checks."""
        self._layer = Layer.APP
        self._booted = False
        self._frozen = False
        """Whether Android gave no answer at all: MuMu is restarted by ending its process."""
        self._app_ready = False
        self._driver_failures = 0
        self._mumu_restarts = 0
        self._app_restarts = 0

    # Public API -------------------------------------------------------------

    def watch(self, booker: Booker, deadline: datetime, wait: Callable[[datetime], None]) -> None:
        """Check every :data:`WATCH_INTERVAL` until ``deadline`` that the run is still ready.

        ``wait`` waits until a time, by the run's clock. A check reads the app in front and
        its screen (:meth:`Booker.check_home`); one that fails is repaired as in
        :meth:`prepare`, from the layer it points to. The checks are counted from the start,
        so a clock that stands still in tests still ends them.
        """
        tick = self.now() + WATCH_INTERVAL
        while tick < deadline:
            wait(tick)
            self.run_step(booker, booker.check_home, deadline)
            logger.debug("Still ready at %s", format_time(self.now()))
            tick += WATCH_INTERVAL

    def run_step(self, booker: Booker, step: Callable[[], None], deadline: datetime) -> None:
        """Run ``step`` on the app; one that fails is repaired as in :meth:`prepare` (the app
        made ready on its home screen again) and run again, until ``deadline``.

        For the check while the run waits, and the utilities list opened at the warm-up.
        """
        while True:
            self._layer = Layer.APP
            try:
                step()
                return
            except Exception as exc:  # repaired below unless permanent
                layer = self._blame(exc)
                if layer is None or permanent(exc) or self.now() >= deadline:
                    raise
                logger.warning("The run was no longer ready: %s", exc)
                if self._plan(layer, exc, booker) is None:
                    raise
                self.prepare(booker, deadline)

    def prepare(self, booker: Booker, deadline: datetime) -> None:
        """Bring every layer up and the app to its home screen, repairing until ``deadline``.

        Raises the failure no repair can change at once, and any other one still there at
        ``deadline``.
        """
        self._deadline = deadline
        while True:
            try:
                self._bring_up(booker)
                return
            except Exception as exc:  # each failure is repaired unless permanent
                layer = self._blame(exc)
                if layer is None or permanent(exc):
                    raise
                if self.now() >= deadline:
                    logger.error(
                        "Not ready by %s after %d repair(s)", format_time(deadline), self.repairs
                    )
                    raise
                pause = self._plan(layer, exc, booker)
                if pause is None:
                    raise
                self._pause(pause, deadline)

    # The layers, bottom up -------------------------------------------------

    def _bring_up(self, booker: Booker) -> None:
        """Check and repair each layer from the bottom up; a layer that works ends its run of
        failures, so only failures in a row escalate."""
        steps: list[tuple[Layer, Callable[[], None]]] = []
        if self.managed:
            steps += [
                (Layer.MUMU, self._ensure_mumu),
                (Layer.ADB, self._ensure_adb),
                (Layer.DRIVER, self._ensure_driver),
            ]
        steps.append((Layer.APP, lambda: self._ensure_app(booker)))
        for layer, ensure in steps:
            self._layer = layer
            ensure()
            self._failures[layer] = 0

    def _ensure_mumu(self) -> None:
        """Start the instance unless booted in this run; a pending repair restarts it.

        Once booted, MuMuManager is not asked again: the ADB layer above tells whether Android
        answers, and a frozen instance makes MuMuManager hang as well (field notes).
        """
        if not self.config.mumu_manager:
            return
        if self.mumu is None:
            manager = find_manager(self.config.mumu_manager)
            self.mumu = MuMu(manager, self.config.mumu_index, attempts=CALL_ATTEMPTS)
            prepare_screen(self.mumu)
            prepare_performance(self.mumu)
        if Layer.MUMU in self._pending:
            self._restart_mumu()
            self._pending.discard(Layer.MUMU)
            return
        if self._booted:
            return
        self._wait_for_turn()
        self.mumu.ensure_started(self.config.boot_timeout)
        self._booted = True

    def _wait_for_turn(self) -> None:
        """Wait until the machines before this one in the run have booted, so one boots at a time.

        Five or six instances booting together left 0.5 GB of the PC's 16 GB free (2026-11-23),
        where a lack of memory froze all three on 2026-11-21. Each machine before is given
        :data:`LAUNCH_TURN`, and the wait ends halfway to the deadline whatever happens, leaving
        this machine time to boot and be repaired; one that is already running costs nothing.
        """
        if not self.launch_after or self.mumu is None:
            return
        started = self.now()
        limit = started + LAUNCH_TURN * len(self.launch_after)
        if self._deadline is not None:
            limit = min(limit, started + (self._deadline - started) / 2)
        before = [self.mumu.sibling(index) for index in self.launch_after]
        while True:
            waiting = [mumu.index for mumu in before if not _booted(mumu)]
            if not waiting:
                if self.now() > started:
                    logger.info(
                        "Machines before booted; launching after %.0f s",
                        (self.now() - started).total_seconds(),
                    )
                return
            if self.now() >= limit:
                logger.warning(
                    "MuMu %s not booted yet; launching instance %d all the same",
                    ", ".join(map(str, waiting)),
                    self.mumu.index,
                )
                return
            self.sleep(TURN_POLL)

    def _restart_mumu(self) -> None:
        """Stop the instance, check that it stopped, and start it again.

        A frozen one has its process ended at once; any other is shut down through
        MuMuManager first, and its process ended only if it is still running after
        :data:`SHUTDOWN_WAIT`.
        """
        mumu = self.mumu
        assert mumu is not None  # only a configured MuMu gets a restart pending
        frozen, self._frozen = self._frozen, False
        self._mumu_restarts += 1
        self.device.drop(stop=False)  # the driver goes with Android
        self._driver_failures = 0  # a fresh Android may start the driver again
        logger.warning(
            "Restarting MuMu instance %d (%d of %d)%s",
            mumu.index,
            self._mumu_restarts,
            MUMU_RESTARTS,
            ", which froze" if frozen else "",
        )
        stopped = False
        if not frozen:
            try:
                mumu.shutdown()
            except EmulatorError as exc:
                logger.warning("MuMu did not take the shutdown: %s", exc)
            stopped = mumu.wait_stopped(SHUTDOWN_WAIT)
        if not stopped:
            if not mumu.kill():
                raise EmulatorError(f"MuMu instance {mumu.index} runs in no process to end")
            if not mumu.wait_stopped(KILL_WAIT):
                raise EmulatorError(f"MuMu instance {mumu.index} did not stop")
        if self.adb is not None and self.serial is not None and ":" in self.serial:
            self.adb.disconnect(self.serial)  # adb keeps a stopped instance offline
        mumu.ensure_started(BOOT_RETRY_WAIT)
        self._booted = True

    def _ensure_adb(self) -> None:
        """Connect the instance's serial unless online, then check that Android answers."""
        if self.adb is None:
            folders = [] if self.mumu is None else [self.mumu.manager.parent]
            self.adb = Adb(find_adb(self.config.adb_path, folders))
        adb = self.adb
        if self.serial is None:
            preferred = None
            if self.mumu is not None:
                preferred = self.mumu.adb_serial()
                if preferred is None:
                    raise DeviceConnectionError(
                        f"MuMu instance {self.mumu.index} did not report its ADB address"
                    )
            self.serial = resolve_device(adb, self.config.device, preferred, ADB_CONNECT_WAIT)
            logger.info("Connecting to %s", self.serial)
        serial = self.serial
        if Layer.ADB in self._pending and ":" in serial:
            # That serial alone: the adb server is shared with the other instances' processes,
            # whose connections and driver forwards a restarted server would drop.
            adb.disconnect(serial)
        if serial not in adb.devices():
            adb.connect_until(serial, ADB_CONNECT_WAIT)
        adb.ping(serial)
        self._pending.discard(Layer.ADB)

    def _ensure_driver(self) -> None:
        """Connect the driver unless one answers; a pending repair starts it again."""
        if Layer.DRIVER in self._pending or not self.device.connected or self.device.hung:
            self._connect_driver()
            self._pending.discard(Layer.DRIVER)
        self.device.app_current()  # one round trip: the driver answers

    def _connect_driver(self) -> None:
        """Connect the driver, or uiautomator2 once the driver failed :data:`DRIVER_STARTS`."""
        adb, serial = self.adb, self.serial
        assert adb is not None and serial is not None  # the ADB layer is up
        self.device.drop()
        watchdog = Watchdog()
        mode = self.driver_mode
        if mode == INSTRUMENTATION or (
            mode == AUTO_DRIVER and self._driver_failures < DRIVER_STARTS
        ):
            try:
                device = watchdog.run("connect", lambda: connect_driver(adb, serial))
            except DeviceNotRespondingError:
                if watchdog.hung is not None:
                    self.device.ever_hung = True  # its thread still waits on the connection
                raise
            except Exception as exc:  # any driver failure; the layer is repaired
                self._driver_failures += 1
                # A driver that started and failed after holds UiAutomation, which uiautomator2
                # and the next start need.
                adb.shell(serial, "am", "force-stop", DRIVER_PACKAGE)
                if mode == INSTRUMENTATION or self._driver_failures < DRIVER_STARTS:
                    raise
                logger.warning("Driver unavailable (%s); using uiautomator2", exc)
            else:
                self._use(GuardedDevice(device, watchdog))
                return
        self._use(GuardedDevice(QuickTap(connect_uiautomator2(serial, watchdog)), watchdog))

    def _use(self, device: Any) -> None:
        self.device.replace(device)
        logger.info("Driving the device with %s", device.driver)
        self.report(EventKind.DEVICE_READY, driver=device.driver)

    def _ensure_app(self, booker: Booker) -> None:
        """Make the app ready on its home screen unless it is; a pending repair restarts it."""
        if self._app_ready and Layer.APP not in self._pending:
            return
        booker.prepare(restart=Layer.APP in self._pending)
        self._pending.discard(Layer.APP)
        self._app_ready = True

    # Repairs ---------------------------------------------------------------

    def _blame(self, error: BaseException) -> Layer | None:
        """Return the layer to repair for ``error``, or ``None`` if none can be."""
        layer = self._layer
        if layer is Layer.APP and isinstance(error, DeviceError):
            layer = Layer.DRIVER  # the app failed because the device under it did
        if not self.managed and layer is not Layer.APP:
            return None
        return layer

    def _plan(self, layer: Layer, error: BaseException, booker: Booker) -> float | None:
        """Mark what the next pass repairs; return the pause before it, ``None`` to give up."""
        if layer is Layer.APP:
            log_screen(booker.last_screen, "Last screen read")
        self._fail(layer)
        if layer is Layer.ADB and isinstance(error, DeviceNotRespondingError):
            # Android gave no answer at all: MuMu froze, and nothing above it can help.
            self._pending.add(Layer.MUMU)
            self._frozen = True
        if Layer.MUMU in self._pending and self._mumu_restarts >= MUMU_RESTARTS:
            logger.error("MuMu was restarted %d times already; giving up", self._mumu_restarts)
            return None
        if self.repairs >= REPAIRS_MAX:
            logger.error("%d repairs made already; giving up", self.repairs)
            return None
        self._app_ready = False
        if Layer.MUMU in self._pending:
            target = Layer.MUMU
        elif Layer.ADB in self._pending:
            target = Layer.ADB
        elif Layer.DRIVER in self._pending:
            target = Layer.DRIVER
        else:
            target = Layer.APP
        self._pending.add(Layer.APP)  # whatever is repaired, the app is made ready again
        self.repairs += 1
        action, words = _ACTIONS[target]
        logger.warning("%s failed (%s); %s (repair %d)", _NAMES[layer], error, words, self.repairs)
        self.report(
            EventKind.REPAIRED,
            layer=layer.value,
            action=action,
            error=str(error),
            repair=self.repairs,
        )
        if layer is not Layer.APP:
            return RETRY_PAUSE
        # The app's pauses grow even when its failures got the driver repaired: what keeps the
        # app from its home screen is most often the network.
        pause = APP_BACKOFF[min(self._app_restarts, len(APP_BACKOFF) - 1)]
        self._app_restarts += 1
        return pause

    def _fail(self, layer: Layer) -> None:
        """Count a failure of ``layer``; after :data:`ESCALATE_AFTER` repair the one below."""
        self._failures[layer] += 1
        self._pending.add(layer)
        below = _BELOW.get(layer)
        if below is None or not self.managed or self._failures[layer] < ESCALATE_AFTER:
            return
        self._failures[layer] = 0
        logger.warning(
            "%s failed %d times in a row; repairing the layer below it (%s) too",
            _NAMES[layer],
            ESCALATE_AFTER,
            below.value,
        )
        self._fail(below)

    def _pause(self, seconds: float, deadline: datetime) -> None:
        left = (deadline - self.now()).total_seconds()
        seconds = max(0.0, min(seconds, left))
        if seconds:
            logger.info("Trying again in %g s", seconds)
            self.sleep(seconds)
