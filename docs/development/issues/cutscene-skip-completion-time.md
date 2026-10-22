# GH-041: Cutscene skips take too long to complete

- Severity: pacing / responsiveness improvement.
- Status: reported; optimization follow-up, no new fix implemented.
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
