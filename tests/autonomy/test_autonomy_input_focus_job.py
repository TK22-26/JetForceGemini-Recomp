import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from scripts.autonomy.input_focus_job import job_id_for
from scripts.autonomy.scheduler import (
    advance_input_focus_pairs, clock_diagnosis_id, focus_diagnosis_id,
)
from scripts.autonomy.supervisor import file_sha256


class InputFocusJobTests(unittest.TestCase):
    def test_job_identity_changes_with_native_binary(self):
        first = job_id_for("event-one", (566, 569), "a" * 64, "b" * 64)
        second = job_id_for("event-one", (566, 569), "a" * 64, "c" * 64)
        self.assertNotEqual(first, second)
        self.assertTrue(first.startswith("input-focus-"))

    def test_focused_diagnosis_identity_tracks_sealed_report(self):
        first = focus_diagnosis_id("poll-lag-one", "a" * 64)
        second = focus_diagnosis_id("poll-lag-one", "b" * 64)
        self.assertNotEqual(first, second)
        self.assertIn("-focus-", first)
        self.assertLessEqual(len(focus_diagnosis_id("x" * 120, "a" * 64)),
                             128)
        self.assertNotEqual(first, focus_diagnosis_id(
            "poll-lag-one", "a" * 64, "c" * 64))
        self.assertNotEqual(clock_diagnosis_id("poll-lag-one", "c" * 64),
                            clock_diagnosis_id("poll-lag-one", "d" * 64))

    def test_scheduler_queues_once_and_reuses_verified_capture(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            state = root / "state"
            (state / "event-pair-packets").mkdir(parents=True)
            (state / "input-focus-packets").mkdir()
            native = root / "native.exe"
            native.write_bytes(b"pinned-native")
            (state / "event-pair-packets" / "event.json").write_text(
                json.dumps({"pin_files": {"native": str(native)}}),
                encoding="utf-8")
            native_sha = file_sha256(native)
            event = {"spec": {"inputs": ["event-pair-packet:pin"],
                              "pins": {"native_sha256": native_sha}}}
            store = Mock()
            store.job.side_effect = lambda job_id: {
                "event": event, successor: focus_job}[job_id]
            store.status_projection.return_value = {
                "jobs": [{"job_id": "event", "state": "passed"}]}
            successor = job_id_for("event", (566, 569), "a" * 64,
                                   native_sha)
            focus_job = {"spec": {
                "inputs": ["input-focus-packet:pin"],
                "pins": {"native_sha256": native_sha}}}
            (state / "input-focus-packets" / (successor + ".json")).write_text(
                json.dumps({"event_id": "event",
                            "focus_updates": [566, 569]}), encoding="utf-8")
            with patch("scripts.autonomy.scheduler.input_focus_context",
                       return_value={"focus": (566, 569)}), \
                 patch("scripts.autonomy.scheduler.input_focus_tool_sha256",
                       return_value="a" * 64), \
                 patch("scripts.autonomy.scheduler.queue_input_focus",
                       return_value=successor) as queue:
                self.assertEqual(advance_input_focus_pairs(
                    store, root, state), [successor])
                queue.assert_called_once_with(store, root, state, "event")
                store.status_projection.return_value = {"jobs": [
                    {"job_id": "event", "state": "passed"},
                    {"job_id": successor, "state": "queued"}]}
                self.assertEqual(advance_input_focus_pairs(
                    store, root, state), [])
                store.status_projection.return_value = {"jobs": [
                    {"job_id": "event", "state": "passed"},
                    {"job_id": successor, "state": "passed"}]}
                with patch("scripts.autonomy.scheduler.sealed_input_focus_context",
                           return_value={}) as sealed:
                    self.assertEqual(advance_input_focus_pairs(
                        store, root, state), [])
                    sealed.assert_called_once_with(store, root, state,
                                                   successor)
                native.write_bytes(b"changed-native")
                self.assertEqual(advance_input_focus_pairs(
                    store, root, state), [])
                queue.assert_called_once()


if __name__ == "__main__":
    unittest.main()
