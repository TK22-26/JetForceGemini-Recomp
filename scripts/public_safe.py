#!/usr/bin/env python3
"""Shared fail-closed checks for public aggregate JSON documents."""

from __future__ import annotations

import re


FORBIDDEN_KEYS = frozenset(
    {
        "absolute_path",
        "address",
        "body",
        "buffer",
        "descriptor",
        "dmem",
        "file",
        "imem",
        "path",
        "raw_address",
        "raw_bytes",
        "rom",
        "rom_bytes",
        "source_name",
        "symbol",
        "ucode_body",
    }
)

# These checks intentionally favor false positives in public evidence over the
# accidental publication of private paths, target coordinates, or encoded body
# data. Dedicated digest fields remain usable because the payload rules begin
# above the repository's longest approved digest (SHA-256).
PRIVATE_TEXT_PATTERNS = (
    re.compile(r"[A-Z]:[\\/]", re.IGNORECASE),
    re.compile(r"(?:^|\s)\\\\[^\\\s]+\\[^\\\s]+", re.IGNORECASE),
    re.compile(r"/(?:home|users|mnt)/[^\s]*", re.IGNORECASE),
    re.compile(
        r"(?:^|\s)/(?:[A-Za-z0-9._-]+/)+[A-Za-z0-9._-]+(?:\.[A-Za-z0-9._-]+)?"
    ),
    re.compile(
        r"(?:^|[\\/])(?:tools|roms|private-data|extracted|generated|"
        r"build|src|ver)(?:[\\/]|$)",
        re.IGNORECASE,
    ),
    re.compile(r"\b(?:func|d)_[0-9a-f]{6,}\b", re.IGNORECASE),
    re.compile(r"\b0x[0-9a-f]{6,}\b", re.IGNORECASE),
    re.compile(r"(?<![0-9a-z])[0-9a-f]{8,16}(?![0-9a-z])", re.IGNORECASE),
    re.compile(
        r"(?<![0-9a-f])(?:[0-9a-f]{2}[\s,:-]+){7,}[0-9a-f]{2}"
        r"(?![0-9a-f])",
        re.IGNORECASE,
    ),
    re.compile(r"(?<![0-9a-f])[0-9a-f]{96,}(?![0-9a-f])", re.IGNORECASE),
    re.compile(
        r"(?<![a-z0-9+/])[a-z0-9+/]{96,}={0,2}(?![a-z0-9+/=])",
        re.IGNORECASE,
    ),
    re.compile(r"\bdata:[^\s,;]+[;,]", re.IGNORECASE),
)


def _normalized_key(key: object) -> str:
    return str(key).casefold().replace("-", "_")


def validate_public_safe(value: object, location: str = "$") -> list[str]:
    """Reject private-detail fields and strings throughout a JSON-like value."""
    errors: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            child_location = f"{location}.{key}"
            if _normalized_key(key) in FORBIDDEN_KEYS:
                errors.append(f"{child_location}: forbidden private-body field")
            errors.extend(validate_public_safe(child, child_location))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            errors.extend(validate_public_safe(child, f"{location}[{index}]"))
    elif isinstance(value, str):
        if any(pattern.search(value) for pattern in PRIVATE_TEXT_PATTERNS):
            errors.append(
                f"{location}: contains private-path or raw-symbol detail, "
                "target-coordinate, or encoded-body detail"
            )
    return errors


def validate_canonical_json_numbers(value: object, location: str = "$") -> list[str]:
    """Reject non-integral JSON number representations from aggregate evidence.

    JSON Schema deliberately considers ``9.0`` an integer. These documents use
    counts and byte sizes only, so accepting a floating-point token would let
    Python-side integer invariants silently skip the value.
    """
    errors: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            errors.extend(validate_canonical_json_numbers(child, f"{location}.{key}"))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            errors.extend(validate_canonical_json_numbers(child, f"{location}[{index}]"))
    elif isinstance(value, float):
        errors.append(f"{location}: JSON numbers must use canonical integer tokens")
    return errors
