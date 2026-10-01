"""Source-bound observation build, distinct from the frozen gameplay baseline.

Registration is an engineering action, never model output. Qualification is
local to this baseline/window; every new point capture must recheck non-change.
"""
import json
import tempfile
from pathlib import Path

from scripts.autonomy import source_build, execution_contract, state_word_experiment as words
from scripts.autonomy.supervisor import SupervisorError, canonical_bytes, _write_json_atomic
from scripts.compare_phase9_point_pacing import compare


def path_for(state, baseline_id):
    return state / "point-runtimes" / (baseline_id + ".json")


def check(store, repo, state, context, record):
    if (set(record) != {"schema", "kind", "baseline_id", "reference_id", "source_build", "calibration", "native", "oracle"} or
            record["schema"] != 1 or record["kind"] != "diagnostic-point-runtime" or record["baseline_id"] != context["baseline_id"]):
        raise SupervisorError("point runtime registration identity changed")
    build_path = source_build.pinned_file(repo, record["source_build"])
    build_record = json.loads(build_path.read_text())
    build = source_build.validate(repo, record["source_build"], Path(build_record["executable"]))
    reference = words.capture_context(store, repo, state, record["reference_id"], context)
    if reference is None or any(key in reference["capture_packet"] for key in ("entry_probe", "point_probe")):
        raise SupervisorError("point runtime requires the original unprobed reference capture")
    calibration = source_build.pinned_file(repo, record["calibration"])
    directories = [Path(record[side]).resolve(strict=True) for side in ("native", "oracle")]
    if any(not path.is_relative_to(repo / "tools/private") or not path.is_dir() for path in directories):
        raise SupervisorError("point calibration escaped private storage")
    with tempfile.TemporaryDirectory(prefix="jfg-point-check-") as temporary:
        measured = compare(*directories, reference["capture_seal"].parent / "native", reference["capture_seal"].parent / "oracle",
                           input_report_path=Path(temporary) / "input.json", window=context["window"])
    if measured != json.loads(calibration.read_text()) or measured["qualification"]["passed"] is not True:
        raise SupervisorError("point runtime calibration failed or changed")
    native = json.loads((directories[0] / "native-result.json").read_text())
    if native.get("executable_sha256") != build["executable_sha256"] or native.get("native_runtime_sha256") != build["runtime_sha256"]:
        raise SupervisorError("point calibration does not identify the registered build")
    baseline = context["baseline_packet"]
    pins = {**baseline["pin_files"], "native": build["executable"]}
    execution = execution_contract.capture(pins, baseline["execution"]["profile"])
    if any(execution[key] != value for key,value in baseline["execution"].items() if key != "native_runtime_sha256"):
        raise SupervisorError("point runtime changed the reference execution profile")
    return {"record":record, "reference":reference, "calibration":measured, "capture_baseline":{
        **baseline, "source_commit":build["source_commit"], "source_build":record["source_build"],
        "pin_files":pins, "execution":execution}}


def load(store, repo, state, context):
    path = path_for(state, context["baseline_id"])
    if not path.is_file():
        return None
    binding = words.pin(path)
    result = check(store, repo, state, context, json.loads(path.read_text()))
    if binding != words.pin(path):
        raise SupervisorError("point runtime registration changed during validation")
    return {**result, "binding":binding}


def register(store, repo, state, context, *, build, reference_id, native, oracle, calibration):
    path = path_for(state, context["baseline_id"])
    if (state / "PAUSED").exists():
        raise SupervisorError("point runtime registration is paused")
    record = {"schema":1, "kind":"diagnostic-point-runtime", "baseline_id":context["baseline_id"],
              "reference_id":reference_id, "source_build":words.pin(build), "calibration":words.pin(calibration),
              "native":str(native.resolve(strict=True)), "oracle":str(oracle.resolve(strict=True))}
    check(store, repo, state, context, record)
    if path.exists() and path.read_bytes() != canonical_bytes(record):
        raise SupervisorError("point runtime registration is immutable")
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        _write_json_atomic(path, record)
    return words.pin(path)
