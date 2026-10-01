from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from scripts.autonomy.alignment_job import (
    TOOL_FILES, alignment_pins, queue_alignment, validate_alignment_packet,
)
from scripts.autonomy.scheduler import advance_alignments
from scripts.autonomy.update_job import TOOL_FILES as UPDATE_TOOL_FILES
from scripts.autonomy.job_store import JobSpec, JobStore
from scripts.autonomy.supervisor import SupervisorError, file_sha256, run_once


class AlignmentJobTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.repo = Path(temporary.name)
        for relative in set(TOOL_FILES) | set(UPDATE_TOOL_FILES):
            target = self.repo / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(Path(__file__).resolve().parents[1] / relative, target)
        (self.repo / "README.md").write_text("fixture\n", encoding="utf-8")
        for args in (["git", "init", "-q", str(self.repo)],
                     ["git", "-C", str(self.repo), "config", "user.name", "Test"],
                     ["git", "-C", str(self.repo), "config", "user.email", "test@example.com"],
                     ["git", "-C", str(self.repo), "add", "scripts", "README.md"],
                     ["git", "-C", str(self.repo), "commit", "-qm", "fixture"]):
            subprocess.run(args, check=True, capture_output=True)
        private = self.repo / "tools" / "private"
        self.state = private / "autonomy"
        self.state.mkdir(parents=True)
        self.source = private / "selected-input"
        self.source.mkdir()
        (self.source / "controller.input").write_text(
            "jfg-phase8-input-v2\n0,1,1,0000,0,0\n1,200,1,0000,0,0\n",
            encoding="utf-8")
        (self.source / "initial.flash").write_bytes(b"flash")
        (self.source / "initial.pak").write_bytes(b"pak")
        input_sha = file_sha256(self.source / "controller.input")
        (self.source / "export-manifest.json").write_text(json.dumps({
            "kind": "jfg-phase95-selected-input-export",
            "input_sha256": input_sha, "oracle_final_frame": 200,
        }), encoding="utf-8")
        self.native = private / "native"
        self.oracle = private / "oracle"
        self.native.mkdir()
        self.oracle.mkdir()
        self.pins = {}
        for key in ("rom", "emulator", "native"):
            path = private / (key + ".fixture")
            path.write_text(key, encoding="utf-8")
            self.pins[key] = str(path)
        (self.oracle / "oracle-result.json").write_text(json.dumps({
            "source_export": str(self.source),
            "source_export_sha256": file_sha256(self.source / "export-manifest.json"),
            "input_sha256": input_sha,
            "rom_sha256": file_sha256(Path(self.pins["rom"])),
        }), encoding="utf-8")
        (self.native / "native-result.json").write_text(json.dumps({
            "source_export": str(self.source), "input_sha256": input_sha,
        }), encoding="utf-8")
        for relative in ("controller-polls.tsv", "retrace-hashes.jsonl"):
            (self.native / relative).write_text("fixture\n", encoding="utf-8")
        (self.oracle / "retrace-hashes.jsonl").write_text("fixture\n", encoding="utf-8")
        self.diagnosis = private / "diagnosis.json"
        self.diagnosis.write_text('{"classification":"capture_misalignment"}',
                                  encoding="utf-8")
        self.comparison_packet = {
            "pin_files": self.pins,
            "native_trace": {"path": str(self.native / "retrace-hashes.jsonl")},
            "oracle_trace": {"path": str(self.oracle / "retrace-hashes.jsonl")},
        }

    def queue(self) -> None:
        with JobStore(self.state / "jobs.sqlite") as store:
            # The real predecessor is a passed diagnosis. This fixture only
            # tests packet durability, not prerequisite scheduling.
            queue_alignment(store, self.repo, self.state,
                            job_id="alignment-fixture", diagnosis_id="diagnosis-fixture",
                            diagnosis_path=self.diagnosis,
                            comparison_packet=self.comparison_packet)

    def test_packet_is_pinned_and_idempotent(self) -> None:
        self.queue()
        self.queue()
        packet_path = self.state / "alignment-packets" / "alignment-fixture.json"
        packet = json.loads(packet_path.read_text(encoding="utf-8"))
        validate_alignment_packet(packet, self.repo)
        with JobStore(self.state / "jobs.sqlite") as store:
            job = store.job("alignment-fixture")
            self.assertEqual(job["state"], "queued")
            self.assertEqual(job["spec"]["prerequisites"], ["diagnosis-fixture"])
            self.assertEqual(job["spec"]["resource"], "emulator:bizhawk")
        (self.source / "initial.pak").write_bytes(b"changed")
        with self.assertRaisesRegex(SupervisorError, "evidence changed"):
            validate_alignment_packet(packet, self.repo)

    def test_target_cannot_exceed_export(self) -> None:
        with JobStore(self.state / "jobs.sqlite") as store:
            with self.assertRaisesRegex(SupervisorError, "share a pinned export"):
                queue_alignment(store, self.repo, self.state,
                                job_id="too-long", diagnosis_id="diagnosis-fixture",
                                diagnosis_path=self.diagnosis,
                                comparison_packet=self.comparison_packet,
                                target_frame=201)

    def test_worker_seals_nonparity_alignment_bundle(self) -> None:
        self.queue()
        packet = json.loads((self.state / "alignment-packets" /
                             "alignment-fixture.json").read_text(encoding="utf-8"))
        with JobStore(self.state / "jobs.sqlite") as store:
            store.enqueue(JobSpec("diagnosis-fixture", alignment_pins(packet, self.repo),
                                  ("diagnosis-fixture",), (), "test-resource", 0,
                                  "file_sha256"))
            lease = store.lease_job("diagnosis-fixture", "test-owner")
            self.assertIsNotNone(lease)
            store.start("diagnosis-fixture", lease["token"])
            store.verify("diagnosis-fixture", lease["token"])
            store.seal_artifact("diagnosis-fixture", lease["token"], self.diagnosis)
            store.pass_job("diagnosis-fixture", lease["token"])

        def fake_bounded(command, cwd, stdout, stderr, deadline, heartbeat,
                         pause_file, **kwargs):
            heartbeat()
            if "scripts.phase95_oracle_replay" in command:
                output = Path(command[3])
                output.mkdir()
                (output / "oracle-result.json").write_text('{"trace_complete":true}',
                                                             encoding="utf-8")
            else:
                output = Path(command[command.index("--output") + 1])
                output.write_text(json.dumps({
                    "kind": "jfg-phase9-poll-vi-alignment", "schema": 1,
                    "shared_polls_analyzed": 2, "alignment_validated": False,
                    "first_validated_gameplay_divergence": None,
                }), encoding="utf-8")
            return 0, None

        with patch("scripts.autonomy.alignment_job.bounded_command",
                   side_effect=fake_bounded):
            outcome = run_once(self.repo, self.state, Path(self.pins["native"]),
                               require_auth=False)
        self.assertEqual(outcome,
                         "alignment-fixture: alignment diagnostic sealed")
        result = json.loads((self.state / "attempts" / "alignment-fixture" /
                             "0001" / "result.json").read_text(encoding="utf-8"))
        self.assertTrue(result["complete"])
        self.assertFalse(result["alignment_validated"])
        self.assertFalse(result["parity_verified"])
        with JobStore(self.state / "jobs.sqlite") as store:
            self.assertEqual(store.job("alignment-fixture")["state"], "passed")
            queued = advance_alignments(store, self.repo, self.state)
            self.assertEqual(queued, ["alignment-fixture-updates"])
            self.assertEqual(advance_alignments(store, self.repo, self.state), [])
            update = store.job("alignment-fixture-updates")
            self.assertEqual(update["spec"]["prerequisites"], ["alignment-fixture"])


if __name__ == "__main__":
    unittest.main()
