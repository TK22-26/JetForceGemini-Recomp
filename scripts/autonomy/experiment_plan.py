"""Typed, read-only experiment proposals; model output is never a command."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re


SCHEMA_FILE = Path(__file__).with_name("experiment.schema.json")
LABEL = re.compile(r"[a-z][a-z0-9_]{0,47}\Z")
ADDRESS = re.compile(r"0x80[0-3][0-9a-f]{5}\Z")
MAX_WORD_ROUNDS = 3


def contract(window, history=()):
    history = [plan for plan in history if plan["operation"] == "state-words"]
    result = {"version": 1, "schema_sha256": hashlib.sha256(SCHEMA_FILE.read_bytes()).hexdigest(),
              "focus_updates": list(window)}
    if history:
        locations = sorted({(item["address"], item["width"]) for plan in history
                            for item in plan["observations"]})
        result.update(version=2, round=len(history) + 1,
                      prior_reads=[{"address": address, "width": width} for address, width in locations])
    return result


def read_bytes(item):
    address, width = item.get("address"), item.get("width")
    if (not isinstance(address, str) or not ADDRESS.fullmatch(address) or
            type(width) is not int or width not in (1, 2, 4)):
        raise ValueError("experiment observation is not a typed RDRAM read")
    start = int(address, 16)
    if start % width or start + width > 0x80400000:
        raise ValueError("experiment observation is misaligned or outside RDRAM")
    return set(range(start, start + width))


def validate_contract(value):
    if not isinstance(value, dict):
        raise ValueError("experiment contract is unsupported or changed")
    fields = {"version", "schema_sha256", "focus_updates"}
    if value.get("version") == 2:
        fields.update(("round", "prior_reads"))
    if (set(value) != fields or
            type(value["version"]) is not int or value["version"] not in (1, 2) or
            value["schema_sha256"] != hashlib.sha256(SCHEMA_FILE.read_bytes()).hexdigest()):
        raise ValueError("experiment contract is unsupported or changed")
    window = value["focus_updates"]
    if (not isinstance(window, list) or len(window) != 2 or
            any(type(number) is not int for number in window) or
            not 1 <= window[0] <= window[1] <= 1_000_000 or window[1] - window[0] >= 16):
        raise ValueError("experiment window must contain 1..16 completed updates")
    if value["version"] == 2:
        prior = value["prior_reads"]
        if (type(value["round"]) is not int or not 2 <= value["round"] <= MAX_WORD_ROUNDS + 1 or
                not isinstance(prior, list) or not 1 <= len(prior) <= 12 * (value["round"] - 1)):
            raise ValueError("experiment history budget is invalid")
        locations = []
        for item in prior:
            if not isinstance(item, dict) or set(item) != {"address", "width"}:
                raise ValueError("experiment history read is invalid")
            read_bytes(item)
            locations.append((item["address"], item["width"]))
        if locations != sorted(set(locations)):
            raise ValueError("experiment history reads must be canonical and unique")


def validate(plan, context):
    validate_contract(context)
    if (not isinstance(plan, dict) or set(plan) != {
            "operation", "hypothesis", "alternative", "reason", "observations", "prediction"} or
            plan["operation"] not in ("state-words", "needs-instrumentation") or
            any(not isinstance(plan[key], str) or not 1 <= len(plan[key]) <= 600
                for key in ("hypothesis", "alternative", "reason"))):
        raise ValueError("experiment plan fields are invalid")
    observations = plan["observations"]
    if not isinstance(observations, list) or len(observations) > 12:
        raise ValueError("experiment needs at most twelve observations")
    labels, locations = set(), set()
    for item in observations:
        if (not isinstance(item, dict) or set(item) != {"label", "address", "width"} or
                not isinstance(item["label"], str) or not LABEL.fullmatch(item["label"]) or
                not isinstance(item["address"], str) or not ADDRESS.fullmatch(item["address"]) or
                type(item["width"]) is not int or item["width"] not in (1, 2, 4)):
            raise ValueError("experiment observation is not a typed RDRAM read")
        address, width = int(item["address"], 16), item["width"]
        if (address % width or address + width > 0x80400000 or
                item["label"] in labels or (address, width) in locations):
            raise ValueError("experiment observation is misaligned, repeated or outside RDRAM")
        labels.add(item["label"])
        locations.add((address, width))
    prediction = plan["prediction"]
    if plan["operation"] == "needs-instrumentation":
        if observations or prediction is not None:
            raise ValueError("unsupported experiment cannot request observations")
    elif (not observations or not isinstance(prediction, dict) or
          set(prediction) != {"label", "update", "relation"} or
          not isinstance(prediction["label"], str) or prediction["label"] not in labels or
          type(prediction["update"]) is not int or
          not context["focus_updates"][0] <= prediction["update"] <= context["focus_updates"][1] or
          prediction["relation"] not in ("equal", "different")):
        raise ValueError("experiment prediction does not select a bounded observation")
    if plan["operation"] == "state-words" and context["version"] == 2:
        if context["round"] > MAX_WORD_ROUNDS:
            raise ValueError("state-word round budget exhausted; needs instrumentation")
        known = set().union(*(read_bytes(item) for item in context["prior_reads"]))
        target = next(item for item in observations if item["label"] == prediction["label"])
        if read_bytes(target) <= known:
            raise ValueError("experiment prediction repeats previously measured bytes")
    return plan


def read(path: Path, context):
    if path.stat().st_size > 16_384:
        raise ValueError("experiment plan exceeds size limit")
    return validate(json.loads(path.read_text(encoding="utf-8")), context)
