"""Typed entry-register observations, restricted to qualified direct JAL calls."""
import hashlib
import json
from pathlib import Path

from scripts.autonomy.experiment_plan import ADDRESS

SCHEMA_FILE = Path(__file__).with_name("entry_plan.schema.json")
MAX_ENTRY_ROUNDS = 3


def contract(window, history=()):
    previous = [item for item in history if item["operation"] == "entry-gpr"]
    return {"version": 1, "schema_sha256": hashlib.sha256(SCHEMA_FILE.read_bytes()).hexdigest(),
            "focus_updates": list(window), "round": len(previous) + 1,
            "prior_probes": [item["probe"] for item in previous]}


def validate_probe(probe):
    if (not isinstance(probe, dict) or set(probe) != {"entry_pc", "call_pc"} or
            any(not isinstance(value, str) or not ADDRESS.fullmatch(value) or int(value, 16) % 4
                for value in probe.values()) or int(probe["call_pc"], 16) > 0x803ffff4):
        raise ValueError("entry probe needs aligned KSEG0 entry and direct-call PCs")


def validate_contract(context):
    if (not isinstance(context, dict) or set(context) != {
            "version", "schema_sha256", "focus_updates", "round", "prior_probes"} or
            type(context["version"]) is not int or context["version"] != 1 or
            context["schema_sha256"] != hashlib.sha256(SCHEMA_FILE.read_bytes()).hexdigest()):
        raise ValueError("entry experiment contract changed")
    window = context["focus_updates"]
    if (not isinstance(window, list) or len(window) != 2 or any(type(n) is not int for n in window) or
            not 1 <= window[0] <= window[1] <= 1_000_000 or window[1] - window[0] >= 16 or
            type(context["round"]) is not int or not 1 <= context["round"] <= MAX_ENTRY_ROUNDS + 1 or
            not isinstance(context["prior_probes"], list) or
            len(context["prior_probes"]) != context["round"] - 1):
        raise ValueError("entry experiment window or history budget is invalid")
    for probe in context["prior_probes"]:
        validate_probe(probe)


def validate(plan, context):
    validate_contract(context)
    if (not isinstance(plan, dict) or set(plan) != {
            "operation", "hypothesis", "alternative", "reason", "probe", "prediction"} or
            plan["operation"] not in ("entry-gpr", "needs-instrumentation") or
            any(not isinstance(plan[key], str) or not 1 <= len(plan[key]) <= 600
                for key in ("hypothesis", "alternative", "reason"))):
        raise ValueError("entry experiment fields are invalid")
    if plan["operation"] == "needs-instrumentation":
        if plan["probe"] is not None or plan["prediction"] is not None:
            raise ValueError("unsupported entry experiment cannot request capture")
        return plan
    validate_probe(plan["probe"])
    prediction = plan["prediction"]
    if (not isinstance(prediction, dict) or set(prediction) != {"update", "register", "relation"} or
            type(prediction["register"]) is not int or not 0 <= prediction["register"] <= 31 or
            type(prediction["update"]) is not int or
            not context["focus_updates"][0] <= prediction["update"] <= context["focus_updates"][1] or
            prediction["relation"] not in ("equal", "different")):
        raise ValueError("entry prediction is outside the qualified register/window")
    if context["round"] > MAX_ENTRY_ROUNDS or any(
            probe["entry_pc"] == plan["probe"]["entry_pc"] for probe in context["prior_probes"]):
        raise ValueError("entry capture repeats measured registers or exceeds its round budget")
    return plan


def read(path, context):
    if path.stat().st_size > 16_384:
        raise ValueError("entry experiment plan exceeds size limit")
    return validate(json.loads(path.read_text(encoding="utf-8")), context)
