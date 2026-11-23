"""Booking flow, one method per app screen.

Each screen is read with one hierarchy dump (:class:`~court_booker.screen.Screen`),
which lists every element with its bounds in about the time of a single element
query. Elements are found by accessibility label in that dump, so waiting for the next
screen and locating the next element are the same query: a step costs one dump per poll
plus one tap. A tap names the element by its label: the driver
(:class:`~court_booker.driver.DriverDevice`) clicks the element with that label where it is
then, uiautomator2 (:class:`~court_booker.ready.QuickTap`) taps where the dump showed it.
No coordinates are kept across screens. ``device`` is one of them or a test double with
``dump_hierarchy``, ``click`` (with the label of the element tapped), ``press``, ``swipe``,
``shell`` and the app calls.
"""

from __future__ import annotations

import logging
import re
import time
from dataclasses import asdict, dataclass
from datetime import date
from typing import Any, Callable, Optional, TypeVar

from court_booker import catalog
from court_booker.app_language import AppLanguage, app_languages
from court_booker.config import Config
from court_booker.credentials import Login, mask_phone
from court_booker.errors import (
    AppNotReadyError,
    BookingNotOpenError,
    BookingRejectedError,
    BookingUnconfirmedError,
    ElementNotFoundError,
    LoggedOutError,
    LoginFailedError,
    NavigationError,
    QuotaFullError,
    SlotUnavailableError,
    WrongAccountError,
)
from court_booker.events import EventKind, Reporter
from court_booker.geometry import (
    ANY_SLOT_PATTERN,
    is_checkbox_beside,
    is_inside,
    is_small,
    month_index,
    parse_booked_time,
)
from court_booker.screen import Match, Node, Screen

logger = logging.getLogger(__name__)

T = TypeVar("T")
Finder = Callable[[Screen], Optional[T]]
"""Return what to act on in a screen, or ``None`` while it is not shown yet."""

_POLL_INTERVAL = 0.02
_NEXT_SCREEN_TIMEOUT = 2.0
"""How long a screen may take to show after Back before Back is pressed again."""
_RETAP_AFTER = 2.0
"""How long a tap may go without the next screen before its element, if still shown, is
tapped again: the app swallowed the tap. The calendar stayed 2.3 s after a "Tiếp tục" the
app took (2026-10-11), so a shorter wait would send it twice at 06:00. A tap is never
repeated while the app loads the next screen (the element gone): that waits up to
``timeout``, as the server may be slow."""
_COURT_ATTEMPTS = 5
"""Courts opened by mistake before the round gives up."""
_MOVED_COURT_WAIT = 0.6
"""A court list still shown this long after a court tap, with the court moved, missed it.

A tap that opens a court shows the booking details page 0.23-0.45 s later (14-17/10)."""
_BACK_PRESSES = 8
_POPUP_WAIT = 2.0
"""How long ``prepare`` watches the home screen for a promotion popup before it is ready.

The popup showed 0.3-0.8 s after the home screen (2 restarts, 2026-11-17). Closed then, it
cannot cover the home screen's button the moment a run taps it."""
APP_START_TIMEOUT = 45.0
"""Seconds the started app may take to show a screen the run knows: the home screen showed
4-11 s after the start (2026-11-10 to 19). Longer means the app hangs or waits on the network;
the run then restarts it (:mod:`court_booker.ready`)."""
_START_NOTICES = 3
"""Notices closed while the app starts before the run gives up: the one seen is the logout
notice over the login screen (2026-11-11)."""
_FIELD_COUNT = re.compile(r"\d+/\d+")
"""The count of characters a field shows inside it, such as "10/10" in the phone field."""
_LOGIN_SETTLE = 0.3
"""Pause between the login button showing enabled and its tap. On 2026-11-18 a tap 1 ms after
the read that showed it enabled did nothing for 30 s, as "Xác nhận" a few frames after the
tick (field notes); the app takes the password a few frames after the button turns."""
_LOGIN_TIMEOUT = 60.0
"""How long the app may take to answer a login; it is typed in 15 minutes before the start."""
_LOGIN_RETAP_AFTER = 20.0
"""How long the login screen may stay as it was after a tap before the button is tapped again.
The screen stays unchanged while the server checks the login: 7-11 s on 2026-11-22, when taps
every 3 s sent the login three times."""
_LOGIN_TAPS = 2
"""Most taps on the login button: each may send the password, and the app locks an account
after 5 wrong ones. The second one only while the screen stayed unchanged."""
_ACCOUNT_TRIES = 2
"""Times the account tab is read before the run goes on without it, each after a restart of
the app: a page that changed must not cost every machine its bookings."""
_PHONE_WAIT = 5.0
"""How long the account tab may show without its phone number, read at once on 2026-11-22."""
_PHONE = re.compile(r"(?:\+?84|0)(\d{9})")
"""A phone number as the account tab may write it; it wrote 10 digits on 2026-11-22."""
_PHONE_IN_TEXT = re.compile(r"(?<!\d)(0\d)\d{6}(\d{2})(?!\d)")
_LOGIN_READY_WAIT = 2.0
"""How long the login button may stay disabled after the password is typed in: it was enabled
in the read right after (2026-11-18)."""
_CONTINUE_WAIT = 2.0
"""How long the slot list is read again while "Tiếp tục" shows disabled, before the slot tap.

Every booking so far tapped the slot with the button enabled, and 77 reads of the slot list
on 14-18/10 showed both at once; at 06:00:10 on 2026-10-19 the list showed with the button
still disabled. A tap on a page not done yet may be dropped when the page is built again."""
_SLOT_SETTLE = 0.1
"""Pause after the slot tap, before "Tiếp tục": the app takes the slot a few frames later.

A "Tiếp tục" 11-40 ms after the tap booked the slot selected before (3 of 3, with an
accessibility agent, 2026-10-18); 60 and 100 ms got the slot tapped (12 of 12).
uiautomator2's taps were never that close. Nothing on the screen shows the selection, so
there is nothing to wait for."""
_TERMS_SETTLE = 0.2
"""Least time from the checkbox tap to "Xác nhận": the app takes the tick a few frames after
the button shows enabled. A "Xác nhận" 65 ms after the tick did nothing (the driver,
2026-10-18), one 97 ms after it booked, and uiautomator2's 0.14-0.23 s always did."""
_CONFIRM_RETAP_AFTER = 3.0
"""How long "Xác nhận" may go without the ticket or a notice before it is tapped again, if
the confirmation page still shows it enabled: the app swallowed the tap. 2 of 26 rounds under
simulated load (2026-10-19) kept the page unchanged for 30 s with no ticket, and a tap by
hand then booked. The page also stays unchanged while the server answers, so the wait is
about twice the slowest answer at 06:00: the ticket showed 0.66-1.6 s after the tap (7 taps,
15-20/10), 1.1-2.7 s under light lag. A swallowed tap costs 3 s, and a slow answer seldom
gets a second tap."""
_FIRST_DATE_WAIT = 1.5
_NEXT_DATE_WAIT = 0.8
_DATE_RETAP_AFTER = 0.5
"""How long the calendar's prompt may stay after a day tap before the day is tapped again:
the app ignored the tap. The prompt went 0.05 s after a tap the app took; a tap on a day of a
month still sliding in only stopped the slide, and the prompt stayed (2026-10-30)."""
_CHECKBOX_TIMEOUT = 0.8
_SETTLE_TIMEOUT = 1.0
_SWIPE_SECONDS = 0.25
_PAGE_SWIPE = (0.86, 0.16)
_PAGE_SWIPE_SECONDS = 0.6
"""A page swipe, as shares of the height: it moved the history page by about three cards
(2026-11-23)."""
_MIN_VISIBLE_RATIO = 0.6
"""A slot clipped to less than this share of a full slot's height is scrolled into view."""
QUIET_SETTINGS = (
    "window_animation_scale",
    "transition_animation_scale",
    "animator_duration_scale",
    "heads_up_notifications_enabled",
)
"""Android settings set to 0: those Accessibility > Remove animations sets, then the
notification banners that would drop over the top of the app."""


@dataclass
class Booked:
    """What the app showed for a round that went through, for the log and the history.

    Read from screens the round reads anyway, so it costs no device command. A detail not
    found stays ``None``; so do the ticket's in a dry run.
    """

    shown_date: str | None = None
    """ISO date on the confirmation page."""
    shown_slot: str | None = None
    """Slot on the confirmation page."""
    shown_court: str | None = None
    """Court on the confirmation page: the one booked, which once differed from the one tapped."""
    ticket_status: str | None = None
    """The ticket's status in the read that showed the ticket, if it showed already."""

    def event_data(self) -> dict[str, Any]:
        """Return the details found, as data of the ``slot_booked`` event."""
        return {key: value for key, value in asdict(self).items() if value is not None}


class Booker:
    """Drive one booking round per call to :meth:`book`."""

    def __init__(
        self,
        device: Any,
        config: Config,
        report: Reporter | None = None,
        login_for: Callable[[], Login | None] | None = None,
        account_seen: Callable[[], str | None] | None = None,
    ) -> None:
        self.device = device
        self.config = config
        self.report = Reporter() if report is None else report
        """Receives the steps of each round; reporting sends no device commands."""
        self._login_for = login_for
        """Read the saved login of this MuMu instance, the one its app must be logged in with."""
        self._account_seen = account_seen
        """Read the masked phone number an earlier run last saw on this MuMu instance."""
        self.hurry = False
        """Whether the start is near: an account an earlier run saw is not read again."""
        self._account_known = False
        """Whether this run needs not read the account (again)."""
        self._account_unread = 0
        self._logged_in = False
        self.commands = 0
        """Device commands sent so far; each is a round trip to the emulator."""
        self.last_screen = Screen([])
        self.app_start_timeout = APP_START_TIMEOUT
        """Seconds the started app may take to show a screen the run knows."""
        self._entry: Screen | None = None
        self.account_subdivision: str | None = None
        """The subdivision the home screen's apartment code tells, once ``prepare`` read it."""

        self.any_slot = Match(pattern=ANY_SLOT_PATTERN)
        self.court = Match(desc=config.court, clickable=True)
        self.any_court = Match(prefix=config.court, clickable=True)
        self.opened_court = Match(desc=config.court, clickable=False)
        """The court named on the booking details page."""
        self.languages = app_languages(config.labels, config.sport)
        """The languages the app may show; the court names read the same in each."""
        self._use(self.languages[0])

    def _use(self, language: AppLanguage) -> None:
        """Read and tap the app's labels in ``language`` from now on."""
        self.language = language
        self.labels = labels = language.labels
        self.home = Match(desc=labels.home, clickable=True)
        self.utility = Match(desc=labels.utility, clickable=True)
        self.any_day = Match(pattern=language.any_day)
        self.prev_month = Match(desc=labels.prev_month)
        self.next_month = Match(contains=labels.next_month)
        self.pick_date = Match(desc=labels.pick_date)
        self.continue_button = Match(desc=labels.continue_, clickable=True)
        self.venue_list = Match(desc=labels.venue_list)
        self.court_list = Match(desc=labels.court_list)
        self.residents = Match(contains=labels.residents)
        self.agree = Match(contains=labels.agree)
        self.confirm_button = Match(desc=labels.confirm, clickable=True)
        self.notice = Match(desc=labels.notice)
        self.ticket = Match(desc=labels.ticket)
        self.processing = Match(desc=labels.processing)
        self.registered = Match(desc=labels.registered)
        self.popup = Match(desc=labels.dont_show_again, clickable=True)
        self.login_ready = Match(desc=labels.login, clickable=True)
        """The login button once a password is typed in: disabled, it is not clickable."""
        self.home_tab = Match(prefix=f"{labels.home_tab}\n", clickable=True)
        self.account_tab = Match(prefix=f"{labels.account_tab}\n", clickable=True)
        # Whole labels only: "Xóa tài khoản" is the button above.
        self.log_out_button = Match(desc=labels.log_out, clickable=True)
        self.log_out_title = Match(desc=labels.log_out, clickable=False)
        self.log_out_yes = Match(desc=labels.log_out_yes, clickable=True)

    # Public API -------------------------------------------------------------

    def quiet_device(self) -> None:
        """Turn off Android animations and notification banners in one command.

        Screens then change without transitions, so the next one can be read sooner, and no
        banner can cover the top of the app or add nodes to a dump mid-round. The settings
        stay until changed, and a failure only costs these safeguards.
        """
        command = "; ".join(f"settings put global {name} 0" for name in QUIET_SETTINGS)
        self.commands += 1
        try:
            self.device.shell(command)
        except Exception:  # uiautomator2 raises several unrelated types
            logger.warning("Could not turn off animations and banners", exc_info=True)
            return
        logger.debug("Animations and notification banners off")

    def prepare(self, restart: bool = False) -> None:
        """Open the app and stop on its home screen, ready for the first round.

        With ``restart_app`` the app is stopped first, so a stale screen, popup or
        expired session from the previous day cannot get in the way; ``restart`` stops it
        also without, for a try after the app was not made ready. A timed run waits
        on the home screen and opens the utilities list shortly before the start
        (:meth:`locate_entry`), so the list it books from is freshly loaded. The first of
        these screens tells the app's language, whose labels the rounds then use.

        An app logged out (on another device) shows a notice over its login screen: the
        notice is closed, and the saved login typed in (:meth:`log_in`); without one the run
        stops at once with :class:`LoggedOutError`. With a saved login the account logged in must
        be that one's, and is changed if it is not (:meth:`check_account`).
        """
        package = self.config.package
        self.quiet_device()
        if self.config.restart_app or restart:
            logger.info("Restarting %s", package)
            self.device.app_stop(package)
            self.device.app_start(package)
        elif self.device.app_current().get("package") != package:
            logger.info("Starting %s", package)
            self.device.app_start(package)

        screen = self._first_screen()
        logger.info("App language: %s", self.language.name)
        if self._password_field(screen) is not None:
            screen = self.log_in(screen)
        try:
            home = self.check_account(self._settle_home(screen))
        except NavigationError as exc:
            raise AppNotReadyError(str(exc)) from exc
        self.read_account(home)
        logger.info("Ready on the home screen")

    def _settle_home(self, screen: Screen) -> Screen:
        """Return the home screen from ``screen``, with the popup that may come over it closed."""
        home = self.return_to_home(screen)
        popup = self.wait_for(self._finder(self.popup), _POPUP_WAIT, home)
        return home if popup is None else self.return_to_home(popup[1])

    def check_account(self, home: Screen) -> Screen:
        """Have the app logged in with the saved login's account; return the home screen.

        The account tab shows the phone number of the account logged in. Another one than the
        saved login's is logged out and the saved login typed in, once a run
        (:meth:`log_in`), and the number read again. Without a saved login nothing is checked.

        A number that cannot be read is no other number: the app may have changed the page.
        After :data:`_ACCOUNT_TRIES` the run goes on if an earlier run saw this account on
        this MuMu instance, and stops with :class:`WrongAccountError` if none did. It never
        books with an account it read to be another one.
        """
        login = None if self._login_for is None else self._login_for()
        if login is None or self._account_known:
            return home
        seen = None if self._account_seen is None else self._account_seen()
        if self.hurry and seen == login.masked_phone:
            logger.info("The start is near: the account is the one seen before (%s)", seen)
            self._account_known = True
            return home
        page = self._account_page(home)
        phone = None if page is None else self._phone_on(page)
        if page is None or phone is None:
            return self._account_not_read(login, seen)
        switched = phone != login.phone
        if switched:
            logger.warning(
                "The app is logged in with %s, not with the saved login (%s): changing it",
                mask_phone(phone),
                login.masked_phone,
            )
            home = self._settle_home(self.log_in(self._log_out(page)))
            page = self._account_page(home)
            phone = None if page is None else self._phone_on(page)
            if page is None or phone != login.phone:
                shown = "no number" if phone is None else mask_phone(phone)
                raise WrongAccountError(
                    f"The app shows {shown} after logging in with the saved login "
                    f"({login.masked_phone}) on MuMu {self.config.mumu_index}"
                )
        self._account_known = True
        logger.info("Account: %s, the saved login's", login.masked_phone)
        self.report(EventKind.ACCOUNT_CHECKED, phone=login.masked_phone, switched=switched)
        _, screen = self.tap_and_advance(
            page, self.home_tab, self.labels.home_tab, self._either(self.home, self.popup)
        )
        return self._settle_home(screen)

    def _account_not_read(self, login: Login, seen: str | None) -> Screen:
        """Go on without the account's number, or have the app restarted to read it again."""
        self._account_unread += 1
        if self._account_unread < _ACCOUNT_TRIES:
            raise AppNotReadyError("The account tab did not show the account's phone number")
        if seen != login.masked_phone:
            raise WrongAccountError(
                "The account tab did not show the account's phone number, and no earlier run saw "
                f"the saved login ({login.masked_phone}) on MuMu {self.config.mumu_index}"
            )
        logger.warning("Account not read; going on, as an earlier run saw it (%s)", seen)
        self._account_known = True  # not read again after the restart
        raise AppNotReadyError("Restarting the app to leave the account tab")

    def _account_page(self, home: Screen) -> Screen | None:
        """Open the account tab from the home screen; ``None`` if it does not show.

        The home screen may show from the app's store while the session is over: the notice
        or the login then comes instead, and the app is made ready again from there.
        """

        def arrived(screen: Screen) -> bool | None:
            if self._logged_out(screen) or screen.find(self.log_out_button):
                return True
            return None

        try:
            _, page = self.tap_and_advance(home, self.account_tab, self.labels.account_tab, arrived)
        except (ElementNotFoundError, NavigationError) as exc:
            logger.warning("The account tab did not open: %s", exc)
            return None
        if self._logged_out(page):
            raise AppNotReadyError("The app logged out while its account was read")
        return page

    def _logged_out(self, screen: Screen) -> bool:
        return self.notice_text(screen) is not None or self._password_field(screen) is not None

    def _phone_on(self, page: Screen) -> str | None:
        """Return the phone number the account tab shows, as ``0`` and 9 digits."""

        def phone(screen: Screen) -> str | None:
            if self._logged_out(screen):
                raise AppNotReadyError("The app logged out while its account was read")
            for node in screen.nodes:
                found = _PHONE.fullmatch(re.sub(r"[ .\-]", "", node.desc.split("\n")[-1]))
                if found is not None:
                    return f"0{found[1]}"
            return None

        read = self.wait_for(phone, _PHONE_WAIT, page)
        return None if read is None else read[0]

    def _log_out(self, page: Screen) -> Screen:
        """Log out from the account tab ``page`` and return the login screen.

        Both buttons are found by their whole labels, the second one only in the dialog that
        asks whether to log out: a button above deletes the account.
        """

        def asked(screen: Screen) -> bool | None:
            if screen.find(self.log_out_title) and screen.find(self.log_out_yes):
                return True
            return None

        _, dialog = self.tap_and_advance(page, self.log_out_button, self.labels.log_out, asked)
        _, login = self.tap_and_advance(
            dialog, self.log_out_yes, self.labels.log_out_yes, self._password_field
        )
        return login

    def _first_screen(self) -> Screen:
        """Return the first screen of the started app that tells its language.

        That is the home screen (or the popup over it), the utilities list or the login. A
        notice at the start, such as the one that the account logged in elsewhere, is closed
        with Back, which is pressed again only while the notice still shows: on the login
        screen Back would leave the app.
        """
        deadline = time.monotonic() + self.app_start_timeout
        notices = 0
        while True:
            found = self.wait_for(self._find_language, max(0.0, deadline - time.monotonic()))
            if found is None:
                *labels, last = [
                    repr(label)
                    for language in self.languages
                    for label in (language.labels.home, language.labels.utility)
                    if label
                ]
                raise AppNotReadyError(
                    f"The app did not show {', '.join(labels)} or {last} in "
                    f"{self.app_start_timeout:.0f} s; check the app on MuMu "
                    f"{self.config.mumu_index}"
                )
            self._use(found[0])
            screen = found[1]
            message = self.notice_text(screen)
            if message is None:
                return screen
            notices += 1
            if notices > _START_NOTICES:
                raise AppNotReadyError(f"The app kept showing a notice: {message or 'no message'}")
            logger.warning("Closing a notice of the app: %s", message or "no message")
            self.press_back()
            self.wait_for(self._notice_gone, _NEXT_SCREEN_TIMEOUT)

    def _notice_gone(self, screen: Screen) -> bool | None:
        return True if self.notice_text(screen) is None else None

    def log_in(self, screen: Screen) -> Screen:
        """Type the saved login into the login ``screen`` and return the screen after it.

        The app keeps the last phone number in its field; it is typed again all the same. The
        login button is tapped :data:`_LOGIN_SETTLE` after it shows enabled, and again only
        while the login screen stays exactly as it was (the app missed the tap), at most
        :data:`_LOGIN_TAPS` times: the app locks an account after 5 wrong passwords. The home
        screen (or the popup over it) means logged in; a notice or a
        message in a field means refused, and the run stops with :class:`LoginFailedError`.
        Without a saved login it stops with :class:`LoggedOutError` before typing anything.
        """
        login = self._login_for() if self._login_for is not None else None
        if login is None:
            raise LoggedOutError(
                f"The app is logged out (the account logged in on another device): log in "
                f"again on MuMu {self.config.mumu_index}, or attach an account in the app's "
                "setup so a run logs in by itself"
            )
        if self._logged_in:
            raise LoginFailedError("The app logged out again right after the saved login")
        self._logged_in = True
        password = self._password_field(screen)
        assert password is not None  # the caller saw the login screen
        phone = next(
            (
                node
                for node in screen.nodes
                if node.field and not node.password and node.box[3] <= password.box[1]
            ),
            None,
        )
        logger.info("Logging in with the saved login (%s)", login.masked_phone)
        if phone is not None:
            self.type_text(phone, login.phone)
        self.type_text(password, login.password)
        ready = self.wait_for(self._finder(self.login_ready), _LOGIN_READY_WAIT)
        if ready is None:
            raise LoginFailedError(f"{self.labels.login!r} stayed disabled after typing the login")
        time.sleep(_LOGIN_SETTLE)
        button: Node | None = ready[0]
        deadline = time.monotonic() + _LOGIN_TIMEOUT
        taps = 0
        while True:
            if button is not None and taps < _LOGIN_TAPS:
                if taps:
                    logger.info("%r tapped again: the login screen stayed as it was", button.desc)
                self.tap(button)
                taps += 1
            outcome = self.wait_for(self._after_login, _retap_wait(deadline, _LOGIN_RETAP_AFTER))
            if outcome is not None:
                break
            if time.monotonic() >= deadline:
                raise LoginFailedError(
                    f"Neither the home screen nor a message showed {_LOGIN_TIMEOUT:.0f} s "
                    f"after {self.labels.login!r} ({taps} tap(s)); check the app"
                )
            # Tapped again only while the app shows the same enabled button: one that took
            # the tap shows something else (a message ends the login above).
            button = self.last_screen.find(self.login_ready)
        message = self.notice_text(outcome[1])
        if message is None:
            message = self._field_message(outcome[1])
        if message is not None:
            raise LoginFailedError(
                f"The app refused the saved login: {message or 'no message'}; save it again "
                "in the app's setup (the app locks an account after 5 wrong passwords)"
            )
        logger.info("Logged in again")
        self.report(EventKind.LOGGED_IN)
        return outcome[1]

    def _after_login(self, screen: Screen) -> bool | None:
        """Return ``True`` once the home screen, the popup over it or a refusal shows."""
        if screen.find(self.home) or screen.find(self.popup):
            return True
        if self.notice_text(screen) is not None or self._field_message(screen) is not None:
            return True
        return None

    def _password_field(self, screen: Screen) -> Node | None:
        """Return the login screen's password field: the app's only field shown in dots."""
        return next((node for node in screen.nodes if node.field and node.password), None)

    def _field_message(self, screen: Screen) -> str | None:
        """Return the message the login screen shows under a field, or ``None``.

        It is a label inside the field's bounds, such as "Sai mật khẩu. Vui lòng thử lại"
        under the password (2026-11-18); the phone field's count of digits ("10/10") is no
        message.
        """
        for field in (node for node in screen.nodes if node.field):
            for node in screen.nodes:
                if (
                    node.desc
                    and not node.field
                    and is_inside(node.box, field.box)
                    and _FIELD_COUNT.fullmatch(node.desc) is None
                ):
                    return node.desc
        return None

    def read_account(self, home: Screen) -> None:
        """Tell the account's subdivision from the apartment code on the home screen.

        Costs no command: ``home`` is read anyway. The code itself is personal data, so only
        the subdivision is logged and reported. A court of another subdivision is a warning
        only, since the guess may be wrong. Never fails the run.
        """
        try:
            codes = (node.desc.split("\n")[0] for node in home.nodes if node.clickable)
            code = next((code for code in codes if catalog.APARTMENT.fullmatch(code)), None)
            found = None if code is None else catalog.subdivision_of_apartment(code)
            if found is None:
                logger.debug("No subdivision told by the home screen")
                return
            self.account_subdivision = found
            name = catalog.subdivision(found).name
            logger.info("Account subdivision: %s", name)
            self.report(EventKind.ACCOUNT_SUBDIVISION, subdivision=found)
            if catalog.court_outside(found, self.config.court):
                logger.warning(
                    "Court %s is not in %s, the subdivision of the account", self.config.court, name
                )
        except Exception:  # a guess never costs a booking
            logger.warning("Could not tell the account's subdivision", exc_info=True)

    def locate_entry(self) -> None:
        """Open the utilities list from the home screen, or read it again if it is shown.

        A timed run calls this at ``warm_up_seconds`` before the start, which taps
        the home screen's utilities button and loads the list, and again just before
        the start, which only reads it. The first round then taps the utility with a
        single command at the start time.
        """
        self._entry = self.return_to_utilities()
        logger.info("On the utilities list ahead of the start time")

    def book(self, slot: str, target: date, dry_run: bool = False) -> Booked:
        """Book ``slot`` on ``target``, starting from the home or utilities screen.

        Returns what the confirmation page and the ticket showed.
        """
        labels = self.labels
        screen = self.open_slot(slot, target)
        if screen.find(self.continue_button) is None:  # the slot was tapped with it disabled
            found = self.wait_for(self._finder(self.continue_button), self.config.timeout)
            if found is None:
                raise ElementNotFoundError(f"{labels.continue_!r} stayed disabled")
            screen = found[1]
        shown, screen = self.tap_and_advance(
            screen, self.continue_button, labels.continue_, self._after_calendar
        )
        if self.notice(shown):
            raise self._refusal(self.notice_text(screen) or "")
        if not self.court_list(shown) and not self.residents(shown):
            if labels.fully_booked in shown.desc:
                venue_name = shown.desc.split("\n")[0]
                raise SlotUnavailableError(f"Venue {venue_name} is fully booked")
            # Only the court list's heading counts after the venue: a read right after the
            # tap may still show the venue (2026-10-23), which ended the round at once.
            venue = Match(desc=shown.desc, clickable=True)
            shown, screen = self.tap_and_advance(screen, venue, shown.desc, self._courts_or_details)
        if not self.residents(shown):
            # A court that the bottom edge cuts off is tapped as it is: it is in the tree, and
            # the driver clicks it by its label (field notes, "Other sports").
            found = self.wait_for(self._court_or_details, self.config.timeout, screen)
            if found is None:
                raise ElementNotFoundError(f"Court {self.config.court!r} is not on the court list")
            shown, screen = found
        if self.residents(shown):
            screen = self.check_single_court(screen)
        else:
            if labels.fully_booked in shown.desc:
                raise SlotUnavailableError(f"Court {self.config.court} is fully booked")
            screen = self.select_court(screen)
        self.report(EventKind.COURT_SELECTED, court=self.config.court)
        point, screen = self.tap_and_advance(
            screen, self.continue_button, labels.continue_, self.locate_checkbox
        )
        booked = self.read_confirmation(screen, slot, target)
        after = self.accept_and_confirm(point, dry_run)
        if after is not None:
            self.read_ticket(after, booked)
        return booked

    def open_slot(self, slot: str, target: date) -> Screen:
        """Open the calendar and select ``target`` and ``slot``.

        Returns the calendar screen read before the slot was tapped, which also
        holds the continue button unless it stayed disabled. Until ``open_retry_seconds``
        have passed, a notice in place of the calendar, such as the closed-hours notice,
        is closed with Back and the utility tapped again; and
        a date or slot the server does not list yet, right at the opening time, reloads
        the calendar by leaving and entering it again. A fully booked slot and the quota
        notice fail at once.
        """
        deadline = time.monotonic() + self.config.open_retry_seconds
        attempt = 1
        notices = 0
        screen = self._entry
        self._entry = None
        while True:
            screen = self.return_to_utilities(screen)
            # A tap after a notice logs at debug: before the opening one goes every 0.2 s.
            _, screen = self.tap_and_advance(
                screen,
                self.utility,
                self.labels.utility,
                self._calendar_or_notice,
                quiet=notices > 0,
            )
            message = self.notice_text(screen)
            if message is not None:
                refusal = self._refusal(message)
                if isinstance(refusal, QuotaFullError):  # never seen here; a new tap won't help
                    raise refusal
                message = message or "a notice without a message"
                if time.monotonic() >= deadline:
                    raise BookingNotOpenError(
                        f"{target.isoformat()} {slot} not open after {attempt} attempt(s): "
                        f"{message}"
                    )
                notices += 1
                # 0.2 s a try: on 2026-10-19 the list showed 0.1 s after Back.
                log = logger.info if notices == 1 else logger.debug
                log("Not open yet: %s; closing the notice and tapping again", message)
                screen = self.go_back(screen, self._finder(self.utility))
                attempt += 1
                continue
            if notices:
                logger.info("Calendar opened after %d attempt(s)", attempt)
            self.report(EventKind.CALENDAR_OPENED, attempt=attempt)
            try:
                screen = self.select_date(screen, target)
                return self.select_slot(slot, screen)
            except ElementNotFoundError as exc:
                if time.monotonic() >= deadline:
                    raise BookingNotOpenError(
                        f"{target.isoformat()} {slot} not open after {attempt} attempt(s): {exc}"
                    ) from exc
                logger.info("Not open yet (%s); reloading the calendar", exc)
            screen = None
            attempt += 1

    def select_court(self, screen: Screen) -> Screen:
        """Tap the court on the court list ``screen`` and return the booking details page.

        The list moves up 232 px when the service info above it has loaded, and a read
        cannot tell that it is about to (field notes), so a tap placed from the read before
        can land two courts lower: the app opens that court if it is free (S9 booked instead
        of S6 on 2026-10-13 and 17) and does nothing if it is full. The details page names
        the court it opened; another court is left with Back, and the court is tapped again
        where the list shows it then, as it is when the list moved under a tap that opened
        nothing. A tap the app swallowed is tapped again, and the details page is awaited up
        to ``timeout``, as in :meth:`tap_and_advance`.
        """
        name = self.config.court
        node = screen.find(self.court)
        if node is None:
            raise ElementNotFoundError(f"Button not found: {name!r}")
        deadline = time.monotonic() + self.config.timeout
        wrong = 0
        attempt = 1
        while True:
            if node is not None:
                self.tap(node)
            found = self.wait_for(self._court_tapped(node), _retap_wait(deadline))
            if found is None:
                node = self.last_screen.find(self.court)
                attempt += 1
                logger.debug("Next screen missing after %r (attempt %d)", name, attempt)
            elif found[1].find(self.continue_button) is None:
                logger.warning("%r moved on the court list under the tap; tapping it again", name)
                node = found[0]
            elif found[1].find(self.opened_court) is not None:
                logger.info("Tapped %r", name)
                return found[1]
            else:
                wrong += 1
                logger.warning("The app opened another court than %r; going back to the list", name)
                screen = self.go_back(found[1], self._finder(self.court))
                back = self.wait_for(self._finder(self.court), _NEXT_SCREEN_TIMEOUT, screen)
                if back is None:
                    raise NavigationError(f"Could not return to the court list for {name!r}")
                if wrong >= _COURT_ATTEMPTS:
                    break
                node = back[0]
            if time.monotonic() >= deadline:
                break
        if wrong:
            raise NavigationError(f"The app opened another court than {name!r} {wrong} time(s)")
        raise NavigationError(f"Tapped {name!r} but the next screen did not appear")

    def check_single_court(self, screen: Screen) -> Screen:
        """Return the booking details page ``screen`` shows in place of the court list.

        A court list with a single court, such as table tennis's, passes on to that court's
        details page by itself, often before a read shows the list (field notes, "Other
        sports"). The page is awaited until its "Tiếp tục" is enabled, as after a court tap,
        and must name the configured court.
        """
        name = self.config.court
        found = self.wait_for(self._details_page, self.config.timeout, screen)
        if found is None:
            raise ElementNotFoundError(f"{self.labels.continue_!r} stayed disabled")
        screen = found[1]
        if screen.find(self.opened_court) is None:
            raise ElementNotFoundError(f"The app opened its only court, which is not {name!r}")
        logger.info("The app opened its only court, %r", name)
        return screen

    def return_to_utilities(self, screen: Screen | None = None) -> Screen:
        """Navigate to the utilities list from the home, ticket or any inner screen."""
        if screen is None:
            screen = self.snapshot()
        arrived = self._either(self.utility, self.home)
        for _ in range(_BACK_PRESSES):
            if screen.find(self.utility):
                return screen
            if screen.find(self.home):
                _, screen = self.tap_and_advance(
                    screen, self.home, self.labels.home, self._finder(self.utility)
                )
                return screen
            closed = self.close_popup(screen, arrived)
            if closed is not None:
                screen = closed
                continue
            self._warn_about_notice(screen)
            screen = self.go_back(screen, arrived)
        raise NavigationError("Could not return to the utilities list")

    def check_home(self) -> None:
        """Check that the app is still in front on its home screen, as a run left it.

        Two commands: the app in front, one screen read. A popup that came over the home
        screen is closed; a screen the run cannot get back from, or another app in front,
        raises :class:`AppNotReadyError`, and the app is made ready again
        (:mod:`court_booker.ready`).
        """
        package = self.config.package
        self.commands += 1
        current = self.device.app_current().get("package")
        if current != package:
            raise AppNotReadyError(f"{package} is no longer in front ({current or 'none'} is)")
        screen = self.snapshot()
        if screen.find(self.home):
            return
        try:
            self.return_to_home(screen)
        except NavigationError as exc:
            raise AppNotReadyError(str(exc)) from exc

    def return_to_home(self, screen: Screen | None = None) -> Screen:
        """Press Back until the home screen shows; Back is never pressed on it (that exits)."""
        if screen is None:
            screen = self.snapshot()
        arrived = self._finder(self.home)
        for _ in range(_BACK_PRESSES):
            if screen.find(self.home):
                return screen
            closed = self.close_popup(screen, arrived)
            if closed is not None:
                screen = closed
                continue
            self._warn_about_notice(screen)
            screen = self.go_back(screen, arrived)
        raise NavigationError("Could not return to the home screen")

    # Navigation -------------------------------------------------------------

    def tap_and_advance(
        self,
        screen: Screen,
        target: Match,
        name: str,
        find_next: Finder[T],
        *,
        quiet: bool = False,
    ) -> tuple[T, Screen]:
        """Tap ``target`` on ``screen`` and return what ``find_next`` finds on the next one.

        The next screen is awaited up to ``timeout``, and acted on as soon as a read shows
        it. A tap swallowed by a lagging app is repeated every :data:`_RETAP_AFTER` while
        ``target`` is still shown, never while the app loads the next screen. ``quiet``
        logs the tap at debug level, for a tap repeated many times.
        """
        node = screen.find(target)
        if node is None:
            raise ElementNotFoundError(f"Button not found: {name!r}")
        deadline = time.monotonic() + self.config.timeout
        attempt = 1
        while True:
            if node is not None:
                self.tap(node)
            found = self.wait_for(find_next, _retap_wait(deadline))
            if found is not None:
                (logger.debug if quiet else logger.info)("Tapped %r", name)
                return found
            if time.monotonic() >= deadline:
                raise NavigationError(f"Tapped {name!r} but the next screen did not appear")
            node = self.last_screen.find(target)
            attempt += 1
            logger.debug("Next screen missing after %r (attempt %d)", name, attempt)

    def go_back(self, screen: Screen, arrived: Finder[Node]) -> Screen:
        """Press Back on ``screen`` and return the next screen as soon as it shows.

        That is the first read that shows ``arrived``, or controls of its own while a
        control of ``screen`` is gone. Each screen shows 0.13-0.24 s after Back
        (2026-10-15); waiting for the destination alone cost 2 s per screen on the way.
        Controls are compared, not labels: the status bar's labels change on their own, and
        a screen that only gains controls, such as a ticket still loading, is the same
        screen, where a second Back would go one screen too far. The frame read while a
        screen is built has no controls and is read again. If nothing changed in 2 s, as
        after a Back the app missed, the last read is returned and Back is pressed again.
        """
        before = _controls(screen)

        def next_screen(shown: Screen) -> bool | None:
            controls = _controls(shown)
            if arrived(shown) is not None or (controls and not before <= controls):
                return True
            return None

        self.press_back()
        found = self.wait_for(next_screen, _NEXT_SCREEN_TIMEOUT)
        return found[1] if found is not None else self.last_screen

    def wait_for(
        self, find: Finder[T], timeout: float, screen: Screen | None = None
    ) -> tuple[T, Screen] | None:
        """Read the screen until ``find`` returns a value; ``None`` after ``timeout``.

        ``screen``, if given, is checked first without reading the device again.
        """
        deadline = time.monotonic() + timeout
        while True:
            if screen is None:
                screen = self.snapshot()
            found = find(screen)
            if found is not None:
                return found, screen
            if time.monotonic() >= deadline:
                return None
            time.sleep(_POLL_INTERVAL)
            screen = None

    # Calendar screen --------------------------------------------------------

    def select_date(self, screen: Screen, target: date) -> Screen:
        """Tap ``target`` in the calendar shown on ``screen``, switching month if needed.

        Returns the screen read after the tap the app took.
        """
        match = Match(pattern=self.language.day_pattern(target))
        target_month = month_index(target.year, target.month)
        current: Screen | None = screen
        for attempt in range(5):
            wait = _FIRST_DATE_WAIT if attempt == 0 else _NEXT_DATE_WAIT
            if attempt == 0 and self._month_shown(screen) not in (None, target_month):
                wait = 0  # a month shows only its own days: switch at once
            found = self.wait_for(self._finder(match), wait, current)
            if found is not None:
                shown = self._tap_day(found[1], match, target)
                logger.info("Selected date %s", target.isoformat())
                self.report(EventKind.DATE_SELECTED, date=target.isoformat())
                return shown
            first_day = self.last_screen.find(self.any_day)
            logger.debug(
                "Date %s not shown; first day listed: %r",
                target.isoformat(),
                first_day.desc if first_day else None,
            )
            shown = self._month_shown(self.last_screen)
            forward = attempt % 2 == 0 if shown is None else shown < target_month
            self._switch_month(self.last_screen, forward)
            current = None
        raise ElementNotFoundError(f"Date {target.isoformat()} is not bookable")

    def _tap_day(self, screen: Screen, match: Match, target: date) -> Screen:
        """Tap the day ``match`` finds once it stands still, again while the app ignores it.

        A month switched to slides in, and a tap on a day still sliding only stops the slide
        (2026-10-30). The day is tapped again every :data:`_DATE_RETAP_AFTER` while the
        calendar's prompt stays, up to ``timeout``. Returns the screen without the prompt.
        """
        deadline = time.monotonic() + self.config.timeout
        taps = 0
        while True:
            node = self._still_day(screen, match)
            if node is not None:
                self.tap(node)
                taps += 1
            found = self.wait_for(self._day_taken, _retap_wait(deadline, _DATE_RETAP_AFTER))
            if found is not None:
                if taps > 1:
                    logger.info("Date %s taken after %d taps", target.isoformat(), taps)
                return found[1]
            if time.monotonic() >= deadline:
                raise ElementNotFoundError(
                    f"Date {target.isoformat()} not taken after {taps} tap(s)"
                )
            logger.debug("Calendar prompt still shown after tap %d; tapping the day again", taps)
            screen = self.last_screen

    def _still_day(self, screen: Screen, match: Match) -> Node | None:
        """Return the day ``match`` finds once it is clickable: it is not while it slides in.

        After :data:`_SETTLE_TIMEOUT` the day is returned as it is; ``None`` if it is gone.
        """
        deadline = time.monotonic() + _SETTLE_TIMEOUT
        while True:
            node = screen.find(match)
            if node is None or node.clickable or time.monotonic() >= deadline:
                return node
            time.sleep(_POLL_INTERVAL)
            screen = self.snapshot()

    def _day_taken(self, screen: Screen) -> bool | None:
        """Tell whether the calendar's prompt is gone: the app took the day tap."""
        return True if screen.find(self.pick_date) is None else None

    def select_slot(self, slot: str, screen: Screen | None = None) -> Screen:
        """Tap ``slot`` once the list shows it, scrolling only while it is hidden.

        ``screen``, if given, is checked first without reading the device again. The slot
        is tapped once "Tiếp tục" shows enabled too, or after the list was read again for
        :data:`_CONTINUE_WAIT` with it disabled. Returns the screen read before the tap.
        """
        match = Match(prefix=slot)
        button = self.labels.continue_
        deadline = time.monotonic() + self.config.timeout
        swipes = 0
        disabled_since: float | None = None
        while True:
            remaining = max(0.0, deadline - time.monotonic())
            found = self.wait_for(self._finder(self.any_slot), remaining, screen)
            if found is None:
                break
            screen = found[1]
            node = screen.find(match)
            if node is None:
                down = True
            else:
                if self.labels.fully_booked in node.desc:
                    raise SlotUnavailableError(f"Slot {slot} is fully booked")
                position = self._visibility(screen, node)
                if position == "visible":
                    now = time.monotonic()
                    if screen.find(self.continue_button) is None:
                        if disabled_since is None:
                            disabled_since = now
                            logger.debug("%r disabled; reading the slot list again", button)
                        if now - disabled_since < _CONTINUE_WAIT:
                            time.sleep(_POLL_INTERVAL)
                            screen = None
                            continue
                        logger.warning(
                            "%r still disabled after %.0f s; tapping the slot anyway",
                            button,
                            _CONTINUE_WAIT,
                        )
                    elif disabled_since is not None:
                        logger.info("%r enabled after %.2f s", button, now - disabled_since)
                    self.tap(node)
                    time.sleep(_SLOT_SETTLE)
                    logger.info("Selected slot %s (%d swipe(s))", slot, swipes)
                    self.report(EventKind.SLOT_SELECTED, slot=slot, swipes=swipes)
                    return screen
                down = position == "below"
            if swipes >= self.config.max_swipes or time.monotonic() >= deadline:
                break
            self._scroll(screen, down)
            swipes += 1
            screen = self._settled_screen()
        raise ElementNotFoundError(f"Slot {slot} not found after {swipes} swipe(s)")

    # Confirmation screen ----------------------------------------------------

    def locate_checkbox(self, screen: Screen) -> tuple[int, int] | None:
        """Return the tap point of the consent checkbox, or ``None`` if not rendered.

        The checkbox has no label; it is the small node beside its caption,
        preferring clickable and smaller nodes. Nodes that are not level with the
        caption are never returned.
        """
        caption = screen.find(self.agree)
        if caption is None:
            return None
        width, _ = screen.size
        candidates = [
            node for node in screen.nodes if is_checkbox_beside(node.box, caption.box, width)
        ]
        if not candidates:
            return None
        node = min(candidates, key=lambda n: (not n.clickable, _area(n)))
        logger.debug("Checkbox found beside caption at %s", node.box)
        return node.center

    def read_confirmation(self, screen: Screen, slot: str, target: date) -> Booked:
        """Read the date, slot and court that the confirmation page on ``screen`` books.

        The court is checked on the booking details page already (:meth:`select_court`),
        so a difference here is only logged as a warning and the round still confirms.
        """
        labels = self.labels
        booked = Booked(shown_court=screen.line_after(labels.booked_place))
        time_text = screen.line_after(labels.booked_time)
        parsed = None if time_text is None else parse_booked_time(time_text)
        if parsed is not None:
            booked.shown_date, booked.shown_slot = parsed[0].isoformat(), parsed[1]
        shown = (booked.shown_date, booked.shown_slot, booked.shown_court)
        wanted = (target.isoformat(), slot, self.config.court)
        if None in shown:
            logger.warning("Could not read the date, slot and court on the confirmation page")
        elif shown != wanted:
            logger.warning(
                "The confirmation page books %s %s on %s, not %s %s on %s; confirming anyway",
                *shown,
                *wanted,
            )
        else:
            logger.info("Confirmation page: %s %s on %s", *shown)
        return booked

    def read_ticket(self, screen: Screen, booked: Booked) -> None:
        """Note the ticket's status on ``screen``, the first read that showed the ticket.

        The ticket loads in steps: its title first, then the status (seen "Đang xử lý" at
        06:00), the time and the court. Waiting for the rest would delay the next round, so
        only this read counts.
        """
        status = screen.find(self.processing) or screen.find(self.registered)
        booked.ticket_status = None if status is None else status.desc
        logger.debug("Ticket shown, status %r", booked.ticket_status)

    def accept_and_confirm(self, point: tuple[int, int], dry_run: bool) -> Screen | None:
        """Tick the consent checkbox at ``point`` and submit the booking.

        The confirm button only becomes clickable once the box is ticked, which
        verifies the tick. The round is booked only once the ticket shows; a notice
        dialog, such as a slot taken a moment earlier by someone else, fails it, and so
        does neither in ``timeout``: better a booking reported missing than a missing one
        reported booked. "Xác nhận" is tapped again every :data:`_CONFIRM_RETAP_AFTER`
        while the page still shows it enabled, never while the next screen is built. A
        notice after such a tap may answer the second tap of a booking the first one made,
        so it leaves the outcome unknown. Returns the screen that showed the ticket, or
        ``None`` in a dry run.
        """
        deadline = time.monotonic() + self.config.timeout
        while True:
            ticked = time.monotonic()
            self.tap_point(*point)
            found = self.wait_for(self._finder(self.confirm_button), _CHECKBOX_TIMEOUT)
            if found is not None:
                break
            if time.monotonic() >= deadline:
                raise NavigationError("Checkbox tapped but the confirm button stayed disabled")
            point = self.locate_checkbox(self.last_screen) or point
        logger.info("Accepted terms")
        self.report(EventKind.TERMS_ACCEPTED)

        if dry_run:
            logger.info("Dry run: skipping final confirmation")
            return None
        time.sleep(max(0.0, ticked + _TERMS_SETTLE - time.monotonic()))
        button: Node | None = found[0]
        name = found[0].desc
        deadline = time.monotonic() + self.config.timeout
        taps = 0
        tapped = 0.0
        while True:
            if button is not None:
                if taps:
                    logger.info(
                        "%r tapped again %.1f s after the last tap with the page unchanged "
                        "(attempt %d)",
                        name,
                        time.monotonic() - tapped,
                        taps + 1,
                    )
                tapped = time.monotonic()
                self.tap(button)
                taps += 1
            outcome = self.wait_for(
                self._after_confirm, _retap_wait(deadline, _CONFIRM_RETAP_AFTER)
            )
            if outcome is not None:
                break
            if time.monotonic() >= deadline:
                raise BookingUnconfirmedError(
                    "Outcome unknown: neither the ticket nor a notice showed "
                    f"{self.config.timeout:.0f} s after confirming (taps on {name!r}: {taps}); "
                    "check the app"
                )
            button = self.last_screen.find(self.confirm_button)
        message = self.notice_text(outcome[1])
        if message is not None and taps > 1:
            raise BookingUnconfirmedError(
                f"Outcome unknown: a notice after {taps} taps on {name!r}: "
                f"{message or 'no message'}; an earlier tap may have booked, check the app"
            )
        if message is not None:
            raise self._refusal(message)
        logger.info("Booking confirmed")
        return outcome[1]

    # Dialogs ----------------------------------------------------------------

    def notice_text(self, screen: Screen) -> str | None:
        """Return the message of the app's notice dialog on ``screen``, or ``None``.

        The dialog's title node spans the whole dialog and holds its buttons; a node
        with the same label but no button inside, such as a tab, is not a dialog. The
        message is every other label inside the title that is not a button.
        """
        return _dialog_message(screen, self.notice)

    def locate_popup_close(self, screen: Screen) -> Node | None:
        """Return the X of a promotion popup over the home screen, or ``None`` if none shows.

        The popup (an event invitation, 2026-11-17) is an image with a "Không hiện lại" tick
        box below it and an X above its right corner; it covers the home screen's labels, and
        Back leaves it open. The X has no label: it is the smallest clickable node without a
        label above the tick box's row that is the size of an icon, not the image.
        """
        caption = screen.find(self.popup)
        if caption is None:
            return None
        width, _ = screen.size
        candidates = [
            node
            for node in screen.nodes
            if node.clickable
            and not node.desc
            and node.box[3] <= caption.box[1]
            and is_small(node.box, width)
        ]
        return min(candidates, key=_area, default=None)

    def close_popup(self, screen: Screen, arrived: Finder[Node]) -> Screen | None:
        """Close a promotion popup on ``screen`` with its X; ``None`` if none shows.

        The X closed it within 0.1 s (2026-11-17). The tick box is left alone, so the app's
        own setting is unchanged; the popup shows again after a restart and is closed again.
        Returns the first read that ``arrived`` finds, such as the home screen, or the last
        read after :data:`_NEXT_SCREEN_TIMEOUT`, for the caller to look at again. A read
        without the popup is not enough: a frame without labels in between would get a
        Back, which leaves the app on the home screen.
        """
        node = self.locate_popup_close(screen)
        if node is None:
            return None
        logger.info("Closing a popup of the app over the home screen")
        self.tap(node)
        found = self.wait_for(arrived, _NEXT_SCREEN_TIMEOUT)
        return found[1] if found is not None else self.last_screen

    def _warn_about_notice(self, screen: Screen) -> None:
        """Log a notice about to be closed with Back; it may belong to the round before."""
        message = self.notice_text(screen)
        if message is not None:
            logger.warning("Closing a notice of the app: %s", message or "no message")

    # Device commands --------------------------------------------------------

    def snapshot(self) -> Screen:
        """Read every element of the current screen with one command.

        A screen that differs from the previous read is logged, so the debug log shows
        every screen a run went through, also the ones a failure or a popup left behind.
        """
        self.commands += 1
        screen = Screen.parse(self.device.dump_hierarchy(compressed=False))
        if screen.nodes != self.last_screen.nodes:
            log_screen(screen, "Screen")
        self.last_screen = screen
        return screen

    def tap(self, node: Node) -> None:
        self.tap_point(*node.center, label=node.desc)

    def tap_point(self, x: float, y: float, label: str = "") -> None:
        """Tap ``(x, y)``; ``label`` names the element tapped.

        The driver clicks the element with that label where it is now, which may be away
        from ``(x, y)`` if the screen moved since it was read; uiautomator2 taps the point.
        """
        self.commands += 1
        logger.debug("Tap %s(%d, %d)", f"{label!r} at " if label else "", x, y)
        self.device.click(x, y, label=label)

    def type_text(self, field: Node, text: str) -> None:
        """Replace the text of ``field`` with ``text``, which may be a password: never logged."""
        self.commands += 1
        logger.debug("Type into the %s field", "password" if field.password else "other")
        self.device.set_text(*field.center, text)

    def press_back(self) -> None:
        self.commands += 1
        logger.debug("Press Back")
        self.device.press("back")

    # Helpers ----------------------------------------------------------------

    def _finder(self, match: Match) -> Finder[Node]:
        return lambda screen: screen.find(match)

    def _either(self, first: Match, second: Match) -> Finder[Node]:
        return lambda screen: screen.find(first) or screen.find(second)

    def _find_language(self, screen: Screen) -> AppLanguage | None:
        """Return the language whose home or utility button ``screen`` shows.

        Their labels differ in each language (field notes), so no screen shows two. A
        popup over the home screen hides its button, so the popup's tick box counts too.
        The login screen tells it by its login button (disabled, so not clickable), and a
        notice by its title with a button inside; a login screen without the button's label
        in either language is taken in the first.
        """
        for language in self.languages:
            labels = language.labels
            for label in (labels.home, labels.utility, labels.dont_show_again):
                if label and screen.find(Match(desc=label, clickable=True)) is not None:
                    return language
            if screen.find(Match(desc=labels.login)) is not None:
                return language
            if _dialog_message(screen, Match(desc=labels.notice)) is not None:
                return language
        if self._password_field(screen) is not None:
            return self.languages[0]
        return None

    def _after_confirm(self, screen: Screen) -> bool | None:
        """Return ``True`` once the ticket's title or a notice shows.

        The confirmation page stays about 1 s while the server answers, then a frame with
        no labels shows while the next screen is built, before the ticket and before a
        notice alike (2026-10-15), so the page going away does not tell the outcome.
        """
        if screen.find(self.ticket) is not None or self.notice_text(screen) is not None:
            return True
        return None

    def _find_calendar(self, screen: Screen) -> Node | None:
        return (
            screen.find(self.any_day)
            or screen.find(self.prev_month)
            or screen.find(self.next_month)
        )

    def _calendar_or_notice(self, screen: Screen) -> bool | None:
        """Return ``True`` once the calendar or a notice shows, such as the closed-hours one.

        The notice showed 0.05 s after a tap on the utility before 06:00 (2026-10-19), in
        place of the calendar; waiting for the calendar alone then cost the round 10 s.
        """
        if self._find_calendar(screen) is not None or self.notice_text(screen) is not None:
            return True
        return None

    def _court_tapped(self, tapped: Node | None) -> Finder[Node]:
        """Find the details page's continue button, or the court moved on a list left as is.

        The details page is known by its residents caption, which can show before the
        continue button is enabled, so both are awaited. A list still shown
        :data:`_MOVED_COURT_WAIT` after the tap, with the court somewhere else than
        ``tapped``, ignored the tap; the court is returned where it shows now.
        """
        since = time.monotonic()

        def find(screen: Screen) -> Node | None:
            button = self._details_page(screen)
            if button is not None:
                return button
            court = screen.find(self.court)
            if (
                court is not None
                and tapped is not None
                and court.box != tapped.box
                and time.monotonic() - since >= _MOVED_COURT_WAIT
            ):
                return court
            return None

        return find

    def _courts_or_details(self, screen: Screen) -> Node | None:
        """Return the court list's heading, or the booking details page's caption."""
        return screen.find(self.court_list) or screen.find(self.residents)

    def _court_or_details(self, screen: Screen) -> Node | None:
        """Return the court on the list, or the caption of the details page it passed on to."""
        return screen.find(self.any_court) or screen.find(self.residents)

    def _details_page(self, screen: Screen) -> Node | None:
        """Return the booking details page's continue button once it is enabled."""
        button = screen.find(self.continue_button)
        if button is not None and screen.find(self.residents) is not None:
            return button
        return None

    def _after_calendar(self, screen: Screen) -> Node | None:
        """Return what shows after the calendar's "Tiếp tục", once it shows.

        That is the court list's heading, the venue to tap, the booking details page's
        caption or a notice's title. A utility with a single court shows its details page in
        place of the court list. The quota notice shows in place of the next screen (field
        notes, "Dialogs"); waiting for the courts alone cost the round ``timeout``.
        """
        found = (
            screen.find(self.court_list) or self._venue_entry(screen) or screen.find(self.residents)
        )
        if found is None and self.notice_text(screen) is not None:
            return screen.find(self.notice)
        return found

    def _refusal(self, message: str) -> BookingRejectedError:
        """Return the error for the app's notice ``message`` in place of the next screen."""
        quota = self.labels.quota_full
        if quota and quota in message:
            return QuotaFullError(f"Booking quota used up: {message}")
        return BookingRejectedError(f"The app refused the booking: {message or 'no message'}")

    def _venue_entry(self, screen: Screen) -> Node | None:
        """Return the venue to tap below the venues' heading, once it is listed.

        The heading shows a read or more before the venues in some reads (8 of 30 by
        2026-10-23). A single venue is tapped whatever its name; of several, the one the
        catalog lists ``court`` under, else the one that names ``venue_keyword`` (a court
        typed by hand, or a venue the app renamed).
        """
        heading = screen.find(self.venue_list)
        if heading is None:
            return None
        venues = [
            node
            for node in screen.nodes
            if node.clickable and node.desc and node.box[1] >= heading.box[3]
        ]
        if len(venues) == 1:
            return venues[0]
        name = catalog.venue_of(self.config.court)
        # A full venue reads "BE _ Sân tennis\nHết chỗ" (2026-10-27).
        found = next((node for node in venues if node.desc.split("\n")[0] == name), None)
        if found is not None:
            return found
        keyword = self.config.venue_keyword
        return next((node for node in venues if keyword and keyword in node.desc), None)

    def _visibility(self, screen: Screen, node: Node) -> str:
        """Return ``visible``, ``below`` or ``above`` relative to the tappable area.

        Dump bounds are clipped to what is shown, so a partly hidden slot is
        shorter than a full one. The sticky bottom button counts as hidden area.
        """
        _, height = screen.size
        button = screen.find(Match(desc=self.labels.continue_))
        bottom_limit = button.box[1] if button is not None else height
        full_height = max(n.height for n in screen.find_all(self.any_slot))
        if node.box[3] <= bottom_limit and node.height >= full_height * _MIN_VISIBLE_RATIO:
            return "visible"
        return "below" if node.center[1] > height / 2 else "above"

    def _scroll(self, screen: Screen, down: bool) -> None:
        width, height = screen.size
        start, end = (0.62, 0.38) if down else (0.38, 0.62)
        self.commands += 1
        logger.debug("Swipe %s", "down the list" if down else "up the list")
        self.device.swipe(width * 0.5, height * start, width * 0.5, height * end, _SWIPE_SECONDS)

    def scroll_page(self, screen: Screen) -> None:
        """Move a long list, such as the history page, on by most of the screen."""
        width, height = screen.size
        self.commands += 1
        logger.debug("Swipe a page down the list")
        self.device.swipe(
            width * 0.5,
            height * _PAGE_SWIPE[0],
            width * 0.5,
            height * _PAGE_SWIPE[1],
            _PAGE_SWIPE_SECONDS,
        )

    def _settled_screen(self) -> Screen:
        """Read the screen until the slot list stops moving after a swipe."""
        deadline = time.monotonic() + _SETTLE_TIMEOUT
        previous = None
        while True:
            screen = self.snapshot()
            boxes = [node.box for node in screen.find_all(self.any_slot)]
            if boxes == previous or time.monotonic() >= deadline:
                return screen
            previous = boxes
            time.sleep(_POLL_INTERVAL)

    def _month_shown(self, screen: Screen) -> int | None:
        """Return the month index of the first day ``screen`` lists, ``None`` without one."""
        first_day = screen.find(self.any_day)
        return None if first_day is None else self.language.month_index_from_label(first_day.desc)

    def _switch_month(self, screen: Screen, forward: bool) -> None:
        button = screen.find(self.next_month if forward else self.prev_month)
        if button is not None:
            self.tap(button)
        else:
            x_ratio, y_ratio = self.config.next_month_xy if forward else self.config.prev_month_xy
            width, height = screen.size
            self.tap_point(width * x_ratio, height * y_ratio)
        logger.debug("Switched to %s month", "next" if forward else "previous")


def log_screen(screen: Screen, title: str) -> None:
    """Log every labelled or clickable element of ``screen`` under ``title`` (debug).

    One record per screen, so the history writes one row for it instead of one per element.
    """
    # The account tab shows the account's phone number, which no log holds whole.
    lines = [_PHONE_IN_TEXT.sub(r"\1••••••\2", line) for line in screen.describe()]
    logger.debug("%s (%d elements):%s", title, len(lines), "".join(f"\n  {x}" for x in lines))


def _retap_wait(deadline: float, after: float = _RETAP_AFTER) -> float:
    """Return how long to wait for the next screen before a tap may be repeated."""
    return min(after, max(0.0, deadline - time.monotonic()))


def _controls(screen: Screen) -> set[Node]:
    """Return the clickable elements of ``screen``, except one that covers all of it.

    The frame read while a screen is built has none: its only clickable element spans the
    whole screen (2026-10-15).
    """
    whole = (0, 0, *screen.size)
    return {node for node in screen.nodes if node.clickable and node.box != whole}


def _area(node: Node) -> int:
    left, top, right, bottom = node.box
    return (right - left) * (bottom - top)


def _dialog_message(screen: Screen, title_match: Match) -> str | None:
    """Return the message of the dialog titled as ``title_match`` finds, or ``None``.

    The dialog's title node spans the whole dialog and holds its buttons; a node with the
    same label but no button inside, such as a tab, is not a dialog. The message is every
    other label inside the title that is not a button.
    """
    for title in screen.find_all(title_match):
        inner = [node for node in screen.nodes if is_inside(node.box, title.box)]
        if not any(node.clickable and node is not title for node in inner):
            continue
        return " ".join(
            node.desc
            for node in inner
            if node.desc and not node.clickable and node.desc != title.desc
        )
    return None
