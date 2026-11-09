#!/usr/bin/env python3
"""Strict owner-attributed acceptance policy for the Phase 4 architecture ADR."""

from __future__ import annotations

# Support direct execution from any working directory after domain organization.
if __package__ in (None, ""):
    import sys as _sys
    from pathlib import Path as _Path
    _sys.path.insert(0, str(_Path(__file__).resolve().parents[2]))
    __package__ = "scripts"


import re


ACCEPTED_STATUS_LINE = "- Status: Accepted by `TK22-26`"


def accepted_architecture_decision(text: str) -> bool:
    if not isinstance(text, str) or "\x00" in text:
        return False
    lines = text.replace("\r\n", "\n").splitlines()
    if not lines or not re.fullmatch(r"# [^#].*", lines[0]):
        return False
    index = 1
    while index < len(lines) and not lines[index].strip():
        index += 1
    status_lines = [
        line
        for line in lines
        if line.lstrip().startswith("- Status:")
    ]
    return (
        index < len(lines)
        and lines[index] == ACCEPTED_STATUS_LINE
        and status_lines == [ACCEPTED_STATUS_LINE]
    )
