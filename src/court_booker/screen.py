"""One parsed UI hierarchy dump.

A dump returns every element on the screen with its bounds in about the time of
a single element query, so a screen can be read once and searched locally.
Kept free of device access for unit tests.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass

from court_booker.geometry import Box, center, parse_bounds


@dataclass(frozen=True)
class Node:
    """An element of the screen: its accessibility label and visible bounds."""

    desc: str
    box: Box
    clickable: bool

    @property
    def center(self) -> tuple[int, int]:
        """Return the tap point in the middle of the visible bounds."""
        return center(self.box)

    @property
    def height(self) -> int:
        return self.box[3] - self.box[1]


class Screen:
    """The elements of one hierarchy dump, in document order."""

    def __init__(self, nodes: list[Node]) -> None:
        self.nodes = nodes

    @classmethod
    def parse(cls, xml: str) -> Screen:
        """Build a screen from ``dump_hierarchy`` XML; nodes without bounds are skipped."""
        nodes = []
        for element in ET.fromstring(xml).iter("node"):
            box = parse_bounds(element.get("bounds", ""))
            if box is not None:
                nodes.append(
                    Node(element.get("content-desc", ""), box, element.get("clickable") == "true")
                )
        return cls(nodes)

    @property
    def size(self) -> tuple[int, int]:
        """Return ``(width, height)`` covered by the elements, i.e. the screen size.

        Read from the dump because ``window_size()`` reports the landscape size when
        MuMu runs a tablet resolution with the app in portrait.
        """
        if not self.nodes:
            return 0, 0
        return max(n.box[2] for n in self.nodes), max(n.box[3] for n in self.nodes)
