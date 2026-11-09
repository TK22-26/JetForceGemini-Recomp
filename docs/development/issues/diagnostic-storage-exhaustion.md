# Diagnostic storage exhaustion

- ID: **STORAGE-001**
- Severity: high for autonomous investigation availability; no established game-runtime defect.
- Status: October 28 bulk cleanup verified; latest enemy-timing set retained, three small supplemental leftovers blocked by approval review. Automatic retention remains open.
- Reported/observed: 2026-10-12, during AUDIO-001 investigation.

## Symptoms and cause

The original checkout's private diagnostics accumulated approximately 321 GB of
logical file contents across historical investigations. The active executable
pin operation failed with insufficient disk space and left a partial file. The
production supervisor then failed to persist a SQLite heartbeat on the full
volume. The failed attempt, partial artifact and budget charges were retained.
This was a storage failure, not evidence of an audio fix or runtime regression.

Logical file sizes overstate reclaimable disk space when NTFS compression is in
use. Report actual volume free-space changes separately from archived byte sums.

## Attempts and recovery

The owner requested cleanup of the old checkout. A compiler-intermediate cleanup
command was supplied to the owner; free space subsequently increased. An earlier
assistant deletion attempt was rejected by automatic approval review and was not
retried. NTFS compression did not materially help because files were already
compressed. The owner then explicitly authorized clearing more of the private
storage and continuing the existing investigation.

Preparing a second archive-continuation script was also rejected by automatic
approval review with only "blocked by policy" as the stated reason. That action
was not retried or routed through another tool. The previously running guarded
archive continued under its existing limits.

The guarded archive worker selected historical diagnostic directories, excluding
the production ledger and active PC-input/audio investigation. For each selected
directory it copies to a separate volume, checks every file's SHA-256 and length,
checks file counts and unchanged source metadata, writes a verification manifest,
and only then releases the original copy. A junction preserves the original path.
Copy or verification failure leaves the source in place. Source code, Git history,
saves and user profiles are outside the selected scope.

The existing production investigation/root and guard stay enabled. Owner-approved
continuation preserves the disk-full failure and all charges; it does not reset
the approved deadline. The current supervisor requires a 2 GiB reserve. This
reserve mitigates immediate recurrence; it is not a repository-wide retention
policy and cannot guarantee protection against unrelated disk consumers.

## Verification and limits

Completed and verified directories: **4**. Archived logical size: **51.99 GB**.

The selected batch has not produced a completion summary; retained per-directory receipts establish only completed directories.

Private evidence: archive batch 20261012, per-directory file-hash manifests, completed.json, and summary.json when present. Archived data remains available through its original paths while the archive volume is available. No game release or audio acceptance follows from this cleanup.

## Archive batch outcome

The batch stopped during verification of the fifth directory: PowerShell Get-Item without -Force could not see a hidden .git file. A read-only check with hidden-file access confirmed that the file exists in both locations. The fifth original directory was never removed or replaced; its copied data remains unqualified. Four completed directories retain verified manifests and working junctions. No unfinished junction transition remains. The failed batch is retained as a failure, not recorded as full completion.

The helper needs hidden-file-aware enumeration and lookup consistently in any future owner-authorized archive. It was not retried during this continuation. Private receipt: storage-archive-verification.json.

At audio-preview handoff, C: has 59.54 GB free (55.45 GiB). This is the current volume reading, not a claim that the archive alone reclaimed that amount; other cleanup and concurrent builds also affect free space. The verified archive remains 51.99 GB of logical data across four directories.

## 2026-10-15 high-refresh build recovery

The ordinary candidate restore link failed with LNK1180 after the control
captures had completed. The previous executable was unavailable afterward;
no replay was attempted against that incomplete output. All source restoration
had already completed. Two dependent jobs failed their prerequisite checks and
did not proceed. The prior failures remain recorded.

The active high-refresh build tree was copied to D:, with every regular file
checked by SHA-256 and length, then its C: path was retained by a junction. Only
the verified redundant original was removed. Shared dependency trees, preview
profiles and unrelated builds were outside this move. The candidate then linked
successfully. Evidence: build-drive-recovery-20261015/before-manifest.json,
relocation.json, build.log and result.json. Existing build scripts still use
the C: path, which now requires D: to be available. Long-term retention remains
open; this does not qualify the gameplay candidate.

## 2026-10-15 owner-requested legacy checkout preservation

The owner requested preservation and a pause before deleting the two legacy
checkouts named `Jet Force Gemini Recomp`. All high-refresh jobs stopped and
three queued experiments were withdrawn before execution. The current checkout
named `JetForceGemini-Recomp` and its active worktree remain separate.

Legacy source, Git history and uncommitted changes were moved to the private
archive `D:/JFG-retained/legacy-preservation-20261015/legacy-checkout`; Git status
before and after the move matched. Only top-level legacy build directories were
left in the old D: checkout. Required upstream references, emulator and private
signing material from the old Desktop tools directory were copied separately,
with file counts, lengths and SHA-256 checks. Rebuildable Python virtual
environments were excluded. Copy manifests and the source-move receipt are
retained in the archive; private material must not be published.

The production ledger was preserved at
`D:/JFG-private/autonomy-production/jobs.sqlite` using SQLite backup. Its logical
dump matched the original, integrity checking passed, the guard remained enabled
and all investigation roots, counters and admission history were unchanged.
The old operational filename was retired. See the
[updated ledger location and continuation requirements](../../planning/autonomy-progress-guard.md#production-ledger).

This preservation removes the high-refresh task's dependency on the two old
checkout roots. Historical scripts and old builds may still contain absolute
paths and are recovery material, not qualified runnable installations. The
active `C:/JFG-builds` tree remains required. No gameplay fix, release acceptance,
new investigation allowance or measured disk-space saving follows from this
administrative move. Work remains paused at the owner's request.

## 2026-10-28 owner-directed test artifact disposal

The owner requested removal of obsolete JFG data on both drives, explicitly
requiring useful findings to be distilled into text and all old tests removed.
The confirmed exception is the October 28 enemy-timing research together with
the October 27 playable Flying Enemy Timing Review, treated as one current set.
Source test definitions are part of the maintained source, not disposable runs.

The initial inventory measured 274.005 GB of regular files in the D: JFG roots
and 35.525 GB in the current C: checkout, including old build/private outputs.
The owner subsequently identified approximately 2.5 TB of unrelated data and
noted installed games account for additional volume usage. Logical inventory
totals must not be presented as measured physical space recovered.

Preparation preserves the current source and user changes, personal saves,
ROMs, signing material, the current released installation and the production
ledger. Distinct old saves and scratch-repository source deltas are compressed
with a path/hash manifest. The current timing set is hash-pinned. No gameplay
experiments or builds are performed by the cleanup. The production guard is
enabled, no runs are live, and the high-refresh investigation remains shelved
with its 115 attempts, 94 activities and every earlier charge intact.

Private record: `storage-cleanup-20261028`; human-readable summary:
`JFG-cleanup-findings-2026-10-28.txt`. It retains the established timing causes,
candidate-versus-release distinctions, open audio/owner-coverage limitations
and links to the full source issue records. Selected small historical result
fields are distilled into a text appendix before raw data disposal.

After disposal, references to removed private artifacts in older reports remain
historical citations; they are not claims that the original files still exist.
No historical verification is invented or upgraded. Fresh reproduction would
require eligible guarded execution and does not receive allowance from this
maintenance request.

### Verified cleanup outcome

All 582 selected targets were removed with zero deletion errors: 517,496 regular
files, 37,427 directories and 1,987 links. Recursive removal checked absolute
boundaries and removed links themselves without traversing their targets.
Measured free-space increases from a fresh baseline immediately before deletion
were **33.885 GB on C:** and **265.629 GB on D:**, approximately **299.514 GB**
combined. A separate approximately 2.67 TB increase on D: occurred before this
deletion pass and is explicitly excluded from the cleanup result. Concurrent
ordinary activity can slightly affect volume readings.

All 3,782 pinned current timing/release files still match SHA-256; 1,577 existing
source files outside the three cleanup documentation edits also match. ROM hashes
and the separate dirty source checkout's status are unchanged. The production
ledger passes SQLite quick-check and its enabled guard, investigations, roots,
states and counters exactly match the initial read-only snapshot. No game build,
replay, release, commit or new gameplay verification occurred.

One historical checkout already had a dangling Git worktree pointer. Its entire
non-generated source was preserved in a verified archive rather than claiming a
Git diff could be obtained. Distinct saves, source deltas and local Git histories
from removed scratch checkouts were preserved separately. The first preservation
pass was stopped before deletion because repeated metadata calls were slow;
directory-enumeration metadata allowed the replacement pass to finish. Neither
event changed production investigation state or lost original input data.

Automatic approval review rejected a separate supplemental deletion command with
only "blocked by policy". No alternate deletion route or retry was used. Three
files remain, totaling 93,357,359 bytes: the superseded incomplete preservation
archive, an old support-test ZIP and the duplicate Remaining Issues Review
shortcut. Exact paths and sizes are in the private `policy-blocked-leftovers.json`.
This is a verified bulk cleanup with those explicit residuals, not a claim that
every obsolete byte was removed or that an automatic retention mechanism shipped.

The post-cleanup inventory measures approximately 9.728 GB in all D: JFG roots
and 1.497 GB in the current source checkout. These include current timing data,
its build/reference/fixture dependencies, maintained source, the released personal
installation, ROMs, ledger and compact preservation records. Future disposable
results need bounded retention and distilled findings; copying large old traces
into another archive alone does not recover space on that volume.
