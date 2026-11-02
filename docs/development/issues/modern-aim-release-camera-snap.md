# Modern Aim release snaps the camera

- ID: MODERN-AIM-RELEASE-20261102.
- Reported: 2026-11-02 during owner manual testing.
- Status: source candidate and focused component checks pass; full native build and live verification pending.
- Severity: visible camera transition regression in Modern controls.
- Affected: current local v30 launcher/v28 enhanced native handoff (`5bac0c8`); the observed manual session uses the US runtime. PAL/JP and older releases are not individually reproduced.

## Symptoms and reproduction

With Modern controls, aim down the gun, then release Aim. The owner reports
that the camera instantly snaps back to its old/default position instead of
sweeping gently back into the normal view. The owner identifies this as
Modern-only. Physical input device and exact weapon/location have not yet
been narrowed; do not assume those restrict the report.

Expected: a continuous return from the actual aimed camera pose into the
normal camera, preserving current look, collision and original timing.

## Evidence and hypotheses

The existing automated Modern-action slice covered aim/look and release, but
did not assert the camera trajectory during release. Its prior pass does not
verify this transition. The owner report supplies new visual evidence.

Inspect the shared Modern camera ownership transition in
[guest execution](../../../src/boot/native/guest_execution.cpp),
[controller input](../../../src/boot/native/controller_input.cpp) and
[view state](../../../include/jfg/runtime/pc_input.hpp). A direct handoff from
the native aiming camera to the retained Modern shoulder pose is a hypothesis,
not yet a proven cause. Keep the native collision path and per-region timing
authoritative. The pinned [upstream review](../../upstream/reference-review-2026-10-01.md)
and camera/state history provide context; they do not establish this cause.

## Attempts and validation

Source investigation is running inside the existing four-hour continuation,
with the production guard enabled and the original deadline/counters unchanged.
Automated game runs are muted at the owner's request. Preserve the owner's
manual session and profile; private reproductions use separate save copies.
The source candidate below remains separate from the currently delivered
handoff; no release or live acceptance is claimed.

## Compatibility and lesson

A button/action transition passing does not prove camera continuity. Verify
position, orientation and return duration around Aim release, including
rapid re-aim, moving/obstructed views, controller and mouse, and regional clocks.
Keep [prior Modern state fixes](modern-controller-state-transitions.md) and
[collision recovery](camera-collision-bounce.md) intact.

## Source candidate

The Modern normal-camera adapter unconditionally replaced the original
follow-interpolated camera with the collision-resolved shoulder endpoint.
The source therefore bypassed the return path on Aim release as well as
removing ordinary look latency. The new candidate distinguishes native Aim
ownership from normal view, seeds a return from the actual aimed position,
and decays that inherited position offset in simulation time before the
existing scenery/clearance solver. Look, player movement and collision safety
remain immediate; re-aim and actor/control replacement reset the transition.

This is a candidate, not a verified fix. PC input, Modern controls and Modern
roll component suites pass, including equal-elapsed 50/60-Hz return tests,
rapid re-aim, moving targets and control-lifetime resets. The handoff is unchanged.

## Native build limitation

The first enhanced US native attempt compiled changed C++ consumers but failed
in MSBuild with StackOverflowException under an 8-GiB nested cap. A serialized
retry under 12 GiB, inside the unchanged 16-GiB production cap, failed in the
identity/dependency build with the same exception; measured nested peak was
12,884,967,424 bytes. No linked candidate or native return-trajectory replay
was produced. Logs and original failures are retained in
`aim-release-candidate-us` and `aim-release-candidate-us-serial`. This does not
establish a C++ source error or native correctness. No further memory-limit
escalation was attempted. All full native/live acceptance remains open.

Local source commit: `504aebdcbe843c0c493ca0da3400b340c125996d` on `develop`.
Not pushed or released; native rebuild and live acceptance remain pending.
