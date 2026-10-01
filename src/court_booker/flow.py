"""Luồng đặt sân: mỗi hàm tương ứng một màn hình trong app.

Mọi nút được tìm theo chữ (content-desc) tại thời điểm chạy; không dùng tọa độ cố định.
`d` là đối tượng thiết bị của uiautomator2 (hoặc đối tượng giả trong kiểm thử).
"""
from __future__ import annotations

import time
import xml.etree.ElementTree as ET
from datetime import date

from .config import Config
from .geometry import (
    DAY_RE,
    SLOT_ANY_RE,
    box_from_info,
    center,
    day_pattern,
    is_checkbox_beside,
    month_from_desc,
    month_index,
    parse_bounds,
)


class BookingError(RuntimeError):
    """Lỗi trong một lượt đặt; lượt sau vẫn chạy tiếp."""


class Booker:
    def __init__(self, d, cfg: Config, log=print) -> None:
        self.d = d
        self.cfg = cfg
        self.log = log
        self._wh: tuple[int, int] | None = None
        lb = cfg.labels
        self.sel_home = dict(description=lb.home, clickable=True)
        self.sel_utility = dict(description=lb.utility, clickable=True)
        self.sel_calendar = [
            dict(description=lb.prev_month),
            dict(descriptionContains=lb.next_month),
            dict(descriptionMatches=DAY_RE),
        ]
        self.sel_continue = dict(description=lb.continue_, clickable=True)
        self.sel_venue = dict(descriptionContains=cfg.venue_keyword)
        self.sel_court = dict(description=cfg.court, clickable=True)
        self.sel_confirm_page = dict(description=lb.confirm_page)

    # ------------------------------------------------------------------ chung
    def screen_size(self) -> tuple[int, int]:
        if self._wh is None:
            self._wh = self.d.window_size()
        return self._wh

    def wait_any(self, sels: list[dict], timeout: float) -> dict | None:
        """Chờ tới khi một trong các selector xuất hiện."""
        end = time.time() + timeout
        while True:
            for s in sels:
                if self.d(**s).exists(timeout=0):
                    return s
            if time.time() >= end:
                return None
            time.sleep(0.05)

    def go(self, label: str, sel: dict, next_label: str, next_sels: list[dict], tries: int = 5) -> None:
        """Chờ nút -> bấm ngay -> chờ màn kế tiếp; app lag làm bấm hụt thì bấm lại."""
        if not self.d(**sel).wait(timeout=self.cfg.timeout):
            raise BookingError(f"Không thấy nút '{label}'")
        for i in range(tries):
            if i == 0 or self.d(**sel).exists(timeout=0):
                self.d(**sel).click()
            if self.wait_any(next_sels, 2):
                self.log(f"OK  {label}")
                return
        raise BookingError(f"Đã bấm '{label}' nhưng không sang được màn '{next_label}'")

    def scroll(self, down: bool = True) -> None:
        """Kéo nhẹ màn hình (vuốt chậm để không trôi quá đà)."""
        w, h = self.screen_size()
        y1, y2 = (0.62, 0.38) if down else (0.38, 0.62)
        self.d.swipe(w * 0.5, h * y1, w * 0.5, h * y2, 0.25)
        time.sleep(0.15)

    def where_on_screen(self, el) -> str:
        """'ok' nếu phần tử nằm trọn trong vùng bấm được, 'below' / 'above' nếu bị khuất
        (kể cả bị nút 'Tiếp tục' cố định ở đáy che)."""
        _, h = self.screen_size()
        b = el.info["bounds"]
        bottom_limit = h
        cont = self.d(description=self.cfg.labels.continue_)
        if cont.exists(timeout=0):
            bottom_limit = min(bottom_limit, cont.info["bounds"]["top"])
        if b["bottom"] > bottom_limit - 4:
            return "below"
        if b["top"] < int(h * 0.10):
            return "above"
        return "ok"

    # --------------------------------------------------------- màn lịch
    def _shown_month(self) -> int | None:
        el = self.d(descriptionMatches=DAY_RE)
        if not el.exists(timeout=0):
            return None
        return month_from_desc(el.info.get("contentDescription", ""))

    def _click_month(self, forward: bool) -> None:
        lb = self.cfg.labels
        if forward:
            btn, xy = self.d(descriptionContains=lb.next_month), self.cfg.next_month_xy
        else:
            btn, xy = self.d(description=lb.prev_month), self.cfg.prev_month_xy
        if btn.exists(timeout=0):
            btn.click()
        else:
            self.d.click(*xy)
        self.log("... Sang tháng sau" if forward else "... Về tháng trước")

    def pick_date(self, target: date) -> None:
        """Chọn ngày; lịch đang ở tháng khác thì tự bấm < hoặc >."""
        pattern = day_pattern(target)
        target_m = month_index(target.year, target.month)
        for i in range(5):
            el = self.d(descriptionMatches=pattern)
            if el.wait(timeout=1.5 if i == 0 else 0.8):
                el.click()
                self.log(f"OK  Chọn ngày {target:%d/%m/%Y}")
                return
            cur = self._shown_month()
            self._click_month((i % 2 == 0) if cur is None else (cur < target_m))
        raise BookingError(f"Không thấy ngày {target:%d/%m/%Y} (có thể chưa mở đặt)")

    def pick_slot(self, slot: str) -> None:
        """Chọn khung giờ; khuất dưới thì tự kéo, chỉ bấm khi hiện trọn."""
        end = time.time() + self.cfg.timeout
        swipes = 0
        while time.time() < end:
            el = self.d(descriptionStartsWith=slot)
            if el.exists(timeout=0):
                if self.cfg.labels.full in (el.info.get("contentDescription") or ""):
                    raise BookingError(f"Khung giờ {slot} đã HẾT CHỖ")
                pos = self.where_on_screen(el)
                if pos == "ok":
                    el.click()
                    self.log(f"OK  Chọn khung giờ {slot}" + (f" (đã kéo {swipes} lần)" if swipes else ""))
                    return
                down = pos == "below"
            elif self.d(descriptionMatches=SLOT_ANY_RE).exists(timeout=0):
                down = True  # danh sách giờ đã hiện nhưng chưa thấy khung này
            else:
                time.sleep(0.2)  # danh sách giờ chưa load xong
                continue
            if swipes >= self.cfg.max_swipes:
                break
            self.scroll(down)
            swipes += 1
        raise BookingError(f"Không thấy khung giờ {slot} (đã kéo {swipes} lần)")

    # ------------------------------------------------- màn xác nhận đăng ký
    def find_checkbox(self) -> tuple[str | None, tuple[int, int] | None]:
        """Ô tick = phần tử nhỏ bên trái, ngang hàng dòng chữ 'Tôi đã hiểu...'.
        Không bao giờ trả về phần tử không ngang hàng -> không bấm nhầm nút khác."""
        label_el = self.d(descriptionContains=self.cfg.labels.agree)
        if not label_el.exists(timeout=0):
            return None, None
        label = box_from_info(label_el.info["bounds"])
        w, _ = self.screen_size()

        # Cách 1 (nhanh): phần tử bấm được gần nhất bên trái dòng chữ
        try:
            box_el = label_el.left(clickable=True)
        except Exception:
            box_el = None
        if box_el is not None and box_el.exists(timeout=0):
            box = box_from_info(box_el.info["bounds"])
            if is_checkbox_beside(box, label, w):
                return f"phần tử ô tick {list(box)}", center(box)

        # Cách 2 (dự phòng): quét toàn bộ cấu trúc màn hình
        root = ET.fromstring(self.d.dump_hierarchy(compressed=False))
        cands = []
        for n in root.iter("node"):
            b = parse_bounds(n.get("bounds", ""))
            if b and is_checkbox_beside(b, label, w):
                score = (0 if n.get("clickable") == "true" else 1, (b[2] - b[0]) * (b[3] - b[1]))
                cands.append((score, b))
        if cands:
            b = min(cands)[1]
            return f"quét màn hình {list(b)}", center(b)
        return None, None

    def tick_and_confirm(self, dry_run: bool) -> None:
        """Tick ô đồng ý (nhớ vị trí khi bấm lại), chỉ coi là xong khi nút Xác nhận sáng."""
        lb = self.cfg.labels
        confirm = self.d(description=lb.confirm, clickable=True)
        self.d(description=lb.confirm).wait(timeout=self.cfg.timeout)

        end = time.time() + self.cfg.timeout
        xy = None
        while time.time() < end:
            if xy is None:
                way, xy = self.find_checkbox()
                if xy is None:
                    time.sleep(0.2)
                    continue
                self.log(f"... Ô tick: {way} -> bấm {xy}")
            self.d.click(*xy)
            if confirm.wait(timeout=0.8):
                break
        else:
            if xy is None:
                raise BookingError("Không tìm thấy ô tick trên màn hình (không bấm gì)")
            raise BookingError("Đã bấm ô tick nhưng nút Xác nhận vẫn mờ")
        self.log("OK  Đã tick đồng ý")
        if dry_run:
            self.log("--  DRY-RUN: dừng, KHÔNG bấm 'Xác nhận'")
            return
        confirm.click()
        self.log("OK  Bấm Xác nhận")
        # Chờ sang màn vé: chắc chắn app đã nhận đặt chỗ, không Back cắt ngang
        if not self.d(**self.sel_confirm_page).wait_gone(timeout=self.cfg.timeout):
            raise BookingError("Đã bấm Xác nhận nhưng app chưa chuyển sang màn vé")
        self.log("OK  Đã sang màn vé")

    # ------------------------------------------------------------- điều hướng
    def back_to_utilities(self) -> None:
        """Về 'Danh sách tiện ích' (thấy 'Sân Tennis'): từ màn vé chỉ cần Back 1 lần,
        ở màn hình đầu thì bấm 'Tiện ích'."""
        for _ in range(8):
            if self.d(**self.sel_utility).exists(timeout=0):
                return
            if self.d(**self.sel_home).exists(timeout=0):
                self.go(self.cfg.labels.home, self.sel_home, "Danh sách tiện ích", [self.sel_utility])
                return
            self.d.press("back")
            self.wait_any([self.sel_utility, self.sel_home], 1.5)
        raise BookingError("Không quay về được màn 'Danh sách tiện ích'")

    def run_round(self, slot: str, target: date, dry_run: bool) -> None:
        cfg = self.cfg
        self.back_to_utilities()
        self.go(cfg.labels.utility, self.sel_utility, "Đăng ký tiện ích (lịch)", self.sel_calendar)
        self.pick_date(target)
        self.pick_slot(slot)
        self.go(cfg.labels.continue_, self.sel_continue, "chọn sân", [self.sel_venue, self.sel_court])
        if self.d(**self.sel_venue).exists(timeout=0):  # màn "Origami_ Sân tennis" (nếu có)
            self.go(cfg.venue_keyword, self.sel_venue, "chọn sân", [self.sel_court])
        self.go(cfg.court, self.sel_court, "thông tin đặt chỗ", [self.sel_continue])
        self.go(cfg.labels.continue_, self.sel_continue, "Xác nhận đăng ký", [self.sel_confirm_page])
        self.tick_and_confirm(dry_run)
