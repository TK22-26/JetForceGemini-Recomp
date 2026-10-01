"""Bounded all-thread observations between consecutive qualified calls."""
import hashlib
import json
import re
from pathlib import Path

from scripts.autonomy.point_plan import validate_probe

SCHEMA_FILE = Path(__file__).with_name("interval_plan.schema.json")
MAX_ROUNDS = 3


def contract(window, runtime_sha256, history=(), known_counts=()):
    previous = [item for item in history if item["operation"] == "interval-state"]
    return {"version": 1, "schema_sha256": hashlib.sha256(SCHEMA_FILE.read_bytes()).hexdigest(),
            "focus_updates": list(window), "runtime_manifest_sha256": runtime_sha256,
            "round": len(previous) + 1, "prior_experiments": previous,
            "known_counts": list(known_counts)}


def selector(value, probe):
    if (not isinstance(value, dict) or set(value) != {"pc", "register", "value_lo"} or
            value["pc"] not in probe["pcs"] or type(value["register"]) is not int or
            not 0 <= value["register"] <= 31 or not isinstance(value["value_lo"], str) or
            not re.fullmatch(r"0x[0-9a-f]{8}", value["value_lo"])):
        raise ValueError("interval selector must name a captured PC and bounded GPR low word")


def validate_contract(context):
    if (not isinstance(context, dict) or set(context) != {"version", "schema_sha256", "focus_updates",
            "runtime_manifest_sha256", "round", "prior_experiments", "known_counts"} or
            type(context["version"]) is not int or context["version"] != 1 or
            context["schema_sha256"] != hashlib.sha256(SCHEMA_FILE.read_bytes()).hexdigest() or
            not isinstance(context["runtime_manifest_sha256"], str) or
            not re.fullmatch(r"[0-9a-f]{64}", context["runtime_manifest_sha256"])):
        raise ValueError("interval experiment contract changed")
    window = context["focus_updates"]
    if (not isinstance(window, list) or len(window) != 2 or any(type(n) is not int for n in window) or
            not 1 <= window[0] < window[1] <= 1_000_000 or window[1] - window[0] >= 16 or
            type(context["round"]) is not int or not 1 <= context["round"] <= MAX_ROUNDS + 1 or
            not isinstance(context["prior_experiments"], list) or len(context["prior_experiments"]) != context["round"] - 1 or
            not isinstance(context["known_counts"], list) or len(context["known_counts"]) > 64):
        raise ValueError("invalid interval window/history budget")
    for old in context["prior_experiments"]:
        _shape(old, window)
        if old["operation"] != "interval-state":
            raise ValueError("interval history contains an unsupported proposal")
    for known in context["known_counts"]:
        if set(known) != {"probe", "selection"}:
            raise ValueError("invalid retained interval count")
        validate_probe(known["probe"])
        selector(known["selection"], known["probe"])


def _shape(plan, window):
    if (not isinstance(plan, dict) or set(plan) != {"operation", "hypothesis", "alternative", "reason", "probe", "selection", "prediction"} or
            plan["operation"] not in ("interval-state", "needs-instrumentation") or
            any(not isinstance(plan[key], str) or not 1 <= len(plan[key]) <= 600 for key in ("hypothesis", "alternative", "reason"))):
        raise ValueError("invalid interval plan fields")
    if plan["operation"] == "needs-instrumentation":
        if any(plan[key] is not None for key in ("probe", "selection", "prediction")):
            raise ValueError("unsupported interval plan cannot request capture")
        return
    validate_probe(plan["probe"])
    selector(plan["selection"], plan["probe"])
    p = plan["prediction"]
    if (not isinstance(p, dict) or set(p) != {"kind", "update", "occurrence", "register", "address", "relation"} or
            p["kind"] not in ("event-count", "register", "word") or type(p["update"]) is not int or
            not window[0] < p["update"] <= window[1] or p["relation"] not in ("equal", "different")):
        raise ValueError("invalid interval prediction")
    if p["kind"] == "event-count":
        if any(p[key] is not None for key in ("occurrence", "register", "address")):
            raise ValueError("interval count cannot select a value")
    else:
        if type(p["occurrence"]) is not int or not 1 <= p["occurrence"] <= 4096:
            raise ValueError("interval value requires bounded occurrence")
        if p["kind"] == "register" and (type(p["register"]) is not int or not 0 <= p["register"] <= 31 or p["address"] is not None):
            raise ValueError("invalid interval register")
        if p["kind"] == "word" and (p["address"] not in plan["probe"]["words"] or p["register"] is not None):
            raise ValueError("invalid interval word")


def validate(plan, context):
    validate_contract(context)
    _shape(plan, context["focus_updates"])
    if plan["operation"] == "needs-instrumentation":
        return plan
    if context["round"] > MAX_ROUNDS:
        raise ValueError("interval experiment round budget exceeded")
    for old in [*context["prior_experiments"], *context["known_counts"]]:
        if (old["selection"] == plan["selection"] and
                all(old["probe"][key] == plan["probe"][key] for key in ("entry_pc", "call_pc"))):
            p = plan["prediction"]
            if p["kind"] == "event-count" or ("prediction" in old and (
                    p["kind"] == "register" or p["address"] in old["probe"]["words"])):
                raise ValueError("interval prediction repeats retained measurement")
    return plan


def read(path, context):
    if path.stat().st_size > 16_384:
        raise ValueError("interval plan exceeds size budget")
    return validate(json.loads(path.read_text(encoding="utf-8")), context)
