"""Integrity-audit surviving Phase 9.5 artifacts into the autonomy ledger.

Imported jobs are read-only historical *evidence audits*. Their producer source
commit was not recorded, so passing imports do not certify a replay or parity.
Only hashes, private wrapper manifests, and a redacted projection are written.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.autonomy.job_store import JobSpec, JobStore, JobStoreError


ROOT = Path(__file__).resolve().parents[2]
ABSENT_NATIVE_PIN = hashlib.sha256(b"not-applicable:historical-oracle-only").hexdigest()
RESULT_NAMES = {"south21": "scenario-result.json",
                "east48": "scenario-result.json",
                "death_retry": "death-retry-result.json"}


class ImportErrorEvidence(ValueError):
    pass


def digest(path: Path) -> str:
    result = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            result.update(chunk)
    return result.hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ImportErrorEvidence(f"expected JSON object: {path.name}")
    return value


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ImportErrorEvidence(message)


def inside(path: Path, directory: Path) -> bool:
    try:
        path.resolve().relative_to(directory.resolve())
        return True
    except ValueError:
        return False


def canonical(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def audit_batch(batch: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    objective_path, result_path = batch / "batch-objective.json", batch / "batch-result.json"
    objective, summary = read_json(objective_path), read_json(result_path)
    require(objective.get("kind") == "jfg-phase95-seeded-goldwood-batch" and
            objective.get("schema") == 1 and objective.get("acceptance") is False,
            "invalid batch objective")
    require(all(summary.get(key) == value for key, value in objective.items()),
            "batch result does not preserve objective pins")
    require(summary.get("completed") is True and summary.get("job_count") == 10 and
            summary.get("jobs_completed") == 10 and
            summary.get("native_parity_verified") is False,
            "batch does not document ten completed non-parity jobs")
    jobs = objective.get("jobs")
    require(isinstance(jobs, list) and len(jobs) == 10 and
            [item.get("seed") for item in jobs] == list(range(10)),
            "batch seed range is not exactly 0..9")
    assets = objective.get("assets")
    require(isinstance(assets, dict) and "rom" in assets and "emulator" in assets,
            "batch asset pins missing")
    for key, item in assets.items():
        require(isinstance(item, dict) and set(item) == {"path", "sha256"},
                f"invalid {key} asset pin")
        path = Path(item["path"])
        require(path.is_absolute() and path.is_file() and digest(path) == item["sha256"],
                f"{key} asset pin drifted")
    require(assets["rom"]["sha256"] == objective.get("rom_sha256"),
            "ROM pin conflict")
    journal_path = batch / "batch-completed.jsonl"
    journal = [json.loads(line) for line in journal_path.read_text(encoding="utf-8").splitlines()]
    require(len(journal) == 10 and [entry.get("seed") for entry in journal] == list(range(10)),
            "completion journal is not exactly ten ordered seeds")
    reviewed = []
    for declaration, entry in zip(jobs, journal):
        seed, goal = declaration["seed"], declaration["objective"]
        require(goal in RESULT_NAMES and entry.get("objective") == goal and
                entry.get("attempt") == 1,
                f"seed {seed} objective/attempt mismatch")
        root = batch / f"seed-{seed:04d}" / "attempt-01"
        require(Path(entry.get("artifact_root", "")).resolve() == root.resolve(),
                f"seed {seed} journal points outside its declared attempt")
        result = root / RESULT_NAMES[goal]
        payload = read_json(result)
        require(payload.get("completed") is True and payload.get("acceptance") is False,
                f"seed {seed} result is not a completed diagnostic")
        reviewed.append({"job_id": f"import-phase95-seed-{seed:04d}",
                         "objective": goal, "artifact": result,
                         "artifact_sha256": digest(result)})
    require(sorted(summary.get("covered_objectives", [])) == sorted(RESULT_NAMES),
            "batch covered-objective summary mismatch")
    return reviewed, {"objective_sha256": digest(objective_path),
                      "batch_result_sha256": digest(result_path),
                      "rom_sha256": assets["rom"]["sha256"],
                      "emulator_sha256": assets["emulator"]["sha256"]}


def audit_frontier(frontier: Path, rom_sha256: str,
                   emulator_sha256: str) -> dict[str, Any]:
    manifest_path, result_path = frontier / "manifest.json", frontier / "result.json"
    manifest, result = read_json(manifest_path), read_json(result_path)
    require(manifest.get("kind") == "jfg-phase95-frontier-job" and
            manifest.get("schema") == 1 and manifest.get("acceptance") is False,
            "invalid frontier manifest")
    require(result.get("kind") == "jfg-phase95-frontier-result" and
            result.get("schema") == 1 and result.get("acceptance") is False and
            result.get("job_id") == manifest.get("job_id") and
            result.get("edge_id") == manifest.get("edge_id") and
            result.get("outcome") == "covered" and result.get("deterministic") is True,
            "frontier result does not match manifest")
    attempts = result.get("attempts")
    require(isinstance(attempts, list) and len(attempts) == 2 and
            all(item.get("completed") is True for item in attempts) and
            attempts[0].get("rdram_sha256") == attempts[1].get("rdram_sha256"),
            "frontier repeat endpoint mismatch")
    require(manifest.get("identity", {}).get("rom_sha256") == rom_sha256,
            "frontier ROM identity differs from batch")
    emulator = frontier / "attempt-02" / "emulator" / "EmuHawk.exe"
    require(emulator.is_file() and digest(emulator) == emulator_sha256,
            "frontier emulator executable differs from batch")
    graph = read_json(frontier / "frontier-evidence.json")
    evidence = graph.get("evidence", [])
    require(any(item.get("id") == manifest["job_id"] and
                item.get("outcome") == "covered" for item in evidence),
            "frontier graph lacks covered-edge evidence")
    return {"job_id": "import-phase95-frontier-0055",
            "objective": "waypoint-0055-proximity-only", "artifact": result_path,
            "artifact_sha256": digest(result_path),
            "manifest_sha256": digest(manifest_path),
            "frontier_graph_sha256": digest(frontier / "frontier-evidence.json")}


def import_one(store: JobStore, state: Path, item: dict[str, Any],
               pins: dict[str, str], batch_digest: str) -> None:
    require(digest(item["artifact"]) == item["artifact_sha256"],
            "historical source artifact changed during audit")
    job_id = item["job_id"]
    spec = JobSpec(job_id, pins,
                   ("historical-artifact:" + item["artifact_sha256"],
                    "batch-manifest:" + batch_digest), (),
                   "import:phase95", 0, "json_complete")
    store.enqueue(spec)
    wrapper = {
        "schema": 1, "complete": True, "kind": "historical-evidence-audit",
        "job_id": job_id, "objective": item["objective"],
        "source_artifact_sha256": item["artifact_sha256"],
        "batch_manifest_sha256": batch_digest,
        "historical_source_commit": None,
        "audit_source_commit": pins["source_commit"],
        "original_run_replayed": False, "native_parity_verified": False,
        "milestone_acceptance": False,
    }
    output_dir = state / "imports"
    output_dir.mkdir(parents=True, exist_ok=True)
    output = output_dir / (job_id + ".json")
    encoded = canonical(wrapper)
    if output.exists() and output.read_bytes() != encoded:
        raise ImportErrorEvidence("historical import wrapper changed")
    if not output.exists():
        temporary = output.with_suffix(".tmp")
        temporary.write_bytes(encoded)
        temporary.replace(output)
    existing = store.job(job_id)
    if existing["state"] == "passed":
        require(existing["sealed_sha256"] == digest(output),
                "sealed historical import changed")
        return
    lease = store.lease_job(job_id, "historical-importer", ttl=300)
    require(lease is not None, "historical import job is not leaseable")
    store.start(job_id, lease["token"])
    store.verify(job_id, lease["token"])
    store.seal_artifact(job_id, lease["token"], output)
    store.pass_job(job_id, lease["token"])


def import_evidence(repo: Path, state: Path, batch: Path,
                    frontier: Path) -> dict[str, Any]:
    private = repo / "tools" / "private"
    require(inside(state, private) and inside(batch, private) and
            inside(frontier, private), "imports must remain under tools/private")
    seeds, batch_pins = audit_batch(batch)
    waypoint = audit_frontier(frontier, batch_pins["rom_sha256"],
                              batch_pins["emulator_sha256"])
    source_commit = subprocess.check_output(
        ["git", "-C", str(repo), "rev-parse", "HEAD"], text=True).strip()
    pins = {"source_commit": source_commit,
            "tool_sha256": digest(Path(__file__)),
            "rom_sha256": batch_pins["rom_sha256"],
            "emulator_sha256": batch_pins["emulator_sha256"],
            "native_sha256": ABSENT_NATIVE_PIN}
    with JobStore(state / "jobs.sqlite") as store:
        for item in [waypoint, *seeds]:
            import_one(store, state, item, pins,
                       batch_pins["batch_result_sha256"])
        projection = store.status_projection()
    imported = {item["job_id"] for item in [waypoint, *seeds]}
    status = {"schema": 1, "kind": "phase95-historical-import-status",
              "imported_count": len(imported),
              "imported_passed": sum(job["job_id"] in imported and job["state"] == "passed"
                                     for job in projection["jobs"]),
              "jobs": [{"job_id": job["job_id"], "state": job["state"]}
                       for job in projection["jobs"] if job["job_id"] in imported],
              "historical_source_commit_known": False,
              "original_runs_replayed": False, "native_parity_verified": False}
    return status


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=ROOT)
    parser.add_argument("--state", type=Path, default=ROOT / "tools" / "private" / "autonomy")
    parser.add_argument("--batch", type=Path, required=True)
    parser.add_argument("--frontier", type=Path, required=True)
    parser.add_argument("--projection", type=Path)
    args = parser.parse_args(argv)
    try:
        status = import_evidence(args.repo.resolve(), args.state.resolve(),
                                 args.batch.resolve(), args.frontier.resolve())
        rendered = json.dumps(status, indent=2, sort_keys=True) + "\n"
        if args.projection:
            args.projection.write_text(rendered, encoding="utf-8")
        print(rendered, end="")
        return 0
    except (ImportErrorEvidence, JobStoreError, OSError, ValueError) as error:
        print(f"historical import failed: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
