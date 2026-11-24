"""Exception hierarchy.

``BookingError`` aborts one booking round and later rounds still run, except after a
``QuotaFullError``, which leaves them unrun. The other ``CourtBookerError`` subclasses stop
the whole run.
"""

from __future__ import annotations

from collections.abc import Iterable


class CourtBookerError(Exception):
    """Base class for all errors raised by court_booker."""


class BookingError(CourtBookerError):
    """Base class for errors that abort a single booking round."""


class ElementNotFoundError(BookingError):
    """A required UI element did not appear within the timeout."""


class NavigationError(BookingError):
    """A tap did not lead to the expected screen."""


class SlotUnavailableError(BookingError):
    """The requested time slot is fully booked."""


class BookingNotOpenError(BookingError):
    """The date or slot did not appear before the retry window ended."""


class BookingRejectedError(BookingError):
    """The app answered with a notice instead of the next screen, such as the ticket."""


class QuotaFullError(BookingRejectedError):
    """The app's notice says the apartment's booking quota is used up.

    Every round of a run books the same day, so no later round can book either.
    """


class BookingUnconfirmedError(BookingError):
    """The app showed neither the ticket nor a notice in time after the confirmation."""


class TicketNotCancelledError(BookingError):
    """The app still shows the ticket as booked after its cancel was confirmed."""


class RequestError(CourtBookerError):
    """Invalid arguments or configuration; nothing was sent to the device."""


class DeviceError(CourtBookerError):
    """The emulator or its ADB connection is not usable."""


class EmulatorError(DeviceError):
    """The emulator could not be found, launched or booted."""


class MuMuNotFoundError(EmulatorError):
    """MuMuManager.exe is not where the config or the install says: no repair can start it."""


class AdbNotFoundError(DeviceError):
    """No adb executable was found."""


class NoDeviceError(DeviceError):
    """No device is reachable over ADB."""


class MultipleDevicesError(DeviceError):
    """Several devices are reachable and none was chosen."""

    def __init__(self, serials: Iterable[str]) -> None:
        self.serials = list(serials)
        super().__init__(
            f"Several devices found ({', '.join(self.serials)}); set 'device' in config.toml"
        )


class DeviceConnectionError(DeviceError):
    """The configured device could not be connected."""


class DeviceNotRespondingError(DeviceError):
    """A command to the device did not end in time: the emulator froze."""


class DriverUnavailableError(DeviceError):
    """The driver could not be installed or started, or speaks another protocol."""


class DriverError(DeviceError):
    """The driver refused a command or closed the connection."""


class AppNotReadyError(CourtBookerError):
    """The app did not reach its home or utilities screen, e.g. after a logout."""


class LoggedOutError(AppNotReadyError):
    """The app shows its login, and no login is saved for this MuMu instance."""


class LoginFailedError(AppNotReadyError):
    """The saved login was typed in once and the app did not take it; never tried again."""


class WrongAccountError(AppNotReadyError):
    """The app is not known to be logged in with the account saved for the MuMu instance."""


class AppMissingError(AppNotReadyError):
    """The app is not installed on the emulator: a person must install it."""


class LockHeldError(CourtBookerError):
    """Another run holds the run lock; nothing was sent to the device."""


class ScheduleError(CourtBookerError):
    """``schtasks`` could not create, delete or query the scheduled task."""
