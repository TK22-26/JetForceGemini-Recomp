"""Typed pre-instruction observations inside one qualified direct-call span."""
import hashlib
import json
import re
from pathlib import Path

from scripts.autonomy.entry_plan import validate_probe as validate_anchor
from scripts.autonomy.experiment_plan import ADDRESS
from scripts.phase9_point_probe import validate as validate_addresses

SCHEMA_FILE = Path(__file__).with_name("point_plan.schema.json")
MAX_POINT_ROUNDS = 3


def contract(window, runtime_sha256, history=()):
    previous = [item for item in history if item["operation"] == "point-state"]
    return {"version": 1, "schema_sha256": hashlib.sha256(SCHEMA_FILE.read_bytes()).hexdigest(),
            "focus_updates": list(window), "runtime_manifest_sha256": runtime_sha256,
            "round": len(previous) + 1, "prior_probes": [item["probe"] for item in previous]}


def validate_probe(probe):
    if not isinstance(probe, dict) or set(probe) != {"entry_pc", "call_pc", "pcs", "words"}:
        raise ValueError("point probe fields differ")
    validate_anchor({key: probe[key] for key in ("entry_pc", "call_pc")})
    for key in ("pcs", "words"):
        if not isinstance(probe[key], list) or any(not isinstance(value, str) or not ADDRESS.fullmatch(value) for value in probe[key]):
            raise ValueError("point probe addresses must be canonical KSEG0 strings")
    validate_addresses([int(value,16) for value in probe["pcs"]], [int(value,16) for value in probe["words"]], [1,2], True)
    if probe["entry_pc"] not in probe["pcs"] or f"0x{int(probe['call_pc'],16)+8:08x}" not in probe["pcs"] or "0x800a9e90" not in probe["words"]:
        raise ValueError("point probe must include producer entry, caller return and US running-thread word")


def validate_contract(context):
    if (not isinstance(context, dict) or set(context) != {"version", "schema_sha256", "focus_updates", "runtime_manifest_sha256", "round", "prior_probes"} or
            type(context["version"]) is not int or context["version"] != 1 or
            context["schema_sha256"] != hashlib.sha256(SCHEMA_FILE.read_bytes()).hexdigest() or
            not isinstance(context["runtime_manifest_sha256"], str) or not re.fullmatch(r"[0-9a-f]{64}", context["runtime_manifest_sha256"])):
        raise ValueError("point experiment contract changed")
    window = context["focus_updates"]
    if (not isinstance(window, list) or len(window) != 2 or any(type(n) is not int for n in window) or
            not 1 <= window[0] <= window[1] <= 1_000_000 or window[1]-window[0] >= 16 or
            type(context["round"]) is not int or not 1 <= context["round"] <= MAX_POINT_ROUNDS+1 or
            not isinstance(context["prior_probes"], list) or len(context["prior_probes"]) != context["round"]-1):
        raise ValueError("point experiment window/history budget is invalid")
    for probe in context["prior_probes"]:
        validate_probe(probe)


def validate(plan, context):
    validate_contract(context)
    if (not isinstance(plan, dict) or set(plan) != {"operation", "hypothesis", "alternative", "reason", "probe", "prediction"} or
            plan["operation"] not in ("point-state", "needs-instrumentation") or
            any(not isinstance(plan[key], str) or not 1 <= len(plan[key]) <= 600 for key in ("hypothesis", "alternative", "reason"))):
        raise ValueError("point experiment fields are invalid")
    if plan["operation"] == "needs-instrumentation":
        if plan["probe"] is not None or plan["prediction"] is not None:
            raise ValueError("unsupported point experiment cannot request capture")
        return plan
    validate_probe(plan["probe"])
    p = plan["prediction"]
    if (not isinstance(p, dict) or set(p) != {"kind", "pc", "update", "occurrence", "register", "address", "relation"} or
            p["kind"] not in ("event-count", "register", "word") or p["pc"] not in plan["probe"]["pcs"] or
            type(p["update"]) is not int or not context["focus_updates"][0] <= p["update"] <= context["focus_updates"][1] or
            p["relation"] not in ("equal", "different")):
        raise ValueError("invalid point prediction")
    if p["kind"] == "event-count":
        if any(p[key] is not None for key in ("occurrence", "register", "address")):
            raise ValueError("event count prediction cannot select a value")
    else:
        if type(p["occurrence"]) is not int or not 1 <= p["occurrence"] <= 4096:
            raise ValueError("point value prediction requires a bounded occurrence")
        if p["kind"] == "register" and (type(p["register"]) is not int or not 0 <= p["register"] <= 31 or p["address"] is not None):
            raise ValueError("invalid point register prediction")
        if p["kind"] == "word" and (p["address"] not in plan["probe"]["words"] or p["register"] is not None):
            raise ValueError("invalid point word prediction")
    if context["round"] > MAX_POINT_ROUNDS:
        raise ValueError("point experiment round budget exceeded")
    for old in context["prior_probes"]:
        if (all(old[key] == plan["probe"][key] for key in ("entry_pc", "call_pc")) and p["pc"] in old["pcs"] and
                (p["kind"] != "word" or p["address"] in old["words"])):
            raise ValueError("point prediction repeats an already measured event/value")
    return plan


def read(path, context):
    if path.stat().st_size > 16_384:
        raise ValueError("point experiment plan exceeds size budget")
    return validate(json.loads(path.read_text(encoding="utf-8")), context)
