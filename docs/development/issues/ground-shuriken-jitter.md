# RENDER-009: Ground shurikens sometimes jitter

Status: missing interpolation ownership reproduced; correction verified in trace tests, owner visual confirmation pending. Severity: visible gameplay/control regression. Affected: unified-keys high-refresh preview, source 19a2373, runtime SHA-256 93514316aada84480c437c3f6eb08dfe192b22a43fa29f678242d4143bf133d7.

## Symptoms and reproduction

The owner reports occasional jitter on shurikens lying on the ground in the latest capture. Other enemies/items now appear good by the owner report. Exact onset/object state is unknown.

Private evidence: shuriken-followup-20261016/owner-capture, copied and SHA-256 verified from owner session 20261016-192948-9c8c9b5ded9b427682d6affeda20b3bc. Raw timing and initial profile are retained; no owner settings are changed for investigation.

## Hypotheses and acceptance

Check actor/projectile identity and draw grouping, object rest/rotation state, vertex interpolation, and camera correspondence. No cause or fix is established.

Record candidate changes, informative failures, exact checks and remaining live acceptance here. Preserve game timing, saves and other preferences. See [shuriken reticle recurrence](shuriken-reticle-flicker.md).


Source lead and candidate: US module 122 ShirukenPushMtx (0x07A00F38) bypasses camPushModelMtx and calls camPushFloatModelMtx with a custom rolling/attached matrix. Our ordinary rigid observer never sees this actor. The owner capture has 7,805 shuriken actor observations and zero corresponding rigid-owned records. Candidate observes the complete custom matrix function with the same output/actor ABI, validates the 64-byte output advance, then uses the existing actor lifetime, byte validation and world/view/projection product checks. It does not change projectile physics or game memory. Runtime interpolation coverage and visuals remain to be checked.


## Runtime coverage

The replay now has 12,612 shuriken rigid-owned observations, of which 12,268 match a preceding pose. The baseline owner capture and first replay had zero. The remaining observations are not forced to match: lifetime, visibility gaps, discontinuities and operand validation retain the existing rejection rules. A separate unchanged-position analysis checks projectiles stationary for at least 30 VI. Private evidence: shuriken-followup-20261016/line-ground-analysis.json and stationary-shuriken-coverage.json. These records establish that resting projectiles enter interpolation, not that every camera/ground pose is visually accepted.

The correction changes presentation identity only. The original custom rolling/attached matrix, physics and lifetimes stay native. Existing semantic ownership and renderer tests pass. Lesson: generic actor draw hooks do not cover custom projectile matrix builders; register their completed output with the same lifetime and exact-byte validation instead of guessing batch identities.


The shared followup runtime and bounded checks are pinned in [qualification](../../../evidence/high-refresh-shuriken-followup.json). Owner live confirmation remains pending.
