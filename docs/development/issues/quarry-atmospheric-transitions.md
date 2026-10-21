# Quarry atmospheric day/night transition jumps

Status: owner-verified in the corrected preview (2026-10-20 Eastern /
2026-10-21 UTC). The complete day/night cycle capture has 2,971 matching
environment-fog render commands and no colour-match rejection. Native Release
and three component suites pass. The earlier strobing candidate remains
rejected and documented below. Unreleased; no commit/release claimed.

## Report and reproduction

After loading review scene 411 / variant 0 and skipping into Quarry gameplay,
remain through the daylight, orange evening, dark-blue night, dawn and daylight
cycle. The owner reports smooth colour blending interrupted by distinct darker
or lighter jumps, then continued blending. The owner explicitly clarified that
this is atmospheric only; actors and other rendering look good after the repair.
Severity: visual fidelity defect; no crash or progression failure reported.

Affected capture: 20261020-215634-e17310e1a5ea4d5ca3a21417d06386da,
Original FPS, accepted lighting-preview runtime SHA-256
4fd680f2c5bf6b04859a660eb6b3da44aafd7da3c7b8621b96192399993a0bcc.
The capture proves the build/scene route and retains runtime logs plus final
physical RDRAM. It does not contain sequential video frames or per-frame
atmospheric colour values. Therefore the precise visible jumps are not yet
confirmed from that recording alone.

## Findings and rejected interpretations

- Actor-lighting integer steps in prior EmuHawk samples do not explain the
  atmospheric-only report. The initial actor-quantization lead is insufficient.
- Native overlay 22 advances a 12-stage cycle and interpolates its geometry
  modulation, fog colour, sun parameters and ambient values.
- The original reference checkpoint uses a stage duration of 480 native ticks.
  A source-derived evaluation of its six geometry/fog colour channels over all
  12 stages changes by at most one 8-bit unit per tick, including stage edges.
  This is a calculation against the original table, not a rendered comparison
  or proof that the recomp supplies the correct timing/values at runtime.
- The original table bytes match the inactive original-code image in the
  recomp exit snapshot. Mutable globals in that image are zero: generated code
  uses relocated canonical overlay storage outside the physical 4 MiB snapshot.
  Those zero values must not be interpreted as a stopped/broken live cycle.
- Geometry recolouring consumes the cycle RGB values and performs another
  integer multiply/shift into vertex colours. Fog has a separate getter.
  Quantization, stale downstream colours and cycle timing remain hypotheses;
  none is established as the cause of the owner-visible large jumps.

## Diagnostic and next comparison

The diagnostic records read-only daynight-atmosphere events after the cycle
update and after its geometry/fog getters. Existing detailed gameplay logging
enables it; normal sessions with that logging disabled do no extra reads.
The trace uses the validated canonical section mapping and captures getter
outputs separately. It does not modify game memory, cycle speed, colours,
actor lighting, saves, or owner review notes.

Payload after the ordinary event/time fields (all numeric values hexadecimal):

- 0: VI retraces; 1: gameplay update count; 2: normalized called entry;
  3: room; 4: canonical overlay base.
- 5..21: words at overlay offsets 0x7D0..0x810. Within these: 9 is phase,
  10 is elapsed phase ticks, 11 is phase duration, 12..14 geometry RGB,
  15..17 fog RGB, 18..19 fog range, 20 ambient, 21 auxiliary value.
- 22..26: actual getter outputs. Geometry getter 0x017006B0 returns three
  words; fog getter 0x0170066C returns two halfword ranges and three colour
  bytes. Unused or unavailable output fields are 0xFFFFFFFF.
- Cycle update entry is 0x0170015C.

Owner offered to recapture. Keep the camera stationary with sky and landscape
visible through a full cycle; note the visible jump timing. Compare the log's
phase increments and getter values against the source-derived expected values
before choosing a runtime or renderer remedy. No new atmospheric fix should
be inferred from the successful diagnostic build.

## Earlier tribal-fix provenance

The retained legacy report docs/planning/quarry-lighting-audio-performance.md
documents a 2026-10-07 repair that reapplied original actor-light selection after
the day/night ambient setter. It reported integration in that older checkout
and preserved private replay comparisons. The 2026-10-08 private candidate
still contains that repair. A 2026-10-09 original-OS control script explicitly
disabled it in that mode and described the extra re-entry as obsolete.

The current public repository's available git log -S/-G history contains no
addition/removal of that hook. Commit 06b7161 integrated original guest timing,
but its native_boot.cpp diff does not contain the lighting hook. Thus the
control's disabling operation is directly evidenced, while the exact commit
or integration step that lost the correction is not established. Do not claim
a proven deletion commit or infer that the old control established visual
equivalence.

## Evidence and compatibility

Private evidence directory:
D:/JFG-private/v131-rnd-20261019/cutscene-skip/quarry-lighting-stepping-20261020.
Earlier reference: quarry-emuhawk-checkpoint-20261020; accepted repair:
quarry-daylight-restoration-20261020. Preserve source saves and comparison
captures; do not publish ROMs, generated code or personal saves.

Keep the accepted actor repair separate from atmospheric changes. Future timing
or runtime integrations must retain visually accepted compatibility corrections
or replace them with independently verified equivalents. Component test passes
alone do not establish day/night visual fidelity.

Related: [cutscene skip investigation](optional-cutscene-skipping.md).

The diagnostic compiled and all 14 installed package entries verified. The
accepted actor-fix executable is preserved for rollback. The launcher was
opened for owner recapture; no Play or gameplay input was sent by automation.
Runtime: df9a915f83cbc889176467a5810d98eb42bbf015f935610c654cbcb82eead5f7.
Actual diagnostic events and the atmospheric cause remain unverified until
that capture arrives. This is not a new atmospheric fix.


## Live diagnostic capture (2026-10-21 UTC)

Capture 20261021-003237-2ef90a424c05479dabc9ba507a5e7878 used the pinned
df9a915f83cbc889176467a5810d98eb42bbf015f935610c654cbcb82eead5f7 runtime.
It contains 6,598 atmospheric events: 2,200 cycle updates and 2,199 calls
to each geometry/fog getter, all in Quarry room 272. All recorded colours
and fog ranges match the original source-table interpolation; all getter
outputs match the corresponding live globals. There are no model or getter
mismatches. Every consecutive update advances two native ticks.

The capture covers phases 6 through 11 then 0 through 3, not the full
12-stage cycle. Colour changes are small (maximum two units per native
update). Fog distance changes in discrete integer steps. In phase 6,
fog near/far move from 988/1023 to 987/1022, then 986/1021 and 985/1020,
with approximately 2.67 seconds between the steps while fog RGB remains
unchanged at those instants. This is a concrete lead for smooth colour
blending interrupted by visible atmospheric steps. It is NOT yet proof
that these steps are the owner-visible jumps: no timestamped video has
been correlated and downstream fog/render consumption needs examination.

The accepted actor correction is preserved. No atmospheric smoothing remedy
has been implemented. Next: inspect fog coefficient generation and evaluate
fractional cycle-derived fog distances while retaining original cycle timing,
colour endpoints and static-scene fog. Compare before/after with the owner.
Private summary and full sample/analysis JSON are retained in the evidence
directory; this report does not publish the original table or personal saves.

## Original-ROM confirmation and precision candidate (2026-10-21 UTC)

An isolated EmuHawk worker imported the sealed original-ROM Quarry checkpoint,
kept the camera still, and sampled 6,180 VI frames across all 12 phases. All 310
sampled geometry colours, fog colours and fog ranges match the same original
table calculations used by the recomp. No game-memory edits were made. This
is an emulator reference, not a hardware capture or normal story-route test.

A second capture preserves 36 consecutive VI images around a phase-6 fog step.
Fog near/far change from 987/1022 to 986/1021 while geometry modulation and fog
RGB remain white. After the original renderer's presentation delay, mean
absolute RGB change in the distant-wall sample is 6.78 levels; the nearby-ground
sample is unchanged. The sky sample changes by 1.86 levels. This establishes
an abrupt visible atmosphere change in the original-ROM reference as well.
It does not prove every owner-noticed jump has precisely the same cause.

Cause: the controller rounds interpolated fog near/far to whole numbers before
the native fog-position macro encodes its depth coefficients. A one-unit
distance change moves the fog gradient several alpha levels at once.

The candidate keeps the controller's 14-bit phase fraction through distance
interpolation, rounding only when encoding the signed 16-bit fog coefficients.
It preserves exact native encoding at integer-distance endpoints and constant
fog, original cycle speed and colour values. The native game state is untouched.
Immutable per-task metadata is captured with the RAM submission; only commands
matching both the current native environment coefficients and colour are refined.
Other fog controllers, damage-flash commands, stale/invalid snapshots and tasks
without the day/night controller retain native behavior. The existing fog
percentage is applied afterward. The accepted actor-lighting fix is unchanged.

Regression coverage checks steady/end-point encoding, monotonic sub-unit
distance changes in both directions, stale/invalid ranges (including signed
extremes), unrelated effect commands/colours and zero/full fog strength.
Native Release and the daynight_fog, video_settings and rt64_f3ddkr_texture
component suites pass. These are not owner visual acceptance or a performance
qualification.

Private evidence: quarry-atmosphere-fog-20261021 below the existing cutscene-skip
evidence directory. Full-cycle and consecutive-frame EmuHawk captures, pixel
metrics, build receipts and tests are retained. Initial consecutive-frame
setup exceeded the bridge's action-length bound and was rejected before that
action; the corrected run split it into bounded actions. The first build
request used an incorrect target name; the corrected and final builds are
recorded separately. Neither failed attempt is included in validation.

Compatibility lesson: original-game numeric fidelity can preserve a visible
original limitation. Separate a documented precision enhancement from renderer
parity fixes; keep task ownership and effect-specific fog behavior explicit.

The Windows build also caught a near/far macro collision in local distance
names; those names were corrected before the successful build. The final
precision candidate is installed with all 14 package entries verified and
save/profile/checklist hashes preserved. Runtime SHA-256:
1107dd9a4efc8d6f2e4bb6a7e8bde32c3a02b11c75f034c2d791156267831722. Owner visual acceptance remains pending.


## Owner review: precision candidate regresses to strobing

Owner reported "weird now the fog strobes" on runtime 1107dd9a4efc8d6f2e4bb6a7e8bde32c3a02b11c75f034c2d791156267831722. This candidate is rejected pending investigation; passing component tests did not establish visual correctness. Investigate render-command matching, native/smoothed coefficient alternation, and task snapshot timing using the new owner capture. Do not describe the atmosphere issue as fixed.


## Strobing cause and frame ownership correction

The closed owner capture 20261021-010105-2c8f72ed7a64460d82f6a92d59daf87b
used the first precision candidate. It records 1,170 consecutive native
fog-query/controller-update pairs. The native getter runs before the day/night
update; task submission runs later. The candidate incorrectly sampled the
controller at task snapshot time. Across these pairs the fog colour differs
564 times and the integer near/far range differs 17 times. During changing
phases the renderer trace shows isolated matching frames instead of continuous
refinement. Matching the older draw commands against newer globals caused the
candidate to switch between native and refined fog. This is a candidate
regression, distinct from the original game's integer-distance stepping.

The correction captures refinement when dayGetFog returns, associates that
immutable value with each native display-list submission, and consumes only
the matching list's value when making its graphics task. Primary submission
clears the query so a frame without a new getter cannot inherit stale fog.
Queued buffers retain independent values. Competing controllers still reject
refinement, and command coefficients plus colour still must match.

Added regression coverage exercises two queued buffers across changing
colours and integer distance boundaries, consumption, primary/offscreen order,
missing new queries and competing controllers. Additional renderer tracing
records matching decisions even when the refined value equals the original.
Private query-vs-update-mismatch.json and strobe-trace-summary.json preserve
the count and timing evidence. Live correction acceptance is still pending.

The query-bound candidate passes native Release and the daynight_fog, video_settings and rt64_f3ddkr_texture suites. Runtime SHA-256: ca94e6b4c3437fa86086c7bc8e0009767144313c2eef0654ce020d8265ccd50d. All package entries and copied save/profile/checklist preservation verified. Owner visual review remains pending; the first candidate stays recorded as rejected.


## Owner acceptance and capture verification (2026-10-21 UTC)

The owner reviewed the corrected preview and stated "approved - looks good."
Closed session 20261021-011623-b230575709994e33b31616e678de5a97 pins runtime
ca94e6b4c3437fa86086c7bc8e0009767144313c2eef0654ce020d8265ccd50d.
It spans all 12 day/night phases. All 2,972 captured fog queries are valid;
2,971 environment-command match events have the expected colour, with zero
colour-match rejection, across 844 distinct queried colours. This supports
continuous matching through the changing phases which strobed previously.
Query and rendered-command totals differ by one at the capture boundary;
they are not asserted to be one-to-one for the entire process. One three-VI
gap exists among match timestamps; this is not a zero-stutter performance
qualification.

The final remedy retains fractional native fog distances and binds each
correction to the native getter values used to build that display list.
It preserves cycle timing, colour endpoints, the accepted tribal correction,
other fog controllers/effects, and existing fog-strength behavior.
This is an intentional precision enhancement over the whole-distance steps
also reproduced in original-ROM EmuHawk, not a claim of identical N64 output.

The user has moved to a broader cutscene pass using this accepted preview.
Saved per-character checkboxes/notes remain intact. That broader pass and
separate Floyd/controller work are not covered by this atmosphere acceptance.
Private acceptance and trace summary: owner-accepted-query-binding-capture.json
under quarry-atmosphere-fog-20261021. No public release or commit is recorded.
