# Modern Aim release snaps the camera

- ID: MODERN-AIM-RELEASE-20261102.
- Reported: 2026-11-02 during owner manual testing.
- Status: owner confirms smooth scope-out and natural scope-in on PAL/controller; USA/JP manual testing pending; US/PAL/JP native regressions pass; local v33, unreleased.
- Severity: visible camera transition regression in Modern controls.
- Affected: initial US v30/v28 owner report and confirmed v31 PAL controller retest. The v31 return candidate never armed on the native ground-Aim path. A separate JP owner reproduction is not claimed.

## Symptoms and reproduction

With Modern controls, aim down the gun, then release Aim. The owner reports
that the camera instantly snaps back to its old/default position instead of
sweeping gently back into the normal view. The owner identifies this as
Modern-only. Physical input device and exact weapon/location have not yet
been narrowed; do not assume those restrict the report.

Expected: a continuous return from the actual aimed camera pose into the
normal camera, preserving current look, collision and original timing.

## Actual cause and remedy

The Modern normal-camera override replaced the native follow easing with its
direct shoulder endpoint. The v31 candidate added a return transition but
observed Aim ownership inside the normal-camera adapter. Native ground Aim
uses a separate camera path, so that observer never ran and the added return
stayed inactive. Two actual PAL releases reproduce the entire approximately
144.4-unit jump in a single emitted view update.

The correction observes ground-Aim ownership at the existing native Aim-camera
completion hook, after the actual aimed pose is published. Releasing Aim now
activates the retained return before the existing scenery/clearance solver.
Air Aim retains the normal-camera path and does not repeatedly arm a ground
return. Re-aiming cancels the old return; actor/control replacement still clears
its lifetime. This is shared implementation for all three qualified revisions,
without a regional or weapon-specific workaround.

The native trace regression rejects the old PAL executable and passes two
stationary controller releases per region in the new builds. PAL mouse-input
semantics and rapid re-aim also pass. These are automated native checks;
the owner subsequently rejected v32's initial release jump and jagged path; see the boundary investigation below.

## Evidence and hypotheses (initial investigation)

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

The initial source investigation ran inside the existing four-hour continuation,
with the production guard enabled and the original deadline/counters unchanged.
Automated game runs are muted at the owner's request. Preserve the owner's
manual session and profile; private reproductions use separate save copies.
At that checkpoint the source candidate below remained separate from the delivered
handoff. Later builds and owner rejection are recorded below; no release is claimed.

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

The source correction is now compiled and linked in all three verified regional
runtimes in local `owner-review-v31`. Its keyboard replays establish normal Play
only; they do not verify this camera/locomotion behavior. Owner verification
remains pending. The earlier build failure is retained as historical evidence;
see [compiler-memory cause](build-blur-audit-compiler-memory.md).

## Owner rejects v31 candidate, 2026-11-03

After the v31 four-item test handoff, the owner reports: "Modern Aim release -
still bad (instant) the rest is fixed". The camera candidate therefore does not
resolve the observed snap. The owner did not specify the region, device, weapon
or location in this follow-up; do not turn it into three separately verified
regional failures. The original report was Modern-only.

The passing return-helper components and linked regional builds did not verify
the final camera consumed by the native view. The source bypass identified
above is insufficient to explain or repair the live symptom; the remaining
cause is unknown. No new remedy or release is claimed.

The production guard remained enabled and stopped new investigation at its
128-attempt limit. The owner then explicitly approved two additional hours.
The new job retains the same high-refresh investigation, ancestry and all
counters, with one additional bounded attempt and a fixed deadline. Evidence:
private aim-release-20261104-owner2h. Automated sessions remain muted and
use copied saves/settings. Next: qualify actual native Aim ownership, release
ordering and the final displayed camera before choosing another correction.

The owner identifies the failed retest as **PAL with a controller**. The other
three accepted items were in that testing context; US/JP appearance remains a
separate coverage claim. The private reproduction uses the qualified menu/save
entry and isolated repeated ground Aim holds/releases with controller look.

The first new automated route copied controller.ini without its required
modern-controls.ini sibling. It remained in Magnus dialogue with zero Modern
camera events, so the qualification rejected it before any candidate edit.
This is a private reproduction setup failure, not evidence about the camera.
Both files are now copied from the qualified private settings; the first run
and failed assertion remain preserved.

The second reproduction confirms Modern camera ownership but its forward-walk
prefix triggers nearby Magnus dialogue before Aim. It has 146 normal-camera
samples and zero Aim samples, so it also fails qualification before any source
change. The next route keeps Juno stationary and preserves both setup failures.

### Native-path failure reproduced

The fresh v31 PAL controller replay enters ground Aim twice and returns to normal
movement. It emits Aim and normal shoulder-camera observations, but no
pc-aim-return-start or pc-aim-return events. The transition helper was never
armed: ownership observation lived inside the normal follow-camera adapter,
which the native ground-Aim branch bypasses.

The new candidate observes ground-Aim ownership after the existing native camera
movement dispatcher has published its pose. Air Aim retains the normal-camera
path and does not arm a ground return. The normal release adapter and collision
solver still own the return itself. Candidate rebuild/native trajectory review
remain pending; the failed v31 evidence is preserved in baseline-v3-qualification.json.

### Rendered-camera regression qualification

The corrected PAL runtime passes two stationary controller releases. The old
v31 runtime moves the entire approximately 144.4-unit distance in one source
update, with no return-start event. The candidate moves about 17% on the first
update, then decreases the remaining distance continuously across subsequent
updates. The final normal-camera position agrees with the inverse of the actual
emitted view matrix within 0.001 unit. This tests the rendered camera, not only
the helper or an intended intermediate position. Owner visual acceptance of
this new candidate remains pending.

The retained [native trace regression](../../../tests/evidence/aim_release_trace.py)
requires completed native Play, repeated ground-Aim releases, stationary body
and view direction, finite orthonormal emitted views, a meaningful displacement,
a multi-update monotonic return, settling and actual ownership-start events.
Its [consumer tests](../../../tests/evidence/test_aim_release_trace.py) reject
instant/delayed snaps, missing ownership, short/moving fixtures, invalid views
and malformed observations. The real pre-fix trace fails both releases; the
rebuilt trace passes both. Camera emission can cross a VI boundary after the
player update, so matching uses ordered producer calls and their emitted update
identity, not equality of VI timestamps. The first timestamp-only checker
failed informatively and its log remains preserved.

Evidence: baseline-pal-v3, candidate-pal-replay, their final-regression.json
receipts and trace-checker-tests-v3.log under the current private root.
These stationary replay checks do not qualify every collision, physical input
device, multiplayer camera or campaign location.

### Final native qualification and v32 handoff, 2026-11-04 UTC

US/PAL/JP builds contain the same corrected source closure. Each regional native
controller replay exits normally and passes two emitted-camera release checks.
PAL's separate mouse-input replay passes two settled returns plus four complete
Aim/release cycles. A re-aim six VIs after release cancels the old transition;
all four later return origins exactly match the newest actual aimed position.
Physical mouse delivery, every weapon/location and visual acceptance remain
separate from replay semantics.

The nine trace-consumer regressions and the PC input, Modern controls and Modern
roll component suites pass. The public checker is run as:

    python -m tests.evidence.aim_release_trace --trace gameplay.tsv --run-result result.json --output return-check.json

Use its documented stationary fixture and explicit native camera diagnostics;
a boot log or a trace without the complete release/settling route cannot pass.
The first private quick-reaim analyzer rejected a TSV header as a number;
filtering the selected numeric events corrected only that analysis helper.
Its failure remains in mouse-quick-qualification.log, with the qualified retry
in mouse-quick-qualification-v2.json.

Local owner-review-v32 retains one unchanged launcher UI with the new three
regional runtimes and copies of the current v31 manual profiles. The original
manual profiles and their audio preferences are preserved. It is not a release.
Detailed receipts: candidate-pal-replay-final-regression.json,
candidate-us-rendered-return.json, candidate-jpn-rendered-return.json,
regional-replays.result.json and mouse-quick-qualification-v2.json.

Compatibility lesson: observe a camera owner on the path that actually produces
that camera, and qualify the emitted view after the complete native update.
A passing interpolation helper cannot prove that its runtime transition starts.

The completed v32 package also passes actual launcher init/setup/direct Play
and normal close for every matching runtime in isolated muted profiles.
The handoff saves remain unchanged. Evidence: launcher-smoke-v32.result.json.
Owner visual confirmation of the new Aim return remains pending.

Local replacement implementation and native regression commit: `a363722823b23f1e47a09371143f3cd670e14083` on develop. Not pushed or released.

## Owner rejects v32 scope-out continuity, 2026-11-04 UTC

On PAL with a controller, the owner reports an instant jump to an intermediate
distance followed by smoothing. Scope-in feels smooth and natural; scope-out
remains jagged and awkward. v32 is an incomplete fix despite passing the earlier
stationary trajectory checks. The initial release boundary and perceived zoom
continuity need stronger qualification; the remaining cause is not established.
Preserve the accepted scope-in behavior. The owner offered a short logged
zoom-in/out capture if needed and approved one further guarded hour.

The same production investigation retains its root and prior charges, with one
additional authorized attempt. Guarded evidence: private
aim-boundary-20261104-owner1h. Automated sessions remain privately muted.

### Recorded initial jump and recovery interference

The owner supplied a second, verified PAL/controller recording with nine Aim
releases at several pitch angles. Level and upward releases reproduce a roughly
24-unit first movement followed by near-stalling and vertical deviation. The
projection changes gradually through those boundaries. The earlier stationary
v32 native trace also has a 17% first step and about 7% deviation from its direct
unobstructed return path. The previous checker accepted both because it required
only a multi-update monotonic approach to the endpoint.

Two mechanisms contribute: a simple exponential offset decay starts at its
highest velocity, and camera-boom recovery treats an authored radius contraction
as if an obstacle forced it inward. The latter arms an unnecessary hold and
filters the radius again on subsequent clear updates, bending the camera path.

The replacement uses a critically damped return with zero initial velocity,
and carries obstacle shortening independently of changes in the requested
radius. Existing wall/floor queries and validation remain authoritative. The
native Aim-entry camera and its zoom are unchanged. Strengthened component
regressions fail the old first-step behavior and pass the new behavior; existing
obstruction, water, timing, Modern controls and roll cases also pass.

The native trace consumer now bounds the initial step, total step, deviation
from an unobstructed path and projection changes. Twelve consumer tests pass,
including a large first hop with a smooth tail and a bent path. It correctly
rejects both formerly passing v32 stationary returns. Native rebuilt validation
is still pending; this is not yet a visually accepted fix.

Capture setup evidence is retained: the first launch inherited diagnostic flags
that ordinary launcher Play intentionally sanitizes, so it produced no detailed
trace. The corrected direct native session uses copied owner preferences and
verified recording, with a normal window close. An initial membership checker
also referenced the previous worker receipt; direct verification confirmed the
new launch remained inside the current production job. These setup failures do
not count as game verification. Private evidence: owner-pal-capture-v2,
v32-strengthened-regression.json and boundary-components.json.

The first rebuilt candidate passes the clear stationary PAL route (first step
3.2%, essentially zero off-path deviation) and improves four exact-body/angle
owner-recorded comparisons. It is nevertheless rejected: later downward-looking
releases in the same owner replay have 44-52-unit initial jumps. Slight analog
integration differences in the replay do not justify accepting these regressions.
Collision-recovery state retained across the native Aim ownership interval is
being investigated. The failing candidate and all traces remain preserved.

### Collision ownership correction

The rejected downward candidate's first requested return point is unchanged by
the native scenery solver, but the retained boom then shortens it to the focus
or roughly ten units from it. That directly explains the remaining jump: the
previous normal view's obstacle shortening survived the interval in which the
native Aim camera owned position and collision.

Ground-Aim observation now retires normal-camera obstruction history while
arming its position return. The next normal view evaluates collision from the
actual aimed pose afresh. Radius adjustment also retains the solver's minimum
four-unit distance. A component regression seeds a shortened/held boom, enters
native Aim ownership, releases and checks that the clear return keeps its
requested position. All three input/Modern/roll suites pass with this correction.
New native qualification is in progress in the candidate-v2 runtimes.

The comparison helper initially required identical world positions and angles
between recorded/replayed runs. Native input grouping can slightly alter later
analog integration, so exact-body/angle pairs are qualified separately. The
later mismatches remain visible observations; they were not used to excuse the
downward regression. A private comparison-script syntax failure was also fixed
without changing runtime evidence. All failed checks remain in the private log.

### Owner PAL acceptance of the final candidate

The owner reports "Both feel smooth" for the corrected PAL/controller build,
then explicitly approves it as fixed. Scope-out and scope-in feel correct in
that test. The owner clarifies that USA and JP still need manual testing; do
not extend PAL visual acceptance to those versions. The exact tested runtime
identity is retained in private owner-feedback.json. Final regional automated
checks and local packaging are still completing; no release is claimed.

The final mouse replay exposed a checker assumption: a legitimate three-tick
update moved 15.2% of the return, slightly above the original per-update 15%
limit. The production camera was unchanged. The checker now uses the recorded
native simulation interval to bound travel rate, while retaining the stricter
initial-step, clear-path and projection checks. Fourteen consumer tests pass,
including variable intervals and missing timing rejection. The old v32 trace
still fails, and the same completed final mouse trace passes. The initial
fixed-step checker failure remains preserved.

### Final local v33 qualification, 2026-11-04 UTC

The final boom policy carries recovery only while a prior obstruction still
shortens the requested view. A clear camera follows its authored radius changes
directly. A newly requested point inside the prior safe radius is accepted
immediately; only actual obstruction contractions arm the recovery hold. This
replaces the intermediate candidate's fixed shortening-offset approach, which
could retain unnecessary shortening after a requested clear contraction. A
separate regression fails that intermediate implementation and passes the final
policy. Ground-Aim ownership also retires the prior boom history, and the return
starts with zero velocity rather than a large exponential first step.

All three rebuilt regional runtimes pass two completed native stationary
rendered-camera releases with the strengthened boundary, straight-path and
projection checks. The final PAL replay covers all nine releases in the owner's
recording, including downward views: every first movement is under eight world
units. The final replay independently qualifies all nine clear release boundaries. It
starts one movement update away from the recording; matching directions and
world-position differences are reported without claiming identical game states.
The separate PAL mouse-semantics/quick-reaim replay passes, as do the fourteen trace
consumer tests and the PC-input, Modern-controls and Modern-roll suites.

Scope-in's native position/zoom implementation is unchanged. The capture/replay
comparison has normal update-grouping variation, so it does not establish
byte-identical scope-in motion. Owner feel feedback is recorded separately below.
Original wall/floor validation and immediate collision contraction remain in
place; these fixtures do not establish every weapon, location or multiplayer view.

The v33 package contains the final three runtimes and the existing launcher UI.
Actual packaged launcher setup, direct Play and normal close pass for all three
revisions using isolated muted profiles. Current v32 manual settings/saves were
copied and their originals preserved; manual audio preferences are retained.
No push or release occurred.

Private evidence: candidate-v3-build.result.json, v3-final-qualification.json,
v3-owner-route-comparison.json, v3-mouse-qualification.json,
shorter-radius-regression.json, final-components.json and handoff-v33.result.json
under aim-closeout-20261104-owner20m, with inherited-evidence.json identifying
original receipts from aim-boundary-20261104-owner1h. The earlier guarded worker
ended with Windows quota status 0xC0000044 before USA/JP final qualification and
packaging; the exact quota cause was not established. The owner approved a
20-minute guarded continuation under the same investigation. USA/JP traces and
launcher checks completed in that continuation; earlier interrupted evidence and
rejected candidates are retained in their original directories.

Transferable lesson: distinguish authored camera motion from obstacle recovery,
retire recovery state when its camera owner changes, and qualify the first
rendered release steps as well as the later smooth tail. A monotonic distance
to the endpoint alone can conceal a lurch and an off-path dip.

Final owner feedback: Owner approves PAL/controller as fixed: scope-out is smooth at the requested test angles and scope-in remains natural. USA and JP manual verification is explicitly pending.

Final v33 implementation and regression commit: `571acde2ea9ba1ddd9ef3558aa8095151fc9a9f3` on develop.
PAL/controller is owner-approved. USA/JP manual checks remain pending.
Not pushed or released.
