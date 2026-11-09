import copy
import json
import hashlib
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from scripts.autonomy.branch_count_repair import advance, drive_case, register, require_red_proof
from scripts.autonomy.supervisor import SupervisorError, canonical_bytes


class BranchRepairProofTests(unittest.TestCase):
    def proof(self):
        return {"kind": "jfg-native-branch-count-check", "complete": True, "match": False,
                "cases": 28, "hardware_qualified": False, "game_cause_proved": False,
                "mismatches": [{"kind": kind, "taken": 0, "iterations": count,
                                "native_ticks": 8 * count + 2, "oracle_ticks": 10 * count + 2}
                               for kind in (4, 5) for count in (16, 128)]}

    def test_accepts_only_the_independently_measured_four_failures(self):
        require_red_proof(self.proof())
        for key, value in (("complete", False), ("match", True), ("cases", 27),
                           ("hardware_qualified", True), ("game_cause_proved", True)):
            proof = self.proof()
            proof[key] = value
            with self.subTest(key=key), self.assertRaises(SupervisorError):
                require_red_proof(proof)

    def test_rejects_extra_missing_reordered_or_different_failures(self):
        base = self.proof()
        for rows in (base["mismatches"][:3], base["mismatches"] + base["mismatches"][:1],
                     list(reversed(base["mismatches"]))):
            with self.assertRaises(SupervisorError):
                require_red_proof(dict(base, mismatches=rows))
        bad = copy.deepcopy(base)
        bad["mismatches"][0]["native_ticks"] = 132
        with self.assertRaises(SupervisorError):
            require_red_proof(bad)

    def test_registration_creates_parent_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as temporary:
            repo = Path(temporary)
            state = repo / "tools/private/autonomy"
            report, trace = repo / "report.json", repo / "trace.tsv"
            report.write_text("{}")
            trace.write_text("fixture")
            first = register(repo, state, diagnosis_id="diagnosis", baseline_id="baseline",
                             oracle_report=report, oracle_trace=trace)
            second = register(repo, state, diagnosis_id="diagnosis", baseline_id="baseline",
                              oracle_report=report, oracle_trace=trace)
            self.assertEqual(first, second)
            self.assertEqual(json.loads(first.read_text())["policy"], "regimm-annulled-count-v1")
            (state / "PAUSED").touch()
            self.assertEqual(advance(None, repo, state, None), [])

    def test_drive_rejects_unbounded_budget(self):
        for count in (0, 4, True):
            with self.assertRaises(SupervisorError):
                drive_case(None, None, None, None, max_jobs=count)

    def test_drive_waits_for_existing_active_worker_without_duplicate_launch(self):
        with tempfile.TemporaryDirectory() as temporary:
            state = Path(temporary)
            case = state / "case.json"
            case.write_text('{"fixture":true}')
            job_id = "bc-" + hashlib.sha256(canonical_bytes({"fixture": True})).hexdigest()[:12]
            store = MagicMock()
            store.job.return_value = {"state": "running"}
            store.status_projection.return_value = {"jobs": [{"job_id": job_id}]}
            context = MagicMock()
            context.__enter__.return_value = store
            with patch("scripts.autonomy.branch_count_repair.JobStore", return_value=context), \
                 patch("scripts.autonomy.branch_count_repair.queue_case", return_value=None), \
                 patch("scripts.autonomy.supervisor.run_once") as run:
                result = drive_case(state, state, None, case)
            self.assertEqual(result, {"state": "running", "stage": "implementation", "job_id": job_id})
            run.assert_not_called()

    def test_drive_resumes_exact_retest_and_is_idempotent_after_completion(self):
        with tempfile.TemporaryDirectory() as temporary:
            state = Path(temporary)
            case = state / "case.json"
            case.write_text('{"fixture":true}')
            job_id = "bc-" + hashlib.sha256(canonical_bytes({"fixture": True})).hexdigest()[:12]
            review, retest = job_id + "-review", job_id + "-review-native-retest"
            states = {job_id: "passed", review: "passed", retest: "queued"}
            store = MagicMock()
            store.job.side_effect = lambda name: {"state": states[name]}
            store.status_projection.side_effect = lambda: {"jobs": [{"job_id": name} for name in states]}
            context = MagicMock()
            context.__enter__.return_value = store
            result = {"candidate_disposition": "rejected-regression", "raw_frontier": {"classification": "regressed-earlier"}}
            def run(*args, **kwargs):
                self.assertEqual(kwargs["job_id"], retest)
                states[retest] = "passed"
                return "sealed"
            with patch("scripts.autonomy.branch_count_repair.JobStore", return_value=context), \
                 patch("scripts.autonomy.branch_count_repair.queue_case", return_value=None), \
                 patch("scripts.autonomy.candidate_review.queue_evidence_review", return_value=None), \
                 patch("scripts.autonomy.branch_count_repair._sealed_result", return_value=(None, result, None)), \
                 patch("scripts.autonomy.supervisor.run_once", side_effect=run) as worker:
                first = drive_case(state, state, None, case)
                second = drive_case(state, state, None, case)
            self.assertEqual(first, second)
            self.assertEqual(first["disposition"], "rejected-regression")
            self.assertFalse(first["parity_verified"])
            worker.assert_called_once()


if __name__ == "__main__":
    unittest.main()
