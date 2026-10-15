# Issue investigations and resolutions

Keep an issue record from the first reproducible report through its final verified
resolution. This is the persistent engineering history for bugs, regressions and
significant limitations. It complements [known issues](../../known-issues.md), the
[runtime fix log](../boot-gameplay-fix.md), and feature implementation notes; link
those sources rather than copying conflicting accounts.

## Recording policy

- Start or update a record while investigating, not only after success. Use the
  [template](template.md). Give the issue a stable descriptive filename and ID.
- Record symptoms and reproduction, affected version/profile/platform, severity,
  evidence provenance, observed facts, hypotheses, attempts and their results.
- Retain failed or inconclusive attempts when they explain a decision. Correct
  invalid evidence explicitly; do not silently promote a hypothesis to a cause.
- Record the actual final code/behavior change, why it fixes the demonstrated
  cause, regression checks, remaining gaps, and where it is available. A patch,
  successful build, or completed replay alone is not a verified resolution.
- Separate **reported**, **reproduced**, **candidate**, **verified in tests**,
  **awaiting live verification**, and **resolved/released**. State the specific
  scope of a pass. Record a commit/release only once one actually exists.
- Keep public records free of ROMs, generated game code, personal save data and
  identifying machine paths. Reference private artifact IDs and hashes as needed.
- Preserve useful findings from older feature/fix logs through links. Historical
  tests apply to their recorded build, not automatically to the current tree.

This practice applies to future work throughout the repository, including
launcher/UI, controls, runtime, rendering, audio, setup and tooling. Documentation
does not authorize reopening an exhausted investigation or reset guard budgets.

## Active and historical issue index

The historical rows below index existing evidence; they do not claim a new retest.
Detailed per-issue records are added as those issues receive further work.

| ID | Issue | Current recorded status | Investigation / resolution |
|---|---|---|---|
| DISPLAY-001 | Widescreen viewport and pointer alignment | Verified in tests; preview installed, live check pending | [Investigation](widescreen-pointer-and-airborne-aim.md) |
| INPUT-007 | Keep aiming active throughout modern jumps | Verified in tests; preview installed, live check pending | [Investigation](widescreen-pointer-and-airborne-aim.md) |
| LAUNCHER-001 | No launcher update discovery; stale release description | Verified in tests and live API; awaiting release | [Cause, implementation and checks](launcher-update-discovery.md) |
| RENDER-001 | Smooth 60-360+ FPS presentation | Presentation pacing and FPS preset corrections tested; owner visual confirmation pending | [Evidence and plan](high-refresh-rendering.md) |
| RENDER-002 | Juno joint/terrain seams and incorrect dark lighting | Owner reports thigh gaps and delayed lighting absent at 120 FPS in semantic preview; broader coverage remains | [Report and evidence](character-seams-lighting.md) |
| RENDER-003 | Jitter despite steady 120 OUTPUT / 30 SCENES | Bounded holds corrected; finite-clock/shadow-scene queue cause captured; private ownership candidate and live verification pending | [Report and investigation](steady-fps-jitter.md) |
| RENDER-004 | Gems/enemies shake or flash; level culls at camera edge | Owner confirms gems/drones good; pickup particles and combat cadence remain open | [Report and investigation](actor-jitter-edge-culling.md) |
| RENDER-005 | Pickup particles desynchronize from gems | Lifetime/shape correction tested and delivered locally; owner live confirmation pending | [Report and investigation](pickup-particle-desync.md) |
| RENDER-006 | Late tutorial crates, exit light and bridge jitter | Numeric/equal-slot, explicit camera supplementation and bounded zoom corrections pass exact comparisons; full-route/live verification remains open | [Live capture review](tutorial-late-object-jitter.md) |
| RENDER-007 | Ground shadow appears less smooth than Juno | Clipped receiver/mask gap investigated; no qualified shadow fix | [Shadow cadence](shadow-cadence.md) |
| PERF-001 | Goldwood drone-combat update slowdown | CPU/history reductions delivered locally; MI-mask candidate preserves recorded state but is held after a native 360 failure; combat/damage drops remain open | [Evidence and attempts](goldwood-combat-slowdown.md) |
| PERF-002 | Frame diagnostics and reported stutter | Asynchronous tracing and cheaper byte-identical row formatting verified; sparse per-stage CPU/wait profiling added privately; combat drops and Unlimited starvation remain open | [Counter and CSV diagnostics](frame-diagnostics.md) |
| AUTO-001 | Pending request withdrawal aborts a worker | Cached withdrawals survive live recovery; successor resume handling passes isolated corruption/cancellation fixtures | [Cause and recovery](high-refresh-queue-cancellation.md) |
| NATIVE-001 | Access violation during extended native Play replay | Fresh overlay reset fixes captured stale path-cache write; targeted return/native respawn tests pass; local preview installed, live verification pending | [Crash evidence](native-play-access-violation.md) |
| BUILD-001 | Restored source and stale generated renderer disagree | Coherent rebuild qualified in exact-state replay with sane renderer rates; desktop baseline unaffected | [Cause and safeguards](stale-generated-renderer.md) |
| STORAGE-001 | Historical diagnostics fill the working volume | Local recovery; retention policy open | [Cause and verified archive](diagnostic-storage-exhaustion.md) |
| AUDIO-001 | Intermittent background-music crackle | Verified in tests and owner live verification; local preview only | [Investigation](intermittent-music-crackle.md) |
| DIAG-001 | Bounded replay misses final image capture | Verified in hidden replays; unchanged final reference RAM | [Cause and verification](final-probe-frame-capture.md) |
| CAMERA-005 | Modern camera jumps upward over terrain / apparent pond-lip contact | Actual pond regression reproduced and corrected in tests; revised preview installed, owner live check pending | [Report and investigation](camera-collision-bounce.md) |
| CAMERA-003 | Modern area entry faces the exit | Verified in focused tests and owner live play; local preview | [Reproduction and work](modern-controller-state-transitions.md) |
| MOVE-003 | Dual-stick jump loses direction and air steering | Verified in focused tests and owner live play; local preview | [Reproduction and work](modern-controller-state-transitions.md) |
| CAMERA-004 | Focus loss lowers camera angle | Verified in focused tests and owner live play; local preview | [Reproduction and work](modern-controller-state-transitions.md) |
| CAMERA-001 | Small repeated forward camera steps | Verified in isolated replay; delivered preview, live verification pending | [Fixed modern camera boom](../../features/pc-controls.md#2026-10-11-goldwood-capture-camera-stepping-and-native-pause-save) |
| CAMERA-002 | Large scenery-driven camera pull-ins | Open; targeted response correction in CAMERA-005, broader scenery coverage pending | [Capture findings](../../features/pc-controls.md#2026-10-11-goldwood-capture-camera-stepping-and-native-pause-save), [candidate and limits](camera-collision-bounce.md) |
| INPUT-001 | Main-menu clicks eaten; resize cursor remains in client | Corrected and regression-tested; physical focus verification remains | [Win32 activation/cursor cause and fix](../../features/pc-controls.md#live-menu-click-and-cursor-correction-2026-10-10) |
| INPUT-002 | Hover traverses intermediate save slots | Corrected with semantic native selection; tested | [Pointer audit](../../features/pc-controls.md#modern-shoulder-camera-and-mouse-audit-2026-10-10) |
| INPUT-003 | Fire drops mouse aim; aim entry snaps view | Corrected and tested; broader live coverage remains | [Capture ownership and camera handoff](../../features/pc-controls.md#modern-shoulder-camera-and-mouse-audit-2026-10-10) |
| INPUT-004 | Missing pause mouse targets / modern Save | Submenu navigation, contextual Back and sounds verified in tests; live check pending | [Current report and investigation](modern-pause-navigation.md) |
| INPUT-006 | Modern aiming prevents jumping | Native jump-from-aim verified for all characters; live check pending | [Investigation](modern-pause-navigation.md) |
| LAUNCHER-002 | Controller window opens off-center | Owner-centered placement verified in hidden windows; live check pending | [Investigation](modern-pause-navigation.md) |
| MOVE-001 | Upward view moves idle character | Reproduced; corrected and zero-displacement replay verified | [Camera translation cause](../../features/pc-controls.md#upward-camera-running-speed-and-scripted-input-follow-up-2026-10-10) |
| MOVE-002 | Modern movement 23.08% too fast | Native axis scaling/cap restored and tested | [Movement cap cause and fix](../../features/pc-controls.md#upward-camera-running-speed-and-scripted-input-follow-up-2026-10-10) |
| INPUT-005 | Mouse ownership during pickups/cutscenes | Shared lock fix tested; exact shotgun chest awaits live verification | [Input-lock audit](../../features/pc-controls.md#upward-camera-running-speed-and-scripted-input-follow-up-2026-10-10) |
| ANIM-001 | Backward movement uses wrong clip and leans | Native selector inputs corrected and tested | [Animation cause and fix](../../features/pc-controls.md#native-backward-and-directional-locomotion-2026-10-10) |
| ANIM-002 | Stationary turning has no planted-foot pivot | Open research; no confirmed reusable pivot or installed asset | [Feasibility findings](../../features/pc-controls.md#stationary-pivot-feasibility-review-2026-10-11) |

For earlier runtime defects, retain the [existing fix log](../boot-gameplay-fix.md).
Other currently reported limitations remain in [known issues](../../known-issues.md).
