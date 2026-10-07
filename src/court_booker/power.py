"""Keep Windows awake during a run started by a wake timer."""

from __future__ import annotations

import sys
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Callable

# A PC woken by a scheduled task falls back to sleep after about two idle minutes
# unless a program asks to keep the system awake.
ES_CONTINUOUS = 0x80000000
ES_SYSTEM_REQUIRED = 0x00000001

SetState = Callable[[int], int]


@contextmanager
def keep_awake(set_state: SetState | None = None) -> Iterator[None]:
    """Prevent system sleep inside the block; a no-op outside Windows."""
    if set_state is None:
        if sys.platform != "win32":
            yield
            return
        import ctypes

        set_state = ctypes.windll.kernel32.SetThreadExecutionState
    set_state(ES_CONTINUOUS | ES_SYSTEM_REQUIRED)
    try:
        yield
    finally:
        set_state(ES_CONTINUOUS)
