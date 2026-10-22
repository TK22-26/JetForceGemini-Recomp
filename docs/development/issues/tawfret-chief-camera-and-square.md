# Tawfret chief cutscene: rapid bad-angle camera motion and floating square

- Status: camera-cut and original-game camera-helper visibility corrections owner-verified; included in v1.4.0; see the release qualification for delivery status.
- Severity: visible cinematic rendering/camera regression.
- Reported (UTC): 2026-10-22.
- Build: v1.4.0 candidate ea9845e, Custom 120 FPS, VSync on, Reduced blur,
  fog 100%; normal launcher, diagnostics and FPS logging/overlay off.

## Symptoms and reproduction

During the Tawfret tribal chief sequence, a small yellow square with a dark
surround appears beside/behind the chief in three distinct shots. The owner
also initially described a white flash on camera changes, then clarified that
the camera moves very quickly through bad angles: this is not a white
framebuffer flash. The owner initially believed neither artifact was in the base game.
The owner initially reported the square absent on original N64 hardware, then
rechecked and confirmed it is present but obscured by native resolution and TV
blur. See the later hardware confirmation and intentional original-game fix below.

Evidence: owner video 2026-10-21 20-18-01.mkv, four VLC snapshots extracted
at 20h22m31s527 / 20h22m40s602 / 20h22m45s150 / 20h22m52s478, and three
annotated conversation images. Private hash inventory:
v14-tawfret-chief-20261022/inputs.json.
The owner supplied a pre-scene save and completed an instrumented launcher capture.

## Initial evidence and hypotheses

Unknown whether the square is a world-space primitive, an actor effect or a
screen-space overlay. Camera path/interpolation at cuts is a hypothesis, not
a demonstrated cause. Do not equate this report with the earlier corrected
character-selection framebuffer/depth flash.

## Attempts and results

2026-10-22: preserve references, inspect the supplied video and source. Current
owner session stays on unchanged candidate binaries. A diagnostic success
cannot establish ordinary-release correctness, given the earlier rain/reticle
logging dependency.

## Verification and remaining limits

Camera acceptance is recorded below. The square is confirmed as an original-game
camera-helper artifact; the scoped visibility correction is built and owner-verified
in the ordinary 120 FPS launcher with logging disabled.
A candidate must retain normal camera shots, actor geometry, progression and
rain/reticle presentation with logging disabled. The owner performs live review.

## Capture preparation clarification

The owner meant an instrumented launcher capture, not another OBS video. The
first reopened launcher was ordinary Play and produced no diagnostic recording;
that misunderstanding is corrected with a separate copied-save capture profile.
It uses unchanged v1.4 binaries with camera/actor/interpolation logging and exit
RAM capture, without periodic screenshots or weather/pixel probes. The normal
final-pass launcher remains untouched. No fix is claimed by this diagnostic.

## Camera discontinuity candidate

The 120 FPS video contains three intermediate bad-angle/scenery frames at
approximately 15.10-15.12 seconds before the next shot settles. A focused
regression proves that a distant shape's small screen displacement can anchor
a shared scenery transform even when the byte-bound camera poses identify a
discontinuity. The new assertion fails on the previous implementation.

The candidate makes a valid camera-cut rejection veto that same matrix cohort.
Unusable/conflicting metadata keeps the existing conservative fallback policy;
normal small camera movement and a second independent camera remain eligible.
The focused interpolation-history and semantic-presentation suites pass after
the correction. This establishes the fallback defect, not owner acceptance for
this particular scene. The floating square remains a separate open target.

Build compatibility finding: the native RT64 target includes this shared header
under C++17, although the focused test target uses C++20. The initial candidate
used set::contains and failed that target. Replaced it with the equivalent
find/end lookup; no compiler standard or dependency settings were changed.

Native Release build and four relevant CTest suites pass. A separate camera-only
preview is prepared with the original copied pre-scene save, 120 FPS, diagnostics
and FPS logging/overlay disabled. The exact dirty source identity and refreshed
package hashes are retained privately. The owner subsequently confirmed: "Camera cuts fixed; square remains."
That review used 120 FPS with diagnostics and FPS logging/overlay disabled.

Original comparison setup attempts are retained: the first stopped at the
existing-file confirmation; handling that confirmation then entered the wrong
character checkpoint (room43). Neither is valid evidence about the chief scene.

## Original-command rendering isolation

A copied-save fixture now reaches scene255 correctly after explicitly admitting
Juno at character selection. The original ROM runs in isolated muted EmuHawk;
the first successful reference uses GLideN64. Initial visual inspection did not
identify the small square; that assessment was inconclusive and is superseded
by the software-renderer comparison below. Selection-only fixture flags are
not story-progression proof.

Replaying that same original RDRAM, VI registers and native display lists through
the current RT64 adapter reproduces the yellow square, independently of native
gameplay execution and of high-refresh interpolation. Private artifacts:
`v14-tawfret-chief-20261022/original-through-rt64`, scene snapshot 11, main list
0x1fb2d0. This isolates the symptom from native gameplay execution and
interpolation. An initial inference that this proved a renderer-side difference
was premature: the subsequent Angrylion/software-RSP reference also shows it.

The suspected SteveLight sprite has the same raw actor state in original/native
captures, and suppressing its two triangles in a private copied-list probe
changes no pixels. It is therefore ruled out as the square's source in this
shot. No object has been hidden in product code. A diagnostic trace initially
refused source comparison because checkout line endings differed; normalized
text comparison preserves the check, and exact original bytes are restored
after temporary instrumentation. Original reference and all failed setup/probe
attempts remain retained privately.

## Camera fix acceptance and square fidelity limits

The owner verified the camera-cut correction in the ordinary 120 FPS preview:
"Camera cuts fixed; square remains." The failing-before/passing-after regression,
native Release build and four relevant CTest suites pass. Source:
[interpolation history](../../../include/jfg/renderer/interpolation_history.hpp)
and [regression tests](../../../tests/interpolation_history_tests.cpp).
No square-removal change has been made, and this is not a released resolution.

The original ROM in EmuHawk with Angrylion and software RSP also draws the square
in checkpoint 11 (private `emuhawk-chief-angrylion/session/checkpoint-11.png`).
The owner then explicitly confirmed that it is absent on original N64 hardware.
That prompted keeping the hardware-versus-software discrepancy open at this stage.
The later owner confirmation below resolves it. Neither agreement between
emulators nor running the original ROM alone establishes hardware fidelity.
No live N64 RAM dump is required from the owner to continue local draw tracing.

## Draw ownership and external reference research

The two yellow-square triangles are at physical 0x2b0f10 and 0x2b0f20 in the
original snapshot 11. They lie inside the triangle table of model `camera` at
0x802b0c10, used by `AnimCamera` objects. The model table starts at 0x802b0cf0
and has 36 triangles; these are indices 34/35. The first offline probe applied only the first triangle patch because the
second positional argument requested a private RAM output instead. Its changed
pixels were confined to [522,252,527,257), matching part of the yellow region.
The corrected comma-separated two-triangle and whole-model probes are recorded
in `camera-model-isolation-confirmed.json`; no temporary RAM output is left in
the public checkout. This is an identification experiment, not a product remedy. The earlier
SteveLight hypothesis was ruled out by its no-pixel-change counterfactual.
Private evidence: `square-geometry-model-candidates.json`,
`square-geometry-isolation.json`, `square-geometry-difference.png` and
`camera-model-visibility-state.json`. Temporary renderer tracing was removed
from source and the task renderer rebuilt without it.

Owner-requested online research found a relevant mechanism in
[Diddy Kong Racing's decompilation](https://github.com/DavidSM64/Diddy-Kong-Racing/blob/master/src/object_functions.c):
`obj_loop_animcamera` follows the animation path, explicitly sets
`OBJ_FLAGS_INVISIBLE`, and writes the resulting view position. The
[JFG decompilation](https://github.com/Ryan-Myers/Jet-Force-Gemini) describes
JFG as a heavily modified DKR engine. This supports investigating camera-helper
visibility; it does not prove the same flag layout or defect in JFG. A
[first-person Conker emulator report](https://www.emutalk.net/threads/conker-bfd.1216/)
mentions an unwanted upper-left square and speculates that it is a shadow
rendering scratchpad. That explanation is unverified and is not a match for the
camera-model geometry identified here. No exact matching published report or
established cross-game fix was found in this bounded search.

Initial follow-up plan: identify the exact drawn camera instance and follow JFG's visibility and
animation update rules. Preserve camera logic, shot timing and actor behavior;
do not hide pixels or remove an actor merely by its screen position or color.

JFG-specific visibility follow-up: snapshot 11 has camera-model instances with
both flags 0x0002 and flags 0x0402. Native `objPrintObject` at 0x8000DB94 rejects
objects whose +6 halfword intersects 0x0c00. Behavior 47 dispatches to
`animobjControl` at 0x80026FD4, a no-op; it is not DKR's camera-loop function.
Therefore copying DKR's flag operation directly would be an unsupported fix.
The next trace must establish where JFG's animation script sets/clears camera
visibility and whether natural scene entry differs from the copied-save fixture.

Tooling limit: Capstone is unavailable in this environment; the visibility
follow-up used the existing generated instruction comments and the original
snapshot words, without changing generated code. A documentation worker initially
failed reading the UTF-8 changelog through Windows' default encoding; rerunning
that read with explicit UTF-8 completes the entry without changing game code.

Corrected two-triangles probe: changed bounds (522, 252, 528, 257), 28 pixels.

Corrected whole-camera-model probe: changed bounds (517, 248, 530, 258), 120 pixels.

## Original hardware confirmation and helper visibility candidate

The owner rechecked the original N64 reference and confirmed that the square is
present there too: the low resolution/TV blur made it resemble background detail.
This resolves the previously reported hardware discrepancy. The camera-cut
interpolation defect remains a separate recomp defect and owner-verified fix.
The owner explicitly requested fixing the original camera-helper artifact in our
release. Do not describe this as mistranslated guest instructions or a generic
renderer bug.

The original path interpreter starts path 13 at 20 seconds, clearing actor +6
bit 0x0400 in animseqStartPath (0x800767EC). Later camera commands select other
paths without stopping path 13. In snapshot 11, path 13/actor 0x801bc130 is still
drawable at (-1101.75,79.875,1344.875), while the current camera is path 20/actor
0x801bd920. The normal object gate at 0x8000DB94 therefore submits its camera mesh.
A fresh Angrylion/software-RSP diagnostic hiding only that former camera removes
the square. Its timing differs enough to move some sparkle pixels (3,574 pixels
changed overall), so this is not claimed as an isolated pixel-identical replay;
the earlier immutable display-list replay changes only the square's 120 pixels.
Clearing the widescreen preference changes no screenshot pixels in this cinematic
and does not remove the square. Reference runs have no inherited cheat files.
Private evidence: v14-tawfret-camera-helper-20261022/camera-script-and-matrix.json,
original-camera-paths.json and original-counterfactual-results.json.

Candidate: exclude only the supported AnimCamera object (behavior47, object30,
exact terminated header name) at the pinned native object-draw gate. Its native
hidden flag is scoped to that draw and restored immediately, including on unwind.
Animation paths, camera selection, simulation flags, positions and progression
remain intact. Other behavior47 objects include visible props and must remain
unaffected. The correction has no room, screen-position, color, FPS or logging
condition. Source: include/jfg/renderer/camera_helper_presentation.hpp and the
native dispatch wrapper. Focused regression coverage checks native draw-gate
eligibility, exact state restoration, nesting/unwind, same-behavior props,
malformed pointers and incompatible instruction/header identities. Build and
owner visual verification subsequently passed as recorded below; not yet released.

The first build produced the native executable but rejected the regression fixture
because std::fill inferred an int zero for a byte container under MSVC /WX.
The fixture now uses an explicit uint8_t zero; compiler strictness is unchanged.
Preview preparation correctly stopped at its failed-build gate and launched
nothing. Both failed logs remain private evidence.

Native Release build and all four focused renderer/history suites pass, including
the new helper scope checks. A separate copied-save 120 FPS preview uses normal
Play with diagnostics, FPS logging and the overlay disabled. The owner confirmed:
"Square gone; scene looks correct" after being asked to check all three shots,
camera motion and the rest of the cinematic. The prior camera-cut correction
remains included. This is acceptance of the reviewed chief sequence, not an
exhaustive claim about every cinematic. See the standalone
[findings write-up](../tawfret-camera-helper-findings-2026-10-22.md).
