"""Bounded atomic publication in the presence of short-lived Windows readers."""
from __future__ import annotations

import os
from pathlib import Path
import time


def replace(source: Path, destination: Path, *, timeout: float = 0.5) -> None:
    """Keep the previous complete file until replacement succeeds or fails.

    Ordinary Windows file readers may omit FILE_SHARE_DELETE, temporarily
    denying MoveFileEx. Retry only Windows access/sharing/lock errors, within
    a short fixed budget. Persistent permissions errors still propagate;
    never delete/truncate the published file as a fallback.
    """
    if not 0 <= timeout <= 1:
        raise ValueError("atomic replace retry budget must be 0..1 seconds")
    deadline = time.monotonic() + timeout
    while True:
        try:
            source.replace(destination)
            return
        except OSError as error:
            remaining = deadline - time.monotonic()
            if os.name != "nt" or getattr(error, "winerror", None) not in (5, 32, 33) or remaining <= 0:
                raise
            time.sleep(min(0.01, remaining))
