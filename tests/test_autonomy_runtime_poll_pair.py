"""The poll-pair ledger accepts exactly one sealed predecessor kind."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from scripts.autonomy.poll_pair_job import validate
from scripts.autonomy.scheduler import advance_runtime_poll_pairs
from scripts.autonomy.supervisor import SupervisorError, file_sha256


class RuntimePollPairTests(unittest.TestCase):
    def test_scheduler_refreshes_only_a_real_runtime_upgrade(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            store = Mock()
            store.status_projection.return_value = {"jobs": [
                {"job_id": "return-job", "state": "passed"}]}
            store.job.return_value = {"spec": {
                "inputs": ["controller-return-packet:pinned"],
                "pins": {"native_sha256": "a" * 64}}}
            packet = {"caller_event_id": "event-job", "target": 1500,
                      "pin_files": {"native": "upgraded-native"}}
            event = {"packet": {"pin_files": {"native": "older-native"}}}
            with patch("scripts.autonomy.scheduler.sealed_controller_return_context",
                       return_value={"packet": packet}), \
                 patch("scripts.autonomy.scheduler.sealed_event_pair_context",
                       return_value=event), \
                 patch("scripts.autonomy.scheduler.poll_pair_tool_sha256",
                       return_value="b" * 64), \
                 patch("scripts.autonomy.scheduler.queue_from_controller_return",
                       return_value="poll-pair-new") as queue:
                self.assertEqual(advance_runtime_poll_pairs(
                    store, root, root), ["poll-pair-new"])
                queue.assert_called_once_with(
                    store, root, root, "return-job", target=1500)
                event["packet"]["pin_files"]["native"] = "upgraded-native"
                queue.reset_mock()
                self.assertEqual(advance_runtime_poll_pairs(
                    store, root, root), [])
                queue.assert_not_called()

    def test_controller_return_predecessor_schema(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source"
            source.mkdir()
            pins = {}
            for name in ("rom", "emulator", "native"):
                path = root / name
                path.write_bytes(name.encode("ascii"))
                pins[name] = str(path)
            evidence = []
            for index in range(5):
                path = root / f"evidence-{index}"
                path.write_bytes(bytes([index]))
                evidence.append({"path": str(path),
                                 "sha256": file_sha256(path)})
            packet = {
                "schema": 1, "job_id": "poll-pair-test",
                "controller_return_id": "controller-return-test",
                "source_commit": "a" * 40, "pin_files": pins,
                "source_export": str(source), "target": 1500,
                "timeout_seconds": 600, "evidence_files": evidence,
            }
            with patch("scripts.autonomy.poll_pair_job._inside",
                       return_value=True), \
                 patch("scripts.autonomy.poll_pair_job._git_ok",
                       return_value="a" * 40):
                validate(packet, root, root)
                packet["baseline_id"] = "old-baseline"
                with self.assertRaises(SupervisorError):
                    validate(packet, root, root)
                del packet["controller_return_id"]
                validate(packet, root, root)
                del packet["baseline_id"]
                with self.assertRaises(SupervisorError):
                    validate(packet, root, root)


if __name__ == "__main__":
    unittest.main()
