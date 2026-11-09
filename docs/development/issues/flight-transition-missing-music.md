# AUDIO-FLIGHT-045: Music absent during some flight transitions

- Severity: native NTSC music omission; Walkway behavior confirmed on original hardware.
- Status: owner classifies #45 as a native NTSC bug; correction deferred to a separate general native-bug-fixes update using a different approach. No new remedy is implemented or accepted. The Walkway override remains removed; the two Vela candidates remain individually unverified. No remote issue change or release.
- Reported/updated: 2026-10-24 UTC intake; corrected hardware expectation 2026-10-31; rollback and runtime refactor 2026-11-01; future-update disposition 2026-11-08.
- Original affected report: v1.4.0; Windows 10, GTX 1080, Xbox controller, 60 FPS.
- Report: [GitHub #45](https://github.com/TK22-26/JetForceGemini-Recomp/issues/45).

## Current finding and remedy

On November 8 the owner explicitly classified #45 as a **native NTSC issue** and
deferred its correction to a **separate general native-bug-fixes update**, using
a different approach. The implementation and release date are not yet selected.
This is a documented future correction, not a current manual-test blocker or a
completed fix. See the [native bug catalog](../../original-game/bugs.md#n64-003-missing-flight-transition-music-on-ntsc-45).

The owner corrected the earlier request to add music after rechecking **leaving Walkway on physical
NTSC N64 hardware**: this departure has no flight music in the original. The earlier cutscene was
misidentified. The same departure has music in the owner's original PAL ROM session in EmuHawk.
PAL hardware and Japanese music behavior remain untested. The regional code/asset cause is unknown.

The unsupported Walkway descriptor (scene 15, group 1, asset 15) is removed from the shared override
list in [flight_transition_music.hpp](../../../include/jfg/runtime/flight_transition_music.hpp).
That removes both loaded-header mutation and next-scene tune prediction for this route, restoring
original US selection. Outbound and inbound Walkway are explicit no-mutation regression cases.
The original scene selects track 2; the later scene 102 selects track 7. A track-selection trace is
not itself fresh owner listening or a claim that every sound in either scene is silent.

The two Vela overrides are retained as separate candidates. The Walkway hardware correction neither
accepts nor disproves them, and their original-game expectations still need individual verification.
Those route/regional checks belong to the future native-bug-fixes work. The new disposition does
not imply that every reported route was individually checked on hardware. Earlier tests below
prove that the old candidate inserted music; they do not establish the intended future remedy.

The October 31 Audio Settings review package still contains the historical three-override runtime.
This source follow-up does not silently replace an already-open or older preview. Its accepted
standalone Audio Settings window and unknown original delay cause are independent of this rollback.
[Regional support](regional-rom-support.md) records matching PAL/JP metadata and remaining native work.

## Regional comparison and separate future ROM support, October 31

The owner requested `Jet Force Gemini (PAL).n64` in EmuHawk. Its normalized
SHA-1 matches the bundled BizHawk database's Europe (En,Fr,De,Es) entry:
`50651c4e0c46332f7f0b45870263f0a8b9a49602`. EmuHawk 2.11.1 uses Mupen64Plus
with the software renderer in an isolated review directory. The ROM was not
patched and no NTSC savestate or US memory-address hook was applied to PAL.

A copy of the owner's existing FlashRAM was used. At the owner's request,
slot 1 was changed to Juno's Walkway checkpoint, with the original checksum
updated. Other slots and save devices were byte-verified unchanged and the
original source save hash remained unchanged. The owner confirmed **Yes,
Walkway**, then reported **PAL DOES have the music** and **NTSC does NOT**.
The difference is observed behavior by region; its underlying ROM/code/asset
cause has not been isolated. It does not resolve the other two Vela reports.

The temporary positioning script initially paused between commands and
injected controller input; its copied test configuration also lacked analog
axis bindings. This blocked normal owner control. The loop was stopped,
normal analog bindings restored, and EmuHawk relaunched without ongoing input
injection. The owner confirmed **Yes, it works**. This was a local test-session
setup issue, not a PAL controller defect. A preliminary world-ID assertion
failed before any save mutation: a remembered world number belonged to a
different checkpoint. The original lookup routine and known checkpoint fields
were then checked, and the corrected edit passed checksum/isolation checks
and the owner's in-game Walkway verification. Preserve both attempts.

Private evidence: `pal-walkway-review-20261031/provenance.json`,
`walkway-save-edit.json`, and the guarded folder-audit step logs. Personal
saves, ROMs and emulator snapshots remain private. No new audio capture is
claimed; the music result is the owner's live listening report.

At this October 31 stage the owner requested [PAL and Japanese ROM support](regional-rom-support.md)
as separate future work; the initial documentation-only reorganization did not remove the override
or implement regional support. The November 1 follow-up below removes the unsupported US insertion
and adds matching regional metadata. US/NTSC fidelity must not acquire PAL music unconditionally.

## Symptoms and reproduction

The reporter hears no music in specific flight segments, followed by music
restarting from its beginning in the next segment. Named routes are leaving
Walkway for SS Anubis, finishing Vela's first level, and leaving Vela's bonus
level on Goldwood. Whether the cutscenes were skipped was not specified.

## Evidence and hypotheses

Do not conflate this with [persistent host audio delay](audio-crackle-persistent-latency.md).
The owner reported no audio regression in an SS Anubis pass of candidate
`1d631c0`, but has not yet confirmed or ruled out these particular transitions.
Potential explanations include guest music/fade state and scene transition
handling; no cause has been established. Consulted upstream audio reference
JFG-UP-024; it provides investigation leads rather than a validated fix.

## Attempts and results

2026-10-24: prepared a separate copied profile using the unchanged tested
executable (SHA-256 `726946fc5583617d4625ed0dfe4455045459fa096f89aebe42739afe3b102626`).
Existing diagnostic hooks record cutscene music/volume/fade calls, scene
changes, queue events, inputs, actor state and timing. No new code probes
are needed for initial intake. Private evidence root: `flight-shot-capture-20261024`.
Owner settings are retained at 120 FPS; the report used 60 FPS, so subsequent
comparisons must preserve and state their actual rate.

## Earlier closure and verification limits (superseded)

Initially closed as original-game behavior on 2026-10-24 after the owner's first comparison of all three reported routes. The owner retracts that conclusion on 2026-10-30 after a new playthrough; it is not the current resolution. No runtime music change was made. The following capture limitations remain applicable to the earlier investigation.
A diagnostic trace is not a recording of audible output; owner listening or
a separate audiovisual recording is still needed to locate a missing segment.
Detailed logging can alter timing and capped traces can miss late events.
Use short sessions and verify trace coverage before drawing conclusions.

## Route confirmed in completed capture

The owner skipped Anubis to Walkway (341, then 15 variant 0), and played the
return Walkway to Anubis (15 variant 1, then 102) normally. The requested direction
was captured. Standard logs include music commands, but no audible recording;
owner confirmation of a missing-music symptom is pending. One transient device
underrun occurred before leaving Anubis, followed by resume; this is separate
from establishing whether the later flight's intended music is present.
Private command analysis: flight-shot-analysis-20261024/walkway-anubis-audio-calls.json.

Owner clarification: they are certain there was no audio at the reported
Walkway segment. This is a confirmed audible absence in our build; comparison
with original expected sound remains pending. A command requesting a track is
not acceptance that the track was actually audible.

## Initial original-hardware comparison (superseded)

2026-10-24: the owner explicitly confirmed that the Walkway to SS Anubis
flight also has no music on original N64 hardware. The silence observed in
our build therefore matches the original for this route; no music-insertion
change is warranted. This confirmation supersedes the pending expectation
comparison above. It does not resolve the other two reported Vela flights,
which the owner will check separately. No GitHub reply has been posted.

## Initial owner closure (superseded)

On 2026-10-24 the owner confirms the remaining reported missing-audio
sections match the original and asks that they be closed. The owner's
[GitHub reply](https://github.com/TK22-26/JetForceGemini-Recomp/issues/45#issuecomment-6389834642)
explicitly confirms all three named routes match native hardware, and #45 was
closed at21:36:29UTC. This supersedes the earlier pending Vela comparisons.

Earlier conclusion: expected original-game silence, with no code change. Verification
is the owner's listening/hardware comparison, not an inferred result from track
commands or a new automated audio capture. No duplicate reply was posted.
Persistent accumulated host audio delay (#35) is a different report and remains
open pending affected-machine verification of its unreleased candidate.

## Reopened assessment: hardware report confirmed (2026-10-30)

The reporter's [October 25 follow-up](https://github.com/TK22-26/JetForceGemini-Recomp/issues/45#issuecomment-6397858708)
states that music plays when leaving Walkway on a ModRetro M64 using the
European version. The reporter could not capture the output. GitHub #45 is
open when checked on October 30.

The owner now confirms the report is real and proven on original N64 hardware,
and clarifies: "we initially marked it as false but on a new playthru it was
not false. He was correct". This supersedes the original-behavior conclusion
above. Treat the missing music as a confirmed defect requiring a fix. The
new confirmation does not supply a runtime hash, precise reproduction profile,
audio capture, or an established cause; do not infer those details. Preserve
the European-version detail for comparison without treating it as an explanation
or grounds to dismiss the defect.

No new runtime candidate, build, replay, or audible-output verification has
been performed in this follow-up. The cause and remedy remain open. After
guarded execution is admitted, recover the retained Walkway-to-Anubis capture,
trace the music/fade lifecycle across its scene boundaries, and compare the
audible result with the confirmed hardware behavior. Qualification must cover
the three reported routes and state whether scenes played normally or were
skipped; music-call traces or a successful build alone cannot close the report.

### October 30 execution blocker (renewed October 31)

Read-only inspection of `D:/JFG-private/autonomy-production/jobs.sqlite` on
October 30 confirms the production guard is enabled. Both existing
`high-refresh-rendering-20261011-flight-shot-capture-20261024` and
`high-refresh-rendering-20261011-flight-shot-analysis-20261024` jobs belong to
`high-refresh-rendering-20261011`. That investigation is shelved with the
reason "no verified progress within the investigation allowance": 115/115
attempts, 94/94 supporting activities, 21/24 no-progress outcomes, and
594595.712/714822 execution seconds charged. There is no live or ungraded
attempt and no registered recovery job. Remaining execution seconds do not
override exhausted attempt/activity limits.

The issue status and documentation are corrected, but autonomous investigation,
coding, builds and replays remain stopped under [AGENTS.md](../../../AGENTS.md)
and the [guard contract](../../planning/autonomy-progress-guard.md). Continuing
requires explicit owner renewal of this same investigation's allowance;
the guard, root, counters and historical evidence must remain preserved.

### Transferable lesson and compatibility limits

A later hardware reproduction can invalidate an earlier parity conclusion.
Preserve the historical comparison, but update the current status everywhere
and distinguish audible verification from issued music commands. No regional
compatibility result, runtime behavior change, fix commit, or release is claimed
by this documentation correction.

## October 31 owner renewal and interrupted capture

The owner approved two hours on October 30 and renewed two hours on October 31.
The same investigation/root and all counters are retained. The October 30
supervisor was interrupted during the first copied-profile capture; after the
system restarted, its PID belonged to a newer system service and its worker
was absent. The ordinary expired-lease recovery recorded the attempt as expired
and no-progress. No successful flight capture or audio conclusion is inferred.
A harness variable-scope error on resumption was also retained and corrected
before the fresh capture. The guard stays enabled.

The October 28 owner-authorized cleanup removed the original flight-shot traces;
the existing links above are historical evidence references. New execution and
receipts are under `D:/JFG-private/issue45-flight-music-20261031`, with the earlier
interrupted attempt under `issue45-flight-music-20261030`. At resumption, no runtime candidate had yet been implemented.

## October 31 candidate: departure music selection

Fresh guarded captures use copied profiles, the supported US ROM, real PCM
synthesis/delivery with muted host output, and 60 FPS presentation. The
October 28 cleanup also removed generated source roots; the retained qualified
CPU/audio/renderer objects were reused. Pinned N64Recomp API headers and the
existing timing API were restored privately to compile and link the changed
native boot translation unit. This is an incremental build, not a new full
qualification of generated code.

The baseline music player accepts its requested sequence and sets a nonzero
volume. The US scene headers and global scripts explain the selection gap:

| Departure shot | Level / group | Sequence asset | Header tune | Following flight tune |
| --- | --- | --- | --- | --- |
| Walkway to SS Anubis | 15 / 1 | 15 | 2 | 7 (level 102) |
| Sekhmet departure, after the back-tube shot | 88 / 0 | 91 | 21 | 7 (level 368) |
| Goldwood Lodge departure | 20 / 0 | 20 | 23 | 7 (level 271) |

These three global scripts have no explicit flight-theme command. In contrast,
Walkway's inbound group 0 explicitly requests tune 7. The Sekhmet capture plays
94 -> 88 -> 368 and records tune selection 7 -> 21 -> 7. The Goldwood Lodge
capture reaches 20 -> 271. A Water Ruin flight (342 -> 66) was initially captured
while identifying the Vela route; it is retained as an unaffected control,
not mislabeled as the reported Goldwood Lodge flight.

The final implementation in [flight_transition_music.hpp](../../../include/jfg/runtime/flight_transition_music.hpp)
corrects tune 7 in the loaded header copy before the original `levelTunePlay`
comparison. The transition's earlier `levelGetTune` query receives the same
selection, restricted to its pinned caller, pending destination/group and exact
US level-summary entry. That lets the original code retain an already playing
flight theme. Scene/group/asset/header-tune identities and native instructions
are checked. Explicit script commands, other groups, gameplay, fades, volume
settings, ambient-channel calls and sequence playback remain native. ROM bytes,
the persistent summary table and personal saves are not modified. The observed
selection/handoff gap is repaired; regional differences and exact hardware
soundtrack matching still require listening verification.

Private evidence: `issue45-flight-music-20261031/flight-script-music-catalog.json`,
`observer-route-94-0`, `observer-goldwood-lodge`, `observer-route-342-1`,
`candidate-build.json`, and the guarded step receipts. Baseline traces and PCM
are retained. Runtime listening and hardware comparison remain required before
claiming a fully verified resolution or closing #45.

Informative failures are preserved: an initial inbound/exit harness used the
wrong JSON exit field; the corrected warp reached the native area-clear
confirmation prompt, which the neutral replay did not acknowledge. Neither is
a successful outbound route test. A quoting error prevented the first Vela
harness from launching; it was corrected before capture. The initial focused
test command named a nonexistent test source; no test result is inferred from
that attempt. Build setup failures while reconstructing removed API headers
are retained separately from game behavior. No production guard decision was
bypassed, and no counter or root was reset.

## First candidate qualification and local delivery (superseded)

This first candidate was implemented and tested but was not a released or
hardware-verified resolution. Its original receipt is preserved privately as
`issue45-flight-music-20261031/flight-transition-music-v1-public-receipt.json`.
The [current receipt](../../../evidence/flight-transition-music.json) records
the final candidate described below.

- All three reported departure shots pass 60 FPS before/after selection and
  recorded-PCM checks. Walkway now requests 7 instead of 2, Sekhmet's second
  departure shot requests 7 instead of 21, and Goldwood Lodge requests 7 instead
  of 23. The following Anubis, Dune and Space Station shots keep tune 7 through
  the original same-track handoff instead of starting it again there.
- The Water Ruin control (342/1 -> 66) keeps its original tune 7 and produces no
  correction event. Inbound Walkway group 0 is also left unchanged.
- The copied-profile Walkway test enters 15/0 diagnostically, reaches gameplay
  room 22, selects the exit contact through the existing diagnostic mod,
  acknowledges the native area-clear prompt with recorded A presses, and plays
  15/1 -> 102 -> gameplay room 35 without skipping. Baseline and candidate both
  complete; only the candidate corrects the outbound music selection. This is
  native exit/confirmation coverage, not an unmodified controller walk or N64
  hardware comparison.
- The production-source build, without the private observer probe, passes an
  Original-mode Walkway flight and 120 FPS Sekhmet/Goldwood flights. All three
  60 FPS skip gestures reach confirmed native skip completions. The focused
  suites pass 421 music-boundary, 62 skipped-sound, 8,794 skip/completion, and 74
  scene-review checks under MSVC C++20 with warnings treated as errors.
- Recorded samples are stereo signed 16-bit PCM at 22,018 Hz, captured before
  host master volume. The WAV sample rate is derived from the captured AI DAC
  rate. Nonzero PCM and track commands do not replace listening verification.

The review is prepared at `D:/JFG-previews/issue45-flight-music-review-20261031`.
`Play review.lnk` launches a separate copied October 27 profile at 60 FPS with
host audio enabled. `Listen comparisons.html` contains before/candidate excerpts
for all three shots. The original profile hashes were checked unchanged.
The folder is private and contains ROM/save/audio copies; it is not a release.

Remaining validation: compare the intended flight theme and engine-effects mix
with the owner's hardware playthrough, including all three named routes.
No regional explanation is established. The first candidate still started tune 7
again upon entering scene 88 after scene 94; the former silent segment and
restart at scene 368 are corrected, but uninterrupted music across the earlier
94 -> 88 boundary was not claimed by that first candidate. The final candidate
below corrects that handoff too. Keep #45 open until owner listening confirms
acceptance; record any remaining discrepancy instead of treating this build as
a completed hardware-parity fix.

Transferable lesson: a nonzero music request can select the wrong sequence, and
a nonzero PCM stream can consist of effects. Compare the actual scene/variant,
asset selection, next-shot handoff and audible output. Scope compatibility
repairs to validated US asset/caller identities so explicit scripts, gameplay
and unknown assets keep their original behavior. Preserve the original-hardware
correction and informative failed attempts as history.

## Continuity refinement: cause and correction

The first candidate restores all three missing segments, but its late argument
substitution still stops/restarts the theme entering Sekhmet scene 88. The
original transition calls levelGetTune before loading the next header; matching
only amTunePlay cannot preserve that earlier handoff. A second candidate now
corrects the loaded header before levelTunePlay and supplies the matching tune
to the pinned next-scene comparison, scoped to the pending destination/group
and exact US summary bytes. ROM bytes and the persistent level-summary table
remain unchanged. The first candidate, captures and review are retained; the
second candidate was subsequently qualified as recorded below. A signed
literal warning in the new optional-result test prevented its first compile
under /WX; the literal is corrected without weakening warnings.

## Final candidate: selection and continuous handoff verified in tests

The final candidate corrects both music-selection stages. In the US data, the
three departure headers select sequences 2, 21 and 23 and their global scripts
supply no flight-theme override. The transition compares that metadata with the
playing sequence before the next header is loaded. The first candidate's late
play-call substitution repaired the missing segments but still restarted tune 7
at Sekhmet's earlier boundary. Correcting the next-scene prediction and loaded
header together lets the original same-track logic retain the theme.

Fresh production-source captures verify one native theme start throughout each
normal chain: Walkway 15/1 -> 102, Sekhmet 94 -> 88 -> 368, and Goldwood Lodge
20 -> 271. Sekhmet no longer stops/restarts at scene 88. The affected shots have
nonzero captured PCM and nonzero music volume; no music-stop call occurs inside
Sekhmet scene 88. The Water Ruin control is unchanged and inbound Walkway group 0
receives no override. All three normal chains were checked at 60 FPS; Walkway
also passed Original mode and Sekhmet/Goldwood passed 120 FPS. All three 60 FPS
skip chains complete, and the fresh Walkway native exit/prompt test reaches
Anubis gameplay without skipping. These finite captures cover the affected
shots and handoff, not a full fresh story playthrough.

The final focused suites pass **486 music-boundary, 62 skipped-sound, 8,794
skip/completion and 74 scene-review checks** with warnings treated as errors.
Tests verify that only the loaded header's music byte changes, the neighboring
byte and complete persistent summary remain unchanged, repeated application is
inert, and mismatched groups/assets/metadata/callers/instructions are rejected.
[Final evidence receipt](../../../evidence/flight-transition-music.json).

Final local review: `D:/JFG-previews/issue45-flight-music-review-20261031-v2`.
Use `Play review.lnk` for the separate copied profile or `Listen comparisons.html`
for updated before/after excerpts. The earlier review remains historical evidence.
The review executable uses the actual production source, excludes the private
observer, and is hash-matched to the tested binary. It remains an incremental
build using retained generated/audio/renderer objects, not a full rebuild of
all outstanding source changes. Original profiles and the ROM are preserved.

Owner/hardware listening is the remaining acceptance step: confirm the intended
flight music and engine-effects mix on the three routes. No US/European parity,
release or issue closure is claimed. The guard remains enabled under the same
investigation and owner-approved two-hour session, with every prior charge and
root preserved. All source changes, builds and replays ran in its supervised
worker. The correction does not alter audio buffering, audio-device timing or
other unresolved audio reports.

The first final-package attempt copied the retained first-candidate executable
instead of the second one because its path substitution was incomplete. The
runtime hash assertion rejected it before creating a profile or play shortcut.
The corrected package uses the tested second-candidate executable; the failed
receipt and runtime identities are retained privately. No game-code change or
additional replay was needed for this packaging error.

## November 1 follow-up: restore original NTSC Walkway behavior

The owner approved this follow-up within the three-hour runtime/history/regional work. The Walkway
entry is removed from both header-selection and next-tune prediction overrides by removing its
shared scene descriptor. The outbound and inbound Walkway cases now explicitly assert no metadata
or RAM mutation. The two Vela candidates remain separate and unverified against original behavior.
The rebuilt Windows host runtime passes the 118-case CTest suite. Copied-profile replays cover
normal and skipped Walkway departure, the retained Goldwood/Vela candidate, a before/after Water
Ruin control and the native Walkway exit/prompt chain. The last uses diagnostic positioning before
real native confirmation; it is not an entirely natural player route. Walkway produces no override
events, and the skipped chain completes. Final artifact checks are retained in the private
`reorganization-followups-20261101` receipt. No fresh owner listening, release or issue closure is
claimed. [Runtime module validation](native-runtime-modularization.md) records the build boundary.

### Regional architecture migration, 2026-11-01

The two retained candidate corrections now use typed regional globals and
qualified original instruction sites. Their applicability is explicitly US
only; PAL/JP execute their original music behavior without inheriting these
unverified corrections. This does not add Walkway back or change the recorded
NTSC hardware/PAL emulator distinction. Existing 334 boundary checks and
non-US policy rejection tests pass; no new live music acceptance is claimed.
