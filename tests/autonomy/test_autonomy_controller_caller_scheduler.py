"""Caller discovery only schedules return capture from unambiguous seals."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from scripts.autonomy.scheduler import advance_controller_returns
from scripts.autonomy.supervisor import file_sha256
from scripts.phase9_controller_return_pair import CAPABILITY_MARKER


class ControllerCallerSchedulerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.state = self.root / "state"
        self.state.mkdir()
        self.native = self.root / "native.exe"
        self.native.write_bytes(CAPABILITY_MARKER)
        self.rom = self.root / "rom.z64"
        self.rom.write_bytes(b"rom")
        self.emulator = self.root / "EmuHawk.exe"
        self.emulator.write_bytes(b"emulator")
        self.source = self.root / "source"
        self.source.mkdir()
        self.packet = {
            "pin_files": {"native": str(self.native), "rom": str(self.rom),
                          "emulator": str(self.emulator)},
            "source_export": str(self.source), "target": 1500,
            "event_windows": [[13, 21], [566, 577]],
            "timeout_seconds": 600,
        }
        self.job = {"spec": {"inputs": ["event-pair-packet:pinned"],
                             "pins": {"native_sha256":
                                      file_sha256(self.native)}}}
        self.store = Mock()
        self.store.status_projection.return_value = {
            "jobs": [{"job_id": "event", "state": "passed"}]}
        self.store.job.return_value = self.job

    def context(self, callers):
        return {"packet": self.packet, "caller_report": {
            "windows": [{"rows": 9, "unique_caller": callers[0]},
                        {"rows": 12, "unique_caller": callers[1]}]}}

    def test_queues_discovered_caller(self):
        with patch("scripts.autonomy.scheduler.sealed_event_pair_context",
                   return_value=self.context(
                       ("0x800431bc", "0x800431bc"))), \
             patch("scripts.autonomy.scheduler.queue_controller_return",
                   return_value="successor") as queue:
            self.assertEqual(advance_controller_returns(
                self.store, self.root, self.state), ["successor"])
            self.assertEqual(queue.call_args.kwargs["return_pc"], 0x800431bc)
            self.assertEqual(queue.call_args.kwargs["windows"],
                             ((13, 21), (566, 577)))

    def test_ambiguous_caller_does_not_guess(self):
        with patch("scripts.autonomy.scheduler.sealed_event_pair_context",
                   return_value=self.context(
                       ("0x800431bc", "0x80043200"))), \
             patch("scripts.autonomy.scheduler.queue_controller_return") as queue:
            self.assertEqual(advance_controller_returns(
                self.store, self.root, self.state), [])
            queue.assert_not_called()

    def test_uses_one_sealed_runtime_when_event_native_lacks_hook(self):
        self.native.write_bytes(b"older event-only native")
        self.job["spec"]["pins"]["native_sha256"] = file_sha256(self.native)
        donor_native = self.root / "hooked.exe"
        donor_native.write_bytes(CAPABILITY_MARKER)
        donor = {"spec": {"inputs": ["controller-return-packet:pinned"],
                          "pins": {"native_sha256":
                                   file_sha256(donor_native)}}}
        self.store.status_projection.return_value = {"jobs": [
            {"job_id": "event", "state": "passed"},
            {"job_id": "donor", "state": "passed"}]}
        self.store.job.side_effect = lambda job_id: {
            "event": self.job, "donor": donor}[job_id]
        donor_packet = {
            "pin_files": {**self.packet["pin_files"],
                          "native": str(donor_native)},
            "native_runtime_sha256": "a" * 64,
        }
        (self.state / "controller-return-packets").mkdir()
        (self.state / "controller-return-packets" / "donor.json").write_text(
            json.dumps(donor_packet), encoding="utf-8")
        with patch("scripts.autonomy.scheduler.sealed_event_pair_context",
                   return_value=self.context(
                       ("0x800431bc", "0x800431bc"))), \
             patch("scripts.autonomy.scheduler.sealed_controller_return_context",
                   return_value={"packet": donor_packet}), \
             patch("scripts.autonomy.scheduler.queue_controller_return",
                   return_value="successor") as queue:
            self.assertEqual(advance_controller_returns(
                self.store, self.root, self.state), ["successor"])
            self.assertEqual(queue.call_args.args[4], donor_native)
            self.assertEqual(queue.call_args.kwargs["caller_event_id"], "event")


if __name__ == "__main__":
    unittest.main()
