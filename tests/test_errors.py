from court_booker.config import ConfigError
from court_booker.errors import (
    BookingError,
    CourtBookerError,
    DeviceError,
    EmulatorError,
    MultipleDevicesError,
    RequestError,
    SlotUnavailableError,
)


def test_all_errors_share_one_base():
    for error in (BookingError, RequestError, DeviceError, ConfigError):
        assert issubclass(error, CourtBookerError)


def test_round_and_run_errors_are_separate():
    assert issubclass(SlotUnavailableError, BookingError)
    assert not issubclass(EmulatorError, BookingError)
    assert issubclass(ConfigError, RequestError)


def test_multiple_devices_lists_serials():
    error = MultipleDevicesError(["127.0.0.1:7555", "emulator-5554"])
    assert error.serials == ["127.0.0.1:7555", "emulator-5554"]
    assert "127.0.0.1:7555, emulator-5554" in str(error)
