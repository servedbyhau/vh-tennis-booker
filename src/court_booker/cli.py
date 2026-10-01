"""Dòng lệnh: court-booker [--dry-run] [--days N] [--slots ...] [--config FILE]"""
from __future__ import annotations

import argparse
import sys
import time
from datetime import date, timedelta

from . import __version__
from .config import load_config
from .flow import Booker
from .log import StepLog


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="court-booker", description="Đặt sân tennis Vinhomes Resident qua UI.")
    ap.add_argument("--config", default="config.toml", help="file cấu hình (mặc định: config.toml nếu có)")
    ap.add_argument("--dry-run", action="store_true", help="chạy thử, không bấm 'Xác nhận' cuối cùng")
    ap.add_argument("--days", type=int, help="đặt trước mấy ngày")
    ap.add_argument("--slots", nargs="+", help='khung giờ, ví dụ: --slots "18:00 - 19:00" "19:00 - 20:00"')
    ap.add_argument("--device", help="địa chỉ ADB, ví dụ 127.0.0.1:7555")
    ap.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return ap


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    cfg = load_config(args.config)
    if args.days is not None:
        cfg.days_ahead = args.days
    if args.slots:
        cfg.slots = args.slots
    if args.device:
        cfg.device = args.device

    import uiautomator2 as u2  # import muộn để kiểm thử không cần thư viện này

    log = StepLog()
    log(f"court-booker {__version__} | Kết nối {cfg.device} ...")
    d = u2.connect(cfg.device)
    booker = Booker(d, cfg, log)

    if d.app_current().get("package") != cfg.package:
        log("Mở app ...")
        d.app_start(cfg.package)
        d(**booker.sel_home).wait(timeout=cfg.timeout * 2)

    target = date.today() + timedelta(days=cfg.days_ahead)
    log(f"Ngày đặt: {target:%d/%m/%Y} | Giờ: {', '.join(cfg.slots)}" + ("  [DRY-RUN]" if args.dry_run else ""))

    results = []
    for n, slot in enumerate(cfg.slots, 1):
        log(f"===== LƯỢT {n}/{len(cfg.slots)}: {slot} =====")
        t0 = time.perf_counter()
        try:
            booker.run_round(slot, target, args.dry_run)
            results.append((slot, True, "THÀNH CÔNG", time.perf_counter() - t0))
        except Exception as e:  # lượt sau vẫn chạy
            log(f"LỖI: {e}")
            results.append((slot, False, f"LỖI: {e}", time.perf_counter() - t0))

    print("\n=========== KẾT QUẢ ===========")
    for slot, _, status, secs in results:
        print(f"{slot}: {status}  ({secs:.1f}s)")
    return 0 if all(ok for _, ok, _, _ in results) else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(130)
