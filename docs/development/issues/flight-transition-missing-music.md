# AUDIO-FLIGHT-045: Music absent during some flight transitions

- Severity: moderate audio fidelity regression report.
- Status: closed as original-game behavior. Owner confirms all three reported flight sections match original N64 hardware; GitHub #45 closed by the owner.
- Reported/updated: 2026-10-24 UTC intake.
- Affected: v1.4.0; reporter uses Windows 10, GTX 1080, Xbox controller, 60 FPS.
- Report: [GitHub #45](https://github.com/TK22-26/JetForceGemini-Recomp/issues/45).

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

## Actual resolution and verification limits

Closed as original-game behavior on 2026-10-24 after owner comparison of all three reported routes. No runtime music change was made. The following capture limitations remain applicable to the earlier investigation.
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

## Original-hardware comparison

2026-10-24: the owner explicitly confirmed that the Walkway to SS Anubis
flight also has no music on original N64 hardware. The silence observed in
our build therefore matches the original for this route; no music-insertion
change is warranted. This confirmation supersedes the pending expectation
comparison above. It does not resolve the other two reported Vela flights,
which the owner will check separately. No GitHub reply has been posted.


## Final owner comparison and closure

On 2026-10-24 the owner confirms the remaining reported missing-audio
sections match the original and asks that they be closed. The owner's
[GitHub reply](https://github.com/TK22-26/JetForceGemini-Recomp/issues/45#issuecomment-6389834642)
explicitly confirms all three named routes match native hardware, and #45 was
closed at21:36:29UTC. This supersedes the earlier pending Vela comparisons.

Resolution: expected original-game silence, with no code change. Verification
is the owner's listening/hardware comparison, not an inferred result from track
commands or a new automated audio capture. No duplicate reply was posted.
Persistent accumulated host audio delay (#35) is a different report and remains
open pending affected-machine verification of its unreleased candidate.
