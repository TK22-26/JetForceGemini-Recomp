# TOOLING-SESSION-20261101: Retained Codex process blocks session resume

- Severity: moderate development-tooling interruption; no observed history loss.
- Status: reproduced lock contention; local recovery verified; underlying lifecycle cause open; owner resume verification pending.
- Reported and last updated (UTC): 2026-11-01, including a recurrence later that day.
- Affected profile: Windows, WezTerm, Codex CLI; installed npm package reports version 0.166.0 at the second recovery. Runtime binary version was not independently queried.
- Evidence origin: owner reports, local process inventory, session event metadata and file-lock checks. No game execution or original-ROM comparison applies.
- Related policy: [persistent issue records](README.md) and [production autonomy guard](../../planning/autonomy-progress-guard.md).

## Symptoms and reproduction

The owner requested closure of an older session so it could be resumed, then
reported the same problem again. In both recoveries, the older Codex process
remained running and its saved conversation ended with a completed turn.
The precise terminal-close sequence and a deterministic reproduction remain unknown.

## Evidence and hypotheses

At the second recovery, the older process began at 2026-11-01T03:59:34Z;
the conversation's last event was `task_complete` at 12:17:15.625Z.
Its descendants were the code-mode host and console host, with no build or
shell worker in that tree. A separate, newer Codex process hosted this recovery.
The old session's writer lock rejected a byte-range lock before shutdown and
accepted the same check afterward.

A retained process accounts for the immediate lock contention. Why it remained
alive is unverified; terminal shutdown behavior is a hypothesis, not a proven cause.

## Attempts and results

| Date (UTC) | Action | Result |
|---|---|---|
| 2026-11-01, first recovery | Stop the identified older Codex process and its code-mode host | Lock available; conversation SHA-256 unchanged; later recurrence shows this was only a mitigation. |
| 2026-11-01, first recovery | Hash with PowerShell `Get-FileHash` while the session was open | Sharing violation; succeeded using a read stream with `FileShare.ReadWrite`. |
| 2026-11-01, second recovery | Reidentify both sessions, check the completed turn and descendants, verify process identity, then stop only the old Codex process and its code-mode host | Old process exited; lock released; current recovery session remained running. |

## Actual resolution

Pending. Targeted process shutdown restores lock availability but is not a
verified lifecycle fix. No code change, commit or release resolves the cause.

## Verification and remaining limits

The second recovery's saved conversation was 65,574,860 bytes. Its SHA-256
before and after shutdown was
`4bd74d44171989a89ad6db62d2c57be1acdfd114f9399d4defed71cccc9626b3`.
Conversation contents remain private. Lock files and session databases were not
deleted or edited. Successful interactive resume remains for the owner to verify.
No game tests were run and no production guard state or budget was changed.

## Lessons for future ports and changes

Reidentify process IDs and creation times on every recurrence; distinguish the
recovery session from the old session. Check for live workers before shutdown.
Verify lock release and saved-history integrity instead of deleting lock files
or rewriting session state. Recovery does not authorize resuming exhausted
project investigations or resetting their budgets.
