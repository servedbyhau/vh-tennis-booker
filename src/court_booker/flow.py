"""Booking flow, one method per app screen.

All elements are located by accessibility label at the time of the tap; no
coordinates are stored. ``device`` is a :class:`uiautomator2.Device` or a test
double with the same interface.
"""

from __future__ import annotations

import logging
import time
import xml.etree.ElementTree as ET
from datetime import date
from typing import Any

from court_booker.config import Config
from court_booker.errors import ElementNotFoundError, NavigationError, SlotUnavailableError
from court_booker.geometry import (
    ANY_SLOT_PATTERN,
    DAY_PATTERN,
    box_from_info,
    center,
    day_pattern,
    is_checkbox_beside,
    month_index,
    month_index_from_label,
    parse_bounds,
)

logger = logging.getLogger(__name__)

Selector = dict[str, Any]

_POLL_INTERVAL = 0.05
_NEXT_SCREEN_TIMEOUT = 2.0
_TAP_RETRIES = 5
_BACK_PRESSES = 8
_HEADER_RATIO = 0.10


class Booker:
    """Drive one booking round per call to :meth:`book`."""

    def __init__(self, device: Any, config: Config) -> None:
        self.device = device
        self.config = config
        self._screen_size: tuple[int, int] | None = None

        labels = config.labels
        self.home = {"description": labels.home, "clickable": True}
        self.utility = {"description": labels.utility, "clickable": True}
        self.calendar = [
            {"description": labels.prev_month},
            {"descriptionContains": labels.next_month},
            {"descriptionMatches": DAY_PATTERN},
        ]
        self.continue_button = {"description": labels.continue_, "clickable": True}
        self.venue = {"descriptionContains": config.venue_keyword}
        self.court = {"description": config.court, "clickable": True}
        self.confirm_page = {"description": labels.confirm_page}

    # Public API -------------------------------------------------------------

    def book(self, slot: str, target: date, dry_run: bool = False) -> None:
        """Book ``slot`` on ``target``, starting from the home or utilities screen."""
        labels = self.config.labels
        self.return_to_utilities()
        self.tap_and_advance(self.utility, labels.utility, self.calendar)
        self.select_date(target)
        self.select_slot(slot)
        self.tap_and_advance(self.continue_button, labels.continue_, [self.venue, self.court])
        if self._exists(self.venue):
            self.tap_and_advance(self.venue, self.config.venue_keyword, [self.court])
        self.tap_and_advance(self.court, self.config.court, [self.continue_button])
        self.tap_and_advance(self.continue_button, labels.continue_, [self.confirm_page])
        self.accept_and_confirm(dry_run)

    def return_to_utilities(self) -> None:
        """Navigate to the utilities list from the home, ticket or any inner screen."""
        for _ in range(_BACK_PRESSES):
            if self._exists(self.utility):
                return
            if self._exists(self.home):
                self.tap_and_advance(self.home, self.config.labels.home, [self.utility])
                return
            self.device.press("back")
            self.wait_for_any([self.utility, self.home], _NEXT_SCREEN_TIMEOUT)
        raise NavigationError("Could not return to the utilities list")

    # Navigation -------------------------------------------------------------

    def tap_and_advance(self, target: Selector, name: str, next_screen: list[Selector]) -> None:
        """Tap ``target`` as soon as it appears and wait for ``next_screen``.

        A tap swallowed by a lagging app is retried.
        """
        if not self.device(**target).wait(timeout=self.config.timeout):
            raise ElementNotFoundError(f"Button not found: {name!r}")
        for attempt in range(_TAP_RETRIES):
            if attempt == 0 or self._exists(target):
                self.device(**target).click()
            if self.wait_for_any(next_screen, _NEXT_SCREEN_TIMEOUT):
                logger.info("Tapped %r", name)
                return
            logger.debug("Retrying tap on %r (attempt %d)", name, attempt + 2)
        raise NavigationError(f"Tapped {name!r} but the next screen did not appear")

    def wait_for_any(self, selectors: list[Selector], timeout: float) -> Selector | None:
        """Return the first selector that appears within ``timeout``, else ``None``."""
        deadline = time.monotonic() + timeout
        while True:
            for selector in selectors:
                if self._exists(selector):
                    return selector
            if time.monotonic() >= deadline:
                return None
            time.sleep(_POLL_INTERVAL)

    # Calendar screen --------------------------------------------------------

    def select_date(self, target: date) -> None:
        """Tap ``target`` in the calendar, switching month if needed."""
        pattern = day_pattern(target)
        target_month = month_index(target.year, target.month)
        for attempt in range(5):
            day = self.device(descriptionMatches=pattern)
            if day.wait(timeout=1.5 if attempt == 0 else 0.8):
                day.click()
                logger.info("Selected date %s", target.isoformat())
                return
            shown = self._shown_month()
            forward = attempt % 2 == 0 if shown is None else shown < target_month
            self._switch_month(forward)
        raise ElementNotFoundError(f"Date {target.isoformat()} is not bookable")

    def select_slot(self, slot: str) -> None:
        """Tap ``slot``, scrolling until it is fully visible."""
        deadline = time.monotonic() + self.config.timeout
        swipes = 0
        while time.monotonic() < deadline:
            element = self.device(descriptionStartsWith=slot)
            if element.exists(timeout=0):
                label = element.info.get("contentDescription") or ""
                if self.config.labels.fully_booked in label:
                    raise SlotUnavailableError(f"Slot {slot} is fully booked")
                position = self._visibility(element)
                if position == "visible":
                    element.click()
                    logger.info("Selected slot %s (%d swipe(s))", slot, swipes)
                    return
                scroll_down = position == "below"
            elif self.device(descriptionMatches=ANY_SLOT_PATTERN).exists(timeout=0):
                scroll_down = True
            else:
                time.sleep(0.2)
                continue
            if swipes >= self.config.max_swipes:
                break
            self._scroll(down=scroll_down)
            swipes += 1
        raise ElementNotFoundError(f"Slot {slot} not found after {swipes} swipe(s)")

    # Confirmation screen ----------------------------------------------------

    def locate_checkbox(self) -> tuple[int, int] | None:
        """Return the tap point of the consent checkbox, or ``None`` if not rendered.

        The checkbox has no label; it is the small node beside its caption.
        Nodes that are not level with the caption are never returned.
        """
        caption = self.device(descriptionContains=self.config.labels.agree)
        if not caption.exists(timeout=0):
            return None
        label_box = box_from_info(caption.info["bounds"])
        width, _ = self._get_screen_size()

        try:
            sibling = caption.left(clickable=True)
        except Exception:  # uiautomator2 raises on missing neighbours
            sibling = None
        if sibling is not None and sibling.exists(timeout=0):
            box = box_from_info(sibling.info["bounds"])
            if is_checkbox_beside(box, label_box, width):
                logger.debug("Checkbox found beside caption at %s", box)
                return center(box)

        root = ET.fromstring(self.device.dump_hierarchy(compressed=False))
        candidates = []
        for node in root.iter("node"):
            box = parse_bounds(node.get("bounds", ""))
            if box and is_checkbox_beside(box, label_box, width):
                not_clickable = node.get("clickable") != "true"
                area = (box[2] - box[0]) * (box[3] - box[1])
                candidates.append(((not_clickable, area), box))
        if not candidates:
            return None
        box = min(candidates)[1]
        logger.debug("Checkbox found by hierarchy scan at %s", box)
        return center(box)

    def accept_and_confirm(self, dry_run: bool) -> None:
        """Tick the consent checkbox and submit the booking."""
        labels = self.config.labels
        confirm = self.device(description=labels.confirm, clickable=True)
        self.device(description=labels.confirm).wait(timeout=self.config.timeout)

        deadline = time.monotonic() + self.config.timeout
        point = None
        while time.monotonic() < deadline:
            if point is None:
                point = self.locate_checkbox()
                if point is None:
                    time.sleep(0.2)
                    continue
            self.device.click(*point)
            if confirm.wait(timeout=0.8):
                break
        else:
            if point is None:
                raise ElementNotFoundError("Consent checkbox not found")
            raise NavigationError("Checkbox tapped but the confirm button stayed disabled")
        logger.info("Accepted terms")

        if dry_run:
            logger.info("Dry run: skipping final confirmation")
            return
        confirm.click()
        if not self.device(**self.confirm_page).wait_gone(timeout=self.config.timeout):
            raise NavigationError("Confirmation submitted but the ticket screen did not appear")
        logger.info("Booking confirmed")

    # Helpers ----------------------------------------------------------------

    def _exists(self, selector: Selector) -> bool:
        return bool(self.device(**selector).exists(timeout=0))

    def _get_screen_size(self) -> tuple[int, int]:
        if self._screen_size is None:
            self._screen_size = self.device.window_size()
        return self._screen_size

    def _scroll(self, down: bool) -> None:
        width, height = self._get_screen_size()
        start, end = (0.62, 0.38) if down else (0.38, 0.62)
        self.device.swipe(width * 0.5, height * start, width * 0.5, height * end, 0.25)
        time.sleep(0.15)

    def _visibility(self, element: Any) -> str:
        """Return ``visible``, ``below`` or ``above`` relative to the tappable area.

        The sticky bottom button counts as hidden area.
        """
        _, height = self._get_screen_size()
        bounds = element.info["bounds"]
        bottom_limit = height
        button = self.device(description=self.config.labels.continue_)
        if button.exists(timeout=0):
            bottom_limit = min(bottom_limit, button.info["bounds"]["top"])
        if bounds["bottom"] > bottom_limit - 4:
            return "below"
        if bounds["top"] < int(height * _HEADER_RATIO):
            return "above"
        return "visible"

    def _shown_month(self) -> int | None:
        day = self.device(descriptionMatches=DAY_PATTERN)
        if not day.exists(timeout=0):
            return None
        return month_index_from_label(day.info.get("contentDescription", ""))

    def _switch_month(self, forward: bool) -> None:
        labels = self.config.labels
        if forward:
            button = self.device(descriptionContains=labels.next_month)
            fallback = self.config.next_month_xy
        else:
            button = self.device(description=labels.prev_month)
            fallback = self.config.prev_month_xy
        if button.exists(timeout=0):
            button.click()
        else:
            self.device.click(*fallback)
        logger.debug("Switched to %s month", "next" if forward else "previous")
