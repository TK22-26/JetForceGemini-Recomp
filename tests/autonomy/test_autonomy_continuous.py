from __future__ import annotations

import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

from scripts.autonomy.continuous import (
    agent_attempts_today, audit_state, serve, single_owner,
)
from scripts.autonomy.job_store import JobSpec, JobStore
from scripts.autonomy.supervisor import SupervisorError


PINS = {"source_commit": "a" * 40, "tool_sha256": "b" * 64,
        "rom_sha256": "c" * 64, "emulator_sha256": "d" * 64,
        "native_sha256": "e" * 64}


class ContinuousTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.repo = self.root / "repo"
        self.repo.mkdir()
        self.state = self.repo / "tools" / "private" / "autonomy"
        self.state.mkdir(parents=True)

    def test_audit_detects_tampered_passed_artifact(self) -> None:
        artifact = self.state / "result.json"
        artifact.write_text(json.dumps({"complete": True}), encoding="utf-8")
        with JobStore(self.state / "jobs.sqlite") as store:
            store.enqueue(JobSpec("sealed", dict(PINS), ("private:fixture",),
                                  (), "local", 0, "json_complete"))
            lease = store.lease_next("test")
            assert lease is not None
            store.start("sealed", lease["token"])
            store.verify("sealed", lease["token"])
            store.seal_artifact("sealed", lease["token"], artifact)
            store.pass_job("sealed", lease["token"])
            good = audit_state(store, self.state)
            self.assertTrue(good["healthy"])
            self.assertEqual(good["passed_verified"], 1)
            artifact.write_text(json.dumps({"complete": False}), encoding="utf-8")
            bad = audit_state(store, self.state)
            self.assertFalse(bad["healthy"])
            self.assertEqual(bad["issues"][0]["reason"], "passed-seal-invalid")

    def test_utc_agent_attempt_cap_counts_expired_leases(self) -> None:
        now = time.time()
        with JobStore(self.state / "jobs.sqlite") as store:
            store.enqueue(JobSpec("agent", dict(PINS), ("packet:" + "f" * 64,),
                                  (), "source-writer", 1, "json_complete"), now=now)
            lease = store.lease_next("test", now=now)
            assert lease is not None
            self.assertEqual(agent_attempts_today(store, now=now), 1)
            store.reclaim_expired(now=now + 301)
            self.assertEqual(agent_attempts_today(store, now=now), 1)

    def test_audit_detects_missing_active_resource_lock(self) -> None:
        with JobStore(self.state / "jobs.sqlite") as store:
            store.enqueue(JobSpec("active", dict(PINS), ("private:fixture",),
                                  (), "local", 0, "json_complete"))
            lease = store.lease_next("test")
            assert lease is not None
            self.assertTrue(audit_state(store, self.state)["healthy"])
            store.connection.execute(
                "DELETE FROM resource_locks WHERE token=?", (lease["token"],))
            report = audit_state(store, self.state)
            self.assertFalse(report["healthy"])
            self.assertEqual(report["issues"][0]["reason"],
                             "active-resource-lock-missing")

    def test_single_owner_rejects_second_continuous_loop(self) -> None:
        with single_owner(self.state):
            with self.assertRaisesRegex(SupervisorError, "another continuous"):
                with single_owner(self.state):
                    pass

    def test_bounded_idle_serve_writes_audit(self) -> None:
        fake_binary = self.root / "fake-agent"
        fake_binary.write_text("fixture", encoding="utf-8")
        events = []
        with patch("scripts.autonomy.scheduler.advance_jobs", return_value=[]):
            outcomes = serve(self.repo, self.state, fake_binary,
                             max_cycles=1, max_agent_attempts_per_utc_day=0,
                             on_cycle=events.append)
        self.assertEqual(outcomes, ["idle"])
        self.assertEqual(events[0]["agent_cap"], 0)
        self.assertEqual(len(list((self.state / "audits").glob("*.json"))), 1)

    def test_zero_agent_cap_leaves_agent_packet_queued(self) -> None:
        fake_binary = self.root / "fake-agent"
        fake_binary.write_text("fixture", encoding="utf-8")
        with JobStore(self.state / "jobs.sqlite") as store:
            store.enqueue(JobSpec("agent", dict(PINS), ("packet:" + "f" * 64,),
                                  (), "source-writer", 1, "json_complete"))
        with patch("scripts.autonomy.scheduler.advance_jobs", return_value=[]):
            outcomes = serve(self.repo, self.state, fake_binary,
                             max_cycles=1, max_agent_attempts_per_utc_day=0)
        self.assertEqual(outcomes, ["idle"])
        with JobStore(self.state / "jobs.sqlite") as store:
            self.assertEqual(store.job("agent")["state"], "queued")


if __name__ == "__main__":
    unittest.main()
