"""Tests for parsing hierarchy dumps and matching labels."""

from court_booker.screen import Match, Node, Screen

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


LOGIN_DUMP = """<hierarchy><node content-desc="" bounds="[0,0][540,1600]" clickable="false">
  <node text="0900000079" class="android.widget.EditText" content-desc=""
        bounds="[35,426][505,492]" clickable="true" editable="true" password="false" />
  <node text="••••••••" class="android.widget.EditText" content-desc=""
        bounds="[35,539][505,605]" clickable="true" editable="true" password="true" />
  <node text="" class="android.view.View" content-desc="Đăng nhập"
        bounds="[35,797][505,892]" clickable="false" editable="false" password="false" />
</node></hierarchy>"""


def test_the_driver_s_fields_and_password_are_kept_but_not_their_text():
    screen = Screen.parse(LOGIN_DUMP)

    phone, password, button = screen.nodes[1:]
    assert (phone.field, phone.password) == (True, False)
    assert (password.field, password.password) == (True, True)
    assert (button.field, button.password) == (False, False)
    described = "\n".join(screen.describe())
    assert "[35,426][505,492] clickable field ''" in described
    assert "[35,539][505,605] clickable password ''" in described
    assert "0900000079" not in described


def test_a_uiautomator2_field_is_told_by_its_class():
    dump = LOGIN_DUMP.replace(' editable="true"', "")

    assert Screen.parse(dump).nodes[1].field is True


def test_size_is_read_from_the_dump():
    assert Screen.parse(DUMP).size == (540, 1600)
    assert Screen([]).size == (0, 0)


def test_match_criteria():
    slot = Node("18:00 - 19:00\nHết chỗ", (38, 1178, 263, 1262), True)

    assert Match(prefix="18:00 - 19:00")(slot)
    assert Match(contains="Hết chỗ")(slot)
    assert Match(pattern=r"\d{2}:\d{2} - \d{2}:\d{2}.*")(slot)
    assert not Match(pattern=r"\d{2}:\d{2}")(slot)
    assert not Match(desc="18:00 - 19:00")(slot)
    assert not Match(prefix="18:00 - 19:00", clickable=False)(slot)


def test_find_respects_clickable():
    screen = Screen.parse(DUMP)

    assert screen.find(Match(desc="Xác nhận", clickable=True)) is None
    assert screen.find(Match(desc="Tiếp tục")).center == (270, 1537)
    assert len(screen.find_all(Match(prefix="18:00"))) == 1


def test_describe_lists_labelled_and_clickable_elements():
    screen = Screen.parse(DUMP)
    screen.nodes.append(Node("", (480, 180, 520, 220), True))

    assert screen.describe() == [
        "[38,1178][263,1262] clickable '18:00 - 19:00\\nHết chỗ'",
        "[35,1490][505,1584] clickable 'Tiếp tục'",
        "[35,1490][505,1584] 'Xác nhận'",
        "[480,180][520,220] clickable ''",
    ]
    assert Screen([]).describe() == []


def test_line_after_reads_the_value_under_a_caption():
    details = Node(
        "Sân Tennis\nVị trí/dịch vụ\nS6 - Sân tennis\nTổng tiền", (0, 210, 540, 775), False
    )
    screen = Screen([Node("Vị trí/dịch vụ", (0, 0, 10, 10), False), details])

    assert screen.line_after("Vị trí/dịch vụ") == "S6 - Sân tennis"
    assert screen.line_after("Tổng tiền") is None
    assert screen.line_after("Vị trí") is None
