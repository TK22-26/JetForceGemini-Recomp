# PAL Modern backward movement tilts Juno

- ID: ANIM-PAL-BACKWARD-20261102.
- Status: owner confirms backward body tilt fixed in the v31 retest; accepted locally, unreleased.
- Severity: visible Modern locomotion regression.
- Affected: current v30 launcher/v28 enhanced runtime. Owner reproduced PAL; focused numeric replays reproduce leftover bank in PAL and US. JP has the same incorrect source binding but no dedicated live reproduction.

## Report and reproduction

Hold straight backward with Modern controls. The owner explicitly confirms that
Juno travels straight backward while his body tilts about 45 degrees; this is
not diagonal displacement. The supplied screenshot shows the tilted pose.
The owner recognizes the symptom from the previously corrected NTSC defect
ANIM-001. Device, weapon dependence and other characters are not yet narrowed.

## Evidence and investigation

Preserve the original NTSC correction: native backward/directional animation
selection receives the Modern velocity and direction, and the turn-generated
bank is cleared before animation/physics. Inspect PAL bindings and actual
animation consumers before changing shared movement math or clearing all roll.
Terrain, damage, airborne and Original-control poses must remain intact.
The pinned [reference review](../../upstream/reference-review-2026-10-01.md)
provides context, not proof of this regional cause.

Earlier automated PAL Modern tests establish action delivery and persistence,
not correct backward body orientation. They do not invalidate this report.
Private screenshot and investigation receipts are retained under
`regional-automation-20261101-owner4h/pal-backward-body-tilt`.

## Remaining qualification

Compare the active PAL consumer and resolved fields with the prior US fix.
Reproduce a sustained backward hold and release on an isolated copied save,
measure body roll independently of displacement, and check US/PAL/JP separately.
No correction, live acceptance or release is claimed.

## Actual cause and correction

The regional conversion used `layout.playerControl.turnDelta` (camera turn
delta, offset 0x10A in the reviewed originals) where the prior NTSC correction
cleared the separate body turn bank (0x120). The original ANIM-001 fix cleared
that bank before animation/physics; the new binding accidentally changed its
meaning. The old zero-valued `pc-locomotion` column also read camera delta,
so those traces did not measure body bank.

A separate `layout.playerControl.turnBank` now derives from the original
initializer. Independently hashed Juno, Vela and Lupus movement writers must
agree with it in every revision; generation rejects aliasing to camera delta.
Modern ground animation/physics clears that bound bank, and the diagnostic
column again measures bank. Other camera-delta writes remain intentional.

## Regression evidence and limits

Original-image binding qualification passes for US/PAL/JP. All 22 binding tests
and three focused native component suites pass. Added checks reject the old
alias, each mismatched character writer and read-only witnesses; the runtime
helper clears positive/negative bank in both guest-memory layouts while
preserving every unrelated byte, including camera delta and neighboring pose
fields. These are targeted contracts, not a claim of a full native game fix.

Muted baseline replays on independent copies of the same ordinary new-slot
save route exited normally. Final PAL bank is 22.917 degrees and actor roll
23.165 degrees; US bank is 19.061 and roll 19.352 degrees, despite zero camera
delta and straight backward local velocity. Final cameras are obstructed by
nearby geometry, so screenshots cannot qualify visible posture. Private
receipts: `pal-backward-body-tilt/baseline-pose-comparison.json`,
`turn-bank-qualification` and `turn-bank-components-retry`.

The initial C++ fixture failed MSVC's narrowing-warning policy; an explicitly
typed uint16 array corrected the test. The retry passed, then its separate
baseline analysis failed because its helper evidence root was one parent too
high. Exact passing logs were retained and copied with hashes; only the
previously blocked analysis was rerun. No failed result was overwritten.

Full runtime rebuild and live PAL/US/JP posture checks remain pending. The
owner's existing handoff is unchanged. Lesson: a valid original memory operand
is not proof of its semantic role; independently qualify each field's writers
and keep camera state distinct from body animation state.

Local source commit: `504aebdcbe843c0c493ca0da3400b340c125996d` on `develop`.
Not pushed or released; native rebuild and live acceptance remain pending.

## Native integration follow-up, 2026-11-02

After removing the independently diagnosed compiler-memory blocker, the first
full PAL compile exposed an incorrect call adapter in the earlier candidate:
`pc_clear_turn_bank` received read-only `ResidentMemory`, which has neither
`put16` nor member lookup. Its component test correctly used the mutable memory
contract, so that test did not instantiate the erroneous native call site.
Pass `NativeGameMemory` directly, matching neighboring typed field writes and
the existing ownership tests. No field mapping or bank behavior changes here.
Evidence: `regional-presentation-20261102-owner2h/candidate-v2-pal/build.log`.
Full regional compile and live visual qualification remain distinct gates.

The source correction is now compiled and linked in all three verified regional
runtimes in local `owner-review-v31`. Its keyboard replays establish normal Play
only; they do not verify this camera/locomotion behavior. Owner verification
remains pending. The earlier build failure is retained as historical evidence;
see [compiler-memory cause](build-blur-audit-compiler-memory.md).

Local implementation commit: `0e97d2e347b1bd33c714de9de3ef678aa0e48cec` on `develop`.
The local test package is not a published release.

## Owner acceptance, 2026-11-03

Following the v31 four-item handoff, the owner reports that Modern Aim release
is still instant and "the rest is fixed". This accepts modern backward body tilt in
the tested session. The exact tested region/device is not restated; this is
not three independent regional visual checks. Earlier pending-review passages
are historical. Implementation and test evidence remain as recorded above;
the local package is not a published release.

The owner subsequently identifies this retest as **PAL with a controller**.
Retain that scope for the accepted result; no separate US/JP visual pass is inferred.
