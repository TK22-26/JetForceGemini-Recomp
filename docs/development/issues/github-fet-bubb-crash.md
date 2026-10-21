# GH-038: Crash shortly after Fet-Bubb begins attacking

- Severity: high; reported crash blocks the Tawfret Castle boss encounter.
- Status: attached crash is confirmed to come from another project's v1.1.8 executable. This project's v1.3.0 passed one bounded boss comparison; no local defect or runtime fix established. Reporter routing/clarification pending.
- Reported and reviewed: 2026-10-21 UTC.
- Source: [GitHub #38](https://github.com/TK22-26/JetForceGemini-Recomp/issues/38),
  by @azjsales01-stack, created 09:22 UTC and updated 09:29 UTC.
- Reported build: **1.1.8**; dump identity now matches
  [VibinToast's v1.1.8 release](https://github.com/VibinToast/JetForceGemini-Recomp/releases/tag/v1.1.8),
  not this repository's v1.3.0 runtime. See exact comparison below.
- Setup: Windows 11, RTX 4070 SUPER (12 GB), PS5 controller, Juno at Tawfret
  Castle, with an unspecified 4K texture pack installed and active.

## Owner authorization and evidence intake (2026-10-21)

The owner explicitly requests investigation and repair, then authorizes a
two-hour guard override and parallel work. The trusted host records this as a
bounded admission in the same `high-refresh-rendering-20261011` investigation:
the guard stays enabled, roots and all prior counters remain intact, and only
the named running Juno cutscene job may overlap. Deadline: **22:59:58 UTC**.
Receipt: `fet-bubb-crash-20261021/admission-receipt.json`. No public-posting,
commit, push or release authorization is implied.

The attached dump was downloaded intact (388,464 bytes), SHA-256
`72d888115bd4572a4343a93ef7bc6903a643714f5a1fe706374a19c94c6a1a45`.
The guarded inspection, exact executable comparison and one current-release
comparison are complete. No local reproduction or runtime fix is claimed.

## Confirmed executable identity and fault

The dump records `JetForceGeminiRecompiled.exe`, while this project's release
uses `jfg-native-boot.exe`. The original reported version is absent from this
repository's release tags. Naming alone was treated as a lead; a downloaded
public executable establishes the identity:

- External package: `VibinToast/JetForceGemini-Recomp`, tag `v1.1.8`.
- Package SHA-256 matches its published checksum:
  `77e437c4f249d28ef08c019b0ad9683af6f47c83a1d9af28a38451fa67bb3f17`.
- Executable SHA-256:
  `f5696935d90d7a83702675571e6464602f884069391ff62dc9b056d72f3cce49`.
- Dump and executable match in CodeView debug identity, PE timestamp
  `1792349651`, image size `25927680`, and all 192 captured bytes surrounding
  the fault at executable RVA `0x1693ee`.

Private evidence: `fet-bubb-crash-20261021/exact-binary-match.json`, downloaded
release/checksum and the original dump. Personal installation paths are omitted
from this public record. The external executable was inspected, not run.

The immediate failure is an access-violation read (`0xc0000005`): original-game
register `s1` is `-1`, and squad traversal attempts to read its next-member field
at offset `0x28`. The captured x64 instruction sequence and following register
updates match original overlay 3 function `00313FE4`, instruction `00314128`;
the saved return address `800460B8` agrees with main update calling
`squadsModuleTick`. This identifies the invalid dereference, not the earlier
event that put the invalid pointer in the list. A texture-pack cause is unproved.

The corresponding original-game traversal also exists in this port. Shared
game code does not establish shared runtime/lifecycle behavior or reproduction.
There is no evidence-based reason to patch this project's runtime solely from
a dump of the other executable. Keep #38 open for reporter/build clarification
until the report is routed or reproduced on this project's release.

## Reported reproduction

The game exits about three seconds after Fet-Bubb begins attacking. The reporter
saw the crash on two of two attempts, both when watching and when skipping the
intro cutscene. Reported reproduction: enter the fight as Juno with the supplied
texture configuration and allow the boss to attack. No local reproduction or
comparison with stock textures has been performed.

## Evidence and hypotheses

A [crash dump](https://github.com/user-attachments/files/33761541/crash.dmp) is
attached. No support ZIP, pack identity/version, renderer settings or exception
analysis was supplied at initial triage. The original documentation-only audit
recorded its link; subsequent owner-authorized download and analysis are above.
Private issue/comment snapshot:
`github-follow-up-review-20261021T204709Z/github-issues.json`.

The old reported build and active texture replacement are comparison variables,
not established causes. This report does not establish a regression in v1.3.0,
a texture-pack defect, or a relationship to the unreleased Modern boss-aim fix.

## Attempts and results

| Date | Action | Result |
|---|---|---|
| 2026-10-21 | Read the report and attachment link; check latest public release | Latest release is v1.3.0; preserve reported 1.1.8 identity and request clarification during follow-up |
| 2026-10-21 | Record guarded investigation plan | Dump analysis, reproduction and texture comparisons remain pending; no game/build/test run |
| 2026-10-21 | Preserve dump and inspect exception/module/context streams | Invalid read in `JetForceGeminiRecompiled.exe`; executable name/version differ from this project |
| 2026-10-21 | Query repository identity | Initial `gh search` JSON field was unsupported; corrected query found VibinToast's separate project; missing root CMake file was not treated as proof of source availability |
| 2026-10-21 | Compare published v1.1.8 binary against dump | Published archive checksum, full CodeView record, timestamp, image size and 192 fault-site bytes match |
| 2026-10-21 | Map fault using captured guest context and original instruction sequence | Invalid squad-member dereference identified; origin of the invalid pointer remains unknown |
| 2026-10-21 | Verify official v1.3.0 package and run isolated Juno native boss-entry fixture | All 14 package files verify; 6,000 VI complete with exit 0 and zero unsupported accesses, including 17.875 seconds observed in level 195 combat; no crash reproduced |

## Actual resolution

No runtime correction is claimed. The report's executable attribution is now
resolved: it belongs to VibinToast's separate project. Fixing this repository
cannot change that installed executable. A reporter retest using this project's
release/support ZIP, or routing the crash to the matching project's issue tracker,
is the appropriate next step. No public reply or issue closure has been posted.

## Verification and remaining limits

Runtime attribution is complete; texture-pack identity is still unknown. The
official v1.3.0 runtime SHA-256 is
`1bfc6a04ced93f0eec76a9a4f72817b6d93a5de2f26f4de6af9114cdf13b786f`;
all 14 package files match its manifest. One isolated copied Juno checkpoint
entered the boss through the active native exit from level 194, watched the
introduction, and reached level 195 with Juno in state 32 and a live boss actor.
The run completed 6,000 VI in 102.14 seconds, exit 0, zero unsupported accesses.
Combat was observed for 17.875 seconds across 178 observer samples.

Scope: hidden and muted; 120 FPS, VSync Off; fixed diagnostic retrace timing,
synthetic retained checkpoint, exit warp and health override enabled, enemy-kill
toggle disabled, no 4K pack. The probe explicitly reports `acceptance=false` and
`runtime_snapshot_complete=false`. This is a bounded non-reproduction, not a
complete battle, natural campaign, physical-controller, texture compatibility or
reporter-configuration pass. Original saves, settings inputs and package files
were hash-verified unchanged. No product source was edited.

Receipt: `fet-bubb-crash-20261021/current-release-boss/comparison.json`; copied
fixture, native transition observations and run outputs remain private. Do not
add a generic sentinel clamp based on the external dump: it would conceal the
unestablished lifecycle cause without proving correct squad behavior.

Any further investigation/build/replay work still requires the existing production
guard and eligible admission. This finding grants no additional execution budget.

## Lessons for future changes

Keep reported version, actual runtime identity and optional texture configuration
separate. A timed boss crash needs its own exception and reproduction evidence;
accepted boss-control changes do not establish crash compatibility.
