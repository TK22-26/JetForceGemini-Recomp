# GH-041: Cutscene skips take too long to complete

- Severity: pacing / responsiveness improvement.
- Status: local candidate; three native routes complete; owner batch review pending.
- Reported (UTC): 2026-10-21.
- Affected build: v1.4.0 release candidate, source `ea9845e`.
- Report: [GitHub #41](https://github.com/TK22-26/JetForceGemini-Recomp/issues/41).
- Related: [native cutscene skipping](optional-cutscene-skipping.md) and
  [owner scene review](cutscene-owner-retest-20261020.md).

## Symptoms and reproduction

During the final candidate pass, the owner requested that some cutscenes finish
skipping faster. The specific slow scenes and per-scene delays have not yet been
measured. Measure from acceptance of the one-second hold to gameplay or the
intended next scene; the confirmation hold itself is a separate interaction.

## Evidence and hypotheses

This is an owner-reported follow-up, not a demonstrated new correctness failure.
The current skip preserves native progression and completion behavior. The cause
of the remaining delay is unproved; scene completion work must be measured before
changing scheduling or bypassing commands.

## Attempts and results

2026-10-21: owner explicitly requested a GitHub issue; #41 created. No skip code
changed and no speed improvement claimed. This request does not itself block
the owner's v1.4 final pass.

## Verification and remaining limits

Identify affected scenes and measure before/after completion times. Include
multi-segment sequences and compare story progression, actors, room transitions
and audio with normal completion. One accepted skip should finish the intended
sequence without a black screen or a second hold for an internal segment.
Verify with normal release launch settings, diagnostics and FPS logging off.

## Lessons

Optimizing skip latency must preserve native completion semantics. A faster
transition with lost progression, incomplete audio cleanup or an invalid next
room is not an acceptable optimization.

## October 27 measured transition delay

A bounded normal Play run entered 97/0 through the diagnostic selector and held A. Native completion occurred at 60.724399 seconds, followed by 101/0 completion at 61.444288 and 102/0 completion at 61.860844, then gameplay room35. The same capture also completed 135/0 to158 and 93/0 to92. Each internal scene's completion handler ran once; there was no extra confirmation hold. Times are trace elapsed time, not a production performance benchmark.

Source review found mainChangeLevel writes a 10- or 30-tick presentation delay to 800A3294, and the native level-transition routine subtracts normal update ticks before checking its video-readiness gate and running cleanup/loading. The existing skip already covers transitions with a black native overlay. A candidate can shorten only that presentation wait after a qualified explicit completion, retaining the ordinary readiness gate, loader, script side effects and first update in each internal scene. This is a hypothesis under validation, not yet a verified speed fix.

Private evidence: remaining-gh-issues-20261027/cutscene-timing-030 and native mainChangeLevel/transition source observations. Native scene state and saves remain private. No GitHub action.

### Candidate scope

After an accepted, qualified explicit completion schedules its known destination, the candidate shortens a newly installed 10/30-tick outgoing fade countdown to one tick. It validates the pending level/group, absence of cue/confirmation waits, and the exact native countdown/readiness instructions. Credits, ordinary room transitions, unqualified scenes and unrelated waits are unchanged. The native transition routine still waits for video readiness and runs cleanup, loading and destination fade-in; it is not called early or bypassed. Native source at 80047480 explicitly replaces the outgoing fade with the destination fade after loading. Paired route timing and state comparisons remain pending.

## October 27 validation update

Three normal-Play routes completed with the same explicit completion sequence and destination as the baseline: 97→101→102→35, 135→158, and 93→92. The interval from first to third completion in the flight chain was 1.136445 seconds before and 0.551965 seconds after. This excludes the player's hold time and does not claim loading takes zero time. Native readiness/loading checks remain. Both paired runs exited cleanly. Private evidence: cutscene-timing-030 and cutscene-timing-040. Final owner batch review remains pending.
