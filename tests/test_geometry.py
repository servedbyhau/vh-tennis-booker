import re
from datetime import date

from court_booker.geometry import (
    day_pattern,
    is_checkbox_beside,
    month_from_desc,
    month_index,
    parse_bounds,
)

W = 540  # MuMu 540x960
LABEL = (79, 739, 313, 772)  # "Tôi đã hiểu và đồng ý với " (dữ liệu thật)


def test_parse_bounds():
    assert parse_bounds("[35,740][79,784]") == (35, 740, 79, 784)
    assert parse_bounds("") is None


def test_checkbox_real_layout_is_accepted():
    assert is_checkbox_beside((35, 740, 79, 784), LABEL, W)


def test_back_button_and_frames_are_rejected():
    assert not is_checkbox_beside((0, 40, 60, 100), LABEL, W)     # nút Back góc trên
    assert not is_checkbox_beside((0, 721, 540, 869), LABEL, W)   # khung lớn bao quanh
    assert not is_checkbox_beside((0, 0, 540, 960), LABEL, W)     # toàn màn hình


def test_checkbox_scales_with_resolution():
    k = 1440 / 540
    scaled = lambda b: tuple(int(v * k) for v in b)  # noqa: E731
    assert is_checkbox_beside(scaled((35, 740, 79, 784)), scaled(LABEL), 1440)


def test_day_pattern_matches_exact_day_only():
    p = day_pattern(date(2026, 10, 3))
    assert re.fullmatch(p, "3, Thứ Bảy, 3 tháng 10, 2026")
    assert not re.fullmatch(p, "13, Thứ Ba, 13 tháng 10, 2026")


def test_day_pattern_month_and_year_rollover():
    assert re.fullmatch(day_pattern(date(2026, 11, 1)), "1, Chủ Nhật, 1 tháng 11, 2026")
    assert re.fullmatch(day_pattern(date(2027, 1, 1)), "1, Thứ Sáu, 1 tháng 1, 2027")


def test_month_from_desc():
    assert month_from_desc("2, Thứ Sáu, 2 tháng 10, 2026") == month_index(2026, 10)
    assert month_from_desc("không có ngày") is None
