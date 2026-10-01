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
