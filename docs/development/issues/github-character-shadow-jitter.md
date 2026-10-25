# GH-046: Character shadows jitter at high frame rates

- Status: reported; source cause and reproduction not yet established.
- Severity: moderate visual smoothness issue.
- Report: [GitHub #46](https://github.com/TK22-26/JetForceGemini-Recomp/issues/46).
- Intake: 2026-10-24.
- Affected report: v1.4.0, Windows10, GTX1080, Xbox controller; high frame rate,
  exact target not specified.

## Symptoms and reproduction

The reporter says character shadows do not follow movement smoothly at high
frame rates, reproducible whenever running. No support ZIP, location, character,
video or subsequent comment was supplied at intake.

## Evidence and next check

This is distinct from the accepted flight-camera, ship-beam and smooth-player
fade corrections. Those tests do not cover the projected ground-shadow path.
A shadow updating only at native scene cadence while the character interpolates
is a hypothesis, not an established cause. Compare the moving player and its
shadow in a fixed room at Original and120FPS, then correlate the shadow draw
identity and transform endpoints before changing interpolation policy.

No patch, runtime test, GitHub reply or closure has been performed for #46.
