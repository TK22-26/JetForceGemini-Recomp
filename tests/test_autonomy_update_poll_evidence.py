import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.autonomy.supervisor import SupervisorError, canonical_bytes
from scripts.autonomy.update_poll_evidence import derive


class UpdatePollEvidenceTests(unittest.TestCase):
    def test_derived_report_is_pinned_and_idempotent(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            repo, state, pair = root / "repo", root / "state", root / "pair"
            (repo / "scripts").mkdir(parents=True)
            (pair / "native").mkdir(parents=True)
            (pair / "oracle").mkdir()
            for path in (
                repo / "scripts" / "phase9_update_poll_alignment.py",
                pair / "plan.json", pair / "pair-result.json",
                pair / "native" / "retrace-hashes.jsonl.updates.jsonl",
                pair / "oracle" / "update-hashes.jsonl",
            ):
                path.write_text("pinned\n", encoding="utf-8")
            alignment = {
                "first_semantic_difference": {
                    "reason": "state-difference", "update": 8},
                "alignment_validated": False, "parity_verified": False,
            }
            diagnostic = {
                "classification": "poll-anchored-semantic-resynchronization",
                "same_poll_anchor": {"controller_polls": 12},
                "matched_update_run": 9,
            }
            event = {"pair_root": pair}
            with patch("scripts.autonomy.update_poll_evidence.analyze_updates",
                       return_value=alignment), patch(
                "scripts.autonomy.update_poll_evidence.diagnose",
                    return_value=diagnostic) as diagnose_mock:
                first_path, first = derive(state, "event-test", event, repo)
                second_path, second = derive(state, "event-test", event, repo)
                self.assertEqual(first_path, second_path)
                self.assertEqual(first, second)
                self.assertEqual(first_path.read_bytes(), canonical_bytes(first))
                self.assertEqual(diagnose_mock.call_args.args[2], 8)
                first_path.write_text(json.dumps({"tampered": True}),
                                      encoding="utf-8")
                with self.assertRaises(SupervisorError):
                    derive(state, "event-test", event, repo)

    def test_no_mismatch_produces_no_artifact(self):
        with patch("scripts.autonomy.update_poll_evidence.analyze_updates",
                   return_value={"first_semantic_difference": None}):
            self.assertIsNone(derive(Path("unused"), "event-test",
                                     {"pair_root": Path.cwd()}, Path.cwd()))


if __name__ == "__main__":
    unittest.main()
