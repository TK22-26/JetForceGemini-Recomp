# AUDIO-003: Ship-cutscene stutter and Goldwood exit audio

- Severity: moderate; audible interruptions and cutscene choppiness.
- Status: renderer cause reproduced; focused tests and beta.1 owner pass accept both reported ship scenes with clean audio. Follow-up village/aspect defects remain separate and open; no stable 1.3 release.
- Reported: 2026-10-16 UTC. Last updated: 2026-10-17 UTC.
- Scope: Windows native Play, ship departure/travel and Goldwood exit, high-refresh presentation.
- Related: [walking audio](walking-audio-interruptions.md),
  [capture coverage](frame-diagnostics.md),
  [native audio policy](../native-audio-playback.md).

## Symptoms and reproduction

The owner finished the longer tutorial capture with no perceptible gameplay
slowdown but heard audio interruptions and saw choppiness in the Goldwood exit
cutscene. On 2026-10-17 the owner clarified that they have not tested this scene
in released v1.2.0 and offered a clean new recording. The historical report was initially open without a v1.2.0 reproduction. The
completed owner run and subsequent controlled reproductions are recorded below.

Play through Goldwood using normal Play and allow the exit cutscene to finish.
Preserve the starting save, inputs, exact binary identity, game/presentation
timing and final audio counters. Do not attribute startup idle or deliberate
pause gaps to active-route performance.

## Evidence and hypotheses

The earlier 21-minute capture retained all 131,288 presentation records, but its
detailed gameplay/audio trace hit the 256 MiB cap around 18:27, before the exit.
Earlier zero counters cannot establish the exit's audio health. Private evidence:
`final-measurement-20261016/measurement-review.json`.

That capture also used periodic GPU screenshots. A controlled comparison proved
their periodic main-thread stalls; screenshot removal and independent compact
game/audio health logging subsequently shipped in v1.2.0. This is a confounder,
not proof of the exit's cause or resolution.

A prior comparison had a 160.184 ms presentation gap and one underrun after
roughly 168 ms without game/audio progress. This demonstrates queue exhaustion
under a long stall, not the cause of this particular exit report. Preserve the
original synthesis/sample clocks while investigating any confirmed recurrence.

## Attempts and results

| Date | Attempt | Result / decision |
|---|---|---|
| 2026-10-17 | Recover existing evidence and production guard state | Prior counters retained; same investigation continued for the owner-approved three-hour window. |
| 2026-10-17 | Launch clean owner recording using the published v1.2.0 package | Completed owner run: zero underruns/overruns; two visual ship-scene stalls reported. Copied profile/save, 120 FPS with VSync, original audio preference retained, no periodic screenshots or mods. Builds and automated gameplay tests stay idle during the recording. |

Private capture root: `goldwood-exit-1.3-20261017/owner-sessions`. The launch
receipt and separate initial-profile backup preserve the source/profile hashes.
Published source: `f56cd94c4bd7583bceee201eb3f229f744216bc1`.
Native executable SHA-256:
`72b2844ccaf8c5cc9a93142a7f4b42133b4a33c53ae30ecb31e527fdab40023e`.
Recording begins on Play, not while waiting in the launcher. The release's
compact timing stream and final play-health counters are independent of the
capped detailed gameplay trace. No runtime change has been made for this capture.

## Candidate remedy and remaining verification

The renderer patch in [rt64_call_matching.cmake](../../../cmake/rt64_call_matching.cmake)
filters draw calls that cannot contribute a transform, tile or look-at match.
It removes a quadratic no-op search without changing game timing, audio buffer
policy, AI or original bridge physics. The pinned upstream file is untouched;
the build checks its normalized source hash and patches a generated copy.

The departure performance comparison and exact-state tests below pass. This is
an unreleased 1.3.0-beta.1 preview, not a resolved/released issue. The owner has
requested another full live pass, including both ship scenes and listening for
audio interruptions. That acceptance remains pending.

## Lessons for future changes

Full-session health coverage must outlive detailed diagnostic caps. A muted
short test cannot certify a later audible cutscene. Preserve failed or partial
evidence and distinguish instrumentation overhead from runtime behavior.


## Owner v1.2.0 result (2026-10-17 UTC)

The owner reports no audible underruns in the new run. The completed capture
writes final play-health with zero underruns and zero overruns, matching the
progress snapshot. Detailed logging again reaches its 256 MiB cap, but this
release retains game-update timing and final audio health through clean exit.
This resolves the earlier coverage gap for aggregate counters, not every
possible subjective audio artifact.

The owner identifies reproducible visual stuttering in two ship cutscenes:
(1) after character selection, departure from the mothership and travel toward
Goldwood; (2) the ship rising from the ground at the end of Goldwood. The first
returns to smooth rendering as Goldwood appears; the second improves at the
transition to SS Anubis. Treat this as a visual issue while checking timing and
interpolation, rather than assuming the audio buffer is still starving.
Private evidence: `goldwood-exit-1.3-20261017/first-capture-review/report.json`.
This records the initial owner result; the candidate below is newer. Final owner
visual acceptance remains pending.


### Renderer wait localization and first fixture limit

The new capture's late VI 61200-61800 window has median graphics submission
31.429 ms, including median queue advance wait 25.283 ms. Neighboring smooth
VI 62000-62600 has median queue wait 3 microseconds. History preparation is
about 1.7 ms in the slow window, so the existing measurement localizes most
submission delay downstream to the renderer queue, not that history stage.
This does not yet distinguish renderer CPU work, GPU work or presentation waits.
The slow window averages about 24.9 present returns and 20.4 screen scenes per
second; game-update VI deltas also include 74 three-VI intervals. Frame records
are complete with zero logger queue drops. These windows include scene
transitions and have not been used as a global gameplay-rate acceptance.

A first muted replay truncated owner input too early and stayed on the planet
selection screen (state 5, level 127) instead of reaching the ship cinematic.
Its clean 120/30 result does not reproduce or clear the reported cutscene.
Retain `departure-release-120` as an informative fixture failure; correct the
input boundary before comparing renderer candidates.


### Short ship-cutscene reproduction

Splicing the owner's recorded second menu selection after the title entry
reaches the cinematic at level 365 (then 93) without patching guest RAM or saves.
The published v1.2.0 runtime reproduces sustained queue stalls and visual
frame-delivery drops in that cinematic, recovering in the next scene. This
controlled muted run also records one underrun, so the owner's clean audio
run does not establish universal audio acceptance. Profiling runs have extra
observer cost and additional underruns; they locate work, not benchmark a fix.

The first external sampler attempt failed because a local `symbols` dictionary
shadowed its PDB search-path variable. Its complete runtime/profiler trace is
retained, but it provides no external samples. A successor corrects only that
private helper and keeps both attempts. Evidence: `ship-release-120`,
`ship-profile-120`, `ship-profile-sampled-120` and `ship-profile-review.json`.


### Cause and candidate: no-op cross-frame draw matching

External samples in the reproduced slow cinematic concentrate on RT64
GameFrame::matchScene's nested same-key candidate loop. The observed workload
GPU time is approximately 0.054 ms median, compared with about 45 ms in the
profiled submission synchronization. The sampled run has suspension failures
for some thread handles (retained in its receipt); the successful render-thread
samples are usable for localization but not a complete CPU percentage.

The pinned matcher inserts every draw call into a multimap, then examines all
same-key pairs across frames. JFG already handles its own transform history
and precomputed UVs, so many calls have transform matching and tile interpolation
disabled and do not use generated texture coordinates. Those pairs cannot add
a transform, tile or look-at candidate, yet repeat an O(N*M) no-op traversal.

The candidate removes only these inert entries before the nested search.
Transform, tile and look-at eligibility, ordering and explicit linear-ID
matching stay intact. The pinned dependency remains unchanged; a hash-checked
build-tree copy carries the patch. Actual RT64 buildCallHashMap regression
coverage first fails on the original implementation and passes with the patch.
The first test compile found signed/unsigned bitfield comparisons under warnings
as errors; explicit boolean casts corrected the test without weakening warnings.
The implementation subsequently passed the qualifications below.


### Automated candidate qualification (2026-10-17 UTC)

| Reproduced departure | Rendered FPS | Scene FPS | Median queue wait | Audio underruns (whole short run) |
|---|---:|---:|---:|---:|
| ship-release-120 | 41.42 | 20.06 | 30.8605 ms | 1 |
| ship-candidate-120 | 119.65 | 29.81 | 0.0040 ms | 0 |
| Candidate, 360 FPS / VSync off | 358.92 | 29.81 | 0.0040 ms | 0 |

All measured update intervals inside the candidate departure windows are two VI.
The 120 FPS comparison uses the same recorded menu input, starting save, hidden
window dimensions and VSync setting as the published v1.2.0 binary. It records
615 presentations with 8.338 ms median / 8.828 ms p99 intervals; the largest
individual interval is 32.871 ms, so this is not a claim of zero isolated gaps.
The 360 target checks delivery/cadence, not physical 360 Hz display quality.

Two 4,200-VI fixed-clock A/B pairs, Original and Custom, produce byte-identical
guest RDRAM, save data and renderer input snapshots and identical 1,875-update
instruction sequences. The Custom pair also has identical semantic, billboard,
rigid-pose, ownership and conflict decisions. Both pairs reach levels 365, 93
and 92. These deterministic probes verify correspondence; their host audio
counters are not native-Play performance qualifications.

The linked RT64 regression fails seven checks before the fix and passes after
it, including 4,096 inert calls, explicit linear IDs, mixed-matrix eligibility
and texture-generated look-at matching. Existing interpolation and draw-key
tests pass. CI now builds/runs the new matcher test.

Private artifacts: `ship-candidate-120-comparison.json`,
`reference-correspondence.json`, `route-and-360-review.json`,
`selected-route-review.json` under `goldwood-exit-1.3-20261017`.
The tested candidate runtime SHA-256 is
`6e4ec391fb073744bad6e9ca552a346f56151a00d3b1822a3cf462eb7846858d`.

### Long replay coverage limits

The unspliced native input replay completed 1,079 seconds with zero audio
underruns, overruns, unsupported accesses or dropped frame records. It diverged
from the owner's route, staying in level 27 and later reaching 157 instead of
the reported exit. It is a stability observation, not exit verification.
Native elapsed-time input replay alone does not establish identical scene
coverage; the missed transition's exact cause has not been isolated.

The successor reuses the proven title-to-second-selection input splice, then
replays all remaining owner inputs. It does not patch game memory or save data.
Observed in-game level sequence: `365, 93, 92, 47`. Final audio
underruns/overruns: 0/0;
frame-log drops: 0. It does not reach the owner recording's final observed level 101, so exit coverage remains unverified.
Neither replay substitutes for the requested fresh owner full pass. Keep these
limits with the performance numbers; duration alone is not route coverage.


### Source qualification scope

The first full-object hygiene scan in the shared working repository rejected
unrelated retained stash/history objects (private paths, an oversized blob,
an unapproved binary and non-UTC stash metadata). Those objects are absent from
this preview branch's ancestry. They are preserved, with no allowlist exception
or history rewrite. Current-source checks and an isolated single-branch clone
with no shared object store qualify the exact candidate history before packaging.
The original failed scan remains in private evidence as `preview-source-policy.log`.


### Local 1.3 beta delivery

The local 1.3.0-beta.1 full-pass capture package is built from clean source
`a8144269f86e094426e09ce63af050e2ac4c4b42`. Its runtime SHA-256 is
`9b0fd3b1c3572650882e52c74363c6af2cd46bac9daf7ff95647aec5d6de3f98`. The clean packaged runtime repeats the muted
departure check at 119.65 rendered / 29.81
scene FPS with zero audio underruns/overruns and zero frame-log drops.
Native renderer tests, launcher/setup checks, package integrity and copied-profile
resolution pass. The original save/settings and published v1.2.0 are retained.

The owner-requested full pass starts recording when Play is clicked. Timing,
render/scene counters, input/interpolation logs and independent final audio
health are saved on the data volume. Periodic screenshots and heavy function
profiling remain disabled. Local delivery is not stable publication or owner
visual/listening acceptance. Private receipt: `preview-delivery.json` in the
same investigation evidence directory.


### Owner beta.1 acceptance and follow-up (2026-10-17)

The owner completed the new full pass and confirms that the ship departure to
Goldwood and the ship rising at the Goldwood ending now look fixed. Audio is
fine. These are live acceptance of the two reported ship scenes, not acceptance
of every cinematic. The owner separately reports slight choppiness in the
first new-game village opening and cutscenes expanding to 16:9 despite the
game's widescreen option being off. Gameplay remains 4:3. These follow-ups are
tracked in [DISPLAY-002 / PERF-004](opening-village-and-cutscene-aspect.md).
The completed beta.1 capture is retained in private evidence under
`goldwood-exit-1.3-20261017/beta1-capture-review`. No stable release is claimed.

## v1.3.0 source availability

The documented change is included in tag v1.3.0 (launcher/source
02be6fa9a4c50f4056f778c5148ca8ac70b0e92b; clean runtime
665596482a7395593e85dbe73f1bd4b016d183d9). See the
[combined release qualification](../releases-1.3.0-qualification.md) for owner
acceptance, source CI, package and publication evidence. Earlier failed attempts
and the scene/device/seed limits above remain part of this record; inclusion
does not turn an unverified broader report into a confirmed resolution.
