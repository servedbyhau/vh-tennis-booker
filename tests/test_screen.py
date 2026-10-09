"""Tests for parsing hierarchy dumps."""

from court_booker.screen import Screen

DUMP = """<?xml version='1.0' encoding='UTF-8' standalone='yes' ?>
<hierarchy rotation="0">
  <node content-desc="" bounds="[0,0][540,1600]" clickable="false">
    <node content-desc="18:00 - 19:00&#10;Hết chỗ" bounds="[38,1178][263,1262]" clickable="true" />
    <node content-desc="Tiếp tục" bounds="[35,1490][505,1584]" clickable="true" />
    <node content-desc="Xác nhận" bounds="[35,1490][505,1584]" clickable="false" />
    <node content-desc="no bounds" />
  </node>
</hierarchy>"""


def test_parse_keeps_labels_bounds_and_clickable():
    screen = Screen.parse(DUMP)

    assert [n.desc for n in screen.nodes] == ["", "18:00 - 19:00\nHết chỗ", "Tiếp tục", "Xác nhận"]
    assert screen.nodes[1].box == (38, 1178, 263, 1262)
    assert screen.nodes[2].clickable is True
    assert screen.nodes[3].clickable is False


def test_size_is_read_from_the_dump():
    assert Screen.parse(DUMP).size == (540, 1600)
    assert Screen([]).size == (0, 0)
