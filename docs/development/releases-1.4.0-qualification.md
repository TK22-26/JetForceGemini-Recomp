# v1.4.0 release qualification

Status: final candidate preparation; owner SS Anubis pass pending.
The owner authorized the version change, five-worktree reconciliation, final
documentation, combined build and commit/push to develop. Main merge, tag,
publication and public issue replies await separate approval.

## Source reconciliation

All five worktrees were audited on 2026-10-21. Both clean historical release
worktrees have no commits absent from develop. The high-refresh and rolling/Floyd
working copies were preserved byte-for-byte before comparison. All their changed
paths exist in the current checkout. Differences are superseded by the current
Floyd controls, Mods UI, paused grants, cutscene qualification, Quarry smoothing,
diagnostics, launcher feedback and documentation. No unique committed work or
missing source path was found.

Private audit evidence: v14-release-prep-20261021/worktrees-initial.json,
worktree-snapshots, normalized-1.diff, normalized-4.diff and reconciliation.json.
The historical copies remain preserved; no branches or worktrees were deleted.
One mixed UTF-8/legacy-smart-quote issue note was decoded without changing its
meaning. Full-file line-ending noise was excluded from the content comparison.

## Scope and acceptance

The changelog describes the combined change set. Floyd #37 is fully approved
locally; the reporter should re-verify after delivery. Native cutscene skipping,
camera corrections, rain/reticles, lighting/fog, Mods and weapon grants carry
their recorded owner acceptance. Historical unsuccessful candidates and the
eleven likely development/setup scene entries remain documented, not relabelled
as successful tests.

The final pass will use a separate v1.4.0 launcher and copied profile/save.
It must not modify the owner's existing preview or saves. The package excludes
ROMs, game assets, private recordings, generated source and personal saves.

## Remaining limits

Steam Deck/Proton has a Windows-tested fallback, not a verified Deck result.
Intermittent mouse input #32, delayed audio #35 and reporter-specific Ally X
performance still need affected-user evidence/retesting. The #38 attachment is
from a different project's build; it does not establish a resolved defect here.
Public replies remain drafts pending owner approval.

Combined check results and exact build/package identities will be retained in
the private v14-release-prep-20261021 evidence directory. Compilation alone is
not the final SS Anubis acceptance. The production guard remains enabled with
its original investigation roots and cumulative counters.

## Source-policy follow-up

The combined checks found missing exact-body entries for owner-requested original
skip-button/label artwork, historical notes containing a local video directory,
and adjacent SHA-256 values mistaken for an opaque payload. The artwork and
licenses were reviewed, current directories redacted, and digest labels separated.
Historical public text has exact-body local-path exceptions; no credential,
ROM, archive or generated-source rule was weakened.

A full scan of the maintainer's object database also sees private archived and
unreachable research objects. They are preserved locally, not added to the public
exceptions. Public-history qualification uses a clean fetch of develop and its
reachable release history, matching the source that will actually be pushed.

## Combined local checks before the final clean build

The integrated Release runtime builds and all 123 CTest native/renderer suites
pass. The launcher build passes 685 managed checks, 28 setup checks and the
graphics/viewport/storage checks. Native UI results: 997 Modern/Mods checks,
305 mapping checks, 85 menu/composition checks and 86 injected-fallback checks.
These tests use isolated profiles and do not establish Steam Deck compatibility.

The full Python run executes 1,807 tests with 48 skips, two sanitizer subtest
failures and one WSL trust-anchor error. These match the pre-existing limitation
recorded during v1.2 qualification: the installed WSL executable differs from
the fixed harness pin. The harness and tests are unchanged from develop.
Windows reports a valid Microsoft signature; no trust pin, compiler check or
test assertion was relaxed. The private diagnosis preserves actual/expected
digests and failing outputs. This is not a clean all-platform CI result.
Full CI remains a publication gate.

Current-tree hygiene and project validation pass after the documented
source-policy corrections. Exact-body policy regression checks pass.

The staged cutscene checklist had doubled CR line endings. They are normalized
without changing any of its 169 parsed rows or the private live review manifest.
