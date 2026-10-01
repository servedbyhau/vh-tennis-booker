"""Hàm thuần (không cần thiết bị): đọc khung bao, kiểm tra vị trí, mẫu ngày tháng.

Tách riêng để kiểm thử được mà không cần MuMu.
"""
from __future__ import annotations

import re
from datetime import date

Box = tuple[int, int, int, int]  # (x1, y1, x2, y2)

# Mô tả 1 ô ngày còn bấm được, ví dụ: "2, Thứ Sáu, 2 tháng 10, 2026"
DAY_RE = r"\d{1,2}, .*, \d{1,2} tháng \d{1,2}, \d{4}"
# Mô tả bất kỳ khung giờ nào, còn trống ("09:00 - 10:00") hoặc hết ("...\nHết chỗ")
SLOT_ANY_RE = r"(?s)\d{2}:\d{2} - \d{2}:\d{2}.*"


def parse_bounds(text: str) -> Box | None:
    """'[x1,y1][x2,y2]' -> (x1, y1, x2, y2)."""
    nums = re.findall(r"-?\d+", text or "")
    return tuple(map(int, nums)) if len(nums) == 4 else None  # type: ignore[return-value]


def box_from_info(b: dict) -> Box:
    """Khung bao dạng dict của uiautomator2 -> tuple."""
    return b["left"], b["top"], b["right"], b["bottom"]


def center(box: Box) -> tuple[int, int]:
    x1, y1, x2, y2 = box
    return (x1 + x2) // 2, (y1 + y2) // 2


def is_checkbox_beside(box: Box, label: Box, screen_w: int) -> bool:
    """Ô tick hợp lệ: nhỏ, nằm bên trái dòng chữ và ngang hàng với nó.

    Ngưỡng tính theo chiều rộng màn hình nên đúng ở mọi độ phân giải.
    """
    x1, y1, x2, y2 = box
    lx1, ly1, lx2, ly2 = label
    max_size = screen_w * 0.2
    gap = screen_w * 0.02
    small = 0 < x2 - x1 <= max_size and 0 < y2 - y1 <= max_size
    left_of = x2 <= lx1 + gap
    same_row = y1 < ly2 and y2 > ly1
    return small and left_of and same_row


def day_pattern(target: date) -> str:
    """Biểu thức khớp đúng mô tả ô ngày `target`."""
    return f"{target.day}, .*, {target.day} tháng {target.month}, {target.year}"


def month_index(year: int, month: int) -> int:
    return year * 12 + month


def month_from_desc(desc: str) -> int | None:
    """Đọc tháng/năm từ mô tả ô ngày -> chỉ số tháng, hoặc None."""
    m = re.search(r"tháng (\d{1,2}), (\d{4})", desc or "")
    return month_index(int(m.group(2)), int(m.group(1))) if m else None
