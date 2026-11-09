import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from scripts.autonomy.controller_return_job import _caller_context, job_id_for
from scripts.autonomy.supervisor import SupervisorError, file_sha256


class ControllerReturnJobTests(unittest.TestCase):
    def test_job_identity_tracks_binary_window_caller_and_tools(self):
        base = ("a" * 64, "b" * 64, "c" * 64, 1500,
                ((552, 576),), 0x800431BC, "d" * 64)
        first = job_id_for(*base)
        self.assertTrue(first.startswith("controller-return-"))
        for index, replacement in ((1, "e" * 64),
                                   (4, ((554, 576),)),
                                   (5, 0x800431C0),
                                   (6, "e" * 64)):
            changed = list(base)
            changed[index] = replacement
            self.assertNotEqual(first, job_id_for(*changed))

    def test_caller_event_and_report_are_part_of_identity(self):
        base = ("a" * 64, "b" * 64, "c" * 64, 1500,
                ((13, 21),), 0x800431BC, "d" * 64)
        discovered = job_id_for(*base, "event-pair-one", "e" * 64)
        self.assertNotEqual(discovered, job_id_for(*base))
        self.assertNotEqual(discovered, job_id_for(
            *base, "event-pair-two", "e" * 64))
        self.assertNotEqual(discovered, job_id_for(
            *base, "event-pair-one", "f" * 64))

    def test_caller_evidence_must_match_sealed_event(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            report_path = root / "caller-report.json"
            report_path.write_text("{}", encoding="utf-8")
            packet = {
                "caller_event_id": "event-pair-one",
                "caller_report_sha256": file_sha256(report_path),
                "return_pc": "0x800431bc", "source_export": str(root),
                "target": 1500, "event_windows": [[13, 21]],
                "pin_files": {"rom": "rom", "emulator": "emulator"},
            }
            event = {"packet": {
                "source_export": str(root), "target": 1500,
                "event_windows": [[13, 21]],
                "pin_files": {"rom": "rom", "emulator": "emulator"}},
                "caller_report": {"windows": [{
                    "rows": 9, "unique_caller": "0x800431bc"}]},
                "caller_report_path": report_path}
            with patch("scripts.autonomy.event_pair_job.sealed_context",
                       return_value=event):
                self.assertIs(_caller_context(Mock(), root, root, packet),
                              event)
                packet["caller_report_sha256"] = "0" * 64
                with self.assertRaises(SupervisorError):
                    _caller_context(Mock(), root, root, packet)
                packet["caller_report_sha256"] = file_sha256(report_path)
                packet["return_pc"] = "0x800431c0"
                with self.assertRaises(SupervisorError):
                    _caller_context(Mock(), root, root, packet)


if __name__ == "__main__":
    unittest.main()
