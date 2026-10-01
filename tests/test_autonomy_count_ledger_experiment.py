import copy
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest import mock

from scripts.autonomy import count_ledger_experiment as lane
from scripts.autonomy import experiment_feedback as feedback, research_cycle as cycle, supervisor
from scripts.autonomy.job_store import JobSpec, JobStore
from tests import test_phase9_oracle_count_ledger as ledger_fixtures


class CountLedgerWorkflowTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.repo = Path(temporary.name).resolve()
        self.state = self.repo / "tools/private/autonomy"
        self.state.mkdir(parents=True)
        self.store = JobStore(self.state / "jobs.sqlite")
        self.addCleanup(self.store.close)
        self.pins = {"source_commit": "1" * 40, **{key + "_sha256": "2" * 64 for key in ("tool", "native", "rom", "emulator")}}
        self.store.enqueue(JobSpec("parent", self.pins, ("device-experiment:fixture",), (), "analysis:test", 0, "json_complete"))
        self.seal = self.finish("parent", {"complete": True, "job_id": "parent"})
        self.registration = lane.registration_path(self.state, "parent")
        self.registration.parent.mkdir()
        self.record = {"schema": 1, "kind": "oracle-count-ledger-registration", "parent_id": "parent",
            "oracle": "fixture", "control": "fixture", "oracle_build": {}, "update": 7,
            "measurement_sha256": "3" * 64, "supporting_files": []}
        self.registration.write_bytes(supervisor.canonical_bytes(self.record))
        self.context = {"observation_seal": self.seal, "history": [], "baseline_id": "baseline",
            "observation_id": "parent", "plan": {"operation": "device-events"},
            "observation": {"prediction_observed": None, "observations": []}}
        self.measurement = {"evidence": {str(self.seal): supervisor.file_sha256(self.seal)},
            "ledger_measurement": {"evidence": {}}, "observations": [], "prediction_observed": None,
            "qualification": {"passed": True}, "clock_alignment_validated": False,
            "retirement_validated": False, "completed_queue_operations_proved": False}

    def finish(self, job_id, report):
        lease = self.store.lease_job(job_id, "test", ttl=120)
        self.store.start(job_id, lease["token"])
        path = self.state / "attempts" / job_id / "0001/result.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(supervisor.canonical_bytes(report))
        self.store.verify(job_id, lease["token"])
        self.store.seal_artifact(job_id, lease["token"], path)
        self.store.pass_job(job_id, lease["token"])
        return path

    def enqueue(self):
        with mock.patch.object(lane, "tool_sha", return_value="4" * 64):
            return lane.next_job(self.store, self.repo, self.state, None, "parent")

    def test_existing_pending_running_failed_and_passed_are_never_relaunched(self):
        job_id = self.enqueue()
        self.assertEqual(self.store.job(job_id)["spec"]["prerequisites"], ["parent"])
        for status in ("queued", "running", "blocked"):
            if status == "running":
                lease = self.store.lease_job(job_id, "test", ttl=120)
                self.store.start(job_id, lease["token"])
            if status == "blocked":
                self.store.fail_job(job_id, lease["token"], "fixture", blocked=True)
            with self.subTest(status=status), mock.patch.object(lane, "check", side_effect=AssertionError("no remeasure")):
                self.assertEqual(self.enqueue(), job_id)
                self.assertEqual(self.store.job(job_id)["state"], status)

    def test_pause_missing_registration_and_bad_ids_publish_nothing(self):
        self.assertIsNone(lane.next_job(self.store, self.repo, self.state, None, "missing"))
        for value in ("../parent", "C:/parent", "", None):
            with self.subTest(value=value), self.assertRaises(ValueError):
                lane.registration_path(self.state, value)
        (self.state / "PAUSED").touch()
        self.assertIsNone(self.enqueue())

    def test_queue_rejects_unqualified_or_changed_registration(self):
        self.record["measurement_sha256"] = None
        self.registration.write_bytes(supervisor.canonical_bytes(self.record))
        with self.assertRaisesRegex(ValueError, "not qualified"):
            self.enqueue()
        self.record["measurement_sha256"] = "3" * 64
        self.registration.write_bytes(supervisor.canonical_bytes(self.record))
        sealed = lane.words._sealed_result

        def mutate(*args, **kwargs):
            self.registration.write_text("changed")
            return sealed(*args, **kwargs)

        with mock.patch.object(lane.words, "_sealed_result", side_effect=mutate), self.assertRaisesRegex(ValueError, "changed during"):
            self.enqueue()

    def test_wrong_packet_is_rejected_before_expensive_ancestry(self):
        job_id = self.enqueue()
        spec = self.store.job(job_id)["spec"]
        for key, value in (("inputs", [lane.PREFIX + "0" * 64]), ("prerequisites", [])):
            with self.subTest(key=key), mock.patch.object(lane, "check", side_effect=AssertionError("untrusted")):
                with self.assertRaises(ValueError):
                    lane.inputs(self.store, self.repo, self.state, job_id, {**spec, key: value})

    def test_worker_uses_guard_heartbeat_and_seals_once(self):
        job_id = self.enqueue()
        lease = self.store.lease_job(job_id, "test", ttl=120)

        def command(argv, repo, stdout, stderr, deadline, heartbeat, paused, **kwargs):
            heartbeat()
            self.assertEqual(kwargs["guard_record"].name, "measurement.guard.json")
            output = Path(argv[argv.index("--output") + 1])
            output.write_text(json.dumps({"complete": True, "job_id": job_id, "pins": lease["spec"]["pins"]}))
            return 0, None

        with mock.patch.object(lane, "tool_sha", return_value="4" * 64), mock.patch.object(lane, "bounded_command", side_effect=command):
            self.assertIn("sealed", lane.run_lease(self.store, lease, self.repo, self.state))
        self.assertEqual(self.store.job(job_id)["state"], "passed")
        self.assertEqual(self.enqueue(), job_id)
        self.assertEqual(self.store.job(job_id)["attempts"], 1)

    def test_changed_producer_blocks_without_launch(self):
        job_id = self.enqueue()
        lease = self.store.lease_job(job_id, "test", ttl=120)
        with mock.patch.object(lane, "tool_sha", return_value="5" * 64), mock.patch.object(lane, "bounded_command") as command:
            self.assertIn("blocked", lane.run_lease(self.store, lease, self.repo, self.state))
            command.assert_not_called()

    def test_inputs_preserve_parent_history_and_feedback_pins_registration(self):
        self.context.update(retest_id="retest", window=[7, 7],
            baseline_packet={"source_commit": self.pins["source_commit"], "pin_files": {}},
            baseline_seal=self.seal, diagnosis_message=self.seal, native_trace=self.seal,
            oracle_trace=self.seal, capture={"capture_seal": self.seal})
        job_id = self.enqueue()
        spec = self.store.job(job_id)["spec"]
        with mock.patch.object(lane, "check", side_effect=lambda *a, **k: (copy.deepcopy(self.measurement), self.context)), \
                mock.patch.object(lane.parent_lane, "checked_observation", return_value=self.context), \
                mock.patch.object(lane.parent_lane, "oracle_build"), mock.patch.object(feedback, "enqueue_packet") as enqueue:
            report, context = lane.inputs(self.store, self.repo, self.state, job_id, spec)
            self.finish(job_id, report)
            queued = feedback.queue_feedback(self.store, self.repo, self.state, None, job_id)
        self.assertEqual(context["history"], [self.context])
        self.assertEqual(context["plan_message"], self.registration)
        self.assertEqual(queued, feedback.feedback_id(job_id))
        packet = enqueue.call_args.args[2]
        self.assertEqual(packet["evidence_files"][2], lane.words.pin(self.registration))
        self.assertEqual(packet["prerequisites"], ["retest", "baseline", job_id])
        facts = json.loads(Path(packet["evidence_files"][0]["path"]).read_text())
        self.assertEqual(len(facts["history"]), 2)
        self.assertIn("not retired instruction work", facts["count_ledger_limits"])

    def test_inputs_reject_parent_and_backing_mutation(self):
        job_id = self.enqueue()
        spec = self.store.job(job_id)["spec"]
        wrong = copy.deepcopy(spec)
        wrong["pins"]["native_sha256"] = "9" * 64
        with mock.patch.object(lane, "check", return_value=(self.measurement, self.context)):
            with self.assertRaisesRegex(ValueError, "parent provenance"):
                lane.inputs(self.store, self.repo, self.state, job_id, wrong)
        backing = self.state / "raw.tsv"
        backing.write_text("original")
        self.measurement["ledger_measurement"]["evidence"][str(backing)] = supervisor.file_sha256(backing)

        def mutate(*args, **kwargs):
            backing.write_text("changed")
            return self.context

        with mock.patch.object(lane, "check", return_value=(self.measurement, self.context)), \
                mock.patch.object(lane.parent_lane, "checked_observation", side_effect=mutate):
            with self.assertRaisesRegex(ValueError, "changed during lineage"):
                lane.inputs(self.store, self.repo, self.state, job_id, spec)

    def test_consumer_recomputes_and_rejects_sealed_content_changes(self):
        with mock.patch.object(lane.words, "_sealed_result", return_value=({"spec": {}}, {"complete": True}, self.seal)), \
                mock.patch.object(lane, "inputs", return_value=({"complete": True, "tampered": True}, {})) as compute:
            with self.assertRaisesRegex(ValueError, "contradicts"):
                lane.checked_observation(self.store, self.repo, self.state, "count")
        compute.assert_called_once()

    def test_driver_selects_registered_evidence_before_repeating_old_feedback(self):
        for status in ("queued", "running", "blocked"):
            with self.subTest(status=status), mock.patch.object(cycle.count_ledger_experiment, "next_job", return_value="count"), \
                    mock.patch.object(self.store, "job", return_value={"state": status}), \
                    mock.patch.object(cycle.feedback, "queue_feedback") as queue:
                result = cycle.next_stage(self.store, self.repo, self.state, None, "parent")
                self.assertEqual(result["stage"], "count-ledger-observation")
                self.assertEqual(result["state"], status)
                queue.assert_not_called()

    def test_tool_identity_includes_reader_producer_and_parent(self):
        before = lane.tool_sha()
        real = lane.file_sha256
        for name in ("phase9_oracle_count_ledger.py", "oracle_cpu_boundaries.c", "oracle_cpu_boundaries.patch"):
            with self.subTest(name=name), mock.patch.object(lane, "file_sha256", side_effect=lambda p: "0" * 64 if p.name == name else real(p)):
                self.assertNotEqual(lane.tool_sha(), before)


class CountLedgerQualificationTests(unittest.TestCase):
    def setUp(self):
        self.fixture = ledger_fixtures.OracleCountLedgerTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.fixture.write()
        self.repo = self.fixture.directory / "repo"
        self.private = self.repo / "tools/private"
        self.private.mkdir(parents=True)
        self.oracle, self.control, self.prior = [self.private / name for name in ("oracle", "control", "prior")]
        self.fixture.metadata["runtime_sha256"] = "a" * 64
        self.fixture.save_metadata()
        names = ["oracle-result.json", "device-events.tsv", "cpu-boundaries.tsv"]
        for base in (self.oracle, self.control, self.prior):
            base.mkdir()
            for name in names:
                if name == "cpu-boundaries.tsv" and base != self.oracle:
                    continue
                shutil.copyfile(self.fixture.directory / name, base / name)
            if base == self.control:
                metadata = copy.deepcopy(self.fixture.metadata)
                del metadata["cpu_boundaries"]
                (base / "oracle-result.json").write_text(json.dumps(metadata))
            for name in ("update-hashes.jsonl", "retrace-hashes.jsonl", "consumed-vi-hashes.jsonl",
                         "point-probe.tsv", "checkpoints.tsv", "focus-update-7.rdram"):
                (base / name).write_text("same bounded fixture")
        self.build = self.private / "build"
        self.build.mkdir()
        (self.build / "build-result.json").write_text("fixture")
        for name in ("build.guard.json", "build.stdout", "build.stderr", "emulator/config.ini"):
            path = self.build / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("pinned")
        for base in (self.repo / "scripts", self.build / "mupen64plus-core/src/r4300"):
            base.mkdir(parents=True)
            for name in ("oracle_cpu_boundaries.c", "oracle_cpu_boundaries.h"):
                (base / name).write_text("same observer")
        self.parent = {"window": [7, 7], "plan": {"operation": "device-events", "probe": {}},
            "device_registration": {"oracle": str(self.prior)},
            "observation": {"qualification": {"passed": True}, "observations": [{"update": 7,
                "oracle": {"first_sequence_exclusive": 1, "last_sequence_exclusive": 2,
                    "start_context": {"device_sequence": 1, "pc": 0x80001004},
                    "end_context": {"device_sequence": 2, "pc": 0x80001008}}}]}}
        self.record = {"schema": 1, "kind": "oracle-count-ledger-registration", "parent_id": "parent",
            "oracle": str(self.oracle), "control": str(self.control), "update": 7, "measurement_sha256": None,
            "oracle_build": lane.words.pin(self.build / "build-result.json"),
            "supporting_files": [lane.words.pin(self.build / name) for name in
                                 ("build.guard.json", "build.stdout", "build.stderr", "emulator/config.ini")]}

    def check(self):
        with mock.patch.object(lane.parent_lane, "checked_observation", return_value=self.parent), \
                mock.patch.object(lane.parent_lane, "oracle_build", return_value={"runtime_sha256": "a" * 64}), \
                mock.patch.object(lane.device_observation, "qualify_side"), \
                mock.patch.object(lane, "runtime_digest", return_value="a" * 64):
            return lane.check(None, self.repo, self.private, self.record)[0]

    def test_real_count_join_and_complete_artifact_hashes(self):
        report = self.check()
        self.assertTrue(report["qualification"]["passed"])
        self.assertEqual(report["observations"][0]["device_events_reconciled"], 2)
        self.assertFalse(report["causal_fix_proved"])
        self.record["measurement_sha256"] = hashlib.sha256(supervisor.canonical_bytes(report)).hexdigest()
        self.assertEqual(self.check(), report)

    def test_changed_full_control_trace_is_rejected(self):
        (self.control / "retrace-hashes.jsonl").write_text("changed beyond focused update")
        with self.assertRaisesRegex(ValueError, "complete control artifact"):
            self.check()

    def test_control_cannot_silently_enable_observer(self):
        (self.control / "cpu-boundaries.tsv").touch()
        with self.assertRaisesRegex(ValueError, "off-control"):
            self.check()

    def test_changed_observer_build_is_rejected(self):
        (self.repo / "scripts/oracle_cpu_boundaries.c").write_text("changed")
        with self.assertRaisesRegex(ValueError, "built observer"):
            self.check()

    def test_parent_boundaries_cannot_be_replaced_by_a_convenient_interval(self):
        self.parent["observation"]["observations"][0]["oracle"]["start_context"]["pc"] += 4
        with self.assertRaisesRegex(ValueError, "boundaries changed"):
            self.check()

    def test_registration_cannot_repin_an_invented_measurement(self):
        self.record["measurement_sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "measurement changed"):
            self.check()


if __name__ == "__main__":
    unittest.main()
