from __future__ import annotations

import json
from pathlib import Path
import subprocess
import tempfile
import unittest

from scripts.autonomy.import_evidence import (
    ImportErrorEvidence, audit_batch, digest, import_evidence,
)
from scripts.autonomy.job_store import JobStore


class HistoricalEvidenceImportTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name) / "repo"
        self.root.mkdir()
        subprocess.run(["git", "init", "-q", str(self.root)],
                       check=True, capture_output=True)
        subprocess.run(["git", "-C", str(self.root), "config", "user.name", "Test"],
                       check=True, capture_output=True)
        subprocess.run(["git", "-C", str(self.root), "config", "user.email",
                        "test@example.com"], check=True, capture_output=True)
        (self.root / "README.md").write_text("fixture", encoding="utf-8")
        subprocess.run(["git", "-C", str(self.root), "add", "README.md"],
                       check=True, capture_output=True)
        subprocess.run(["git", "-C", str(self.root), "commit", "-qm", "fixture"],
                       check=True, capture_output=True)
        private = self.root / "tools" / "private"
        self.state = private / "autonomy"
        self.batch = private / "seeded"
        self.frontier = private / "frontier"
        self.batch.mkdir(parents=True)
        self.frontier.mkdir(parents=True)
        rom = private / "rom.fixture"
        emulator = private / "EmuHawk.exe"
        rom.write_bytes(b"rom fixture")
        emulator.write_bytes(b"emulator fixture")
        jobs = [{"seed": seed, "objective": ("south21", "east48", "death_retry")[seed % 3]}
                for seed in range(10)]
        objective = {
            "kind": "jfg-phase95-seeded-goldwood-batch", "schema": 1,
            "acceptance": False, "job_count": 10, "jobs": jobs,
            "rom_sha256": digest(rom),
            "assets": {
                "rom": {"path": str(rom), "sha256": digest(rom)},
                "emulator": {"path": str(emulator), "sha256": digest(emulator)},
            },
        }
        self.write_json(self.batch / "batch-objective.json", objective)
        self.write_json(self.batch / "batch-result.json", {
            **objective, "completed": True, "jobs_completed": 10,
            "native_parity_verified": False,
            "covered_objectives": ["death_retry", "east48", "south21"],
        })
        journal = []
        for job in jobs:
            seed, goal = job["seed"], job["objective"]
            attempt = self.batch / f"seed-{seed:04d}" / "attempt-01"
            attempt.mkdir(parents=True)
            filename = "death-retry-result.json" if goal == "death_retry" else "scenario-result.json"
            self.write_json(attempt / filename, {"completed": True, "acceptance": False})
            journal.append({"seed": seed, "objective": goal,
                            "attempt": 1, "artifact_root": str(attempt)})
        (self.batch / "batch-completed.jsonl").write_text(
            "".join(json.dumps(item) + "\n" for item in journal), encoding="utf-8")
        self.write_json(self.frontier / "manifest.json", {
            "kind": "jfg-phase95-frontier-job", "schema": 1,
            "acceptance": False, "job_id": "waypoint-55", "edge_id": "edge-55",
            "identity": {"rom_sha256": digest(rom)},
        })
        self.write_json(self.frontier / "result.json", {
            "kind": "jfg-phase95-frontier-result", "schema": 1,
            "acceptance": False, "job_id": "waypoint-55", "edge_id": "edge-55",
            "outcome": "covered", "deterministic": True,
            "attempts": [{"completed": True, "rdram_sha256": "a" * 64},
                         {"completed": True, "rdram_sha256": "a" * 64}],
        })
        self.write_json(self.frontier / "frontier-evidence.json", {
            "evidence": [{"id": "waypoint-55", "outcome": "covered"}],
        })
        emu_copy = self.frontier / "attempt-02" / "emulator" / "EmuHawk.exe"
        emu_copy.parent.mkdir(parents=True)
        emu_copy.write_bytes(emulator.read_bytes())

    @staticmethod
    def write_json(path: Path, payload: dict) -> None:
        path.write_text(json.dumps(payload) + "\n", encoding="utf-8")

    def test_imports_eleven_integrity_jobs_idempotently(self) -> None:
        first = import_evidence(self.root, self.state, self.batch, self.frontier)
        second = import_evidence(self.root, self.state, self.batch, self.frontier)
        self.assertEqual(first, second)
        self.assertEqual(first["imported_count"], 11)
        self.assertEqual(first["imported_passed"], 11)
        self.assertFalse(first["historical_source_commit_known"])
        self.assertFalse(first["native_parity_verified"])
        with JobStore(self.state / "jobs.sqlite") as store:
            self.assertEqual(store.status_projection()["counts"]["passed"], 11)
            self.assertEqual(store.job("import-phase95-seed-0009")["attempts"], 1)

    def test_missing_seed_cannot_be_imported(self) -> None:
        (self.batch / "seed-0009" / "attempt-01" / "scenario-result.json").unlink()
        with self.assertRaises(OSError):
            audit_batch(self.batch)
        self.assertFalse((self.state / "jobs.sqlite").exists())

    def test_incorrect_journal_order_is_rejected(self) -> None:
        journal = self.batch / "batch-completed.jsonl"
        lines = journal.read_text(encoding="utf-8").splitlines()
        lines[0], lines[1] = lines[1], lines[0]
        journal.write_text("\n".join(lines) + "\n", encoding="utf-8")
        with self.assertRaisesRegex(ImportErrorEvidence, "ordered seeds"):
            audit_batch(self.batch)


if __name__ == "__main__":
    unittest.main()
