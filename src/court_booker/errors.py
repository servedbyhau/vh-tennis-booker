"""Exception hierarchy for booking rounds."""


class BookingError(Exception):
    """Base class for errors that abort a single booking round."""


class ElementNotFoundError(BookingError):
    """A required UI element did not appear within the timeout."""


class NavigationError(BookingError):
    """A tap did not lead to the expected screen."""


class SlotUnavailableError(BookingError):
    """The requested time slot is fully booked."""
