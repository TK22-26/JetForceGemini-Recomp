# Modern mouse camera report during Floyd preview3

- Status: correction implemented and delivered in preview4; four component suites and 894 original-collision scene checks pass; owner confirms preview4 camera fix on2026-10-21; unreleased.
- Severity: high camera usability impact; repeated near-body camera collapse while looking around.
- Build/profile: Modern Players and Floyd preview3, runtime `126b960c5fe0298d2f2498abed25b6a153bdef2d7bf9dd396ac16a7629129dd2`, Modern mouse/keyboard.
- Reproduction: owner tested P2 Floyd, also reported a Modern M/K camera issue in the same capture, then closed it. Owner clarifies that looking around abruptly brings the camera immediately behind Juno's back, much closer than the normal following distance.

Private capture `floyd-p2-modern-20261021/owner-sessions/20261021-204830-cb4f9d2ef80c467487806504aa7f0e3e`; closed immutable copy and camera/input analysis under `floyd-bounds-20261021/hud-overlap-review/closed-capture`. The evidence consists of diagnostic logs plus final RAM, not a video. At initial intake, camera transitions, focus resets and mouse ownership were hypotheses; the subsequent distance analysis and implementation below supersede that initial assessment.

Separate clarification: mouse can reach Floyd corners directly; holding the controller stick eventually reaches them. Do not equate mouse feel or delayed controller settling with a failed diagonal fix. Existing P1-only input recording limits exact P2 physical input replay; processed P2 targets are present. Track this separately from the crosshair/HUD drawing-order review.

Earlier investigation entries below retain the evidence available at each stage; the implementation and delivery section records the current state.

## Closed-capture review

The4m49s diagnostic capture switches P1 from Modern controller to Modern mouse at VI8124/about158.15s; the initial profile has controller on P1 and M/K on P2, while final profiles reverse those devices. No `pc-view-reset-cause` events are recorded. Of 129 large same-actor shoulder-camera angle changes, 129 match recorded mouse deltas in the corresponding input window. The earlier large actor-change acquisition is separate. Zero look in a later orbit trace is not proof of no input: shoulder processing already consumed it. These checks narrow uncommanded heading/reset hypotheses but do not verify collision, framing, presentation or all camera behavior. Exact owner-visible symptom and approximate time remain needed. No video accompanies this capture; no camera fix or rejection of the report is claimed. Evidence `hud-overlap-review/camera-input-correlation.json`, `closed-capture-analysis.json`, immutable capture and hashes.

## Clarified symptom: camera moves too close

Owner reports the camera jumps immediately behind Juno's back while looking around, losing the expected following distance. This concerns camera position/distance; the previous matching-angle review does not resolve it. Correlate requested, native collision-resolved and Modern final camera coordinates, retained distance, fallback and scene geometry. Private evidence `hud-overlap-review/camera-close-distance`. No implementation or cause accepted yet.

## Confirmed cause: mixed wall/height contact projects behind the pivot

The capture has7,213 shoulder-camera solves, including3,919 after the switch to M/K. Of those,652 finish below50 world units. The clearest collapse is VI8736 at168.383s: previous camera distance158.105, requested distance200, raw native correction196.276, final Modern distance4. The native result changes both horizontal position and height. Its Y correction raises the endpoint above the focus while the requested ray points slightly downward.

`PcCameraBoom::solve` projects each corrected coordinate onto the requested ray and selects the smallest distance estimate. In this sample the X/Z estimates are approximately196.116, but the Y estimate is-1543.317. The solver clamps that negative estimate to its4-unit search minimum. Since X/Z also changed, `height_only` is false; the first collision-accepted4-unit seed returns immediately without the refinement used for pure height contacts. This amplifies a combined contact into the sudden near-body view. The previous yaw/input correlation was correct but did not address this distance defect.

A private C++ fixture includes the unmodified production `pc_input.hpp` and replays447 recorded mixed-contact cases. For each, it supplies only the actual captured initial native correction and the accepted4-unit query response; it throws if the solver requests any unrecorded response. All447 reproduce the captured4-unit result with one query and no fallback. This establishes the current calculation, not a validated farther safe camera point. The first fixture compilation failed because a quoted `/Fo` directory ended in a backslash; that C1083 log is retained. An explicit object-file output corrected the harness invocation; no product workaround.

Proposed remedy: treat mixed off-ray projections as search estimates and refine a bracket of accepted/rejected distances using the native collision query. Preserve wall inset, finite floor/ceiling clearance, view orientation, outward recovery and bounded work. Do not force the full200-unit distance or smooth through obstacles. The exact scene must qualify farther candidate positions before shipping; captured traces only contain the current solver's queries. Existing pure-wall, shallow-lip, moving-obstacle and swimming cases need regression coverage. No production source/build/package changes, fix acceptance, commit or release yet.

Evidence: `hud-overlap-review/camera-close-distance/distance-analysis.json`, `distance.csv`, `negative-projection-cases.json`, `captured-query-replay/run-v2.log` and `cause.json`. Production helper [pc_input.hpp](../../../include/jfg/runtime/pc_input.hpp); runtime caller [native_boot.cpp](../../../src/boot/native_boot.cpp). Related [camera collision history](camera-collision-bounce.md).

Transferable lesson: passing separate wall and floor tests does not qualify a mixed wall-plus-height correction. A negative projection from an off-ray response is not a valid maximum camera distance, and an accepted search seed is not necessarily the nearest safe boundary.

Owner explicitly approved implementation. Candidate ignores nonpositive off-ray distance estimates, refines accepted/rejected mixed-contact brackets and reapplies/validates wall inset. Original pure-wall behavior and existing swimming path remain. Added mixed wall/floor/ceiling tests across30/60/120Hz plus real-wall contraction. Source/test/native qualification and preview pending; no accepted fix claim.

## Implementation and preview4 validation

The shared Modern shoulder-camera solver now rejects nonpositive distance estimates from off-ray native corrections. Mixed wall/height contacts refine a bracket of accepted/rejected positions; each accepted position is checked by the native collision callback. The wall inset is reapplied and validated after refinement. Immediate inward wall response, elapsed-time outward recovery, the existing finite-height validation and the separately accepted swimming resolver remain in place. Both Modern input presets use this shared solver; Classic is unaffected.

Persistent tests cover mixed floor/wall and ceiling/wall geometry, preserved viewing direction, bounded query counts, immediate response to a new nearer wall and 30/60/120 Hz operation. The existing wall, floor, moving-lip, recovery and swimming tests pass. All four focused suites pass: PC input, Modern controls, Modern roll and navigation mods. The serial Release runtime build passes.

A private fixture executes the original 0x8002CC70 routine and its complete 16-function direct-call closure against the owner's final scene RAM. It uses separate scratch memory above the original 4 MiB scene and no substitute collision responses. For all 447 captured problem inputs, the raw native endpoint matches the recording exactly (zero error). Running both generated timing-span and fallback instruction paths gives 894 matching results. Every corrected endpoint passes the same native collision and finite-height validation used by the runtime, with no solver fallback and at most 12 extra queries. Distances are 76.434..136.902 units instead of 4; VI8736 becomes 136.902 units, retaining the requested viewing ray and obstacle clearance.

This qualifies the captured points against the final scene geometry; it is not a full gameplay replay or a claim about all moving geometry, frame-time cost or physical control feel. Owner live verification remains required. Native fixture sources/RAM stay private. Evidence: `camera-close-distance/implementation/native-scene/qualification.json`, `results.csv`, component/build logs and `delivery.json`.

Preview4 is installed in the existing Modern Players and Floyd Preview. Package inventory, runtime protocol and helper setup checks pass; owner profile/settings/save hashes are unchanged. The prior runtime is backed up privately. Runtime SHA-256 `ede714b70ed68f2bd3051969f68b2259652f8d9c660c1f98c49ffad57865de5b`. Launcher and gameplay were not opened during delivery. No commit, push or release.

Next owner check: look around near the reported walls/corners with Modern M/K and controller, then verify water entry/exit and nearby floor transitions. Broader collision coverage remains open. Transferable lesson: qualify combined contacts with original native queries and distinguish a validated search seed from the nearest safe camera boundary.

## Owner acceptance

Owner confirms the preview4 camera correction is fixed on2026-10-21. This accepts the reported camera-collapse fix; broader scenery/performance coverage remains a documented limit. Owner is now testing Floyd minigames and reports inability to activate the SS Anubis pad after Give Floyd and changing rooms. That separate blocker does not reopen the accepted camera correction.
