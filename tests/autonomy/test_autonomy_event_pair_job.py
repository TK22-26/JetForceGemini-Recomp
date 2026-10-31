from pathlib import Path
import json
import tempfile
import unittest
from unittest.mock import Mock, patch

from scripts.autonomy.event_pair_job import (
    CAPABILITY_MARKER, derive_windows, event_capable, job_id_for,
)
from scripts.autonomy.supervisor import SupervisorError
from scripts.autonomy.supervisor import file_sha256
from scripts.autonomy.scheduler import advance_event_pairs


class EventPairJobTests(unittest.TestCase):
    def test_bounded_windows_follow_measured_lag(self):
        report = {"compared_polls": 659,
                  "mismatch_windows": [{"first_poll": 16, "last_poll": 71}],
                  "first_unmatched_polls": [570, 571, 572, 573]}
        self.assertEqual(derive_windows(report), ((13, 21), (566, 577)))
        report["first_unmatched_polls"] = []
        self.assertEqual(derive_windows(report), ((13, 21),))

    def test_nearby_or_end_windows_remain_bounded(self):
        report = {"compared_polls": 30,
                  "mismatch_windows": [{"first_poll": 25}],
                  "first_unmatched_polls": [27]}
        self.assertEqual(derive_windows(report), ((22, 29),))
        report["mismatch_windows"] = [{"first_poll": 31}]
        with self.assertRaisesRegex(SupervisorError, "exceeds"):
            derive_windows(report)

    def test_native_capability_requires_compiled_marker(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "native.exe"
            path.write_bytes(b"ordinary-binary")
            self.assertFalse(event_capable(path))
            path.write_bytes(b"x" * (1024 * 1024 - 10) +
                             CAPABILITY_MARKER + b"y")
            self.assertTrue(event_capable(path))

    def test_job_identity_changes_with_native_binary(self):
        first = job_id_for("poll-lag-one", ((13, 21),), "a" * 64, "b" * 64)
        second = job_id_for("poll-lag-one", ((13, 21),), "a" * 64, "c" * 64)
        self.assertNotEqual(first, second)
        self.assertTrue(first.startswith("event-pair-"))

    def test_scheduler_queues_only_pinned_capable_native(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            state = root / "state"
            (state / "poll-lag-packets").mkdir(parents=True)
            (state / "poll-pair-packets").mkdir()
            (state / "event-pair-packets").mkdir()
            native = root / "native.exe"
            native.write_bytes(CAPABILITY_MARKER)
            (state / "poll-lag-packets" / "lag.json").write_text(
                json.dumps({"pair_job_id": "pair"}), encoding="utf-8")
            (state / "poll-pair-packets" / "pair.json").write_text(
                json.dumps({"pin_files": {"native": str(native)}}),
                encoding="utf-8")
            lag = {"spec": {"inputs": ["poll-lag-packet:pin"]}}
            pair = {"spec": {"pins": {"native_sha256": file_sha256(native)}}}
            store = Mock()
            store.status_projection.return_value = {
                "jobs": [{"job_id": "lag", "state": "passed"}]}
            store.job.side_effect = lambda job_id: {"lag": lag, "pair": pair}[job_id]
            report = {"compared_polls": 659,
                      "mismatch_windows": [{"first_poll": 16}],
                      "first_unmatched_polls": [570]}
            successor = job_id_for("lag", ((13, 21), (566, 577)),
                                   "a" * 64, pair["spec"]["pins"]["native_sha256"])
            event = {"spec": {
                "inputs": ["event-pair-packet:pin"],
                "pins": {"native_sha256": pair["spec"]["pins"]["native_sha256"]}}}
            (state / "event-pair-packets" / (successor + ".json")).write_text(
                json.dumps({"lag_id": "lag", "event_windows":
                            [[13, 21], [566, 577]]}), encoding="utf-8")
            store.job.side_effect = lambda job_id: {
                "lag": lag, "pair": pair, successor: event}[job_id]
            with patch("scripts.autonomy.scheduler.event_pair_context",
                       return_value={"report": report}), \
                 patch("scripts.autonomy.scheduler.event_pair_tool_sha256",
                       return_value="a" * 64), \
                 patch("scripts.autonomy.scheduler.queue_event_pair",
                       return_value=successor) as queue:
                self.assertEqual(advance_event_pairs(store, root, state),
                                 [successor])
                queue.assert_called_once_with(store, root, state, "lag")
                store.status_projection.return_value = {
                    "jobs": [{"job_id": "lag", "state": "passed"},
                             {"job_id": successor, "state": "queued"}]}
                self.assertEqual(advance_event_pairs(store, root, state), [])
                queue.assert_called_once()
                store.status_projection.return_value = {
                    "jobs": [{"job_id": "lag", "state": "passed"},
                             {"job_id": successor, "state": "passed"}]}
                with patch("scripts.autonomy.scheduler.sealed_event_pair_context",
                           return_value={"caller_report": {"rows": 1}}) as sealed:
                    self.assertEqual(advance_event_pairs(store, root, state), [])
                    sealed.assert_called_once_with(store, root, state, successor)
                native.write_bytes(b"changed")
                self.assertEqual(advance_event_pairs(store, root, state), [])
                queue.assert_called_once()


if __name__ == "__main__":
    unittest.main()
