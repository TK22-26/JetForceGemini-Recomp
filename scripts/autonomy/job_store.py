"""Versioned SQLite job ledger for bounded, restartable local work.

The database stores hashes and artifact references, never ROM bytes or other
artifact contents. A caller must keep the database under ignored private
storage and run workers separately; this module does not launch anything.
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path
import re
import secrets
import sqlite3
import time
from typing import Any, Iterator
from scripts.autonomy import progress_guard


SCHEMA_VERSION = 3
ACTIVE = ("leased", "running", "verifying")
STATES = ("queued", *ACTIVE, "passed", "failed", "blocked")
ID_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}\Z")
SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")
COMMIT_RE = re.compile(r"[0-9a-f]{40}(?:[0-9a-f]{24})?\Z")
PIN_KEYS = ("source_commit", "tool_sha256", "rom_sha256",
            "emulator_sha256", "native_sha256")


class JobStoreError(ValueError):
    """A job specification, state transition, or artifact is invalid."""


@dataclass(frozen=True)
class JobSpec:
    job_id: str
    pins: dict[str, str]
    inputs: tuple[str, ...]
    prerequisites: tuple[str, ...]
    resource: str
    retry_budget: int
    completion_predicate: str

    def validate(self) -> None:
        if (not isinstance(self.job_id, str) or not ID_RE.fullmatch(self.job_id) or
                not isinstance(self.resource, str) or not ID_RE.fullmatch(self.resource)):
            raise JobStoreError("job ID and resource must be short stable identifiers")
        if set(self.pins) != set(PIN_KEYS):
            raise JobStoreError(f"pins must contain exactly {PIN_KEYS}")
        if not isinstance(self.pins["source_commit"], str) or \
                not COMMIT_RE.fullmatch(self.pins["source_commit"]):
            raise JobStoreError("source_commit must be a Git SHA-1 or SHA-256")
        if any(not isinstance(self.pins[key], str) or
               not SHA256_RE.fullmatch(self.pins[key]) for key in PIN_KEYS[1:]):
            raise JobStoreError("tool, ROM, emulator, and native pins must be SHA-256")
        if isinstance(self.retry_budget, bool) or not isinstance(self.retry_budget, int) or \
                not 0 <= self.retry_budget <= 100:
            raise JobStoreError("retry budget must be 0..100")
        if self.completion_predicate not in ("file_sha256", "json_complete"):
            raise JobStoreError("unsupported completion predicate")
        if len(set(self.prerequisites)) != len(self.prerequisites) or \
                self.job_id in self.prerequisites or \
                any(not ID_RE.fullmatch(item) for item in self.prerequisites):
            raise JobStoreError("invalid prerequisites")
        if any(not isinstance(item, str) or not 1 <= len(item) <= 512
               for item in self.inputs):
            raise JobStoreError("inputs must be bounded artifact references")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class JobStore:
    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(str(self.db_path), timeout=30,
                                          isolation_level=None)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys=ON")
        self.connection.execute("PRAGMA busy_timeout=30000")
        self.connection.execute("PRAGMA journal_mode=WAL")
        self._migrate()

    def close(self) -> None:
        self.connection.close()

    def __enter__(self) -> JobStore:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    @contextmanager
    def _write(self) -> Iterator[sqlite3.Connection]:
        self.connection.execute("BEGIN IMMEDIATE")
        try:
            yield self.connection
            self.connection.execute("COMMIT")
        except BaseException:
            self.connection.execute("ROLLBACK")
            raise

    def _migrate(self) -> None:
        with self._write() as db:
            version = db.execute("PRAGMA user_version").fetchone()[0]
            if version not in (0, 1, 2, SCHEMA_VERSION):
                raise JobStoreError(f"unsupported job-store schema version {version}")
            if version == SCHEMA_VERSION:
                return
            if version in (1, 2):
                if version == 1:
                    progress_guard.install(db)
                progress_guard.install_continuations(db)
                db.execute(f"PRAGMA user_version={SCHEMA_VERSION}")
                return
            db.execute("""CREATE TABLE jobs (
                job_id TEXT PRIMARY KEY,
                spec_json TEXT NOT NULL,
                resource TEXT NOT NULL,
                retry_budget INTEGER NOT NULL,
                state TEXT NOT NULL CHECK(state IN
                  ('queued','leased','running','verifying','passed','failed','blocked')),
                attempts INTEGER NOT NULL DEFAULT 0,
                lease_token TEXT,
                lease_owner TEXT,
                lease_until REAL,
                heartbeat_at REAL,
                sealed_artifact TEXT,
                sealed_sha256 TEXT,
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL
            )""")
            db.execute("""CREATE TABLE attempts (
                job_id TEXT NOT NULL REFERENCES jobs(job_id),
                number INTEGER NOT NULL,
                owner TEXT NOT NULL,
                token TEXT NOT NULL UNIQUE,
                started_at REAL NOT NULL,
                ended_at REAL,
                outcome TEXT,
                detail TEXT,
                artifact TEXT,
                artifact_sha256 TEXT,
                PRIMARY KEY(job_id, number)
            )""")
            db.execute("""CREATE TABLE resource_locks (
                resource TEXT PRIMARY KEY,
                job_id TEXT NOT NULL REFERENCES jobs(job_id),
                token TEXT NOT NULL UNIQUE
            )""")
            db.execute("CREATE INDEX jobs_state_order ON jobs(state,created_at,job_id)")
            progress_guard.install(db)
            progress_guard.install_continuations(db)
            db.execute(f"PRAGMA user_version={SCHEMA_VERSION}")

    def enqueue(self, spec: JobSpec, *, now: float | None = None) -> None:
        spec.validate()
        timestamp = time.time() if now is None else now
        encoded = json.dumps(asdict(spec), sort_keys=True, separators=(",", ":"))
        with self._write() as db:
            row = db.execute("SELECT spec_json FROM jobs WHERE job_id=?", (spec.job_id,)).fetchone()
            if row:
                if row["spec_json"] != encoded:
                    raise JobStoreError("stable job ID already has a different specification")
                return
            db.execute("""INSERT INTO jobs
                (job_id,spec_json,resource,retry_budget,state,created_at,updated_at)
                VALUES (?,?,?,?,?,?,?)""",
                (spec.job_id, encoded, spec.resource, spec.retry_budget,
                 "queued", timestamp, timestamp))

    def _reclaim(self, db: sqlite3.Connection, now: float) -> list[str]:
        expired = db.execute("""SELECT job_id,lease_token,attempts,retry_budget,resource
            FROM jobs WHERE state IN ('leased','running','verifying')
            AND lease_until <= ? ORDER BY job_id""", (now,)).fetchall()
        reclaimed = []
        for row in expired:
            progress_guard.finish(db, row["lease_token"], now)
            next_state = "queued" if row["attempts"] <= row["retry_budget"] else "failed"
            db.execute("""UPDATE attempts SET ended_at=?,outcome='expired',
                detail='lease expired' WHERE token=? AND ended_at IS NULL""",
                (now, row["lease_token"]))
            db.execute("DELETE FROM resource_locks WHERE resource=? AND token=?",
                       (row["resource"], row["lease_token"]))
            db.execute("""UPDATE jobs SET state=?,lease_token=NULL,lease_owner=NULL,
                lease_until=NULL,heartbeat_at=NULL,updated_at=? WHERE job_id=?""",
                (next_state, now, row["job_id"]))
            reclaimed.append(row["job_id"])
        return reclaimed

    def reclaim_expired(self, *, now: float | None = None) -> list[str]:
        timestamp = time.time() if now is None else now
        with self._write() as db:
            return self._reclaim(db, timestamp)

    def _claim(self, db: sqlite3.Connection, row: sqlite3.Row, owner: str,
               ttl: float, timestamp: float) -> dict[str, Any] | None:
        spec = json.loads(row["spec_json"])
        for item in spec["prerequisites"]:
            dependency = db.execute("SELECT state FROM jobs WHERE job_id=?",
                                    (item,)).fetchone()
            if dependency is None or dependency["state"] != "passed":
                return None
        if db.execute("SELECT 1 FROM resource_locks WHERE resource=?",
                      (row["resource"],)).fetchone():
            return None
        if not progress_guard.permit(db, row["job_id"], timestamp):
            return None
        token = secrets.token_hex(16)
        number = row["attempts"] + 1
        db.execute("""UPDATE jobs SET state='leased',attempts=?,lease_token=?,
            lease_owner=?,lease_until=?,heartbeat_at=?,sealed_artifact=NULL,
            sealed_sha256=NULL,updated_at=? WHERE job_id=?""",
            (number, token, owner, timestamp + ttl, timestamp,
             timestamp, row["job_id"]))
        db.execute("""INSERT INTO attempts
            (job_id,number,owner,token,started_at) VALUES (?,?,?,?,?)""",
            (row["job_id"], number, owner, token, timestamp))
        db.execute("INSERT INTO resource_locks(resource,job_id,token) VALUES (?,?,?)",
                   (row["resource"], row["job_id"], token))
        progress_guard.started(db, row["job_id"], token, timestamp)
        return {"job_id": row["job_id"], "attempt": number,
                "token": token, "lease_until": timestamp + ttl,
                "resource": row["resource"], "spec": spec}

    def lease_next(self, owner: str, *, ttl: float = 300,
                   now: float | None = None,
                   agent_jobs: bool = True,
                   priority_resources: tuple[str, ...] = ()) -> dict[str, Any] | None:
        if not isinstance(owner, str) or not ID_RE.fullmatch(owner) or \
                not 0 < ttl <= 86_400 or type(agent_jobs) is not bool or \
                not isinstance(priority_resources, tuple) or \
                len(priority_resources) > 16 or \
                any(not isinstance(item, str) or not ID_RE.fullmatch(item)
                    for item in priority_resources) or \
                len(set(priority_resources)) != len(priority_resources):
            raise JobStoreError("invalid owner, lease duration, or priority resources")
        timestamp = time.time() if now is None else now
        with self._write() as db:
            self._reclaim(db, timestamp)
            rows = db.execute("""SELECT job_id,spec_json,resource,attempts,created_at
                FROM jobs WHERE state='queued' ORDER BY created_at,job_id""").fetchall()
            priorities = {resource: rank for rank, resource in
                          enumerate(priority_resources)}
            rows = sorted(rows, key=lambda row: (
                priorities.get(row["resource"], len(priorities)),
                row["created_at"], row["job_id"]))
            for row in rows:
                inputs = json.loads(row["spec_json"])["inputs"]
                if not agent_jobs and inputs and inputs[0].startswith("packet:"):
                    continue
                lease = self._claim(db, row, owner, ttl, timestamp)
                if lease is not None:
                    return lease
        return None

    def lease_job(self, job_id: str, owner: str, *, ttl: float = 300,
                  now: float | None = None) -> dict[str, Any] | None:
        """Atomically lease one named queued job, respecting dependencies/locks."""
        if (not isinstance(job_id, str) or not ID_RE.fullmatch(job_id) or
                not isinstance(owner, str) or not ID_RE.fullmatch(owner) or
                not 0 < ttl <= 86_400):
            raise JobStoreError("invalid job ID, owner, or lease duration")
        timestamp = time.time() if now is None else now
        with self._write() as db:
            self._reclaim(db, timestamp)
            row = db.execute("""SELECT job_id,spec_json,resource,attempts
                FROM jobs WHERE job_id=? AND state='queued'""", (job_id,)).fetchone()
            return self._claim(db, row, owner, ttl, timestamp) if row else None

    def _active_job(self, db: sqlite3.Connection, job_id: str, token: str,
                    now: float, state: str | None = None) -> sqlite3.Row:
        row = db.execute("SELECT * FROM jobs WHERE job_id=?", (job_id,)).fetchone()
        if row is None or row["lease_token"] != token or row["state"] not in ACTIVE or \
                row["lease_until"] <= now or (state is not None and row["state"] != state):
            raise JobStoreError("missing, expired, or invalid job lease/state")
        return row

    def heartbeat(self, job_id: str, token: str, *, ttl: float = 300,
                  now: float | None = None) -> float:
        if not 0 < ttl <= 86_400:
            raise JobStoreError("invalid lease duration")
        timestamp = time.time() if now is None else now
        with self._write() as db:
            self._active_job(db, job_id, token, timestamp)
            progress_guard.heartbeat(db, token, timestamp)
            until = timestamp + ttl
            db.execute("""UPDATE jobs SET lease_until=?,heartbeat_at=?,updated_at=?
                WHERE job_id=?""", (until, timestamp, timestamp, job_id))
            return until

    def _advance(self, job_id: str, token: str, old: str, new: str,
                 now: float | None) -> None:
        timestamp = time.time() if now is None else now
        with self._write() as db:
            self._active_job(db, job_id, token, timestamp, old)
            db.execute("UPDATE jobs SET state=?,updated_at=? WHERE job_id=?",
                       (new, timestamp, job_id))

    def start(self, job_id: str, token: str, *, now: float | None = None) -> None:
        self._advance(job_id, token, "leased", "running", now)

    def verify(self, job_id: str, token: str, *, now: float | None = None) -> None:
        self._advance(job_id, token, "running", "verifying", now)

    def seal_artifact(self, job_id: str, token: str, artifact: Path, *,
                      expected_sha256: str | None = None,
                      now: float | None = None) -> str:
        artifact = Path(artifact).resolve(strict=True)
        if not artifact.is_file():
            raise JobStoreError("artifact seal requires a regular file")
        actual = _sha256(artifact)
        if expected_sha256 is not None and actual != expected_sha256:
            raise JobStoreError("artifact SHA-256 does not match expectation")
        timestamp = time.time() if now is None else now
        with self._write() as db:
            passed = db.execute("SELECT * FROM jobs WHERE job_id=? AND state='passed'",
                                (job_id,)).fetchone()
            if passed is not None:
                attempt = db.execute("""SELECT outcome FROM attempts
                    WHERE job_id=? AND token=?""", (job_id, token)).fetchone()
                if (attempt is not None and attempt["outcome"] == "passed" and
                        passed["sealed_artifact"] == str(artifact) and
                        passed["sealed_sha256"] == actual):
                    return actual
                raise JobStoreError("passed job seal differs from the completed attempt")
            row = self._active_job(db, job_id, token, timestamp, "verifying")
            predicate = json.loads(row["spec_json"])["completion_predicate"]
            if predicate == "json_complete":
                try:
                    payload = json.loads(artifact.read_text(encoding="utf-8"))
                except (OSError, ValueError) as error:
                    raise JobStoreError("completion artifact is not valid JSON") from error
                if not isinstance(payload, dict) or payload.get("complete") is not True:
                    raise JobStoreError("completion artifact does not declare complete=true")
            existing_path, existing_hash = row["sealed_artifact"], row["sealed_sha256"]
            if existing_path is not None:
                if existing_path != str(artifact) or existing_hash != actual:
                    raise JobStoreError("attempt already sealed a different artifact")
                return actual
            db.execute("""UPDATE jobs SET sealed_artifact=?,sealed_sha256=?,updated_at=?
                WHERE job_id=?""", (str(artifact), actual, timestamp, job_id))
            db.execute("""UPDATE attempts SET artifact=?,artifact_sha256=? WHERE token=?""",
                       (str(artifact), actual, token))
        return actual

    def pass_job(self, job_id: str, token: str, *, now: float | None = None) -> None:
        timestamp = time.time() if now is None else now
        with self._write() as db:
            row = self._active_job(db, job_id, token, timestamp, "verifying")
            artifact = row["sealed_artifact"]
            try:
                intact = bool(artifact) and _sha256(Path(artifact)) == row["sealed_sha256"]
            except OSError:
                intact = False
            if not intact:
                raise JobStoreError("sealed artifact is absent or has changed")
            progress_guard.finish(db, token, timestamp)
            db.execute("""UPDATE jobs SET state='passed',lease_token=NULL,
                lease_owner=NULL,lease_until=NULL,heartbeat_at=NULL,updated_at=?
                WHERE job_id=?""", (timestamp, job_id))
            db.execute("DELETE FROM resource_locks WHERE resource=? AND token=?",
                       (row["resource"], token))
            db.execute("""UPDATE attempts SET ended_at=?,outcome='passed'
                WHERE token=?""", (timestamp, token))

    def fail_job(self, job_id: str, token: str, reason: str, *,
                 blocked: bool = False, now: float | None = None) -> None:
        if not reason or len(reason) > 512:
            raise JobStoreError("failure reason must be 1..512 characters")
        timestamp = time.time() if now is None else now
        with self._write() as db:
            row = self._active_job(db, job_id, token, timestamp)
            state = "blocked" if blocked else "failed"
            progress_guard.finish(db, token, timestamp)
            db.execute("""UPDATE jobs SET state=?,lease_token=NULL,
                lease_owner=NULL,lease_until=NULL,heartbeat_at=NULL,updated_at=?
                WHERE job_id=?""", (state, timestamp, job_id))
            db.execute("DELETE FROM resource_locks WHERE resource=? AND token=?",
                       (row["resource"], token))
            db.execute("""UPDATE attempts SET ended_at=?,outcome=?,detail=?
                WHERE token=?""", (timestamp, state, reason, token))

    def retry_failed(self, job_id: str, *, now: float | None = None) -> None:
        timestamp = time.time() if now is None else now
        with self._write() as db:
            row = db.execute("SELECT state,attempts,retry_budget FROM jobs WHERE job_id=?",
                             (job_id,)).fetchone()
            if row is None or row["state"] != "failed" or \
                    row["attempts"] > row["retry_budget"]:
                raise JobStoreError("job is not retryable")
            db.execute("UPDATE jobs SET state='queued',updated_at=? WHERE job_id=?",
                       (timestamp, job_id))

    def job(self, job_id: str) -> dict[str, Any]:
        row = self.connection.execute("SELECT * FROM jobs WHERE job_id=?",
                                      (job_id,)).fetchone()
        if row is None:
            raise JobStoreError("unknown job ID")
        return {**dict(row), "spec": json.loads(row["spec_json"])}

    def attempt_history(self, job_id: str) -> list[dict[str, Any]]:
        return [dict(row) for row in self.connection.execute(
            "SELECT * FROM attempts WHERE job_id=? ORDER BY number", (job_id,))]

    def status_projection(self) -> dict[str, Any]:
        """Redacted summary: no pins, inputs, paths, tokens, or failure text."""
        rows = self.connection.execute(
            "SELECT job_id,state,resource,attempts FROM jobs ORDER BY created_at,job_id"
        ).fetchall()
        jobs = [dict(row) for row in rows]
        return {"schema": SCHEMA_VERSION,
                "counts": {state: sum(job["state"] == state for job in jobs)
                           for state in STATES},
                "jobs": jobs}
