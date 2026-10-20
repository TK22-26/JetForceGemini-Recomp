# CAMERA-007: modern dual-stick ledge climb recenters the camera

- Status: owner-confirmed locally; regression/native checks pass; unreleased, reporter retest pending.
- Severity: gameplay usability; abrupt disorienting view change.
- Report: [GitHub #30](https://github.com/TK22-26/JetForceGemini-Recomp/issues/30), 2026-10-19.
- Setup: Windows 10, RTX 5060 Ti, Xbox One controller, Modern dual-stick controls.
- Owner requests inclusion in a quick v1.3.1 together with #31.

## Reproduction and source distinction

Grab a ledge with the camera offset, then climb/jump onto it. The reporter says
the camera immediately snaps behind the character every time.
Character and exact ledge are not specified.

The v1.3 [mouse landing/ledge correction](mouse-camera-high-landing-reset.md)
deliberately retained mouse ownership only. The modern_ledge_view_current
gate in [native_boot.cpp](../../../src/boot/native_boot.cpp) requires the mouse
device selector. This identifies a coverage gap, not a complete measured cause
for the controller report. The earlier mouse acceptance is not controller proof.

## Intended remedy and checks

Retain player-selected dual-stick camera orientation during ordinary ledge
attachment/climb while leaving native body alignment, locomotion, collision,
action restrictions and scripted cameras intact. Verify both look sources,
inversion, approach angles, climb completion, death, dialogue and room changes.
Owner performs live visual verification; no autonomous gameplay authorized.

No source change, new component test, build or delivery exists yet. Public
comments remain on hold until owner review. Keep the mouse issue's historical
acceptance separate. Lesson: ownership fixes must explicitly cover each input
device path rather than assuming Modern Controls is one common path.


## Source cause and candidate (2026-10-19)

The retained-view predicate required device -3 (mouse). During humanoid ledge
states 6/7/8/12, ModernShoulderScope rejects ordinary locomotion ownership and
only preserves its saved view when that predicate permits camera-only ownership.
For XInput/SDL controllers it therefore clears the active PcShoulder. On climb
completion, reacquisition seeds the native body heading, producing the abrupt
recenter described by the reporter.

The candidate removes the mouse-only restriction from modern_ledge_view_current.
It retains the existing Modern-enabled, actor/control identity, native ledge and
script/action gates. Ledge movement remains excluded from modern locomotion,
body alignment and velocity writes. The controller look accumulator already
supports this retained-view path. Landing recovery's separate mouse restriction
is unchanged; this correction targets #30.

## Verification and remaining limits

A private harness extracts the actual ownership predicates and ModernShoulderScope
from native_boot.cpp and compiles them against real memory/look helpers. It uses
a small host State fixture, not a game replay. The old code fails preservation
for a connected controller. The candidate passes 720 assertions covering XInput,
SDL and mouse paths, both humanoid characters, all four ledge states, both look
directions, focus suspension, climb completion, control identity changes,
disconnects, original mappings and native/script locks. It checks that retaining
or moving the ledge camera does not write guest RAM.

The first harness version had incorrect look-sign and new-control expectations.
Those fixture mistakes were corrected before the baseline failure/candidate pass;
both attempts are preserved. This is not gameplay acceptance or proof of every
physical controller/inversion configuration.

The native Release build succeeds. jfg.navigation_mod, jfg.pc_input and
jfg.modern_controls pass. A new muted desktop shortcut, JFG - Controller Ledge Fix
Preview, uses an isolated copy of the latest lighting preview and its save/settings.
It includes the rain/reticle, controller-removal and fog candidates. The original
preview/profile remains unchanged. Owner should verify a ledge with the camera
offset, turn the right stick while attached, and climb without recentering.

Private evidence: D:/JFG-private/v131-rnd-20261019/controller-ledge.
No public reply, closure, commit or release was made.

Preview runtime SHA-256: 8dff015f855bde2d782ae53a7225a3d2e82fb618d5baa3ee7af3440b96945b93

## Owner validation, 2026-10-19 evening

The owner answered "Fixed" to the Modern controller ledge-climb test. Support
logs confirm the new ledge runtime (8dff015f...) was run, followed by the older
Tawfret Lighting Preview (cfac17af...). Mark #30 owner-confirmed locally,
unreleased; reporter hardware retest still pending. The separate lighting-run
lag is tracked in [PERF-005](tawfret-lighting-preview-stutter.md).
