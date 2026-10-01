# Jet Force Gemini Recompilation Executable Scope Assessment

Assessment snapshot: 2026-08-03

## Purpose and status

This document turns `docs/planning/JFG_RECOMP_MASTER_PLAN.md` into an executable program with explicit dependencies, gates, stop conditions, staffing assumptions, and first-quarter work. It is a scope assessment, not evidence that any master-plan phase or milestone has completed.

The recommended delivery strategy is compatibility-first:

1. Prove that the architecture can represent the game.
2. Reach a deterministic native boot and first correct frame.
3. Deliver an interactive, saveable vertical slice.
4. Reach credits and complete release-scoped compatibility coverage.
5. Add ultrawide and high-frame-rate presentation.
6. Commit to a public mod ABI only after subsystem interfaces stabilize.

## Verified technical baseline

The following findings began as discovery inputs. Phase-gate status is tracked
in `docs/dashboard.md`; the Phase 1 build evidence is now recorded separately
in `docs/upstream/phase1-build-evidence.json`.

| Component | Inspected pin | Verified implication |
|---|---|---|
| Jet Force Gemini decomp | `b49aa4791e8fb1e7acd3bba10346876358d0a9a7` | The current report contains 2,931 functions, 594 marked matched by function count, and 7.62% matched code bytes. There are 155 nonempty overlay text modules. The build defines `F3DDKR_GBI`. The repository has no root license file, so public reuse of its source, headers, or metadata requires an explicit permission or license path. |
| N64Recomp | `ffb39cdad1da5de07eaaa48bd1db4a89a7986771` | CPU static and relocatable overlay machinery exists. The inspected RSP recompiler also contains overlay-slot support, despite stale README text saying RSP overlays are unsupported. This capability has not been proven against JFG. |
| RT64 | `5473732a822a4423b5696e7cb18fecc425a59875` | No public `F3DDKR` or DKR-specific HLE path was found. JFG graphics compatibility is therefore a critical feasibility experiment. RT64 describes widescreen/HFR as limited game support; neither should be estimated as routine polish. |
| N64ModernRuntime | `589bbf018a3e6d3646ddf7de1e7919f1b7e99bb1` | The runtime is GPL-3.0 and provides major libultra-facing services. Its inspected Controller Pak `osPfs*` bridges return `PFS_ERR_NOPACK`, while JFG has real Controller Pak paths. Save/accessory support is a required implementation spike. |
| RecompFrontend | `9ef9cdfdead7649247ab4957f43517f44c33931d` | The repository has no root license file at the inspected pin. Do not assume it is distributable until permission or a license is confirmed. |

The low matched-code percentage does not prevent static recompilation, but it increases metadata, symbol-boundary, reverse-engineering, and diagnostic risk. Function-count progress must not be used as the product schedule metric.

## Critical path and go/no-go gates

Later work may be explored in parallel, but it may not be declared complete ahead of these gates.

### G0 — Authority and private-data boundary

Status for Phase 0–2 work: complete under the conservative
metadata-only/local-generation boundary recorded in
`docs/governance/phase0-decisions.md`. The upstream request is deferred and
unsent, the current license remains all-rights-reserved, and `TK22-26` owns
private corpus storage decisions.

Required evidence:

- A lawfully obtained supported US ROM is verified locally against the documented hash.
- The ROM, extracted assets, ROM-derived corpus bodies, screenshots, memory captures, and traces are excluded from Git and public CI artifacts.
- The dependency architecture and GPL-3.0 implications are accepted or replaced with a funded alternative.
- Upstream reuse is either expressly permitted or the project adopts a metadata-only/local-generation boundary that avoids copying unlicensed material.
- It is understood that decomp-maintainer permission covers only material those maintainers can license; it does not grant rights to original game code or assets.
- A private corpus storage and backup policy has a named human owner.

Stop condition: do not publish copied decomp or RecompFrontend material without a permission/license basis. Private feasibility work may continue only inside the conservative data boundary.

### G1 — Reproducible behavior oracle

Status: the master-plan Phase 1 two-environment build gate is complete. The
additional emulator/hardware capture and RSP-program denominator requirements
below remain later feasibility work and are not claimed complete.

Required evidence:

- The pinned upstream target builds in two clean Linux or WSL environments.
- Both builds produce the expected ROM hash and equivalent normalized ELF sections, symbols, and relocations.
- Denominator counts are recorded for executable sections, functions, overlays, relocation records, and RSP programs.
- An approved emulator or hardware capture path can produce timestamped boot, overlay, RSP-task, input, audio, and save traces.

Stop condition: do not configure the full recompilation from an unstable or unexplained ELF.

### G2 — Architecture feasibility

Required executable proofs:

- All executable CPU sections are attempted through N64Recomp and every failure is classified.
- The most complex CPU overlay tested so far loads, relocates, resolves indirect calls, unloads, and reloads correctly.
- Every discovered RSP program and overlay slot is classified.
- At least one real graphics task and one real audio task execute through their proposed native paths.
- The graphics proof includes `F3DDKR_GBI` behavior and demonstrates either a viable RT64 path or a bounded fallback.
- One real Controller Pak/save operation round-trips through the proposed implementation.
- Dynamic-code, runlink, direct-register, TLB/cache, and anti-tamper/trap paths have traces and owned mitigation decisions.

Go only when every critical mechanism has a working prototype or tested fallback with an owner and estimate. A blocker report, open upstream issue, or uncommitted upstream work plan is not a fallback.

### G3 — M1 complete native CPU link

Required evidence:

- Every expected executable CPU symbol is generated or has an approved, evidence-backed exclusion.
- Direct calls resolve and all observed indirect-call ranges are represented.
- CPU overlay tables are complete against the G1 denominator.
- The baseline generated library links with the minimal runtime on the first target toolchain.
- The unresolved-call and stub ledgers contain zero unexplained entries on the boot path.

Cross-platform compiler coverage is desirable but must not delay the first-target boot gate.

### G4 — M2 deterministic boot

Required evidence:

- Original entry reaches repeated scheduler/VI checkpoints.
- Fifty deterministic-mode boot runs produce identical approved event and state checkpoints.
- Boot has no unhandled runtime call, unbounded loop, unexplained overlay failure, or silent stub.
- The native boot trace agrees with the approved oracle at defined checkpoints.

Determinism applies to the explicit test profile; normal host thread timing need not be bit-identical.

### G5 — M3 first correct frame and interactive substrate

Required evidence:

- Title and one deliberately difficult gameplay scene render repeatedly through the selected graphics path.
- Ten consecutive reference-runner captures have stable command checkpoints and approved output.
- Disabling the renderer does not change simulation hashes.
- Input, audio, save/accessory, filesystem, and restart work each have an owned integration lane.

### G6 — M4 complete vertical slice

The slice must be selected from a subsystem and overlay coverage matrix, not only for narrative convenience. It must cover control, combat, collision, camera, animation, graphics, audio, cutscene, overlay transition, save, exit, relaunch, and resume.

Required evidence:

- One hundred automated deterministic completions have identical approved checkpoints and no crash.
- Death/retry, pause, controller loss, mid-slice save/restart, and overlay reload pass.
- There are no unhandled runtime calls in the slice.
- Graphics and audio references pass at designated checkpoints.

### G7 — M5 finishable compatibility route

Required evidence:

- Every required route segment is independently replayable and passing.
- At least three clean new-game end-to-end runs reach credits.
- Boss retry, save/reload around major transitions, required progression, final sequence, credits, and post-game state pass.
- The blocker count for the compatibility route is zero.

### G8 — M6 complete compatibility

Required evidence:

- Every release-scoped campaign, optional-content, multiplayer, menu, controller-count, save, and recovery scenario has an owner and passing result.
- JFG's original in-game widescreen setting is explicitly implemented and verified in both states against the original game, including its menu selection, gameplay presentation, and persistence across save/reload. This is a compatibility requirement, not a substitute for (or something to defer until) the separate PC ultrawide enhancement.
- All release-scoped CPU overlays and branches are exercised.
- An eight-hour soak and the defined fuzz/stress suites pass.
- There are no release-blocking parity defects and no flaky required test.

### G9 — M7/M8 enhanced release

Ultrawide and HFR may branch from a stable M6 baseline. They must preserve compatibility-mode simulation checkpoints. Release requires a fixed platform/feature matrix, license audit, SBOM, clean-machine package tests, rollback artifact, support plan, and a numerical soak/defect policy. A recommended minimum is zero open severity-1 or severity-2 defects, zero required-test flakes, 50 automated route-hours, 20 human play-hours, and a two-week release-candidate freeze.

## Required sequencing changes

- Choose the runtime/dependency architecture before choosing the project license. N64ModernRuntime's GPL-3.0 license constrains the result.
- Move emulator trace and function-capture tooling into G1/G2. The deterministic harness cannot create meaningful differential corpora without an oracle.
- Split the deterministic kernel into v0 before boot—cloneable memory/context, virtual time, journal, replay format, and seeded divergence—and v1 during boot/slice—scheduler model, captured calls, minimization, and subsystem hashes.
- Replace the pre-boot requirement for 100 arbitrary functions with 20–30 risk-weighted boundary functions. Reach at least 100 captured functions by M4.
- Feed a captured JFG graphics task to RT64 during G2. Full renderer integration remains M3 work.
- Test the most difficult known CPU/RSP overlay and microcode task, not merely a representative easy case.
- Start the content and route manifest by Day 45 so late-game overlays, progression flags, and accessory behavior can affect feasibility work.
- Treat input/UI, audio, save/accessories, filesystem/configuration, and process restart as parallel M3-to-M4 lanes.
- Decouple readable-source replacement from mod-ABI work. Proven hotspot replacements may start earlier; a public mod ABI should wait until M6 interfaces are stable.
- Correct milestone ownership: first frame is M3, the Phase 8 subsystems are the interactive substrate, and the complete campaign slice is M4.

## First 30/60/90 days

This baseline assumes three to four experienced full-time contributors. With fewer people, reduce milestone ambition rather than weakening the gates.

### Days 1–30 — authority, oracle, and inventories

Week 1:

- Decide the conservative ROM/corpus boundary, first platform, dependency architecture, and public/private policy.
- Send the upstream permission request and create a dependency/license matrix.
- Pin the decomp, recompilers, runtime, renderer, frontend candidate, compiler, CMake, and Ninja.

Week 2:

- Reproduce two clean upstream builds.
- Create normalized ROM/ELF reports.
- Establish emulator trace capture.
- Record complete CPU, overlay, relocation, RSP, save/accessory, and direct-hardware denominators.

Week 3:

- Build a no-ROM host shell and public CI lane.
- Attempt the initial full N64Recomp configuration.
- Select the worst known CPU overlay, RSP overlay/task, graphics scene, and save/accessory path.

Week 4:

- Prototype CPU overlay relocation and indirect lookup.
- Capture graphics and audio RSP tasks.
- Classify direct-hardware, runlink, dynamic-code, trap, and anti-tamper paths.

Day-30 gate: G0 and G1 evidence exists, and each critical G2 unknown has an owner, experiment, deadline, and fallback candidate. This is not Phase 3 completion.

### Days 31–60 — prove the architecture

- Complete the all-sections CPU generation attempt and link ledger.
- Implement deterministic-kernel v0 and 20–30 boundary-function cases.
- Execute the selected CPU overlay relocation/reload and indirect-call proof.
- Execute one real graphics and one real audio task through the proposed paths.
- Prove `F3DDKR_GBI` handling or a bounded fallback.
- Round-trip one real save/accessory operation.
- Prove the trap/anti-tamper strategy.
- Build the first route/content manifest from tables and traces.

Day-60 gate: G2 must pass before broad port implementation. G3 may also pass, but is not assumed.

### Days 61–90 — native boot and first-frame attempt

Conditional on G2:

- Integrate the selected runtime and run original entry.
- Bring up queues, threads, PI DMA, decompression, initial overlay loading, RSP submission, and repeated VI activity.
- Add boot checkpoints and compare against the approved oracle.
- Integrate the RT64 host path and attempt title plus a difficult gameplay frame.
- Run the deterministic boot repeat lane and secured local ROM-backed nightly lane.
- Maintain the route-health and blocker dashboards.

Day-90 outcome:

- Success is G4 plus the M3 first-frame proof; or
- an evidence-backed no-go/rearchitecture decision is recorded.

A blocker report without a working fallback pauses feature work. For one full-time developer, the realistic Day-90 target is G2/G3 and first runtime events. For serious part-time work, it is G1 plus substantial G2 evidence.

## Calendar planning ranges

These are cumulative elapsed ranges after G0 inputs are available. They assume experienced C++/CMake contributors and no unbounded RSP-overlay or custom-microcode problem.

| Milestone | Solo, about 15 hr/week | Solo full-time | Two experienced FTE | Four experienced FTE |
|---|---:|---:|---:|---:|
| G2 feasibility | 2–5 months | 1–3 months | 1–2 months | 1–2 months |
| M2 stable VI | 6–12 months | 3–7 months | 2–5 months | 2–4 months |
| M3 first correct frame | 9–18 months | 5–10 months | 4–8 months | 3–6 months |
| M4 vertical slice | 15–30 months | 8–15 months | 6–12 months | 4–9 months |
| M5 reaches credits | 30–54 months | 16–30 months | 12–24 months | 8–16 months |
| M6 complete compatibility | 42–72 months | 22–40 months | 16–30 months | 12–22 months |
| M8 enhanced release | 54–84 months | 30–54 months | 22–42 months | 16–30 months |

An unsupported RSP overlay, unhandled `F3DDKR` path, or unsuitable runtime license can add six to twelve months or force an architecture change. Re-estimate at G2, M2, M3, M4, M5, and the first ultrawide/HFR matrix. Lower bounds are optimistic cases, not commitments.

## Staffing and workstream ownership

The fastest credible team is four experienced owners:

1. CPU recompilation, runtime, CPU overlays, scheduler, and DMA.
2. RSP, RT64, graphics correctness, and later presentation enhancements.
3. Deterministic tests, emulator/hardware traces, CI, fuzzing, and route automation.
4. Game reverse engineering, progression, save/accessories, input/audio/UI, and release integration.

Human approval remains required for licensing, data distribution, state-hash exclusions, scheduler semantics, save compatibility, golden changes, severity, and release. Parallel AI analysis can shorten bounded research and test-authoring tasks but does not replace these owners or the critical-path experiments.

## Top risks and triggers

| Risk | Trigger for escalation | Required response |
|---|---|---|
| Unlicensed upstream reuse | No explicit reuse basis before public code depends on upstream material | Keep work private/metadata-only; seek permission or legal review |
| GPL/runtime mismatch | Desired project terms conflict with N64ModernRuntime | Accept compatible terms or fund a replacement before G3 |
| `F3DDKR` unsupported in RT64 | Captured task cannot render correctly | Time-box custom integration, RSP recompilation, or alternate path at G2 |
| RSP overlay-slot mismatch | JFG swap/loading behavior cannot be represented | Prototype upstream change or no-go before broad implementation |
| CPU overlay/runlink complexity | Worst overlay fails relocation or indirect lookup | Build explicit tables/tests or revisit architecture |
| Controller Pak gap | Required JFG save/accessory path returns `NOPACK` | Implement and fuzz a native PFS layer before M4 |
| Deterministic harness overbuild | Test infrastructure consumes two iterations without moving the first divergence | Restrict kernel v0 and prioritize boot-boundary cases |
| Corpus/data leakage | ROM-derived body reaches Git, public CI, logs, or AI service | Stop automation, rotate exposed credentials if applicable, purge artifacts, audit policy |
| Late-game coverage surprise | New overlay/progression mechanism appears after M4 | Maintain early content manifest and re-estimate immediately |
| Enhancement-first scope | Ultrawide/HFR/mod work begins while compatibility route is red | Freeze enhancement work until route health recovers |

## Owner decisions and later resources

Resolved for the Phase 0-2 boundary:

1. Local work verifies only the supported ROM hash; lawful possession remains
   the user's responsibility and the input never enters GitHub.
2. The initial target is a Windows host shell with WSL2/Linux upstream builds,
   CMake, and Ninja. Linux/Steam Deck packaging is deferred.
3. No candidate runtime, renderer, frontend, audio, or input dependency is
   selected or linked yet, so no GPL distribution decision is implied.
4. The upstream permission request is deliberately deferred and unsent. The
   project uses the no-copy/local-generation boundary in
   `docs/governance/phase0-decisions.md`.
5. Compatibility and enhanced execution profiles are defined separately;
   compatibility-first remains the planning order.
6. `TK22-26` owns private-corpus storage decisions. Phase 0-2 authorizes no
   off-machine private corpus or ROM-backed CI.

Required before Phase 3 expands beyond the current boundary or before release:

1. Select the runtime/dependency architecture and approve its license
   consequences, including GPL-3.0 if N64ModernRuntime is retained.
2. State available human hours and whether specialist graphics/RSP or legal
   help can be recruited.
3. Approve and provision an isolated self-hosted runner before any ROM-backed
   automation.
4. Approve a reference oracle and any required hardware/capture equipment.
5. Provide representative Windows GPU/controller coverage, adding Intel and
   Steam Deck before their support is claimed.
6. Designate owners for legal review, release approval, severity
   classification, code signing, branding, and support.

These later inputs keep estimates conditional but do not reopen completed
Phase 0-2 gates unless the project expands beyond the recorded boundary.
