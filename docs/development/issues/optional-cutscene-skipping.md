# ENHANCE-001: optional cutscene skipping

- Status: supported native completion routes implemented; owner confirms SS Anubis flashback, Vela rescue, Juno departure and Tawfret intro. Unsupported scripts remain ineligible; broader route coverage remains open. Unreleased.
- Report: [GitHub #31](https://github.com/TK22-26/JetForceGemini-Recomp/issues/31), 2026-10-19.
- Owner requests inclusion in a quick v1.3.1 together with #30.
- Problem: repeated story/travel/level-transition cinematics interrupt pacing,
  including scenes already watched.

## Scope and correctness requirements

Expose a deliberate skip action. Identify the native end-of-scene path and
complete required progression, character unlocks, room transitions and camera/
input/audio handoff. Merely stopping presentation or jumping the camera is not
a valid skip. Preserve default playback and protect against a held skip input
unintentionally skipping the next scene.

## Planned verification and limits

Check first-time story scenes, already-watched travel, interrupted dialogue,
room loading and scenes that grant progression. Compare post-scene state with
ordinary completion; separately verify owner-visible transitions and controls.

Initial investigation state: no native skip path had been qualified. The implementation update below supersedes that initial status.
No release date or blanket all-cutscene compatibility is claimed. Public
comments wait for owner review. Lesson: distinguish presentation shortening
from executing the gameplay state changes embedded in cinematic scripts.


## Native source review, 2026-10-19 evening

The original US sequence interpreter is identified, but a skip implementation
is not yet qualified. Resident animseqUpdate (0x80077614) advances animated paths
and then animseqProcessCommandList (0x80077ABC) executes timestamped commands.
The command stream ends with 0x7F00; merely reaching that sentinel does not
automatically restore input, set progression flags, or change the level.

The pinned original dispatch table and command bodies establish these relevant
operations:

| Opcode | Native action |
| --- | --- |
| 0x76 | mainSyncNextLevel |
| 0x77 | Conditional end-of-game/front-end transition |
| 0x78 | mainSetGameFlag using the embedded flag and value |
| 0x7A | mainChangeLevel and mainSetAnimGroup with embedded character/room parameters |
| 0x7B | Set sequence play/pause state and reset sequence clock to this command time |
| 0x7C / 0x7D | Disable / enable native player input |
| 0x7E | Loop to the stream start and subtract the elapsed loop duration |

Each supported command has a fixed length, ranging from 4 to 14 bytes.
Unrecognized command slots do not advance the pointer. Consequently a bounded
parser must reject unknown opcodes, truncated payloads, backwards timestamps,
pause gates and looping streams before proposing a finite completion path.
The normal main loop also ticks objects, particles, camera and world effects
around sequence updates. Advancing the sequence clock alone does not establish
equivalent final object/effect state.

The two named play/pause entry points only change the sequence state variable;
they are not hidden native skip functions. A separate object handler uses
these same sequences for proximity-triggered gameplay animation, so an active
sequence alone is not a valid cinematic detector.

Next: qualify a deliberate, input-edge-triggered completion operation for
cinematic scene types, preserving required script actions and returning through
native room/input/audio handoff. Compare progression flags, destination,
character selection and restored controls with ordinary completion before
exposing it in the release. Preserve normal gameplay/ambient sequences.

Private source-review evidence: D:/JFG-private/v131-rnd-20261019/controller-ledge
(sequence-command-table.json, sequence-control-references.json and original
instruction excerpts). These are local research artifacts, not public game-code
exports. No new runtime skip action or user-visible setting was added.

Owner approved 30 minutes on 2026-10-19 to add a deliberate Start-button skip. Existing investigation counters are preserved. Required progression and transitions must still complete; implementation and tests remain in progress.

## Owner direction and implementation scope, 2026-10-19 late evening

The owner changed the requested interaction: pressing A, B or Start reveals a
native blue A button with SKIP to its right. Only holding A continuously for one
second confirms. A clockwise white ring reflects actual hold progress; releasing
A resets it, and the prompt hides after inactivity. Use native N64 display-list
drawing in game; the supplied SVG is visual reference only.

The owner explicitly prefers proper scene completion over accelerated playback.
The 30-minute source/UI session completed normally. An additional two-hour
guarded continuation is approved, ending 2026-10-20 04:29:55 UTC. All existing
investigation counters/roots remain intact.

Current components: include/jfg/runtime/cutscene_skip.hpp emits bounded native
RDP RGBA16 fill commands for the blue button, label and ring, and implements the
real-time hold/focus/scene release policy. cutscene_script.hpp inspects bounded,
big-endian native command streams without mutating guest state. Component checks now include B/Start reveal without confirmation. The runtime integration and current preview are described below; live verification remains pending.

### Upstream review

Reviewed VibinToast/JetForceGemini-Recomp at
91422a30a93c985b87ba9de0db4b317a3ea7c88f, particularly
[src/jfg/jfg_cutscene_skip.cpp](https://github.com/VibinToast/JetForceGemini-Recomp/blob/91422a30a93c985b87ba9de0db4b317a3ea7c88f/src/jfg/jfg_cutscene_skip.cpp).
It accelerates native simulation, drops rendering and transient sound events,
handles audio queue pressure, and continues through cinematic level changes.
The first story intro instead requests a direct character-selection transition.
That is useful evidence of lifecycle concerns, not proof of equivalent completion
in this runtime. No upstream source was copied. The owner declined that approach
in favor of explicit completion contracts.

### Completion evidence and remaining work

Private cutscene-skip/full-scene-contract-inventory.json records complete
original command streams, identities, audio actions and transition parameters
from eighteen saved snapshots (including duplicate observations). The introductory
sequence chains multiple levels/groups; Goldwood travel goes 101 -> 102 -> 35.
The Vela rescue also crosses level/group boundaries. The absence of explicit flag commands in those samples does not by itself establish that actor/level callbacks cannot affect progression.

The normal native mainChangeLevel routine already clears player setup, requests
screen fade, manages pause/transition state, conditionally fades music and stops
rumble. Completion should reuse that routine with the script's actual destination,
character and entry parameters. Still required: qualify persistent state outside
the script, complete scene chains, cancel captions/transient effects, integrate
bounded native HUD drawing without clobbering display-list storage/state, adapt
the logical Confirm input across Modern controller/KM and Original, and compare
post-skip state with ordinary completion. Until then no scene is marked skippable.


## Explicit completion candidate and native prompt

The candidate is in Native Cutscene Skip Preview, using a copied profile and
starting muted. A, B and Start reveal the native blue A/SKIP prompt; only A held
continuously for one second confirms. Releasing A resets progress. The prompt
expires after 2.5 seconds without input. Focus loss and scene changes require
a fresh A press. A/B/Start are consumed during supported cinematics, including
until release after a handoff, so the gesture cannot also activate gameplay.

The button, glyphs and timer ring are native N64 RDP fill commands appended to
the primary graphics task before full sync. Offscreen blur/refraction tasks do
not receive the prompt. RDP fill colour, scissor and other-mode state are
restored. No SVG, host overlay or font/image asset is used.

The gameplay thread parses a bounded immutable copy of the native sequence.
Only reviewed finite command families with a terminal 0x7A or 0x77 and reviewed
cinematic actors are eligible. The planner preserves remaining 0x78 flags,
0x7C/0x7D input controls, 0x74/0x75 front-end controls and 0x76 synchronization.
It calls the original transition routines with the script's character, entry,
mode and group parameters. The conditional ending retains all three native
progress-flag checks. Pausing the completed sequence prevents old timed
commands from overwriting the requested handoff. The sequence clock is not
advanced and no simulated frames are accelerated or dropped.

Subsequent expected cinematic rooms may complete through the same checked path,
up to sixteen segments. Each new room gets an ordinary initialization update.
Menus, character selection, multiplayer, gameplay/ambient sequences, loops,
pause gates, unknown commands, unknown actor controls or conflicting transitions
do not qualify. This is deliberately bounded coverage, not an assertion that
every campaign cinematic has been tested.

### Why intermediate object updates were inspected

Resident animobjControl and animplayerControl are no-op functions in this ROM.
The reviewed cinematic light/cone, particle, scrolling, prop and animation
callbacks change presentation/local objects. Recorded travel/story/rescue
actors have neither the generic movement-script pointer nor the animation-event
table enabled; the scripted rescue NPC has ordinary control disabled.
These observations support explicit completion without replaying every frame.
They are not evidence that arbitrary gameplay sequences can be skipped.

Native animseqFreeGroup clears paths, camera/effect state and captions and calls
the native sequence-sound cleanup, which stops all sixteen tracked sound handles.
The existing level transition invokes that lifecycle. The candidate preserves
it instead of destroying objects midway through the current update.

### Validation and remaining limits

- Native executable and jfg.cutscene_skip tests build/pass, including A/B/Start
  policy, actual hold duration at 20/30/60/120/360 Hz, focus/release protection,
  bounded GBI commands, script rejection and destination/character semantics.
- Production parser/planner and actual actor-check function accept the sixteen
  captured cinematic snapshots and reject the two menu/character-selection
  samples. Several snapshots represent the same level/group.
- An isolated harness compiles the actual production completion handler against
  captured guest memory, replacing native calls with an argument recorder.
  1,826 checks pass: destination/character/front-end branch, one transition,
  pause/sentinel handoff, no repeated completion and unchanged sequence clock.
  This verifies the handler, not a full ordinary-playthrough state equivalence.
- Owner live prompt appearance, progress ring, complete scene chains, audio,
  first-time progression and restored controls are still pending.
- Earlier compile failures (mixed-width auto declaration and nonexistent
  GuestMemory byte writer) were corrected; failed logs are retained.

Private evidence: D:/JFG-private/v131-rnd-20261019/cutscene-skip. Includes original
command/controller analyses, captured-scene-validation.csv,
actual-runtime-validation.log, native-completion-ctest.log and preview-receipt.json.
The preview runtime SHA-256 is
861d7a9a43f56dbfdd777752507bcb56e44c9f3f0bf964ed9d7cc960bae490a5.
No public comment, commit, issue closure or release has occurred.

## Failed first live preview

Owner saw an apparent freeze, then out-of-bounds views before returning inside the ship, where skipping was unavailable. The prompt was much too large; owner requests approximately one-quarter size. Input confirmation and several completion events are recorded, so the failure is after confirmation/in the scene lifecycle. Component argument checks did not establish actual camera/fade/load completion. Preserve this informative failure; do not ship the first candidate or describe it as verified. Owner closed the game and launcher.


## Second candidate: cancel skipped music synchronization

The first live failure is retained above. The completion path preserved opcode
0x76 (mainSyncNextLevel), which sets the native next-level MIDI synchronization
flag. The loader then calls amWaitForMidiSync and waits for a cue from the
unplayed remainder of the original shot. The owner's capture shows approximately
39 seconds between one completion request and the next room initialization.
That wait is inappropriate for an explicit skip; it is presentation timing,
not a progression requirement.

After a confirmed skip, the revised handler clears a previously scheduled
synchronization flag and omits remaining 0x76 requests. Ordinary playback retains
its original synchronization. Native level cleanup, destination/character/group
parameters, progression flags and conditional front-end routing remain active.

The later ship segment (level 323, group 2) contains animation-path rewind
command 0x02. Its reviewed original implementation resets/restarts a cinematic
path; it has no persistent progression effect. This command now qualifies.
Already-executed commands do not block completion of a reviewed remainder.
Unknown future effects and sequences without a departure remain unsupported.

A native black transition covers intermediate cinematic room loads until normal
gameplay/front-end presentation or an unsupported scene resumes. It is bounded
by the existing sixteen-segment limit and a fifteen-second VI timeout; this is
presentation during native room cleanup/loading, not simulation fast-forward.
It must still be checked live for complete handoff, controls and audio.

The A icon is now about one quarter of the former diameter; text is half-size
to retain readability. Native one-cycle primitive-color rectangles retain
quarter-pixel coordinates. The renderer restores primitive color and combiner
as well as scissor, fill color and other mode. No SVG/host overlay was introduced.

Validation: native build and jfg.cutscene_skip pass. An updated isolated harness
compiles the actual completion handler against the captured memory and records
native-call arguments: 2,877 checks pass, including preservation of the sync flag
during ordinary playback, clearing it only on completion, absence of calls that
schedule/wait for the skipped cue, native destinations and conditional endings,
and the original ship group-2 command stream. This still does not establish a
complete live ordinary-versus-skipped state comparison. Owner live retest pending.

Private evidence: skip-cue-fix-build.log, skip-cue-fix-ctest.log,
actual-runtime-validation-v2.log, runtime-harness-v2, and the first failed
owner-sessions/20261020-030015-7f9ab511cb544e958d565613c4a7d2f9 capture.
Transferable lesson: a state/argument harness can pass while asynchronous audio
synchronization and camera/load presentation still fail; both need separate
lifecycle verification.


## Owner second-pass result

The opening story skip worked: nine remaining segments completed in ~3.61
seconds, with no audio underruns recorded. Owner reports the Goldwood ship
landing is still not skippable. Coverage is incomplete; do not mark resolved.
The quarter-diameter prompt is visibly broken/unreadable (owner screenshot);
fractional rectangle bounds passed tests but do not establish native raster
legibility. Reworking the icon to half diameter/quarter area while preserving
the integer-pixel 5x7 glyphs, and investigating the landing's completion handler.

The third-candidate compile caught a missing newline in a test comment (fixed). The new original landing-script regression then rejected opcode 0x67, revealing an additional unreviewed object-field command before live packaging; it is being inspected. Neither failure is treated as live verification.


## Third candidate: Goldwood landing and readable native pixels

Owner confirms the opening story skip works. The landing was rejected for
remaining music-fade opcode 0x22, local actor-flag opcode 0x67 and room actors
32 (waterfall/bubble emitter) and 55 (animated bridge). The captured trace names
these actors; the script's original departure is level 93 -> 92.

The emitter control updates local particle triggers. The bridge control updates
local geometry/physics and sounds; bridge eligibility additionally requires the
native animation flag that disables ordinary control. Movement scripts and
animation-event tables still reject qualification. Opcode 0x67 only toggles a
local flag of the selected cinematic actor; the native departure discards it.

Completion uses original amTuneSetFade with a zero-second duration and the
script's target volume, exercising its existing immediate branch. This preserves
the final envelope/volume state rather than dropping the fade command or waiting
through it. Native room transition and cleanup still perform the gameplay handoff.

The prompt now uses whole native pixels throughout. The button is half the
original diameter (approximately one-quarter area), with a minimum readable
5x7 A/SKIP font. The previous fractional-pixel candidate is rejected and retained
as evidence of the rendering limitation.

Validation: native build and component tests pass. Updated harness: 2,885 checks
pass, including the actual landing script in an explicitly synthetic actor
context, the zero-duration fade argument, level-92 transition and preservation
of the caller's floating-point registers. This is not a captured full landing
RAM comparison. Owner still needs to verify prompt appearance, landing skip,
restored movement and audio. All-cutscene coverage is not claimed.

Private evidence: landing-skip-final-build.log, landing-skip-ctest.log,
actual-runtime-validation-v3.log, runtime-harness-v3 and preview-receipt-v3.json.

## King Jeff invasion owner failure

Third preview skipped travel room164 into invasion163, then stopped completing.
Owner reports landing mid-cinematic with no further skip available. Capture
20261020-033954-dec00c1710984f74841b490c54d0950d confirms room163 actor gate,
room165 command gate and room166 actor gate reject. This is incomplete sequence
coverage, still open. The same capture shows Goldwood365 -> 93 -> gameplay92
completed through two native handoffs; that trace does not establish prompt
legibility or owner acceptance of gameplay after landing.

The invasion source review identifies type 30 lights, type45 audio and type54 huts as no-op ordinary controls; type57 only advances local sprite animation (80024EF4 -> 800577A8). Candidate admits these with the same movement/event-script exclusions. Opcode23 preserves native amTuneSetVolume then amTuneResetFade. The first regression assertion incorrectly assumed volume127; original asset169 specifies45 (0x232d), and the assertion was corrected to the original operand. No production value was changed to make the test pass. Owner considers the third preview prompt passable and requests a generated button image with animated ring/pop, still rendered natively.

## Fourth candidate: invasion sequence and generated native button

The original invasion transition chain is 164 -> 163 -> 165 -> 166 -> the
remembered gameplay destination. Owner session
20261020-033954-dec00c1710984f74841b490c54d0950d identifies the rejection points:
type 30 in 163, music-volume opcode 23 in 165, and types 30/45/54/57 in 166.
The candidate retains native scene loading, first initialization update, object
cleanup, character/entrance selection and gameplay return. It does not advance
the simulation clock or skip an unknown gameplay callback.

Original controller dispatch sends types 30 (RGBA light),45 (audio marker) and
54 (hut) to its no-op return. Type 57 calls 80024EF4, which only updates the
sprite animation through 800577A8. Movement scripts and animation-event tables
still reject eligibility. Opcode23 calls 80000FE4 with its original volume, then
80000798 to cancel an old fade, matching the native interpreter order.

The original script assets 168/167/169/170 and synthetic actor contexts matching
the observed types now pass a four-segment production-handler regression,
including final gameplay return and preserved volume 45 in segment 165. These
asset/level identities are corroborated by the observed departure chain, rather
than guessed from level number minus one. Updated handler harness passes 2,945
checks. This does not establish full gameplay/save/audio parity or all-scene
coverage; owner verification remains required.

Owner accepts the integer-pixel prompt as passable and requests generated
artwork while retaining ring/pop animation. The generated blue-A PNG is stored
unchanged in assets/ui/cutscene-skip; its compiled 32x32 RGBA16 sprite uses the
native RDP texture rectangle and ordinary texture decoder. No guest memory is
allocated or modified. Temporary TMEM, tile state and render state are restored;
only the explicitly added HUD rectangle receives the sprite texture. The
clockwise one-second ring and SKIP label remain native commands. The button
briefly expands during the last 160 ms of the hold, returning to normal at
confirmation; release still resets the hold.

Private evidence: actual-runtime-validation-v4.log, runtime-harness-v4,
invasion-skip-build.log, invasion-skip-ctest.log, native-sprite-build.log and
native-sprite-ctest.log. The first volume regression used an incorrect expected
127; checking the original 0x232d operand corrected the expectation to 45 without
changing production behavior.

## Fourth-preview visual failure

Owner screenshot codex-clipboard-Eej08D.png shows ring and SKIP label but no
new blue-A image. Native build/component checks did not catch presentation
failure. Generated sprite rendering remains open; investigate texture upload,
resolved texture identity and render-state handling before another preview.
Invasion completion result has not yet been confirmed by the owner.

Owner corrected the latest selection: game/launcher closed, but invasion skip was NOT tested. Keep invasion live verification pending.


### Preview 5: native sprite command order and styled lettering (2026-10-20)

The owner corrected their previous answer: King Jeff's invasion was NOT tested.
Do not count the phrase "Closed; invasion skip worked" as verification. Its
completion candidate still needs a live progression/audio handoff check.

The fourth preview's invisible A was reproduced from a saved original graphics
task using the actual RT64 renderer: the ring and label appeared, but the texture
did not. A bounded native draw trace showed zero texture tiles for that draw.
The direct RDP color-combiner API stores the native command words in the opposite
order from their display-list spelling. Passing the unswapped pair selected
neither the intended texel color nor texel alpha. Correcting the word order
restored the blue A in the same replay. This was a draw-state bug, not missing
artwork or a skip-handler failure. Temporary tracing was removed.

At the owner's request the thin 5x7 SKIP lettering is replaced by a native
64x24 RGBA16 texture derived from the bundled OFL-licensed Chakra Petch Bold,
with a slight rightward slant. Both assets use native texture rectangles;
the white hold ring and final button pop remain driven by the live one-second
confirmation gesture. A/B/Start reveal; only A held for one second confirms.

Validation evidence is private under
D:/JFG-private/v131-rnd-20261019/cutscene-skip:
sprite-with.ppm reproduces the failure; sprite-word-order.ppm verifies the
isolated correction. styled-prompt-render-validation.json records native GPU
replays at 0, 0.5, 0.92 and 1 progress with visible button/text pixels and no
changes above the HUD. See styled-prompt-build.log and styled-prompt-ctest.log.
The evidence runner supports JFG_EVIDENCE_CUTSCENE_PROMPT for reproducible
saved-task HUD checks. This variable affects only that evidence executable.

Status: renderer/build verification is separate from owner visual approval.
The revised lettering, in-game pop, and invasion completion remain pending
owner review. No all-cutscene coverage or released-resolution claim.

Transferable lesson: native command words and the renderer's internal packed
combiner representation are different layouts. Check new HUD assets through an
actual native render; testing asset bytes and emitted geometry alone missed
this integration error.


### Forest introduction and smaller smooth prompt (2026-10-20)
Owner reports Goldwood forest/level intro has no A/B/Start prompt; ship shots were
not the reported scene. Latest capture 20261020-041748-98bbfaf2ebff4527ab0162b981e9e62c
records scene399/group1/script396: completion plan is valid, actor gate rejects.
The sole unreviewed type is 48, Fdaylpadobj. Its native dispatch is 0x800104A8,
the same no-control branch already verified for lights/audio/huts (30/45/54).
The actor has no movement script or event callback and carries animation flag8.
Candidate qualifies type48 while retaining the independent script/callback gates.
Owner verification is pending; the separate scene199 training/pickup gate is not
relaxed. Invasion trace now reaches 164->163->165->166->native return0xFFF; this
proves completion commands ran, not owner acceptance of audio/control handoff.

Owner also rejected prompt size, off-center A/ring and blocky progress border.
Candidate reduces all dimensions by25%, shares quarter-pixel button/ring center,
and replaces integer fill blocks with a 64x64 IA8 native texture (4KiB TMEM,
16 alpha levels, rounded animated arc). Four actual GPU renders completed for
progress0/.5/.92/1; further owner visual approval remains pending. No game/save
inputs were injected. Evidence: small-ring-*.png and smooth-ring-build.log.

### Preview6 forest failure and renewed review (2026-10-20)
Owner still reports forest/level introduction has no skip; capture 20261020-042859-b61fbf033aba41798bb372b144d1c57b confirms the type48 change qualifies scene399, but this does not establish that it addresses the reported introduction. Recheck actual room/sequence identity and runtime eligibility. Owner requests removal of final A-button pop/shake; candidate now keeps button diameter fixed throughout hold, preserving animated ring. New two-hour guard receipt preserves original investigation counters/root. All changes remain pending live verification.


### Tutorial pickup classification cause and candidate (2026-10-20)
The preview6 capture records repeated A holds in scene199/group0/script203, the
Magnus health/ammunition/enemy tutorial, while scene399/group1 is its later return
shot. The earlier type48-only candidate addressed that later shot, not the
tutorial rejecting all of the owner's A holds. The current actor gate classified
health's nonzero +7C pointer as an unreviewed script; original health control
uses it as collision/physics state. Ammo type66 was also unreviewed.

Reviewed original healthPickupControl (overlay104+1F0) and ammoPickupControl
(overlay72+64): inventory, health and collection writes require hitPlayer.
hitPlayer's native player list accessor 8000E464 reads count800F2D10. Candidate
allows these two object types only while that count is zero, keeps definition
event callbacks rejected, validates health physics storage, and does not run
collection handlers. Ordinary gameplay pickup cases remain ineligible. Native
script203 finishes with change-level399/group1; script396/group1 finishes at
gameplay21, with its original music fade completion. Actual code tests and owner
confirmation remain pending. This is a typed object-state classification fix,
not an unconditional bypass of actor or sequence completion checks.

Evidence: owner capture20261020-042859, correct-pickup-068001F0.txt,
correct-pickup-04800064.txt, review-8007E150.txt, review-8000E464.txt and extracted
original tutorial/return scripts in private cutscene-skip evidence. Eligibility
changes after the first scene update are now logged to distinguish late gates.

Candidate validation: native runtime/evidence renderer build and existing hold/GBI tests passed. Production completion-function harness passed 3003 checks including original tutorial203 and return396/group1 script bytes in reconstructed actor context, route199->399/group1->21, unchanged sequence clock and actor/inventory memory, and rejection with players present, invalid physics storage or event callbacks. Four actual GPU renders verify identical opaque A-center pixels at progress0/.5/.92/1 and animated ring changes, with fixed sprite diameter confirmed in production source. Earlier whole-prompt color-mask and rectangular-bound checks included transparent sprite corners showing the ring; individual changed pixels were inspected and both failures preserved. These are code/renderer checks; owner gameplay verification remains pending. Receipts: tutorial-no-pop-validation.json and actual-runtime-validation-v5.log.


### Owner follow-up: SS Anubis flashback and A centering (2026-10-20)

Preview 7: owner reports the SS Anubis flashback cannot be skipped and the A button is still slightly off-center in the hold ring. Exact scene/eligibility cause under investigation; forest tutorial fix remains pending explicit live verification. Owner is currently playing, so do not replace the package or interfere with the session. Eight-hour guarded continuation approved; original ledger counters and evidence preserved.


#### SS Anubis diagnosis and candidate
Capture 20261020-115008-3893e8d508e34ef9801628c04fb7c34d uses preview 7's exact runtime hash. The forest tutorial now completes 199/group0 -> 399/group1 -> gameplay21 in the trace; explicit visual acceptance remains pending. The flashback is scene239/group0, asset242, followed by238/asset241 ->240/asset243 -> remembered gameplay35. Its sole unreviewed control is type65, GlowingLight. The original US control jump-table entry resolves to800104A8, the same empty return already accepted for other presentation objects. Its captured movement/event callback slots are zero. Candidate accepts type65 while preserving those callback checks. Asset242's time-zero music-start command must still run normally before the remaining script can qualify.

The A sprite/ring rectangles shared mathematical centers, but the 9-native-pixel button had a fractional top edge. RT64's native RDP rectangle path rounds coverage and applies a T-row adjustment to fractional tops; the even-sized ring did not receive it. Candidate uses whole-pixel cover bounds with fractional positioning in S/T for both axes. Artwork, prompt size and one-second hold remain unchanged. Actual-render validation and owner verification pending.

Preview8 validation: native build and component tests pass. Production-function harness passes3921 checks, including all remaining command boundaries of original flashback assets242/241/243, exact native transitions239->238->240->remembered35, unchanged actor memory and clock, rejection of glowing-light movement/event callbacks, and normal execution of the time-zero music-start before eligibility. These are reconstructed-context tests, not owner live acceptance. Four native GPU renders show a stationary A texture (129-pixel blue mask identical across progress0/.5/.92/1) with animated ring. Raster-bound correction removes the one-output-pixel rightward bias; vertical threshold bounds differ by half an output pixel, within sampling discretization. Owner review of concentric appearance remains pending. Receipt: private cutscene-skip/preview-receipt-v8.json.

Owner confirmed preview8 SS Anubis flashback skip and A-button/ring alignment fixed on2026-10-20; other cutscenes remain under review, unreleased.

New preview8 reports: Vela rescue cannot skip; Juno SS Anubis fly-away cannot skip; brief white flicker on return from SS Anubis to character selection. Owner continues playing; inspect current capture, do not replace active package.

### 2026-10-20 preview8 follow-up: Vela input and Juno departure

Owner accepted the SS Anubis flashback skip and revised A/ring alignment, then
reported no prompt during Vela rescue and Juno's SS Anubis fly-away. Owner
explicitly confirms the game had focus during rescue; map focus is not an
established cause. The recording contains 2,434 neutral logical input samples
over VI 14000..19000 and all six rescue segments qualify for completion. Those
samples occur after mapping and focus/release gates, so they cannot establish
whether hardware input was absent or discarded. Candidate adds change-only
observations of Modern actions, mapped buttons, final buttons and gate state;
it does not bypass focus or synthesize inputs. Vela remains unresolved.

For Juno's departure (room/asset 341, group 1), two type-7 hangar doors block
the actor review. Both have animation byte +9 = 8, no +7C control state and no
data+D4 event callback. Native 800091F4..80009224 explicitly skips their ordinary
objControl dispatch while that animation bit is set. Candidate admits type 7
only on the ordinary object-list suffix (index >= 800F2CAC), with the bit and
existing callback/state checks; an active door remains rejected. Completion
must preserve script flag 96=true and the native conditional ending path.
This is a candidate awaiting tests and owner verification, not a released fix.

Owner also saw a brief white flash on return to character selection. The
recorded departure played naturally: no skip confirmation/completion occurred
there. No pixel capture is available, so the flash's cause and visual parity
are unresolved; it must not be attributed to skip completion without evidence.
Private evidence: cutscene-skip/owner-sessions/20261020-120828-f5778954278646fab80de52b6e003196,
anubis-door-control.txt, anubis-flight341-script-1.bin and guarded steps 432?438.

Preview9 refinement: separately dispatched native objects use count/list 801047E0/801047E4 (8007E484), so cinematic doors also reject membership in that unconditional dispatch list. Completion harness now passes 4,136 checks, including active doors, invalid animation, ordinary-list exclusion, special-list membership/malformed bounds, unchanged actors/clocks, flag96 and all native ending branches. Owner confirms game focus in Vela and will retest both sequences. Added change-only input traces and per-primary-frame native fade/transition/list/target plus presentation VI state during cinematics and 180 VI afterward. Fade requests record arguments and caller. No screenshots or GPU readback are added; the observation cannot alone verify the displayed color of a reported flash. Native build/live review pending.

Preview9 built and packaged: native build and cutscene tests passed; production completion harness passes 4,136 checks. Candidate/runtime evidence: private cutscene-skip/preview-receipt-v9.json. Owner live testing remains pending. Source rain-fade work remains preserved separately. Input trace flags: bit0 UI capture, bit1 Settings, bit2 release/focus gate, bit3 device ready, bit4 physical neutral, bit5 connected, guest-menu kind at bit8; action mask is ModernAction bits. cinematic-frame-state records VI,level,group,list begin/end,target,transition byte,skip cover,fade kind,R,G,B,alpha,script cursor. cinematic-present-state records VI,level,selected target,graphics target,VI origin/status/width/H start/V start/scales/blackout/skip cover.

Preview9 owner result (2026-10-20): Vela rescue is NOW confirmed skippable (owner corrected ?not? to ?now?). Juno fly-away still cannot skip, and the white flash returned; both remain open. Game closed and new capture available for investigation. A passing reconstructed-context test did not establish the live actor membership condition. Preserve failed candidate evidence.

### Preview9 rejection and preview10 candidate

Owner confirms Vela rescue now skips; its six native transitions through 378/2,
379/1,344,380/3,345,380/4 to gameplay241 completed in the new capture.
Juno341/1 initially qualifies at VI0x1341 then loses actor eligibility at0x1342.
Captured door anim+9 remains8 and +7C remains0 throughout the flight; actor slots
reorder with camera distance. The previous special-list/ordinary-prefix exclusion
was too restrictive to represent the native cinematic door behavior.

Source review of controlDoor80025A08: outgoing calls get native/animated players,
read inventory/progression flags, animate local door state, start/stop positional
sounds, and set/remove per-player HUD hints (00601284/006012B0 write the transient
800FF1D0+player*80 hint entry). No progression setter or room-transition call
exists there. Candidate supports these cinematic doors with zero gameplay-player
count, valid disabled-control animation, no custom event callback and no +7C
movement state. It no longer treats a render-list slot or special-list membership
as proof of gameplay side effects. Active gameplay doors remain excluded.

Tests now reproduce the original script cursor0x2C and object reordering after
the initial eligible update, retain eligibility, and check flag96 and all native
ending branches. Owner live verification remains pending.

White flash repeats after natural341->127 at~109.68s. Fade RGB remains0,0,0
throughout; a first empty primary list and one present-skip occur while127
initializes. These are leads, not proof of a renderer fault. Preview10 adds an
explicit diagnostic-only post-departure image window: up to64 downsampled rendered
frames held in RAM and flushed beside the private session RDRAM on close.
GPU readback occurs in this short window, so it is not a performance measurement.
No visual-flash fix is claimed. Original logging without screenshots is preserved
outside this opt-in path. Private source/evidence: steps446?460 and preview9 capture
20261020-123243-bc443c82f2fd4766b230b7c80a0b00d9.

Preview10 packaged: build and native cutscene component tests pass; extracted production completion harness passes 4,136 checks, including post-first-update cursor0x2C, object reordering/list membership and all native ending branches. Owner corrected latest report to Vela rescue NOW confirmed skippable. Preview9 Juno eligibility still failed after its first update; special-list count at the failing VI was not captured, so the exact previous exclusion is not proven. Revised cinematic-door candidate awaits live verification. Diagnostic images span the end of departure and start of character selection (up to64 sampled native presents, downsampled in RAM, PPM flushed on close). This does not capture every interpolated output frame. No white-flash fix claimed. Private receipt: cutscene-skip/preview-receipt-v10.json.

Preview10 live result (2026-10-20): owner confirms Juno SS Anubis departure now skips. White flash reproduced; supplied screenshot shows saturated rainbow/white corrupted scene materials at character selection (geometry remains recognizable), not merely a flat white overlay. Private video C:/Users/tjkos/Videos/2026-10-20 08-56-41.mkv; diagnostics owner-sessions/20261020-125514-ff39bdc0ad794f13a82ffe189ddd4aa5. Investigating captured pixels and scene transition before assigning cause. Vela and Juno skip owner-accepted; white-flash issue remains open.

### Preview10 white-flash video and current framebuffer-role candidate
Owner video is120FPS,1280x720. Frames795/796 (~6.625-6.642s) contain the
rainbow/white scene;794 and797 are normal. This lasts one60Hz output interval.
The screenshot resembles depth interpreted as RGBA16; that is a hypothesis,
not yet a captured renderer-source confirmation.
Actual final room display-list prefixes bind segment1 to10FF00/135700 and
segment2 to15AF40, then clear segment2 through SetColorImage before normal
color rendering. Earlier Vela cutscene traces presented15AF40 as color.
Pinned RT64 early-presentation history matches address/size/VI compatibility
without checking current framebuffer role and can convert selected depth to
color. Workload candidate collection also includes depth-clear pairs.
Candidate excludes known depth-only clears from interpolation candidates and
requires a current color write for history-based redirection. Explicit VI or
debugger depth display keeps its conversion path. No room IDs, timed blanking,
or fade-cover changes. Native tests reconstruct color->depth->color reuse.
Runtime trace now records selected source/role, rejected historical depth
matches, and actual depth conversions. Live confirmation remains pending.
The preview10 opt-in image flag was stripped by the launcher's intentional
JFG_* environment sanitization; no in-game image files were captured. Owner
video is the pixel evidence. Keep ordinary route capture free of GPU readback.

Preview11 retains owner-accepted Vela and Juno skipping. Its independent framebuffer-role candidate for the rainbow/white character-selection flash passed build and renderer/cutscene tests, awaits owner review. See [flash investigation](character-selection-depth-flash.md).

Preview11 owner result: white flash persists. This candidate is NOT a verified fix. New closed capture: owner-sessions/20261020-131703-9007e95299e5435d89e625a93066989b. Reviewing actual present-source/depth-conversion events before further changes; Vela/Juno skip remain accepted.

## Tawfret introduction report

Owner preview12 reports Tawfret introduction cannot be skipped. Capture 20261020-133119 identifies cinematic level135/group0, script802D57B4; parser finite but completion plan and actor review both reject. Reviewing actual commands/object controls before expanding eligibility. Vela/Juno accepted skips retained.

### Tawfret cause and candidate

Native asset139/group0 contains future music-start opcode21, screen fade43 and fog envelope45, which the completion planner rejected. The captured actor list also has type19 (native no-control case800104A8) and type9 (8001C0D8, per-view fog trigger). Source review confirms the added visual effects alter transient presentation; type9 remains allowed only with zero gameplay players and no movement/event callbacks. The new completion action executes native tune start80000510 then fade cancellation80000798, matching opcode21 ordering, before the normal destination158 transition. Component coverage includes future/already-executed tune selection, omitted visual envelopes and preserved destination. Build and live verification pending.

### Tawfret validation

Actual runtime completion harness passes 4,217 checks, including original asset139 at seven cursor positions, native music start/fade-cancel order, normal destination158 transition, untouched script clock/actor bytes and rejection of gameplay fog actors/custom callbacks. An older harness assertion expected pending music-start to block all skipping; it was updated to the new explicitly supported action, while existing no-audio-repeat tests after the music cursor remain. Component/native build passed. Preview13 owner test pending.

## Owner acceptance of Tawfret preview13

Owner confirms Tawfret intro skipping works in preview13. Actual runtime and component checks passed before this visual acceptance. No release yet. The separate post-Vela/room-transition camera snap remains open in CAMERA-009.

## Vela skip audio report and remaining coverage (2026-10-20)

After accepting preview14's room-entry camera fix in both Modern input modes,
the owner reported a brief audio stutter when skipping Vela's rescue. This is
open, affects the local native skip preview, and has not yet been attributed to
an audio underrun, a native music transition or skip completion work. The owner
requested investigation after the accepted changes are committed to develop.
Review the recorded skip transition and audio queue/timing evidence before
changing buffering or music semantics. No fix or fresh audio acceptance is
claimed.

The owner also requested an inventory of every cutscene, with a way to test
skipping without playing the full campaign. Build a source-derived checklist,
distinguish script/room variants and prepared state requirements, and identify
safe direct entry routes. A room warp alone is not evidence that a story scene
has been tested. Completeness of the inventory and untested routes remain open.

### Vela skip audio investigation

The two preview14 owner captures (20261020-141612 and 20261020-141738) each
record zero audio-device underruns/overruns. Both skip six Vela chain segments
in about three seconds. Buffered audio continues through that interval.
This excludes device starvation as an observed cause in these runs, not an
audible source discontinuity. Source inspection finds time-zero sound starts
in intermediate shots that are allowed their initial native update before
automatic completion; normal sequence cleanup stops their tracked handles.
Music restarts are not yet established: the chain largely shares tune66.

Added sparse native music/start/stop/volume and sequence-sound diagnostics to
the existing gameplay trace, including room/group/skip-chain identity, native
fade state and host queue health. No audio behavior or queue sizing changes.
A listening/capture comparison is still needed to identify the reported sound.

Owner clarifies the Vela skip symptom is interrupted music. Native build and four focused suites passed with sparse audio-call tracing. Separate desktop Cutscene Audio Review package prepared using a copied profile; no listening result or audio fix is claimed.

Owner correction after the dedicated audio run: the interrupted sound is a
low continuous effect (spaceship/vent rumble), not music. Closed capture
20261020-171422 is available with music/effect call tracing and final RAM.
Reassess the sound identity from that evidence; the earlier "interrupted music"
description is superseded. No fix is claimed.

### Skipped-shot effect fragments (2026-10-20)

The dedicated 20261020-171422 recording confirms tune66 is not restarted or
stopped during the intermediate Vela skip shots. It changes to gameplay tune5
after completion. The device underrun counter does not increase during the skip.
There was an earlier underrun in this run; this is not a zero-underrun capture.

Original scripts start sound24 at time zero in rooms379/group1 and344/group0,
and start both tracked and actor-bound sounds in345/group0. Native sequence
cleanup stops those handles roughly 0.2?0.3 seconds later during the skip.
This is a concrete source for the repeated short fragments described by the
owner. Exact audible acceptance still needs the new preview.

The completion path intentionally permits each loaded shot's first ordinary
update. The candidate now omits presentation-only effect starts from that
update only while the current shot belongs to a confirmed, qualified skip
chain. It recognizes the original command-interpreter call sites for opcodes20,
27 and29 and validates native instruction signatures, current scene/group,
qualification and already-cleared handle storage. It does not alter memory or
invent handles. Native cleanup, game state, music and ambient-channel state
continue normally. Gameplay and unskipped/unqualified scene callers are unchanged.

Source: runtime/cutscene_audio.hpp and native_boot.cpp dispatch. Native sound
APIs return void; their original unavailable-sound path uses a null handle.
The interpreter already stops and clears a previous handle before the reviewed
start calls. This is not global muting or an audio-buffer workaround.

The candidate passes the native build and five focused suites, including
sound-boundary, skip-completion, scene-review and input regressions. Actual
call-site signatures were verified against the owner capture. Desktop
Cutscene Audio Fix Preview contains the candidate plus the menu-hover fix,
with a copied pre-audio-review save. No live audio pass or released fix claimed.
Private receipts: skip-sound-source-receipt.json, skip-sound-tests.log and
audio-fix-preview-receipt.json. Earlier trace omitted effect-start calls; the
candidate includes those plus explicit cutscene-skip-sound-omitted events.

## Owner audio confirmation (2026-10-20)

Owner reports "audio fix works" in Cutscene Audio Fix Preview. The scoped
suppression of intermediate skipped-shot effect starts is now live verified
for the Vela rescue rumble. This is not a release claim or verification of all
cutscenes. The accompanying menu-hover change failed review separately.

The subsequent corrected menu candidate is also owner-confirmed; see UI-008.
