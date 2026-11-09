import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts.autonomy.service_entry import main
from scripts.autonomy.supervisor import SupervisorError


class ServiceEntryTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.repo = Path(temporary.name)
        self.state = self.repo / "tools" / "private" / "autonomy"
        self.agent = self.repo / "codex.cmd"
        self.agent.write_text("stub", encoding="utf-8")

    def argv(self):
        return ["--repo", str(self.repo), "--state", str(self.state),
                "--codex-bin", str(self.agent), "--max-cycles", "1",
                "--max-agent-attempts-per-day", "0"]

    def events(self):
        return [json.loads(line) for line in
                (self.state / "supervisor-events.jsonl").read_text(
                    encoding="utf-8").splitlines()]

    def test_bounded_service_logs_start_cycle_and_stop(self):
        def fake_serve(repo, state, agent, **kwargs):
            self.assertEqual((repo, state, agent),
                             (self.repo, self.state, self.agent))
            self.assertEqual(kwargs["max_agent_attempts_per_utc_day"], 0)
            kwargs["on_cycle"]({"cycle": 1, "outcome": "idle",
                                 "agent_attempts_today": 0, "agent_cap": 0})
            return ["idle"]

        with patch("scripts.autonomy.service_entry.serve", side_effect=fake_serve):
            self.assertEqual(main(self.argv()), 0)
        self.assertEqual([item["kind"] for item in self.events()],
                         ["service-start", "service-cycle", "service-stopped"])

    def test_failure_is_logged_and_returns_nonzero(self):
        with patch("scripts.autonomy.service_entry.serve",
                   side_effect=SupervisorError("test failure")):
            self.assertEqual(main(self.argv()), 2)
        self.assertEqual(self.events()[-1]["kind"], "service-failed")
        self.assertEqual(self.events()[-1]["error"], "test failure")

    def test_rejects_state_outside_private_repo(self):
        outside = self.repo / "other"
        argv = self.argv()
        argv[argv.index("--state") + 1] = str(outside)
        with self.assertRaises(SystemExit):
            main(argv)
        self.assertFalse(outside.exists())


if __name__ == "__main__":
    unittest.main()
