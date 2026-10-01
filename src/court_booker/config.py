"""Cấu hình: giá trị mặc định, có thể ghi đè bằng file config.toml."""
from __future__ import annotations

import sys
from dataclasses import dataclass, field, fields
from pathlib import Path

if sys.version_info >= (3, 11):
    import tomllib
else:  # pragma: no cover
    import tomli as tomllib


@dataclass
class Labels:
    """Chữ hiển thị trong app. App đổi chữ/ngôn ngữ thì chỉ cần sửa ở đây."""

    home: str = "Tiện ích"
    utility: str = "Sân Tennis"
    continue_: str = "Tiếp tục"
    confirm: str = "Xác nhận"
    confirm_page: str = "Xác nhận đăng ký"
    prev_month: str = "Tháng trước"
    next_month: str = "Tháng sau"
    agree: str = "Tôi đã hiểu"
    full: str = "Hết chỗ"


@dataclass
class Config:
    device: str = "127.0.0.1:7555"
    package: str = "com.vinhomes.resident"
    days_ahead: int = 2
    slots: list[str] = field(default_factory=lambda: ["11:00 - 12:00", "14:00 - 15:00"])
    court: str = "S10 - Sân tennis"
    venue_keyword: str = "Origami"
    timeout: float = 10.0
    max_swipes: int = 6
    # Dự phòng khi nút tháng bị mờ (không có mô tả): tỉ lệ màn hình
    next_month_xy: tuple[float, float] = (0.953, 0.122)
    prev_month_xy: tuple[float, float] = (0.873, 0.122)
    labels: Labels = field(default_factory=Labels)


def load_config(path: str | Path | None) -> Config:
    """Đọc config.toml (nếu có) và ghi đè lên giá trị mặc định."""
    cfg = Config()
    if path is None:
        return cfg
    path = Path(path)
    if not path.exists():
        return cfg
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    known = {f.name for f in fields(Config)} - {"labels"}
    for key, value in data.items():
        if key == "labels":
            for lk, lv in value.items():
                attr = "continue_" if lk == "continue" else lk
                if not hasattr(cfg.labels, attr):
                    raise ValueError(f"config: không có nhãn '{lk}'")
                setattr(cfg.labels, attr, lv)
        elif key in known:
            setattr(cfg, key, tuple(value) if key.endswith("_xy") else value)
        else:
            raise ValueError(f"config: không có mục '{key}'")
    return cfg
