"""Log có mili-giây và thời gian từ dòng trước, để biết bước nào chậm."""
import time


class StepLog:
    def __init__(self) -> None:
        self._last = time.perf_counter()

    def __call__(self, msg: str) -> None:
        now = time.perf_counter()
        ms = int((time.time() % 1) * 1000)
        print(f"[{time.strftime('%H:%M:%S')}.{ms:03d} +{now - self._last:4.2f}s] {msg}", flush=True)
        self._last = now
