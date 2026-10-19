# PERF-005: GitHub #19 invasion replay collapses to 1-2 FPS

- Source: [GitHub #19](https://github.com/TK22-26/JetForceGemini-Recomp/issues/19),
  reported 2026-10-18 UTC.
- Severity: high; a cinematic reportedly becomes almost unwatchable every time.
- Affected: released v1.2.0, Windows 11, RTX 5090, Xbox 360 controller,
  Unlimited frame rate with VSync enabled.
- Status: open, reporter reproduction not yet independently confirmed. No fix
  or release claimed. No external comment posted.
- Related: [PERF-004 opening village](opening-village-and-cutscene-aspect.md),
  [AUDIO-003 ship cutscenes](goldwood-exit-audio.md).

## Symptoms and reproduction

At the start of Goldwood, ask the tribal to replay the invasion. The reporter
identifies the shot where blue drones enter their spacecraft as the onset of
1-2 FPS, persisting through the remainder of the cinematic. The report has no
support ZIP, monitor refresh rate, display resolution or FPS-counter breakdown.
Those omissions are coverage limits, not reasons to dismiss the report.

The owner confirms this PC also has an RTX 5090 and all unrelated tasks are
paused. A quiet machine is a repeatability condition, never a product requirement.
Our previous new-game opening captures are relevant but do not establish
identical state to the tribal-triggered replay.

## Evidence and initial hypotheses

Private issue snapshot: `village-pacing-20261017/github-issue19/issue.json`.
The preserved v1.2.0 runtime is
`D:/JFG-previews/release-1.2.0/jfg-native-boot.exe`; compare its SHA-256 against
the released identity before running it.

The released and current presentation policy converts Unlimited plus VSync
to the detected display refresh rate. The uncapped two-target ring is used only
when VSync is off. Therefore the reporter's configuration must not automatically
be blamed on the uncapped ring. Display-rate selection, finite presentation
ownership, draw matching and replay-specific effects remain candidates.

PERF-004 has captured a feedback loop where an old long interpolation interval
blocks a newer scene and its shadow submissions. AUDIO-003 has a separately
verified quadratic no-op draw-matching cost. Both corrections are candidates
for relevance; neither proves this new report fixed.

An older invasion failure involved effects evicting display buffers from an
eight-entry snapshot cache; that cache was removed before v1.2.0. See the
[historical cause and fix](../boot-gameplay-fix.md#invasion-presentation-gaps).
Do not reintroduce that cache or assume the historical cause recurred.

## Investigation and acceptance

First compare the released binary and private candidate using the reported
Unlimited/VSync configuration and retained new-game invasion inputs. Preserve
native timing, game/output rates, audio counters and source saves. Establish
the tribal replay route separately before claiming exact reproduction.
Use instrumented runs for attribution, ordinary muted runs for qualification.

Final cause, remedy, equivalence checks and repeated performance results are
pending. Keep this report open until the reported route and configuration are
covered; do not close it on a build, a related scene pass or component benchmark.

## Transferable lesson

Record frame-rate mode and VSync together: an Unlimited selection can still
use a finite presentation schedule. Similar scenes entered through different
game states need independent coverage.


The first same-PC comparison uses the verified released executable and current
private candidate, both Unlimited/VSync and muted, with the retained new-game
opening route. This is related-scene evidence, not exact tribal-entry coverage.
Results, all half-thousand-VI windows and largest presentation gaps are retained
in `github-issue19/new-game-comparison.json`. No reported fix is inferred from
the harness completing. The owner preview and public issue remain unchanged.


## First same-PC result (2026-10-18 UTC)

The released v1.2.0 new-game invasion reproduces substantial stuttering with
Unlimited/VSync on this RTX 5090 / approximately 240 Hz display. Selected busy
windows average 11.67 and 13.30 scene FPS (179.05/184.27 output FPS), and the
full run reports 11 audio underruns. The current candidate averages 29.81 scene
FPS and approximately 239.3 output FPS in both windows, with zero underruns.
Both logs have zero dropped records and unsupported accesses.

This does not reproduce the exact reported 1-2 FPS severity or prove the tribal
replay state equivalent. The candidate also retains long transitions elsewhere
and is not globally qualified. No public reply/closure or release is authorized
by these results. Continue with the tribal route and preserve both raw captures.

A separate route-discovery replay observes the copied owner route using the
read-only live export, with navigation mods and injected AI inputs disabled.
It stops at the first ready gameplay choice or its bounded VI limit. The
observer is not a performance qualification. Retained evidence:
issue19-dialogue-route-observer, github-issue19/dialogue-route-observer.json.

The first route observer remained in planet selection (state 5, level 127):
the unmodified recorded confirmation arrived before that screen was ready.
This is a failed reproduction fixture, not a clean game-performance result.
The corrected fixture retains the already verified ship-departure prefix and
continues with recorded walking/dialogue input. Its timestamps are reindexed
for poll replay; saves and guest memory remain unedited. Button fields in v8
input files are hexadecimal, while the other fields are decimal. Earlier
first-active summaries included connection/mode metadata and are not a reliable
button-activity timeline; ship-route-inputs.json applies the actual parser rules.

A separate route-discovery replay observes the copied owner route using the
read-only live export, with navigation mods and injected AI inputs disabled.
It stops at the first ready gameplay choice or its bounded VI limit. The
observer is not a performance qualification. Retained evidence:
issue19-ship-dialogue-observer, github-issue19/ship-dialogue-observer.json.

A separate route-discovery replay observes the copied owner route using the
read-only live export; this fixture appends bounded ordinary stick/A inputs
with navigation mods disabled.
It stops at the first ready gameplay choice or its bounded VI limit. The
observer is not a performance qualification. Retained evidence:
issue19-guide-reinteraction, github-issue19/guide-reinteraction.json.


Route correction: the bounded reinteraction fixture only repeats Magnus
at the landing bridge (level 92); it cannot establish the invasion replay.
The walkthrough identifies King Jeff inside the later hut as the NPC who
offers Show me the invasion: https://gamefaqs.gamespot.com/n64/197682-jet-force-gemini/faqs/31145 .
This is navigation guidance, not runtime verification. The retained owner route
already reaches level 47 at poll 6216 and contains another dialogue sequence
at polls 8843-9065. The earlier 16000-VI observer stopped before those inputs.
A corrected bounded observer continues that exact retained route to 22000 VI
or the first ready choice. The failed Magnus fixture and all observations remain.

A separate route-discovery replay observes the copied owner route using the
read-only live export, with navigation mods and injected AI inputs disabled.
It stops at the first ready gameplay choice or its bounded VI limit. The
observer is not a performance qualification. Retained evidence:
issue19-king-jeff-route, github-issue19/king-jeff-route.json.


### Owner route capture prepared (2026-10-18 UTC)

The extended 22000-VI automated route did not reach King Jeff's ready choice;
its completion is not reproduction of issue #19. The owner offered a direct
recording. Automated tests and builds are paused for that session. A separate
SSD launcher uses the frozen mask/hash candidate, a copied owner profile, muted
audio and standard launcher diagnostics. Original saves and desktop beta.1 are
preserved. Recording starts on Play; evidence stays on the data volume.

Private receipt: `village-pacing-20261017/owner-king-jeff-capture-20261018/launch.json`.
The runtime hash is `cebff6e8e385fc01dcd584a901f0ac3fd546fd714065816e3aede42fdd7de22e`.
The standard launcher does not enable private native fast-path flags. This is
an input/state fixture for subsequent matched comparisons, not the configuration
that passed the earlier SSD timing windows or a newly released fix. Exact tribal
entry and owner capture remain pending. No GitHub reply or closure was sent.


The owner completed the SSD King Jeff capture and reported it looked completely
fine. All streams and final RAM are preserved with hashes in completed-evidence.json.
Numerical analysis and exact-entry verification remain pending while the owner
prioritizes critical controls issue #20. This is not closure of the v1.2.0 report.

### Retained owner capture reviewed (2026-10-18)

The completed owner route has no detailed-trace cap, dropped frame records or
audio underruns/overruns. It traverses gameplay rooms 365, 93, 92, 47, 48, 164,
163, 165 and 166, then returns to 48. It does not contain the opening/invasion
cinematic scene IDs 322-326. Therefore it confirms the owner's smooth traversal
report but does not establish reproduction or resolution of the exact King Jeff
replay requested in #19. The older candidate has one three-VI update in room
47 (48.817 ms) and several other intervals above 42 ms; all loading/pause
intervals remain in the report. This is the pre-upload-optimization runtime,
not acceptance of the final combined 1.3 candidate.

Evidence: owner-king-jeff-capture-20261018/timing-review.json, original session
20261018-025118-5779c9bfae764f88bb3926ddaa5c4c82. Its final progress snapshot
ends at VI 12120 while the completed trace extends to 12145 during shutdown;
final play-health is retained independently. Do not silently treat the earlier
snapshot as the full capture endpoint. No new public reply or closure is made.
