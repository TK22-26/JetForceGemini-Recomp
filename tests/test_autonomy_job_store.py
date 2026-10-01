from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from scripts.autonomy.job_store import JobSpec, JobStore, JobStoreError, SCHEMA_VERSION


PINS = {"source_commit": "a" * 40, "tool_sha256": "b" * 64,
        "rom_sha256": "c" * 64, "emulator_sha256": "d" * 64,
        "native_sha256": "e" * 64}


def spec(job_id: str, *, resource: str = "writer:branch-a",
         prerequisites: tuple[str, ...] = (), retry_budget: int = 1,
         predicate: str = "json_complete") -> JobSpec:
    return JobSpec(job_id, dict(PINS), ("private:input-manifest-01",),
                   prerequisites, resource, retry_budget, predicate)


class JobStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.store = JobStore(self.root / "private" / "jobs.sqlite")
        self.addCleanup(self.store.close)

    def artifact(self, name: str = "result.json", *, complete: bool = True) -> Path:
        path = self.root / name
        path.write_text(json.dumps({"complete": complete, "value": 7}), encoding="utf-8")
        return path

    def test_version_stable_ids_and_redacted_projection(self) -> None:
        first = spec("gate-01")
        self.store.enqueue(first, now=1)
        self.store.enqueue(first, now=2)
        self.assertEqual(self.store.job("gate-01")["attempts"], 0)
        with self.assertRaisesRegex(JobStoreError, "different specification"):
            self.store.enqueue(spec("gate-01", resource="writer:other"), now=3)
        version = self.store.connection.execute("PRAGMA user_version").fetchone()[0]
        self.assertEqual(version, SCHEMA_VERSION)
        projection = self.store.status_projection()
        self.assertEqual(projection["counts"]["queued"], 1)
        encoded = json.dumps(projection)
        self.assertNotIn(PINS["rom_sha256"], encoded)
        self.assertNotIn("private:input", encoded)
        self.assertNotIn(str(self.root), encoded)

    def test_lease_resource_lock_prerequisite_and_sealed_pass(self) -> None:
        self.store.enqueue(spec("a"), now=1)
        self.store.enqueue(spec("b"), now=2)
        self.store.enqueue(spec("c", resource="writer:branch-b",
                                prerequisites=("a",)), now=3)
        other = JobStore(self.store.db_path)
        self.addCleanup(other.close)
        lease = self.store.lease_next("worker-1", now=10, ttl=30)
        assert lease is not None
        self.assertEqual(lease["job_id"], "a")
        self.assertIsNone(other.lease_next("worker-2", now=11, ttl=30))
        self.assertEqual(self.store.heartbeat("a", lease["token"], now=20, ttl=30), 50)
        self.store.start("a", lease["token"], now=21)
        self.store.verify("a", lease["token"], now=22)
        artifact = self.artifact()
        sealed = self.store.seal_artifact("a", lease["token"], artifact, now=23)
        self.assertEqual(self.store.seal_artifact("a", lease["token"], artifact, now=24), sealed)
        self.store.pass_job("a", lease["token"], now=25)
        self.assertEqual(self.store.seal_artifact("a", lease["token"], artifact, now=25), sealed)
        self.assertEqual(self.store.job("a")["state"], "passed")
        next_lease = other.lease_next("worker-2", now=26, ttl=30)
        assert next_lease is not None
        self.assertEqual(next_lease["job_id"], "b")
        independent = self.store.lease_next("worker-3", now=27, ttl=30)
        assert independent is not None
        self.assertEqual(independent["job_id"], "c")
        self.assertEqual(self.store.attempt_history("a")[0]["outcome"], "passed")

    def test_named_lease_does_not_consume_another_queued_job(self) -> None:
        self.store.enqueue(spec("first", resource="source-a"), now=1)
        self.store.enqueue(spec("second", resource="source-b"), now=2)
        named = self.store.lease_job("second", "importer", now=3, ttl=30)
        assert named is not None
        self.assertEqual(named["job_id"], "second")
        self.assertEqual(self.store.job("first")["state"], "queued")
        self.assertIsNone(self.store.lease_job("second", "another", now=4))
        self.assertIsNone(self.store.lease_job("missing", "another", now=4))

    def test_agent_cap_selector_keeps_deterministic_jobs_runnable(self) -> None:
        self.store.enqueue(JobSpec("agent", dict(PINS), ("packet:" + "f" * 64,),
                                   (), "source-writer", 1, "json_complete"), now=1)
        self.store.enqueue(JobSpec("local", dict(PINS), ("comparison-packet:" + "a" * 64,),
                                   (), "comparator", 1, "json_complete"), now=2)
        lease = self.store.lease_next("capped-worker", now=3, agent_jobs=False)
        assert lease is not None
        self.assertEqual(lease["job_id"], "local")
        self.assertEqual(self.store.job("agent")["state"], "queued")

    def test_explicit_resource_priority_keeps_other_jobs_fifo(self) -> None:
        self.store.enqueue(spec("old", resource="native:determinism"), now=1)
        self.store.enqueue(spec("lag", resource="analysis:poll-lag"), now=2)
        self.store.enqueue(spec("later", resource="emulator:bizhawk"), now=3)
        lease = self.store.lease_next(
            "worker", now=4, priority_resources=("analysis:poll-lag",))
        assert lease is not None
        self.assertEqual(lease["job_id"], "lag")
        self.store.fail_job("lag", lease["token"], "fixture", blocked=True, now=5)
        next_lease = self.store.lease_next(
            "worker", now=6, priority_resources=("analysis:poll-lag",))
        assert next_lease is not None
        self.assertEqual(next_lease["job_id"], "old")
        with self.assertRaises(JobStoreError):
            self.store.lease_next("worker", priority_resources=("bad space",))

    def test_expiry_requeues_then_exhausts_retry_budget(self) -> None:
        self.store.enqueue(spec("expiring", retry_budget=1), now=0)
        first = self.store.lease_next("worker-1", ttl=10, now=1)
        assert first is not None
        self.assertEqual(self.store.reclaim_expired(now=11), ["expiring"])
        self.assertEqual(self.store.job("expiring")["state"], "queued")
        with self.assertRaisesRegex(JobStoreError, "invalid job lease"):
            self.store.start("expiring", first["token"], now=12)
        second = self.store.lease_next("worker-2", ttl=10, now=12)
        assert second is not None
        self.assertEqual(second["attempt"], 2)
        self.assertNotEqual(second["token"], first["token"])
        self.assertEqual(self.store.reclaim_expired(now=22), ["expiring"])
        self.assertEqual(self.store.job("expiring")["state"], "failed")
        self.assertIsNone(self.store.lease_next("worker-3", now=23))
        self.assertEqual([x["outcome"] for x in self.store.attempt_history("expiring")],
                         ["expired", "expired"])

    def test_failed_retry_and_blocked_job_release_lock(self) -> None:
        self.store.enqueue(spec("failed"), now=1)
        self.store.enqueue(spec("after"), now=2)
        lease = self.store.lease_next("worker-1", now=3)
        assert lease is not None
        self.store.start("failed", lease["token"], now=4)
        self.store.fail_job("failed", lease["token"], "synthetic failure", now=5)
        self.assertEqual(self.store.job("failed")["state"], "failed")
        self.store.retry_failed("failed", now=6)
        self.assertEqual(self.store.job("failed")["state"], "queued")
        after = self.store.lease_next("worker-2", now=7)
        assert after is not None
        self.assertEqual(after["job_id"], "failed")
        self.store.fail_job("failed", after["token"], "needs user input",
                            blocked=True, now=8)
        self.assertEqual(self.store.job("failed")["state"], "blocked")
        with self.assertRaisesRegex(JobStoreError, "not retryable"):
            self.store.retry_failed("failed", now=9)
        following = self.store.lease_next("worker-3", now=10)
        assert following is not None
        self.assertEqual(following["job_id"], "after")

    def test_incomplete_or_changed_artifact_never_passes(self) -> None:
        self.store.enqueue(spec("seal"), now=1)
        lease = self.store.lease_next("worker-1", now=2)
        assert lease is not None
        self.store.start("seal", lease["token"], now=3)
        self.store.verify("seal", lease["token"], now=4)
        with self.assertRaisesRegex(JobStoreError, "absent or has changed"):
            self.store.pass_job("seal", lease["token"], now=5)
        artifact = self.artifact(complete=False)
        with self.assertRaisesRegex(JobStoreError, "complete=true"):
            self.store.seal_artifact("seal", lease["token"], artifact, now=6)
        artifact = self.artifact(complete=True)
        self.store.seal_artifact("seal", lease["token"], artifact, now=7)
        artifact.write_text("tampered", encoding="utf-8")
        with self.assertRaisesRegex(JobStoreError, "absent or has changed"):
            self.store.pass_job("seal", lease["token"], now=8)
        self.assertEqual(self.store.job("seal")["state"], "verifying")


if __name__ == "__main__":
    unittest.main()
