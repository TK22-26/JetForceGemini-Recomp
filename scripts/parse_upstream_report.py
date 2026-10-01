#!/usr/bin/env python3
"""Validate an upstream progress report and return safe aggregate evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any


CATEGORY_ID_RE = re.compile(r"^[a-z][a-z0-9_-]{0,31}$")
COUNT_FIELDS = (
    "total_code",
    "matched_code",
    "total_data",
    "matched_data",
    "total_functions",
    "matched_functions",
    "total_units",
)
REQUIRED_TOTAL_FIELDS = (
    "total_code",
    "matched_code",
    "total_data",
    "matched_data",
    "total_functions",
    "matched_functions",
    "total_units",
)


def digest(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            hasher.update(block)
    return hasher.hexdigest()


def nonnegative_number(value: Any, label: str) -> int | float:
    if isinstance(value, bool):
        raise ValueError(f"{label} must be numeric")
    if isinstance(value, (int, float)):
        converted: int | float = value
    elif isinstance(value, str) and re.fullmatch(r"\d+(?:\.\d+)?", value):
        converted = float(value) if "." in value else int(value)
    else:
        raise ValueError(f"{label} must be a non-negative number")
    if converted < 0:
        raise ValueError(f"{label} must be non-negative")
    return converted


def validate_measures(
    value: Any,
    label: str,
    *,
    required: tuple[str, ...] = (),
) -> dict[str, int | float]:
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be an object")
    missing = [field for field in required if field not in value]
    if missing:
        raise ValueError(f"{label} is missing required measures: {', '.join(missing)}")

    safe: dict[str, int | float] = {}
    for field in COUNT_FIELDS:
        if field in value:
            converted = nonnegative_number(value[field], f"{label}.{field}")
            if isinstance(converted, float) and not converted.is_integer():
                raise ValueError(f"{label}.{field} must be an integer")
            safe[field] = int(converted)

    for field, raw in value.items():
        if not field.endswith("_percent"):
            continue
        converted = nonnegative_number(raw, f"{label}.{field}")
        if converted > 100:
            raise ValueError(f"{label}.{field} must be between 0 and 100")
        safe[field] = converted

    for base in ("code", "data", "functions"):
        total = safe.get(f"total_{base}")
        matched = safe.get(f"matched_{base}")
        if total is not None and matched is not None and matched > total:
            raise ValueError(f"{label}.matched_{base} exceeds total_{base}")
    return dict(sorted(safe.items()))


def validate_report(path: Path) -> dict[str, object]:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ValueError(f"upstream report could not be read: {error}") from error
    if not isinstance(document, dict):
        raise ValueError("upstream report must be an object")
    if document.get("version") != 2:
        raise ValueError("unsupported upstream report version")

    totals = validate_measures(
        document.get("measures"),
        "measures",
        required=REQUIRED_TOTAL_FIELDS,
    )
    categories_value = document.get("categories")
    if not isinstance(categories_value, list) or not categories_value:
        raise ValueError("categories must be a non-empty array")

    categories: list[dict[str, object]] = []
    seen_ids: set[str] = set()
    for index, category in enumerate(categories_value):
        if not isinstance(category, dict):
            raise ValueError(f"categories[{index}] must be an object")
        category_id = category.get("id")
        if not isinstance(category_id, str) or not CATEGORY_ID_RE.fullmatch(category_id):
            raise ValueError(f"categories[{index}].id is invalid")
        if category_id in seen_ids:
            raise ValueError(f"duplicate category id: {category_id}")
        seen_ids.add(category_id)
        measures = validate_measures(category.get("measures"), f"category.{category_id}")
        categories.append({"id": category_id, "measures": measures})

    if "overlays" not in seen_ids:
        raise ValueError("upstream report is missing the overlays category")
    overlay = next(category for category in categories if category["id"] == "overlays")
    overlay_measures = overlay["measures"]
    assert isinstance(overlay_measures, dict)
    if "total_units" not in overlay_measures:
        raise ValueError("overlays category is missing total_units")
    if overlay_measures["total_units"] != 155:
        raise ValueError("overlays category differs from the pinned 155-overlay baseline")

    # `units` contains source/function-level detail. It is deliberately neither
    # copied nor hashed independently; only the full private report hash survives.
    return {
        "schema_version": 1,
        "report_sha256": digest(path),
        "report_version": 2,
        "measures": totals,
        "categories": sorted(categories, key=lambda item: str(item["id"])),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("report", type=Path)
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    try:
        summary = validate_report(arguments.report)
    except ValueError as error:
        print(f"Upstream report validation failed: {error}", file=sys.stderr)
        return 1

    rendered = json.dumps(summary, indent=2, sort_keys=True) + "\n"
    if arguments.output:
        arguments.output.parent.mkdir(parents=True, exist_ok=True)
        arguments.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
