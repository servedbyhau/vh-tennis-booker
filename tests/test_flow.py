"""Kiểm thử luồng với thiết bị giả (không cần MuMu)."""
import court_booker.flow as flow
from court_booker.config import Config
from court_booker.flow import Booker


class FakeEl:
    def __init__(self, dev, sel):
        self.dev, self.sel = dev, sel

    def _is_continue(self):
        return self.sel.get("description") == "Tiếp tục"

    def exists(self, timeout=0):
        if self._is_continue() or "descriptionMatches" in self.sel:
            return True
        return self.dev.slot_pos() is not None

    @property
    def info(self):
        if self._is_continue():
            return {"bounds": {"left": 20, "top": 890, "right": 520, "bottom": 945}}
        top, bottom = self.dev.slot_pos()
        return {"contentDescription": "14:00 - 15:00",
                "bounds": {"left": 200, "top": top, "right": 330, "bottom": bottom}}

    def click(self):
        self.dev.clicked = self.dev.slot_pos()


class FakeDevice:
    """Khung 14-15h: ban đầu chưa có; kéo 1 lần thì bị nút Tiếp tục che; kéo 2 lần thì hiện trọn."""

    POSITIONS = {0: None, 1: (870, 905), 2: (700, 735)}

    def __init__(self):
        self.swipes = 0
        self.clicked = None

    def slot_pos(self):
        return self.POSITIONS[min(self.swipes, 2)]

    def __call__(self, **sel):
        return FakeEl(self, sel)

    def window_size(self):
        return 540, 960

    def swipe(self, *a):
        self.swipes += 1


def test_pick_slot_scrolls_until_fully_visible(monkeypatch):
    monkeypatch.setattr(flow.time, "sleep", lambda s: None)
    dev = FakeDevice()
    Booker(dev, Config(), log=lambda m: None).pick_slot("14:00 - 15:00")
    assert dev.swipes == 2
    assert dev.clicked == (700, 735)
