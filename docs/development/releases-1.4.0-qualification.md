# v1.4.0 release qualification

Status: v1.4.0 published on 2026-10-22 at 03:37:17 UTC and marked Latest.
The release tag is `5ec705f7d1575135e7965fe1376666b225f22ee1`; the unchanged,
owner-approved runtime retains its actual clean build identity `521f666`.
[All eight release jobs passed](https://github.com/TK22-26/JetForceGemini-Recomp/actions/runs/39716906964).
The ZIP, SHA-256 file and inventory were downloaded anonymously from the public
release and matched the independently verified local package. ZIP SHA-256:
`8bf60c984a23143285c6ccaf7bb489667d21c3fcf936f18d95681a92d9d8d5b1`.

All twelve individually approved replies were posted after publication and
verified against their exact approved text. #15 and #19 were additionally
closed by explicit owner request. #32, #35 and #40 remain open; #41 tracks
future skip-completion optimization. The desktop review plan records each link.
This documentation-only closeout does not change the published tag or assets.

Historical preparation entries below retain their original validation scope.
The release page is the authority for publication availability: [v1.4.0](https://github.com/TK22-26/JetForceGemini-Recomp/releases/tag/v1.4.0).

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
The current publication summary above supersedes the earlier draft-only status; reporter-specific verification limits still apply.

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

## Final-pass launch configuration correction (2026-10-21)

The first desktop final-pass shortcut incorrectly enabled standard diagnostic
capture and inherited `performance.ini` with logging and overlay enabled.
The owner correctly rejected that configuration for release-condition testing:
the earlier [rain/reticle defect](issues/github-ally-x-rendering.md) was masked
by diagnostic output metadata. The FPS box itself was not its cause.

The same verified v1.4.0 candidate binaries now launch without `--diagnostics`,
with performance logging and overlay disabled. Custom 120 FPS, the current
save and all other profile settings are preserved. No runtime patch or new
visual pass is claimed. Previous captures remain historical diagnostic evidence;
normal-play rain/reticle and full-route acceptance remain with the owner.

Private correction receipt: v14-release-prep-20261021/normal-launch-correction.
The production guard stays enabled; one owner-approved additional attempt uses
the existing time window with all investigation counters preserved.

### Tawfret chief final-pass follow-up

The owner verified the camera-cut correction at 120 FPS with logging/overlay off.
The focused regression fails before the change and passes after it; the native
Release build and four relevant renderer/history CTest suites pass. The reviewed
camera preview contains the correction; the earlier release ZIP does not yet.
The owner rechecked and confirmed the floating square on original N64 hardware;
native resolution had obscured it. The scoped camera-helper draw correction is
built and passes four focused suites. The owner confirmed "Square gone; scene
looks correct" in normal 120 FPS Play with logging/overlay off. The earlier ZIP
does not contain either final-pass correction and is superseded by the final
package preparation. The final package must identify the reviewed clean develop
commit in both launcher and runtime, pass package verification, and complete
all-platform CI before publication. See
[the full record](issues/tawfret-chief-camera-and-square.md).
Main merge and release publication remain pending owner approval.

## Clean CI follow-up (2026-10-22)

The first PR run found GCC aggregate-initializer warnings and a raw-byte RT64
source pin sensitive to Windows checkout line endings. Both are corrected
without weakening compiler checks or changing the dependency revision. The
CMake pin accepts LF/CRLF and rejects modified content; all-platform CI must
pass on the corrected source. See [the build record](issues/v14-clean-ci-portability.md).


## Final release candidate qualification (2026-10-22)

The Tawfret camera/helper write-up and owner acceptance are recorded in
[the findings](tawfret-camera-helper-findings-2026-10-22.md). The project,
launcher assembly, packaged launcher FileVersion/ProductVersion and runtime
manifest all identify v1.4.0. No version downgrade to v1.3.1 is planned.

The clean runtime is built from `521f66620e734671a06a07f118e874076f02a133`.
[Its full CI](https://github.com/TK22-26/JetForceGemini-Recomp/actions/runs/39711677000)
passes all six jobs, including the GCC/Clang, Windows, sanitizer, renderer,
launcher and policy/Python lanes. Local Release build and the focused
cutscene/helper/rain tests pass. The subsequent qualification commit changes
documentation only; the runtime identity must retain its actual build revision.
The final launcher/package inventory identifies the exact documentation commit.
PR #42 checks that final source before the owner's signoff.

The earlier ZIP is preserved as historical evidence. The final bundle is built
in a new private directory and verified by the normal release validator: exact
membership, per-file hashes, ZIP checksum, v1.4.0 manifest and clean executable
provenance. ROMs, private game data, personal saves and debug symbols are excluded.
The release-ready desktop profile uses a copied save, 120 FPS, diagnostics off,
and FPS logging/overlay off. The original profile remains untouched.

All five worktrees remain accounted for. The three retained non-build copies
still match the earlier reconciliation inventory; the build worktree's reviewed
changes were preserved before clean checkout. No worktree or branch was deleted.

The final release notes and publication wording are staged privately for owner
review. Main, tags, releases, issue comments and closures remain unchanged.
After final signoff, publication metadata must use the actual release date and
the package must match the exact tagged source; the release workflow repeats
its required checks before publication. Exact package identities and the latest
CI receipt are retained under `v14-final-release-20261022` and in the desktop
handoff. Reporter-specific limits in known issues remain open.
