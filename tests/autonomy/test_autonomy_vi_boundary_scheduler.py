import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts.autonomy.scheduler import advance_vi_boundaries
from scripts.autonomy.supervisor import file_sha256


class FakeStore:
    def __init__(self, jobs):
        self.jobs = jobs

    def status_projection(self):
        return {"jobs": [{"job_id": key, "state": "passed"}
                         for key in self.jobs]}

    def job(self, job_id):
        return self.jobs[job_id]


class ViBoundarySchedulerTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.state = self.root / "tools" / "private" / "autonomy"
        (self.state / "update-packets").mkdir(parents=True)
        self.pin_files = {}
        for key in ("rom", "emulator", "native"):
            path = self.root / key
            path.write_text(key, encoding="utf-8")
            self.pin_files[key] = str(path)

    def job(self, job_id, *, predecessor=None, tool="current"):
        pair = {"native_before": 1264, "native_after": 1265,
                "oracle_before": 1260, "oracle_after": 1261}
        packet = {"focus_pair": pair, "pin_files": self.pin_files}
        if predecessor:
            packet["predecessor_id"] = predecessor
        (self.state / "update-packets" / (job_id + ".json")).write_text(
            json.dumps(packet), encoding="utf-8")
        root = self.state / "attempts" / job_id / "0001"
        root.mkdir(parents=True)
        alignment = root / "update-alignment.json"
        alignment.write_text(json.dumps({"first_later_mismatch": {
            "native_update": 1265, "oracle_update": 1261,
            "reason": "semantic-mismatch"}}), encoding="utf-8")
        result = root / "result.json"
        result.write_text(json.dumps({
            "complete": True, "oracle_vi_trace_sha256": "a" * 64,
            "focus_comparison_sha256": "b" * 64,
            "alignment_diagnostic_sha256": file_sha256(alignment)}),
            encoding="utf-8")
        return {"spec": {"inputs": ["update-packet:test"],
                         "pins": {"tool_sha256": tool, **{
                             key + "_sha256": file_sha256(Path(value))
                             for key, value in self.pin_files.items()}}},
                "sealed_artifact": str(result),
                "sealed_sha256": file_sha256(result)}

    def test_only_current_unsuperseded_focus_is_queued(self):
        jobs = {"old": self.job("old"),
                "current": self.job("current", predecessor="old")}
        queued = []
        with patch("scripts.autonomy.scheduler.boundary_tool_sha256",
                   return_value="boundary"), patch(
                       "scripts.autonomy.scheduler.update_tool_sha256",
                       return_value="current"), patch(
                           "scripts.autonomy.scheduler.queue_boundary",
                           side_effect=lambda *args, **kwargs:
                               queued.append(kwargs["focus_job_id"])):
            result = advance_vi_boundaries(FakeStore(jobs), self.root,
                                           self.state, max_new_jobs=16)
        self.assertEqual(queued, ["current"])
        self.assertEqual(len(result), 1)

    def test_stale_tool_does_not_requeue_historical_focus(self):
        jobs = {"old": self.job("old", tool="old")}
        with patch("scripts.autonomy.scheduler.boundary_tool_sha256",
                   return_value="boundary"), patch(
                       "scripts.autonomy.scheduler.update_tool_sha256",
                       return_value="current"), patch(
                           "scripts.autonomy.scheduler.queue_boundary") as queue:
            self.assertEqual(advance_vi_boundaries(
                FakeStore(jobs), self.root, self.state), [])
        queue.assert_not_called()


if __name__ == "__main__":
    unittest.main()
