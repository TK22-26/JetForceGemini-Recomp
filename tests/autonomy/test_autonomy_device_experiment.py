import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts.autonomy import device_experiment as device, research_cycle as cycle, supervisor
from scripts.autonomy.job_store import JobStore, JobSpec


class DeviceWorkflowTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.repo = Path(temporary.name).resolve()
        self.state = self.repo / "tools/private/autonomy"
        self.state.mkdir(parents=True)
        self.store = JobStore(self.state / "jobs.sqlite")
        self.addCleanup(self.store.close)
        self.pins = {"source_commit": "1" * 40, **{key + "_sha256": "2" * 64 for key in ("tool", "native", "rom", "emulator")}}
        self.seals = {}
        for name in ("baseline", "parent", "reference"):
            prefix = "packet:" if name == "parent" else "update-packet:"
            self.store.enqueue(JobSpec(name, self.pins, (prefix + "fixture",), (), "analysis:test", 0, "json_complete"))
            lease = self.store.lease_job(name, "test", ttl=120)
            self.store.start(name, lease["token"])
            path = self.state / "attempts" / name / "0001/result.json"
            path.parent.mkdir(parents=True)
            path.write_text(json.dumps({"complete": True, "job_id": name}))
            self.store.verify(name, lease["token"])
            self.store.seal_artifact(name, lease["token"], path)
            self.store.pass_job(name, lease["token"])
            self.seals[name] = path
        path = device.registration_path(self.state, "parent")
        path.parent.mkdir()
        self.record = {"parent_id": "parent", "baseline_id": "baseline", "reference_id": "reference", "measurement_sha256": "3" * 64}
        path.write_bytes(supervisor.canonical_bytes(self.record))
        self.context = {"baseline_id": "baseline", "plan_seal": self.seals["parent"],
                        "device_reference": {"capture_seal": self.seals["reference"]}}

    def enqueue(self):
        with patch.object(device, "check", return_value=({}, self.context)), patch.object(device, "tool_sha", return_value="4" * 64):
            return device.next_job(self.store, self.repo, self.state, None, "parent")

    def test_registration_queues_once_and_never_restarts_existing_jobs(self):
        job_id = self.enqueue()
        self.assertEqual(self.store.job(job_id)["spec"]["prerequisites"], ["parent", "reference"])
        for state in ("queued", "running", "blocked"):
            if state == "running":
                lease = self.store.lease_job(job_id, "test", ttl=120)
                self.store.start(job_id, lease["token"])
            if state == "blocked":
                self.store.fail_job(job_id, lease["token"], "fixture failure", blocked=True)
            with self.subTest(state=state), patch.object(device, "check", side_effect=AssertionError("no requeue")):
                self.assertEqual(device.next_job(self.store, self.repo, self.state, None, "parent"), job_id)
                self.assertEqual(self.store.job(job_id)["state"], state)

    def test_pause_and_missing_registration_do_not_publish(self):
        self.assertIsNone(device.next_job(self.store, self.repo, self.state, None, "absent"))
        (self.state / "PAUSED").touch()
        with patch.object(device, "check", side_effect=AssertionError("paused")):
            self.assertIsNone(device.next_job(self.store, self.repo, self.state, None, "parent"))

    def test_evidence_change_during_queueing_or_unqualified_record_is_rejected(self):
        path = device.registration_path(self.state, "parent")
        sealed = device.words._sealed_result
        def mutate(*args, **kwargs):
            path.write_text("changed")
            return sealed(*args, **kwargs)
        with patch.object(device.words, "_sealed_result", side_effect=mutate), self.assertRaisesRegex(ValueError, "changed during"):
            device.next_job(self.store, self.repo, self.state, None, "parent")
        path.write_text(json.dumps(dict(self.record, measurement_sha256=None)))
        with self.assertRaisesRegex(ValueError, "not qualified"):
            device.next_job(self.store, self.repo, self.state, None, "parent")

    def test_ledger_worker_seals_only_complete_current_producer_output(self):
        job_id = self.enqueue()
        lease = self.store.lease_job(job_id, "test", ttl=120)
        def command(argv, repo, stdout, stderr, deadline, heartbeat, paused, **kwargs):
            heartbeat()
            path = Path(argv[argv.index("--output") + 1])
            path.write_text(json.dumps({"complete": True, "job_id": job_id, "pins": lease["spec"]["pins"]}))
            return 0, None
        with patch.object(device, "tool_sha", return_value="4" * 64), patch.object(device, "bounded_command", side_effect=command):
            self.assertIn("sealed", device.run_lease(self.store, lease, self.repo, self.state))
        self.assertEqual(self.store.job(job_id)["state"], "passed")
        self.assertEqual(self.store.job(job_id)["attempts"], 1)

    def test_changed_producer_blocks_before_starting_measurement(self):
        job_id = self.enqueue()
        lease = self.store.lease_job(job_id, "test", ttl=120)
        with patch.object(device, "tool_sha", return_value="5" * 64), patch.object(device, "bounded_command") as command:
            self.assertIn("blocked", device.run_lease(self.store, lease, self.repo, self.state))
            command.assert_not_called()
        self.assertEqual(self.store.job(job_id)["state"], "blocked")

    def test_dispatches_existing_device_observation_without_relaunching_failed_planner(self):
        from tests.test_autonomy_research_cycle import ResearchCycleTests
        store, ids = ResearchCycleTests.tail_store(3, "blocked")
        # There is a passed base plan plus a failed optional successor. New
        # registered evidence descends from the passed base, not the failure.
        base = ids[3]
        store.status_projection.return_value["jobs"][-1]["state"] = "passed"
        store.status_projection.return_value["jobs"].append({"job_id": base + "-operands-v1", "state": "blocked"})
        path = device.registration_path(self.state, base)
        path.write_text("registered")
        for status in ("queued", "running", "blocked", "passed"):
            store.job.return_value = {"state": status}
            with self.subTest(status=status), patch.object(device, "next_job", return_value="observation") as next_job, \
                    patch.object(cycle.interval_experiment, "next_job", side_effect=AssertionError("no planner retry")):
                result = cycle._resume_tail(store, self.repo, self.state, None, "diagnosis")
                next_job.assert_called_once_with(store, self.repo, self.state, None, base)
                self.assertEqual(result.get("observation_id") if status == "passed" else result["state"],
                                 "observation" if status == "passed" else status)

    def test_named_wrong_tool_does_not_consume_lease_or_attempt(self):
        packet = {"job_id": "agent", "kind": "diagnose"}
        self.store.enqueue(JobSpec("agent", self.pins, ("packet:fixture",), (), "agent:test", 0, "json_complete"))
        with patch.object(supervisor, "read_packet", return_value=packet), \
                patch.object(supervisor, "make_pins", return_value={**self.pins, "tool_sha256": "9" * 64}), \
                self.assertRaisesRegex(ValueError, "remains queued"):
            supervisor.run_once(self.repo, self.state, Path("other-agent"), job_id="agent", require_auth=False)
        self.assertEqual(self.store.job("agent")["state"], "queued")
        self.assertEqual(self.store.job("agent")["attempts"], 0)
        self.assertEqual(self.store.attempt_history("agent"), [])

    def test_tool_identity_includes_new_observation_and_raw_adapters(self):
        # Synthetic digests cover every declared input without requiring excluded
        # oracle patches. Production hashing still fails closed on missing files.
        def synthetic(path):
            return hashlib.sha256(path.as_posix().encode()).hexdigest()
        with patch.object(device, "file_sha256", side_effect=synthetic), \
                patch.object(device.interval_experiment, "tool_sha", return_value="a" * 64):
            before = device.tool_sha()
            for name in ('device_observation.py', 'phase9_device_events.py', 'oracle_device_events.c', 'device_event_probe.h', 'oracle_device_events.patch'):
                with self.subTest(name=name), patch.object(
                        device, "file_sha256",
                        side_effect=lambda path: "0" * 64 if path.name == name else synthetic(path)):
                    self.assertNotEqual(device.tool_sha(), before)
            with patch.object(device.interval_experiment, "tool_sha", return_value="b" * 64):
                self.assertNotEqual(device.tool_sha(), before)


    def test_packet_and_registration_tampering_rejected_before_expensive_check(self):
        job_id = self.enqueue()
        spec = self.store.job(job_id)["spec"]
        for field, value in (("inputs", ["device-experiment:" + "0" * 64]), ("prerequisites", ["parent"])):
            with self.subTest(field=field), patch.object(device, "check", side_effect=AssertionError("untrusted packet")), \
                    self.assertRaises(ValueError):
                device.inputs(self.store, self.repo, self.state, job_id, {**spec, field: value})
        path = device.registration_path(self.state, "parent")
        path.write_text(json.dumps(dict(self.record, measurement_sha256="9" * 64)))
        with patch.object(device, "check", side_effect=AssertionError("untrusted registration")), self.assertRaises(ValueError):
            device.inputs(self.store, self.repo, self.state, job_id, spec)

    def test_baseline_and_parent_seal_changes_rejected_after_measurement(self):
        job_id = self.enqueue()
        spec = self.store.job(job_id)["spec"]
        bad_spec = copy.deepcopy(spec)
        bad_spec["pins"]["native_sha256"] = "9" * 64
        with patch.object(device, "check", return_value=({}, self.context)), self.assertRaisesRegex(ValueError, "lineage"):
            device.inputs(self.store, self.repo, self.state, job_id, bad_spec)
        path = self.state / "device-packets" / (job_id + ".json")
        packet = json.loads(path.read_text())
        packet["parent_result"]["sha256"] = "8" * 64
        path.write_bytes(supervisor.canonical_bytes(packet))
        bad_spec = {**spec, "inputs": ["device-experiment:" + hashlib.sha256(supervisor.canonical_bytes(packet)).hexdigest()]}
        with patch.object(device, "check", return_value=({}, self.context)), self.assertRaisesRegex(ValueError, "lineage"):
            device.inputs(self.store, self.repo, self.state, job_id, bad_spec)

    def test_consumer_recomputes_and_rejects_changed_sealed_measurement(self):
        sealed = {"complete": True, "qualification": {"passed": True}}
        with patch.object(device.words, "_sealed_result", return_value=({"spec": {}}, sealed, Path("seal"))), \
                patch.object(device, "inputs", return_value=({**sealed, "changed": True}, {})) as remeasure, \
                self.assertRaisesRegex(ValueError, "contradicts"):
            device.checked_observation(self.store, self.repo, self.state, "observation")
        remeasure.assert_called_once()

    def test_successful_observation_pins_registration_in_feedback(self):
        from scripts.autonomy import experiment_feedback as feedback

        def write(name, payload):
            path = self.state / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(supervisor.canonical_bytes(payload))
            return path

        build = write("build.json", {"executable": "fixture-exe"})
        registration = device.registration_path(self.state, "parent")
        self.record.update(source_build=device.words.pin(build), oracle_build={},
                           supporting_files=[], probe={}, selection={}, occurrence=3)
        registration.write_bytes(supervisor.canonical_bytes(self.record))
        traces = {side: write(side + ".jsonl", {"fixture": side})
                  for side in device.device_observation.TRACES}
        input_file = write("input.json", {"fixture": "input"})
        measurement = {
            "evidence": {side: {"files": {str(path): device.file_sha256(path)}}
                         for side, path in traces.items()},
            "input_evidence": {str(input_file): device.file_sha256(input_file)},
            "observations": [], "prediction_observed": None,
            "qualification": {"passed": True},
            "clock_alignment_validated": False, "retirement_validated": False,
            "completed_queue_operations_proved": False,
        }
        self.context.update(
            retest_id="reference", window=[1907, 1910], history=[],
            baseline_packet={"source_commit": self.pins["source_commit"], "pin_files": {}},
            baseline_seal=self.seals["baseline"],
            diagnosis_message=write("diagnosis.json", {"hypothesis": "not proved"}),
            native_trace=traces["native"], oracle_trace=traces["oracle"],
        )
        job_id = self.enqueue()
        spec = self.store.job(job_id)["spec"]
        with patch.object(device, "check", side_effect=lambda *a, **k: (copy.deepcopy(measurement), self.context)), \
                patch.object(device.interval_experiment, "plan_context", return_value=self.context), \
                patch.object(device.words, "capture_context", return_value=self.context["device_reference"]), \
                patch.object(device.source_build, "validate"), patch.object(device, "oracle_build"), \
                patch.object(feedback, "enqueue_packet") as enqueue:
            report, context = device.inputs(self.store, self.repo, self.state, job_id, spec)
            # Seal real inputs output and consume through the normal dispatcher.
            # Only expensive build/ancestry adapters and final agent enqueue are mocked.
            lease = self.store.lease_job(job_id, "test", ttl=120)
            self.store.start(job_id, lease["token"])
            seal = write(f"attempts/{job_id}/0001/result.json", report)
            self.store.verify(job_id, lease["token"])
            self.store.seal_artifact(job_id, lease["token"], seal)
            self.store.pass_job(job_id, lease["token"])
            queued = feedback.queue_feedback(self.store, self.repo, self.state, None, job_id)

        self.assertEqual(context["plan_message"], registration)
        self.assertIsInstance(context["plan_message"], Path)
        self.assertEqual(queued, feedback.feedback_id(job_id))
        packet = enqueue.call_args.args[2]
        self.assertEqual(packet["evidence_files"][2], device.words.pin(registration))
        self.assertEqual(packet["prerequisites"], ["reference", "baseline", job_id])
        facts = json.loads(Path(packet["evidence_files"][0]["path"]).read_text())
        self.assertFalse(facts["device_limits"]["clock_alignment_validated"])
        self.assertEqual(facts["observation_result"], device.words.pin(seal))


class OracleBuildBindingTests(unittest.TestCase):
    def check(self, mutation=None):
        with tempfile.TemporaryDirectory() as temporary:
            repo = Path(temporary).resolve()
            base = repo / "tools/private/oracle"
            core = base / "mupen64plus-core"
            project = core / "projects/msvc/mupen64plus-core.vcxproj"
            project.parent.mkdir(parents=True)
            project.write_text("project")
            source = core / "observer.c"
            source.write_text("observer")
            dll = base / "emulator/dll/mupen64plus.dll"
            dll.parent.mkdir(parents=True)
            dll.write_bytes(b"dll")
            guard = base / "build.guard.json"
            guard.write_text('{"state":"finished"}')
            report = {"schema": 1, "complete": True, "exit_code": 0, "stop_reason": None, "observation_only": True,
                "command": ["MSBuild.exe", str(project), "/p:Configuration=Release", "/p:Platform=x64"],
                "source_files": {str(p.relative_to(core)): device.file_sha256(p) for p in (source, project)},
                "dll_sha256": device.file_sha256(dll), "runtime_sha256": "a" * 64}
            if mutation == "source": source.write_text("changed")
            if mutation == "library": dll.write_bytes(b"changed")
            if mutation == "incomplete": report["complete"] = False
            if mutation == "unguarded": guard.write_text('{"state":"running"}')
            if mutation == "command": report["command"][0] = "arbitrary.exe"
            if mutation == "missing-source": report["source_files"] = {}
            if mutation == "runtime": report["runtime_sha256"] = "b" * 64
            path = base / "build-result.json"
            path.write_text(json.dumps(report))
            with patch.object(device, "runtime_digest", return_value="a" * 64):
                return device.oracle_build(repo, device.words.pin(path))

    def test_source_and_runtime_bound_guarded_build(self):
        self.assertEqual(self.check()["runtime_sha256"], "a" * 64)

    def test_incomplete_or_changed_build_evidence_fails_closed(self):
        for mutation in ("source", "library", "incomplete", "unguarded", "command", "missing-source", "runtime"):
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                self.check(mutation)


if __name__ == "__main__":
    unittest.main()
