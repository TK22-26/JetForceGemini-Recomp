# Persistent autonomy requirements

The user requires the production anti-stall guard to remain enabled at all
times, including after context compaction, session restart, and Goal resume.

- Before autonomous investigation execution, verify the production ledger's
  guard is enabled and recover its existing investigation state and budget.
- Run autonomous investigation jobs through the guarded supervisor. Foreground
  orchestration and read-only status checks are not substitutes for guarded
  experiment, build, replay, or coding-worker execution.
- Never disable the production guard, reset its counters, rename/re-root the
  same investigation for a fresh allowance, or bypass a denial with direct
  execution. Report an exhausted investigation or blocker and stop that work.
- Keep this requirement in every compaction/handoff summary. A Codex Goal
  resume does not reset project budgets or override supervisor decisions.
- Guard-disabled tests may use isolated fixture ledgers only, never the
  operational ledger. Preserve evidence and existing user changes.

Implementation and limits: docs/planning/autonomy-progress-guard.md.

# Upstream reference knowledge

For upstream dependency updates or overlay, controller/save, camera, and
audio investigations, consult [the pinned reference review](docs/upstream/reference-review-2026-10-01.md)
and [reference catalog](docs/upstream/reference-catalog.json). The catalog
separates existing behavior, source observations, and unvalidated work
items. It does not authorize runtime changes, reopen shelved investigations,
or replace the production guard requirements above.

# Maintainer Git identity

For owner-authorized commits in this checkout, use `TK22-26` with
`254768757+TK22-26@users.noreply.github.com` for the author and committer.
Keep commit timestamps in UTC for the existing public metadata policy.
The old generic maintainer identity is accepted only for preserved history;
do not choose it for new maintainer commits or rewrite existing history.
