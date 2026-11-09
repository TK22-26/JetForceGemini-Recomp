# TOOLING-HISTORY-20261031: Retained local objects fail the whole-history hygiene gate

- Status: resolved locally on 2026-11-01; verified external retention and active-checkout cleanup completed, whole-local-history hygiene passes.
- Severity: medium for the maintainer history-scan gate; no demonstrated game regression or new public-tree contamination.
- Reported: 2026-10-31 UTC during the repository reorganization; cleanup verified 2026-11-01 UTC.
- Affected: this local Git object database and retained refs; no remote repository result is inferred.

## Symptoms and reproduction

Run `python scripts/validation/check_repository_hygiene.py --history` in the original checkout.
The scan reports nine flagged blobs and non-UTC author/committer timestamps on two commits.
Ordinary current-source validation passes. The history function enumerates all local objects,
including objects unreachable from refs, then checks commits reachable from all refs. Its name
`scan_reachable_history` does not mean that its blob scan is limited to the current branch.

## Evidence and actual cause

The first scan occurred before staging the reorganization. The preserved object IDs were then
compared with the audited `develop` baseline (`db9ea90b41b9bf14d806ab6aea1aefbddbb80efa`), every
local ref and the proposed index:

| Finding | Provenance | Scope |
|---|---|---|
| Four blobs | Retained `refs/archive/worktrees-20261013/jfg-luke-shadows` | Community scripts contain machine-specific paths; one image is not in the scanner allowlist |
| Five blobs | Unreachable from current refs | Local-path, opaque-payload or size findings; contents were not copied into public documentation |
| Two commits | `refs/stash` history | Author and committer dates use `-04:00`, not the required public UTC offset |

None of these nine blobs or two commits is reachable from baseline `develop`; none of the flagged
blobs is in the proposed index. The initial possibility that the reorganization introduced them
was rejected. A scanner finding identifies a policy mismatch, not proof that an opaque blob is a ROM
or that an image is safe to publish. No new exemption was added.

Private receipt: `reorganization-implementation-20261031/history-hygiene-classification.json`,
with the complete scan log, object identities, reachability and pre-work develop bundle identity.
The broader [architecture audit](folder-architecture-audit.md) preserves source/test validation.

## Decision, validation and remaining limits

Preserve archived work and six existing stashes. Do not rewrite history, delete refs or prune
objects as an incidental folder cleanup. Current source and staged-tree hygiene are distinct from
a whole-local-database result. An isolated copy of baseline `develop`, with the exact staged candidate applied, passes the full
history scan. Its Git tree matched the original index before checking. The clone used normal Git
transport without local object sharing and copied no archive/stash refs or unreachable objects.
`candidate-history-receipt.json` records the matching tree and passing result. This qualifies the
candidate branch scope; the full original local-object scan remains failing while the retained
objects and refs exist.

A future history cleanup needs explicit retention/disposal decisions and verified backups. It
must preserve evidence, avoid publishing private payloads and keep public metadata requirements.
Changing an allowlist or rewriting timestamps solely to make the scan pass would not establish
that the affected historical work was safe or disposable. New maintainer commits continue to use
the required owner identity and UTC timestamps.

## Transferable lesson

State whether a check covers working files, the index, one branch's reachable history or every
local object. Retained archive refs and stashes can fail the last scope while being absent from
the candidate branch. Keep all results and their boundaries visible rather than reporting a
passing source check as a clean whole-repository history scan.

## Completed local cleanup, November 1

The owner approved the deferred cleanup. Before removal, a separate retained Git database copied
6,989 files (48,988,335 bytes), verified their hashes and the availability of all 6,939 original
objects, and preserved every original ref. All six stash commits also have explicit retained refs,
so restoring an older stash does not depend on a reflog expiring later. Private retention ID:
`git-history-20261101-022947`; its `RESTORE.txt` and preservation receipt describe recovery.

The active checkout then removed only six `refs/archive/worktrees-20261013/` refs and `refs/stash`,
expired unreachable reflog entries and pruned unreachable objects. Branch, remote-tracking and tag
object IDs were compared before/after and are unchanged. No historical commit or timestamp was
rewritten. There are still two local branches, `main` and `develop`, and one source worktree.
All six stashes remain in the external retained database; the active stash list is empty.

`check_repository_hygiene.py --history` now passes in the actual checkout. Scanner rules and
allowlists are unchanged. The private `reorganization-followups-20261101` receipt records the
removed refs, preserved refs, original stash IDs, backup verification and passing scan. This
resolves the local history gate; it is not a claim about a remote database or a release.

Recover historical work in an isolated checkout from the retained database. Reintroducing its
retired refs or private blobs into this checkout can legitimately reproduce the original findings.
