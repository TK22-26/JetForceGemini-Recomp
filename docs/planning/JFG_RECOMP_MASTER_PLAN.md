# Jet Force Gemini Native PC Recompilation Master Plan

**Document status:** Draft execution plan  
**Research snapshot:** 2026-08-03  
**Primary target:** Jet Force Gemini, North American retail N64 release  
**Primary outcome:** A fully playable native PC port with a faithful compatibility mode, ultrawide support, high-frame-rate presentation, modern input, reliable saves, and a path to increasingly readable source and mod support  
**Recommended project model:** New recompilation-port repository that consumes the existing matching-decompilation project as an upstream source of metadata and knowledge  
**Core rule:** No behavioral change is accepted because an AI says it is correct. Changes are accepted only when deterministic tests, differential comparisons, coverage evidence, and route replays show that they are correct.

> This is an engineering plan, not legal advice. Before copying or redistributing code, generated output, symbols, ROM-derived snapshots, or assets, obtain appropriate legal guidance and confirm the licenses and permissions of every dependency and upstream project.

---

## Table of contents

1. [Executive decision](#1-executive-decision)
2. [Mission, scope, and definition of done](#2-mission-scope-and-definition-of-done)
3. [Known starting point](#3-known-starting-point)
4. [Project architecture](#4-project-architecture)
5. [Non-negotiable engineering principles](#5-non-negotiable-engineering-principles)
6. [Testing architecture](#6-testing-architecture)
7. [AI-centered operating model](#7-ai-centered-operating-model)
8. [Continuous integration and automation](#8-continuous-integration-and-automation)
9. [Master phase plan](#9-master-phase-plan)
10. [Function-by-function replacement path](#10-function-by-function-replacement-path)
11. [Full-game route and content coverage](#11-full-game-route-and-content-coverage)
12. [Progress metrics and control dashboard](#12-progress-metrics-and-control-dashboard)
13. [Work-item and issue design](#13-work-item-and-issue-design)
14. [Staffing and ownership model](#14-staffing-and-ownership-model)
15. [Planning ranges and re-estimation gates](#15-planning-ranges-and-re-estimation-gates)
16. [Risk register](#16-risk-register)
17. [Initial 30/60/90-day execution sequence](#17-initial-306090-day-execution-sequence)
18. [Release acceptance checklist](#18-release-acceptance-checklist)
19. [Appendices](#19-appendices)
20. [Primary technical references](#20-primary-technical-references)

---

# 1. Executive decision

## 1.1 What we should build

Create a **new repository** for the native port. Do not make the existing matching-decompilation repository the main PC-port codebase.

A recommended naming pattern is:

```text
jfg-recomp/
```

The matching decomp remains an upstream project whose purpose is to reconstruct and document the original N64 program. The new recomp repository owns:

- N64Recomp configuration.
- Native runtime integration.
- Recompiled output generation.
- PC-specific patches.
- Testing infrastructure.
- Deterministic replay.
- Renderer integration.
- Input, audio, save, configuration, and packaging code.
- Ultrawide and high-frame-rate enhancements.
- Mod support.
- Gradual replacement of translated functions with readable source.

A fork of the decomp may be used temporarily to prepare upstream pull requests, but it should not become the permanent home of the native port.

## 1.2 How the projects relate

```text
                    USER-OWNED JFG ROM
                            |
                            v
             Existing JFG matching decompilation
             - ROM layout
             - build/jfg.us.elf
             - symbols and names
             - overlays
             - structs and headers
             - matching C as it becomes available
                            |
                    sync/export step
                            |
                            v
                     New jfg-recomp repo
             - N64Recomp-generated functions
             - N64ModernRuntime integration
             - RT64 integration
             - native patches
             - deterministic test harness
             - replay corpus
             - PC launcher and packaging
                            |
               +------------+-------------+
               |                          |
               v                          v
       Faithful compatibility mode    Enhanced mode
       original simulation behavior   ultrawide, HFR,
       and reference timing           modern controls, mods
```

## 1.3 The three permanent execution modes

The port should be designed around three modes from the beginning.

### Compatibility mode

Purpose: remain as close as practical to the original game.

- Original simulation rate.
- Original aspect ratio by default.
- Original game logic.
- Minimum required native patches.
- No optional quality-of-life changes.
- Used as the primary whole-game regression target.
- Never removed, even after enhanced mode becomes the default.

### Enhanced mode

Purpose: deliver the desired player-facing PC port.

- Arbitrary aspect ratios.
- Ultrawide-safe projection, culling, effects, HUD, and split-screen.
- High-frame-rate presentation.
- Modern controller mapping.
- Optional mouse/keyboard and dual-analog support.
- Modern configuration UI.
- Optional texture packs and mods.
- Intentional bug fixes behind named feature flags.

### Deterministic test mode

Purpose: make automated proof possible.

- Fixed virtual clock.
- Deterministic scheduler or recorded scheduling decisions.
- Seeded or captured random-number state.
- Recorded input.
- Headless operation where possible.
- Runtime side effects captured in journals.
- Rendering, audio, and host I/O replaceable with deterministic test doubles.
- Stable state hashing and first-divergence reporting.

## 1.4 What success does not require

The first polished release does **not** require:

- A 100% matching decompilation.
- Every translated function to be rewritten in clean C or C++.
- Every original bug to be fixed.
- A new renderer written from scratch.
- Gameplay simulation to run at the monitor refresh rate.
- Support for every regional ROM.
- A public mod SDK before the base game is finishable.

The correct order is:

```text
faithful native execution
        ->
finishable game
        ->
complete regression coverage
        ->
ultrawide and high-frame-rate presentation
        ->
modding and gradual source replacement
```

---

# 2. Mission, scope, and definition of done

## 2.1 Player-facing mission

Deliver a native PC application that allows a player who supplies the supported Jet Force Gemini ROM to:

1. Start a new game.
2. Complete the required campaign from beginning to credits.
3. Save, quit, relaunch, and resume reliably.
4. Use every required playable character and campaign mechanic.
5. Complete all progression gates required by the original game.
6. Play supported local multiplayer modes.
7. Use modern controllers with remapping.
8. Play at 4:3, 16:9, 21:9, and wider supported ratios without broken projection or unusable HUD.
9. Render at high display refresh rates without changing simulation outcomes.
10. Run on the initially supported PC platforms without an emulator process.

## 2.2 Engineering definition of “fully playable”

The project may call a build **fully playable** only when all of the following are true:

- A clean new-game route reaches credits.
- A second route made from intermediate saves also reaches credits.
- Every required level transition succeeds.
- Every required boss and progression event completes.
- All required save/load transitions work after process restart.
- No known deterministic crash blocks normal completion.
- No known state corruption blocks normal completion.
- Audio remains functional throughout a complete route.
- Controller disconnect/reconnect does not corrupt state.
- Compatibility mode produces stable deterministic checkpoints for the approved route corpus.
- All supported overlays load, execute, unload, and reload correctly.
- The supported multiplayer modes pass their scenario matrix.
- The compatibility test suite is green before enhancement testing begins.
- Ultrawide and high-frame-rate modes pass their own matrices without causing compatibility-route state divergence.

## 2.3 “Polished release” definition

A polished release adds:

- User-facing ROM validation and friendly error messages.
- First-run setup.
- Settings persistence.
- Controller remapping.
- Graphics and audio settings.
- Stable frame pacing.
- Crash diagnostics that do not collect private data without consent.
- Release builds for the supported platforms.
- Upgrade-safe save handling.
- A documented known-issues list.
- Reproducible release metadata.
- A release-candidate soak period with no unresolved release-blocking regressions.

## 2.4 Initial platform scope

Recommended order:

1. Windows x86-64.
2. Linux x86-64, including Steam Deck validation.
3. Linux ARM64 if resources allow.
4. macOS ARM64 after the runtime and renderer path are stable.

Do not block first playability on all platforms. Keep platform APIs behind narrow interfaces from day one so later ports do not require game-logic changes.

## 2.5 Initial ROM scope

Use the US retail ROM as the sole initial target because the current decomp project treats it as the default and produces `build/jfg.us.elf` for that version.[^jfg-decomp]

Add the kiosk version only after the retail US route is stable. PAL and Japanese versions remain later projects unless a contributor explicitly owns them.

## 2.6 Explicit non-goals for the first stable release

- Online multiplayer.
- New campaign content.
- Large gameplay redesigns.
- Global cleanup of all generated code.
- Raising engine object limits without a separate feature proposal.
- Replacing all original asset formats.
- Uncapped simulation tick.
- Supporting arbitrary JFG ROM revisions.
- Shipping copyrighted game assets.

---

# 3. Known starting point

## 3.1 Existing Jet Force Gemini decompilation

The current public Jet Force Gemini repository already provides a meaningful foundation:

- A build process for the US and kiosk versions.
- A generated ELF path for the US version: `build/jfg.us.elf`.
- Symbol maps.
- Source and overlay organization.
- An automated progress-report output at `build/report.json`.
- Existing naming and documentation.
- A stated relationship to a heavily modified Diddy Kong Racing engine.
- A large overlay/reference inventory.
- Recent matching work and active maintenance as of the research snapshot.[^jfg-decomp]

This means the recomp effort should begin by consuming existing metadata, not by rediscovering the ROM layout from zero.

## 3.2 Existing N64 recompilation stack

N64Recomp:

- Translates N64 functions into C.
- Uses symbol and section metadata, currently most conveniently supplied through an ELF.
- Supports statically linked and relocatable overlays.
- Supports stubbing, ignoring, and instruction-level patches in configuration.
- Supports single-file patch recompilation so a patched function can override the generated original at link time.
- Can also recompile RSP microcode, with limitations that must be checked against the target game.[^n64recomp]

N64ModernRuntime provides:

- Threads.
- Controllers.
- Audio.
- Message queues.
- Timers.
- RSP task handling.
- VI timing.
- Overlay handling.
- PI DMA.
- EEPROM, SRAM, and Flashram support.
- A bridge between N64Recomp-generated code and the modern runtime.[^modern-runtime]

RT64 provides:

- A modern N64 renderer for native ports.
- D3D12, Vulkan, and Metal paths.
- Arbitrary aspect-ratio support, including ultrawide with game-specific integration.
- High-frame-rate visual interpolation with game-specific integration.
- An extended command set for ports and ROM patches.
- Frame-history and deferred-rendering architecture useful for diagnostics and enhancement work.[^rt64]

Zelda64Recomp demonstrates a production architecture using:

- A separate recompilation repository.
- A separate symbol repository derived from the matching decomp.
- Single-file patch recompilation.
- Decomp headers and selected matched functions for enhancements.
- RT64 high-frame-rate and ultrawide features.
- Mod exports and strict patch-mode configuration.[^zelda-recomp][^zelda-syms]

## 3.3 Jet Force Gemini-specific early risks

The following are not reasons to avoid the project. They are reasons to test them early.

### Large overlay and dynamic-module surface

The JFG repository contains extensive overlay data and cross-overlay references. The port must prove that:

- Overlay addresses are mapped correctly.
- Relocations are correct.
- Function-pointer lookups resolve the currently loaded section.
- Overlay load/unload lifetime is correct.
- A reloaded overlay does not retain stale native state.
- Overlay code can be captured and replayed deterministically.

### DKR-derived graphics behavior

The decomp build defines `F3DDKR_GBI`, indicating Diddy Kong Racing-derived graphics behavior. Treat renderer compatibility and any custom microcode behavior as an early feasibility spike, not a late polish task.[^jfg-makefile]

### RSP microcode inventory

N64Recomp can recompile RSP microcode, but its public documentation states that RSP-overlay support has limitations. The project must identify every graphics, audio, decompression, JPEG, or other RSP program before committing to the final path.[^n64recomp]

### Save-device behavior

JFG symbols include pack/file and flash-related routines. N64ModernRuntime explicitly lists EEPROM, SRAM, and Flashram support, but the team must separately confirm Controller Pak or game-specific pack behavior. Build a save-device matrix before assuming the runtime covers all cases.

### Anti-tamper and trap behavior

The decomp build includes anti-tamper-related configuration, and recent upstream work mentions trap handling. Every trap, dangling-jump workaround, checksum, and anti-tamper path must be catalogued. Do not blindly stub these functions.

### Timing dependencies

Enemy logic, animation, cutscenes, audio, input, and overlays may assume the original VI or simulation cadence. High-frame-rate work must initially leave simulation cadence unchanged.

### Licensing and permissions

At the research snapshot, the JFG decomp repository root did not visibly include a license file. Therefore:

- Do not assume its source can be copied into a new repository.
- Ask the maintainer what reuse is permitted.
- Prefer contributing discoveries upstream.
- Keep a local-path integration option until licensing is clarified.
- Have counsel review distribution of generated code, symbols, test snapshots, and ROM-derived artifacts.

---

# 4. Project architecture

## 4.1 Recommended repository layout

```text
jfg-recomp/
├── CMakeLists.txt
├── cmake/
│   ├── Toolchains/
│   ├── Sanitizers.cmake
│   └── Warnings.cmake
├── config/
│   ├── jfg.us.toml
│   ├── jfg.patches.toml
│   ├── overlays.us.toml
│   └── rsp/
├── upstream/
│   ├── jfg-decomp/              # Optional pinned submodule/local path after permission
│   ├── N64Recomp/
│   ├── N64ModernRuntime/
│   ├── RecompFrontend/
│   └── RT64/
├── generated/
│   ├── funcs/                   # Generated locally; commit policy decided after legal review
│   ├── rsp/
│   └── manifests/
├── symbols/
│   ├── functions.toml
│   ├── data.toml
│   ├── overlays.toml
│   └── provenance.json
├── patches/
│   ├── include/
│   ├── required/
│   ├── compatibility/
│   ├── widescreen/
│   ├── hfr/
│   ├── input/
│   ├── saves/
│   ├── fixes/
│   └── mods/
├── runtime/
│   ├── app/
│   ├── platform/
│   ├── renderer/
│   ├── audio/
│   ├── input/
│   ├── storage/
│   ├── diagnostics/
│   └── test_runtime/
├── tests/
│   ├── unit/
│   ├── function_diff/
│   ├── subsystem/
│   ├── replay/
│   ├── scenarios/
│   ├── graphics/
│   ├── audio/
│   ├── saves/
│   ├── performance/
│   ├── fuzz/
│   └── fixtures/
├── corpus/
│   ├── manifests/               # Public recipes and hashes
│   └── private/                 # Ignored ROM-derived material
├── tools/
│   ├── sync_upstream.py
│   ├── export_symbols.py
│   ├── validate_elf.py
│   ├── build_overlay_manifest.py
│   ├── capture_function_calls.py
│   ├── minimize_corpus.py
│   ├── replay_runner.py
│   ├── state_diff.py
│   ├── first_divergence.py
│   ├── visual_diff.py
│   └── ai_task_builder.py
├── docs/
│   ├── architecture/
│   ├── adr/
│   ├── ai/
│   ├── symbols/
│   ├── subsystems/
│   ├── tests/
│   ├── routes/
│   └── risks/
├── .github/
│   ├── ISSUE_TEMPLATE/
│   └── workflows/
├── LICENSE
├── CONTRIBUTING.md
├── SECURITY.md
└── README.md
```

## 4.2 Upstream synchronization model

Every synchronized artifact must record provenance:

```json
{
  "jfg_decomp_commit": "<sha>",
  "n64recomp_commit": "<sha>",
  "runtime_commit": "<sha>",
  "rt64_commit": "<sha>",
  "rom_sha1": "493ced9008dbe932d6e91179b68e8630cf23a023",
  "symbol_export_version": 1,
  "generated_at_utc": "<timestamp>"
}
```

The sync process must:

1. Verify the ROM hash.
2. Verify the pinned upstream commit.
3. Build the decomp ELF.
4. Export symbols and overlay metadata.
5. Compare exported symbol counts and section ranges with the previous snapshot.
6. Fail on removed or moved symbols unless an approved migration file explains them.
7. Generate a human-readable upstream-change report.
8. Run a recompilation smoke test.
9. Run the compatibility replay smoke suite.
10. Update provenance only after all gates pass.

## 4.3 Symbol repository option

Once licensing is clarified, consider a small separate repository similar to Zelda64RecompSyms:

```text
jfg-recomp-syms/
├── jfg.us.syms.toml
├── jfg.us.datasyms.toml
├── jfg.us.overlays.toml
├── provenance.json
└── README.md
```

Benefits:

- Keeps generated symbol files out of the main history.
- Lets mods consume symbols without consuming the full port.
- Pins every symbol snapshot to a decomp commit.
- Makes upstream drift explicit.
- Allows a clean compatibility contract between decomp and recomp teams.

Do not publish this repository until permissions and legal treatment are clear.

## 4.4 Generated-code policy

Choose one of the following only after legal review.

### Option A: Generate locally

- Generated C is not committed.
- The user supplies the ROM.
- A setup command builds the decomp ELF and runs N64Recomp.
- Public CI tests host code and synthetic fixtures.
- Private/self-hosted CI performs ROM-backed tests.

Advantages: minimizes redistribution of ROM-derived material.  
Disadvantages: slower contributor setup and harder public CI.

### Option B: Commit generated code

- Generated C is versioned.
- Regeneration is reproducible from a verified ROM and pinned tools.
- Diffs are reviewed as generated artifacts, not edited manually.
- A legal opinion and project license explicitly cover distribution.

Advantages: faster builds and easier public CI.  
Disadvantages: repository size, licensing complexity, and generated-diff noise.

### Option C: Publish generated-code release artifacts

- Source repo contains scripts and manifests.
- Generated functions are produced in a controlled pipeline.
- Artifacts are distributed separately if legally approved.

The master plan does not assume which option is legally correct.

## 4.5 Patch architecture

Every patch must be classified.

```text
required          Needed for native execution
compatibility     Fixes a recomp/runtime mismatch
widescreen        Aspect-ratio behavior only
hfr               High-frame-rate presentation only
input             Modern input behavior
save              Native storage behavior
fix               Intentional original-game bug fix
mod               Export/hook/event support
debug             Instrumentation; excluded from release
```

Every patch receives a manifest entry:

```yaml
id: JFG-PATCH-0042
symbol: Camera_BuildProjection
category: widescreen
reason: "Remove fixed 4:3 projection assumption"
original_behavior: "Uses fixed aspect constant"
compatibility_impact: none
feature_flag: widescreen_projection
tests:
  - gfx-projection-4x3
  - gfx-projection-16x9
  - gfx-projection-21x9
  - replay-cutscene-camera-set
upstream_reference:
  commit: "<sha>"
  file: "src/camera.c"
owner: graphics
rollback: "Disable widescreen_projection"
```

Instruction-level patches require even stronger documentation:

- Original address.
- Original instruction.
- Replacement instruction.
- Why a function override was not used.
- Supported overlay/version.
- Exact regression test.
- Removal plan.

## 4.6 Feature-flag rule

Every nonessential enhancement must be independently switchable.

This permits a failing route to be reduced from:

```text
all enhancements enabled
```

to:

```text
compatibility baseline
+ one feature at a time
```

The AI triage system should automatically bisect feature flags when a scenario fails.

---

# 5. Non-negotiable engineering principles

1. **The compatibility baseline is the oracle.**  
   Enhancements may not silently redefine original behavior.

2. **Testing is a deliverable, not cleanup.**  
   A phase is incomplete until its tests exist and pass.

3. **No large AI patch without a failing test or a measurable milestone.**  
   “Looks cleaner” is not evidence.

4. **Prefer the smallest independently testable change.**  
   One function, one overlay rule, one runtime callback, or one scenario defect.

5. **Preserve old and new implementations during migration.**  
   Keep the generated reference callable until the replacement is proven.

6. **Find the first divergence, not the final symptom.**  
   A crash ten minutes later is less useful than the first differing memory write.

7. **Do not mix compatibility fixes with enhancements.**  
   A PR either restores parity or intentionally changes behavior.

8. **All nondeterminism must be measured.**  
   A flaky test is a product defect.

9. **Upstream knowledge should flow back upstream.**  
   Correct names, structs, overlay facts, and matching code belong in the decomp when permitted.

10. **AI confidence is never a merge criterion.**  
    Only machine-checkable evidence, independent review, and appropriate human approval count.

11. **The game must remain playable between milestones.**  
    Avoid month-long branches that cannot boot.

12. **Do not refactor opaque code merely to increase readable-code percentage.**  
    Rewrite only when it improves a named capability, testability, portability, modding, or maintenance.

---

# 6. Testing architecture

# 6.1 Oracle hierarchy

Use multiple oracles because each catches a different failure class.

```text
Highest external confidence
    Original hardware spot checks
    Accuracy-focused emulator traces
    Unmodified static-recomp compatibility mode
    Generated-function baseline
    Subsystem invariants
    Visual/audio reference captures
Lowest isolation cost
```

### Oracle A: original hardware

Use sparingly for:

- Timing-sensitive spot checks.
- Controller behavior.
- Save-device behavior.
- Visual effects that may be emulator-specific.
- Final release comparisons.

It is not the main automated oracle.

### Oracle B: instrumented emulator

Use a selected emulator build to produce:

- Input movies.
- Save states.
- frame/tick checkpoints.
- memory hashes.
- overlay load logs.
- RSP/RDP task logs where possible.
- audio command or PCM captures.

Qualify the emulator and pin its exact version.

### Oracle C: unmodified static recomp

Once the initial recomp is validated against the emulator, keep an unmodified generated path as the primary native behavioral reference.

### Oracle D: per-function generated baseline

For a handwritten replacement, the original generated function is the direct differential oracle.

### Oracle E: invariants

Examples:

- Object count remains within valid bounds.
- An overlay cannot execute when not loaded.
- Save checksum remains valid.
- RNG advances the expected number of times.
- A level transition produces a valid destination.
- Simulation state at canonical ticks is display-rate independent.

## 6.2 Testing layers

| Layer | Purpose | Typical cadence | Merge blocking |
|---|---|---:|---:|
| T0 Build/reproducibility | Toolchain, hashes, generated manifests | Every PR | Yes |
| T1 Static metadata | ELF sections, symbols, overlays, relocations | Every PR touching metadata | Yes |
| T2 Runtime primitive | Threads, queues, timers, DMA, save callbacks | Every PR | Yes |
| T3 Function differential | Generated function vs replacement | Every relevant PR | Yes |
| T4 Subsystem differential | Camera, animation, objects, audio, save | Every relevant PR | Yes |
| T5 Deterministic replay | Frames/ticks from known states | Every PR smoke; nightly full | Yes |
| T6 Scenario routes | Menus, levels, bosses, transitions | Nightly/weekly | Yes for protected branch |
| T7 Graphics/audio regression | Command streams, images, PCM | Nightly/reference runners | Yes with approved tolerances |
| T8 Fuzz/property tests | Unusual state and input combinations | Nightly/weekly | Yes for reproducible defects |
| T9 Performance/platform | Frame pacing, memory, platform build | Nightly/release | Release blocking |

## 6.3 Deterministic test runtime

A deterministic runtime is the foundation of the entire AI strategy.

It must provide:

### Virtual time

- VI ticks supplied by a deterministic counter.
- Timers scheduled against virtual time.
- No direct use of wall-clock time in compatibility logic.
- Recorded host-time inputs when wall time is unavoidable.

### Deterministic scheduling

Choose one:

1. Cooperative single-thread scheduler for test mode.
2. Deterministic event scheduler that records and replays thread wakeups.
3. Recorded schedule journal from a known-good execution.

The production runtime can remain multithreaded. Test mode needs reproducibility.

### Deterministic input

Each controller sample includes:

```yaml
tick: 123456
port: 0
buttons: [A, Z]
stick_x: 42
stick_y: -18
connected: true
accessory: controller_pak
```

Input sampling must occur at the same logical point in every replay.

### Deterministic randomness

- Identify the game RNG functions and state.
- Record seed and call count at checkpoints.
- Fail when a patch adds or removes RNG calls in compatibility mode.
- Separate host-side random values from game RNG.

### Side-effect journal

Host-facing effects must be represented as structured records:

```yaml
- tick: 8102
  type: pi_dma
  rom_offset: 0x01234000
  ram_address: 0x80300000
  size: 16384

- tick: 8103
  type: message_send
  queue_id: 7
  value: 2

- tick: 8104
  type: rsp_task
  task_kind: graphics
  microcode_id: f3ddkr
  data_ptr: 0x80400000
```

This journal allows exact comparison without requiring real host I/O.

## 6.4 Stable state hashing

Create multiple hash scopes.

### Core simulation hash

Include:

- Game globals.
- Active object data.
- Player state.
- Enemy state.
- level and mission state.
- RNG.
- timers.
- overlay identity and relocations.
- progression flags.

Exclude:

- Host pointers.
- Native renderer resources.
- wall-clock timestamps.
- uninitialized padding.
- logging counters.
- addresses that are intentionally nondeterministic.

### Full RDRAM hash

Useful during early bring-up, but noisy. Pair it with page-level hashes to identify the first changed region.

### Subsystem hash

Examples:

- `camera_hash`
- `object_pool_hash`
- `save_state_hash`
- `audio_command_hash`
- `graphics_command_hash`

### Hash contract

Each hash version is explicit. Changing what is hashed requires:

- A schema version increase.
- An explanation.
- Regeneration of approved baselines.
- Review that the change is not hiding a regression.

## 6.5 Function differential harness

For every replacement candidate:

```text
              captured pre-call world
                      |
           +----------+----------+
           |                     |
           v                     v
 generated reference      candidate replacement
           |                     |
           +----------+----------+
                      |
          compare return registers,
          memory writes, globals,
          runtime events, RNG, and
          called-function sequence
```

### Required captured state

- Function symbol and address.
- Overlay identity and load address.
- Arguments and full recomp context.
- Relevant RDRAM pages.
- Referenced globals.
- RNG state.
- virtual time.
- runtime callback state.
- call-stack or caller identity.
- path signature if available.

### Comparison policy

Use exact equality for:

- Integer registers.
- Pointer/offset values.
- memory writes.
- queue operations.
- RNG state.
- overlay state.
- save bytes.
- instruction-visible floating-point bit patterns in strict compatibility tests.

Use tolerances only when:

- The change is intentionally modernized.
- The tolerance is justified in the test manifest.
- Higher-level invariants prove gameplay equivalence.
- Compatibility mode retains the exact path.

### Callee policy

A function test must declare one of these:

- **Shared callees:** both implementations call the same underlying functions.
- **Recorded callees:** callee side effects are replayed from a journal.
- **Dual-world callees:** each world runs its own cloned call graph.
- **Mocked boundary:** a narrow host/runtime boundary is replaced by a deterministic mock.

Never leave the policy implicit.

## 6.6 Automatic call-corpus generation

Do not hand-author a million tests.

Instead:

1. Run approved input replays in compatibility mode.
2. Capture every invocation of target functions.
3. Compute a path signature from branches, callees, and relevant state.
4. Deduplicate equivalent calls.
5. Retain boundary and rare cases.
6. Compress memory snapshots.
7. Store public manifests and hashes.
8. Regenerate ROM-derived bodies locally or in private CI.
9. Fuzz around captured valid states.
10. Add every reproducible defect to the permanent corpus.

A single route can produce millions of calls but only thousands of meaningfully different function states after deduplication.

## 6.7 Coverage-guided test generation

Track:

- Function call coverage.
- Branch coverage.
- Switch-case coverage.
- Overlay coverage.
- Runtime callback coverage.
- RSP task-type coverage.
- Save-device operation coverage.
- Level-transition coverage.
- feature-flag combination coverage.

For a candidate replacement, require:

- Every reachable branch observed in the current corpus, or a documented unreachable/unknown waiver.
- Boundary tests around every comparison.
- At least one case for every switch case.
- Tests for null, empty, maximum, wraparound, and resource-exhaustion behavior where valid.
- A caller-context sample from every known call site when behavior may depend on caller state.

AI may generate candidate states for uncovered branches, but the harness must validate that generated states satisfy known invariants before using them.

## 6.8 Record-and-replay tests

A replay package should contain:

```text
scenario.yaml
inputs.bin
checkpoints.json
expected_events.json
expected_hashes.json
capture_provenance.json
```

Example scenario:

```yaml
id: route-new-game-to-first-level-control
rom_version: us
start:
  type: reset
inputs: inputs.bin
max_ticks: 18000
checkpoints:
  - at: boot-logo
  - at: title-menu
  - at: new-game-confirmed
  - at: first-playable-frame
expected:
  no_crash: true
  overlay_sequence: overlays/first-level.json
  final_state_hash: "..."
```

## 6.9 First-divergence diagnostics

Every deterministic failure should automatically produce:

- First differing tick.
- First differing function call if known.
- First differing RDRAM page.
- First differing byte range.
- First differing subsystem hash.
- Previous 256 runtime events.
- Previous 256 function calls.
- Active overlay list.
- Current RNG state and call count.
- Input sample.
- feature flags.
- build/provenance information.
- minimal replay clip around the divergence.

The report should be machine-readable and human-readable.

AI triage must always begin with this report, not with the eventual crash stack alone.

## 6.10 Emulator differential testing

Before trusting native compatibility mode as the oracle:

1. Create a small boot input movie.
2. Capture emulator checkpoints.
3. Run the native build with the same logical inputs.
4. Compare:
   - progression state,
   - RNG,
   - overlay sequence,
   - selected RDRAM ranges,
   - graphics tasks,
   - audio tasks,
   - save output.
5. Extend from boot to menu.
6. Extend to first gameplay.
7. Extend to a full vertical slice.
8. Continue spot-checking across the campaign.

Exact full-memory equivalence may not always be practical because runtime implementation details differ. Define semantic memory regions and event contracts explicitly.

## 6.11 Graphics testing

Use three levels.

### Graphics-command regression

Compare:

- Display-list command stream.
- RSP task identity.
- framebuffer addresses and dimensions.
- projection/view matrices.
- viewport/scissor.
- texture and palette references.
- render-target transitions.
- RT64 extended commands.

This is more stable than screenshots across GPUs.

### Reference-image regression

On a pinned reference runner:

- Capture approved frames.
- Compare exact pixels where deterministic.
- Use perceptual thresholds only for known GPU/backend variation.
- Generate heat maps.
- Fail on newly visible geometry, missing effects, broken HUD, or incorrect aspect correction.
- Keep 4:3 compatibility images as the baseline.

### Visual scenario matrix

At minimum:

- 4:3.
- 16:9.
- 21:9.
- 32:9.
- windowed and fullscreen.
- each supported split-screen layout.
- menus.
- cutscenes.
- aiming views.
- effects that read framebuffers or depth.
- transitions and fades.
- HUD edge placement.
- text/subtitles.
- particle-heavy scenes.

## 6.12 Audio testing

Capture and compare:

- Audio task inputs.
- command-list hashes.
- sample counts per virtual interval.
- channel activity.
- final PCM where deterministic.
- silence/underrun events.
- music transition state.
- pause/resume behavior.

Run long audio soak tests because a tiny scheduling error can emerge as drift minutes later.

## 6.13 Save-system testing

Build a save matrix:

- New save creation.
- Existing save load.
- Save overwrite.
- corrupted save rejection/recovery.
- full device.
- missing device.
- device disconnect.
- game restart.
- application update.
- controller-port changes.
- every save/accessory type actually used by JFG.
- import/export if provided.

Every release candidate must pass save compatibility from the previous public version.

## 6.14 Overlay testing

For each overlay:

- Can load at expected address.
- Relocations resolve.
- all exported function lookups resolve.
- indirect calls target the active overlay.
- unload clears or invalidates mappings.
- reload produces identical state.
- cross-overlay references are legal.
- no stale native pointer survives unload.
- captured scenario exercises at least one entry point.
- overlay-specific globals are included in state hashes.
- failure produces a clear missing-symbol or relocation report.

Create an overlay coverage dashboard. “Game boots” is not evidence that late-game overlays work.

## 6.15 High-frame-rate testing

The first HFR design should keep simulation at its original cadence and interpolate presentation.

Required invariant:

```text
For identical inputs sampled at canonical simulation ticks,
simulation checkpoint hashes must be identical at
30, 60, 90, 120, 144, 165, and 240 Hz display rates.
```

Test:

- Object transforms.
- camera transforms.
- texture scrolling.
- particles.
- HUD animation.
- cutscenes.
- pause/unpause.
- level transitions.
- input latency modes.
- frame pacing.
- interpolation reset after teleport/load.
- no interpolation across discontinuities.
- no extra simulation or RNG calls.
- no audio-rate coupling.
- no save timing change.

## 6.16 Fuzz and property testing

### Input fuzzing

Mutate:

- button timing.
- simultaneous buttons.
- analog boundaries.
- rapid pause/unpause.
- controller disconnects.
- menu navigation.
- level-transition timing.

### State fuzzing

Mutate only validated fields:

- object counts.
- health boundaries.
- timers near zero/wrap.
- coordinates near collision boundaries.
- pool capacity.
- overlay load order.
- save slot occupancy.
- RNG seeds.

### Metamorphic properties

Examples:

- Disabling visual interpolation must not change simulation state.
- Changing aspect ratio must not change mission progression.
- Saving and immediately loading must preserve the approved save-state fields.
- Running a deterministic replay twice must produce the same checkpoint hashes.
- A no-input replay should remain stable regardless of host CPU speed.
- A renderer backend change must not alter compatibility-mode simulation hashes.

## 6.17 Performance and soak testing

Track:

- startup time.
- level-load time.
- memory use.
- generated-code build time.
- frame time percentiles.
- audio underruns.
- event-queue backlog.
- overlay lookup cost.
- state-capture overhead.
- long-run memory growth.
- save latency.

Soak scenarios:

- 8-hour idle/menu.
- repeated level transitions.
- repeated pause/unpause.
- repeated save/load.
- repeated multiplayer match restart.
- repeated controller disconnect.
- repeated fullscreen/window switching.
- high-particle combat.
- rapid overlay churn.

## 6.18 Test-data legal hygiene

ROM-derived snapshots may contain copyrighted code or assets.

Public repository:

- Store replay input.
- Store hashes.
- Store manifests.
- Store small synthetic fixtures created by the project.
- Store scripts that regenerate private fixtures.
- Store redacted structural metadata after review.

Local/private runner:

- Stores full RDRAM snapshots.
- Stores ROM pages.
- Stores extracted assets.
- Stores emulator save states.
- Stores full graphics/audio captures if they contain original data.

CI must prevent private corpus artifacts from being uploaded to public logs or artifacts.

---

# 7. AI-centered operating model

## 7.1 Purpose of AI in this project

AI should increase throughput by:

- Explaining MIPS and generated C.
- Building call graphs and dependency summaries.
- Comparing JFG with DKR-derived code.
- Proposing names and structs.
- Generating instrumentation.
- Generating focused test cases.
- Minimizing failing replays.
- Grouping divergence reports.
- Drafting replacement code.
- Reviewing patches for hidden state and side effects.
- Maintaining symbol cards and subsystem documentation.
- Prioritizing the next smallest testable task.

AI should not be trusted to:

- Declare equivalence without tests.
- Make broad architecture rewrites autonomously.
- change dozens of functions to “clean up” code.
- invent missing hardware behavior.
- silently weaken test thresholds.
- update golden outputs merely because tests fail.
- merge its own patch without independent evaluation.
- copy upstream code when license permission is unclear.

## 7.2 Agent roles

A practical AI workflow uses separate roles, even if the same underlying model is invoked with isolated contexts.

### Planner agent

- Reads milestone, dashboard, and blockers.
- Selects a bounded work item.
- Creates the task packet.
- Defines test and stop criteria.
- Cannot modify code.

### Reverse-engineering analyst

- Reads disassembly, generated C, decomp source, symbols, callers, and traces.
- Produces a hypothesis and dependency map.
- Identifies unknown state.
- Cannot merge code.

### Test author

- Adds or improves a failing test.
- Produces capture requirements.
- Defines exact comparison policy.
- Cannot alter production behavior.

### Implementer

- Makes the smallest patch that satisfies the task packet.
- May only touch allowed files.
- Must preserve feature flags and baseline path.

### Test runner/triage agent

- Runs focused tests.
- Runs subsystem tests.
- Runs replay smoke tests.
- Generates first-divergence evidence.
- Cannot change golden baselines.

### Independent reviewer

- Receives the task packet, diff, and evidence but not the implementer’s internal reasoning.
- Searches for missed globals, aliasing, timing, error paths, and weakened tests.
- Can reject or request a narrower task.

### Knowledge curator

- Updates symbol cards.
- Updates architecture decisions.
- Links tests to functions and scenarios.
- Records unresolved questions and confidence levels.

### Human maintainer

Required for:

- Legal/licensing decisions.
- New instruction-level patches.
- Changes to compatibility hash exclusions.
- Test-threshold changes.
- save-format changes.
- scheduler/timing architecture.
- release approvals.
- intentional behavior changes.
- security-sensitive code.
- large or cross-subsystem patches.

## 7.3 The bounded AI task packet

Every AI coding job must begin with a machine-readable task packet.

```yaml
id: JFG-FUNC-0127
milestone: M4-first-playable
title: "Replace and type squadsGetClosestPlayer"
goal: >
  Produce a readable replacement that is exactly equivalent in
  compatibility mode and exposes a typed helper for later AI work.
scope:
  subsystem: squads
  allowed_symbols:
    - squadsGetClosestPlayer
  allowed_files:
    - patches/compatibility/squads.c
    - tests/function_diff/squads_get_closest_player.cpp
    - docs/symbols/squadsGetClosestPlayer.md
  max_production_lines_changed: 180
  max_test_lines_changed: 350
context:
  upstream_commit: "<sha>"
  symbol_address: "0x..."
  callers:
    - overlay_146_func_...
  known_globals:
    - gPlayerArray
    - gPlayerCount
oracle:
  type: generated_function
  exact:
    - return_registers
    - rdram_writes
    - rng_state
    - runtime_events
tests_required:
  captured_cases_minimum: 100
  path_signatures_minimum: 4
  boundary_cases:
    - zero_players
    - one_player
    - equal_distance_tie
    - maximum_player_count
exit_criteria:
  focused_suite: pass
  subsystem_suite: pass
  replay_smoke: pass
  no_new_hash_divergence: true
stop_conditions:
  max_attempts: 3
  max_elapsed_agent_iterations: 6
  stop_if_unknown_memory_read: true
risk: medium
human_review_required: true
```

## 7.4 Autonomous work loop

```text
1. Read milestone and CI dashboard.
2. Select the highest-value unblocked small task.
3. Assemble only the relevant context.
4. State a falsifiable hypothesis.
5. Add or identify a failing test.
6. Instrument before guessing when state is unknown.
7. Make the smallest implementation.
8. Run focused tests.
9. On failure, generate first-divergence report.
10. Attempt a bounded correction.
11. Run subsystem tests.
12. Run deterministic replay smoke suite.
13. Run static analysis and sanitizers.
14. Produce an evidence bundle.
15. Send to independent AI review.
16. Send risk-appropriate changes to human review.
17. Merge only when all gates pass.
18. Update knowledge base and dashboard.
19. Select the next task.
```

## 7.5 Stop and refocus rules

The agent must stop coding and open a research/instrumentation task when any of these occur:

- Three implementation attempts fail for the same first divergence.
- The first divergence is earlier after a change.
- The required patch exceeds the task’s line/file budget.
- More than one subsystem must change.
- The target function reads unknown memory.
- A call target cannot be resolved.
- An overlay identity is ambiguous.
- A test is flaky.
- The candidate requires weakening an exact comparison.
- A golden output would need to change without an approved intentional-behavior proposal.
- The change adds an instruction-level patch.
- The change alters save data or scheduler semantics.
- The agent cannot explain every new side effect.
- Compatibility-mode replay regresses.
- The patch fixes the final crash but not the first divergence.

The refocused task should be one of:

- Add logging.
- Name a global.
- recover a struct field.
- map a call target.
- capture more cases.
- isolate a smaller function.
- build a deterministic mock.
- document a hardware behavior.
- ask for maintainer input.

## 7.6 AI evidence bundle

Every AI-authored PR should attach:

```text
evidence/
├── task.yaml
├── hypothesis.md
├── context_manifest.json
├── patch.diff
├── focused_tests.json
├── subsystem_tests.json
├── replay_smoke.json
├── coverage_before.json
├── coverage_after.json
├── first_divergence/            # Empty when passing
├── sanitizer_report.txt
├── reviewer_report.md
└── risks.md
```

## 7.7 Independent verification policy

The same AI context must not both:

1. write the patch, and
2. approve the patch.

At minimum:

- Implementer and reviewer use separate conversations/context.
- Reviewer receives raw evidence.
- Reviewer reruns or requests tests.
- Golden-baseline changes require human approval.
- High-risk changes require two human approvals when the team size permits.

## 7.8 AI knowledge base

Maintain source-controlled, structured project memory.

### Symbol card

```yaml
symbol: save_symbol_example
address_us: "<private>"
subsystem: save
status:
  named: true
  matched_upstream: unknown
  replacement: false
signature_confidence: medium
reads:
  - save_context
writes:
  - accessory_buffer
side_effects:
  - controller_pak_io
tests:
  - save-create-slot
  - save-overwrite
open_questions:
  - "Does this path write EEPROM or Controller Pak for this mode?"
sources:
  - upstream_commit: "<sha>"
```

### Subsystem map

Each subsystem document includes:

- Purpose.
- entry points.
- data structures.
- globals.
- overlays.
- thread ownership.
- runtime callbacks.
- known timing assumptions.
- tests.
- unresolved questions.
- replacement status.
- enhancement hooks.

### Architecture decisions

Use ADRs for:

- deterministic scheduling.
- renderer choice.
- generated-code distribution.
- save-path mapping.
- interpolation model.
- symbol synchronization.
- mod ABI.
- supported ROM version.

## 7.9 AI task selection score

The planner may rank tasks with:

```text
priority =
    milestone_unblock_value
  + test_coverage_gain
  + knowledge_gain
  + number_of_downstream_callers_unblocked
  + reproducibility
  - scope_size
  - unknown_state_penalty
  - cross_subsystem_penalty
  - legal_risk
  - flake_risk
```

Prefer:

- leaf functions.
- pure math.
- table lookups.
- known SDK/libultra routines.
- functions with many captured calls.
- functions blocking an early boot or route milestone.
- functions already matched upstream.

Avoid early autonomous rewrites of:

- scheduler.
- memory allocator.
- overlay loader.
- save format.
- audio scheduler.
- global object loop.
- anti-tamper logic.
- custom RSP behavior.

---

# 8. Continuous integration and automation

## 8.1 CI lanes

### Public PR lane

Runs without proprietary ROM material:

- Formatting.
- Static analysis.
- CMake configure.
- Host runtime compilation.
- Patch compilation against permitted/synthetic symbols.
- Unit tests.
- Synthetic N64Recomp fixtures.
- schema validation.
- task-packet validation.
- documentation links.
- license/secret scanner.
- generated-manifest consistency where possible.

### Authorized ROM-backed PR lane

Runs on a secured self-hosted runner:

- ROM hash verification.
- Upstream decomp build.
- ELF validation.
- N64Recomp generation.
- full native build.
- focused function differential tests.
- replay smoke suite.
- no-upload check for ROM-derived data.

### Nightly lane

- All deterministic replay segments.
- Fuzzing with registered seeds.
- sanitizers.
- audio soak.
- overlay load matrix.
- save matrix.
- visual command-stream comparison.
- reference screenshot subset.
- nondeterminism detector: repeat the same suite multiple times.

### Weekly lane

- Full campaign route.
- optional-content route segments.
- multiplayer matrix.
- long soak tests.
- supported-platform build matrix.
- performance trend report.
- upstream-sync dry run.
- corpus minimization.
- AI dashboard reprioritization.

### Release-candidate lane

- Clean-room setup from documentation.
- ROM validation.
- full compatibility route.
- full enhanced route at selected aspect ratios and refresh rates.
- save upgrade tests.
- package install/uninstall.
- portable mode if supported.
- crash-report redaction.
- artifact license and asset scan.
- final dependency provenance.

## 8.2 Required branch protections

The protected branch requires:

- All relevant CI lanes green.
- No flaky-test waiver.
- Patch manifest updated.
- task packet linked.
- test coverage evidence.
- independent reviewer approval.
- human approval for medium/high-risk changes.
- no committed ROM or unapproved ROM-derived artifact.
- no unreviewed generated-code changes.
- no decrease in route coverage.
- no increase in unexplained stubs.

## 8.3 Golden baseline governance

Only a designated command may update goldens.

The update command must produce:

- Old hash.
- New hash.
- first divergence.
- reason.
- linked issue.
- affected scenarios.
- compatibility/enhancement classification.
- approver.

An AI agent may propose a golden update but may not apply or approve it.

## 8.4 Flake policy

A test that passes on retry is still failing.

When a flake appears:

1. Quarantine only if it blocks all development.
2. Create a release-blocking flake issue.
3. Record seeds and schedules.
4. Repeat until reproduced.
5. fix nondeterminism.
6. restore the test.
7. do not lower thresholds to hide it.

## 8.5 Failure clustering

Nightly automation should cluster failures by:

- first divergent symbol.
- first divergent memory range.
- overlay.
- call-stack prefix.
- runtime event type.
- RNG-call mismatch.
- feature flag.
- platform/backend.
- visual heat-map pattern.

The planner should create one task per root-cause cluster, not one task per failed scenario.

---

# 9. Master phase plan

Each phase has an exit gate. Work may overlap, but a later phase may not declare completion until prior gates are satisfied.

# Phase 0 — Charter, permissions, and project governance

## Objective

Establish exactly what can be built, reused, tested, and distributed.

## Tasks

- Contact the JFG decomp maintainer.
- Explain the separate recomp-port architecture.
- Ask about:
  - source reuse,
  - header reuse,
  - symbol export,
  - submodule use,
  - contribution expectations,
  - preferred communication channel,
  - licensing plans.
- Review licenses of:
  - N64Recomp,
  - N64ModernRuntime,
  - RT64,
  - RecompFrontend,
  - selected UI/audio/input libraries,
  - upstream decomp dependencies.
- Decide project license.
- Write asset and ROM policy.
- Write private test-corpus policy.
- Write code-of-conduct and contribution policy.
- Define supported ROM hash.
- Define compatibility and enhanced modes.
- Define the release definition of done.
- Establish security rules for AI agents and self-hosted runners.

## Tests and controls created first

- Secret scanner.
- forbidden-file patterns for ROMs and extracted assets.
- CI check for unsupported large binary additions.
- dependency-license inventory.
- provenance schema validation.

## AI work

- Draft policy documents.
- inventory dependency licenses.
- detect binary and secret risks.
- produce questions for maintainers and counsel.

## Human-only decisions

- Legal interpretation.
- licensing.
- permission to copy upstream code.
- public/private artifact policy.

## Exit gate

- Written permission/license path is understood.
- Project license chosen.
- ROM and test-data policies committed.
- No unresolved blocker to starting a separate repository.

## Deliverables

- `docs/adr/0001-project-boundaries.md`
- `docs/legal/rom-and-assets-policy.md`
- `docs/legal/test-corpus-policy.md`
- `LICENSE`
- `CONTRIBUTING.md`
- `SECURITY.md`

---

# Phase 1 — Reproduce and pin the upstream decomp build

## Objective

Prove that every authorized developer can build the existing US decomp target and produce a stable ELF.

## Tasks

- Pin an upstream commit.
- Verify the US ROM SHA-1.
- Run:
  - setup,
  - extraction,
  - build,
  - verification.
- Record tool versions.
- Record the ELF section table.
- Record symbol counts by category.
- Record overlay count and address ranges.
- Generate `build/report.json`.
- Make the process reproducible in a container or scripted environment where licensing permits.
- Add a local `doctor` command that reports missing dependencies.

## Tests

- ROM hash test.
- reproducible ELF section test.
- symbol uniqueness test.
- no overlapping section test unless explicitly expected.
- map/ELF consistency test.
- repeated-build determinism test.
- upstream report parser test.

## AI work

- Diagnose setup failures.
- normalize environment documentation.
- summarize changes between upstream commits.
- classify unknown sections.
- generate an initial subsystem and symbol inventory.

## Exit gate

Two clean environments produce equivalent decomp build outputs and the expected `build/jfg.us.elf`.

## Deliverables

- `tools/build_upstream.py`
- `tools/validate_elf.py`
- `docs/upstream/pinned-version.md`
- `symbols/provenance.json`
- baseline static reports

---

# Phase 2 — Create the recomp repository and CI skeleton

## Objective

Create a buildable native-port repository before any game code runs.

## Tasks

- Initialize CMake.
- Add pinned tool dependencies.
- Add platform abstraction.
- Add logging.
- Add configuration.
- Add test framework.
- Add CI lanes.
- Add patch categories.
- Add task-packet and patch-manifest schemas.
- Add compatibility/enhanced/test feature profiles.
- Add ROM validation interface without storing a ROM.
- Add local/private corpus directories to `.gitignore`.

## Tests

- Empty host executable launches and exits.
- All target platforms configure.
- unit-test target runs.
- feature-profile configuration test.
- no-ROM path produces a friendly message.
- invalid-ROM path produces a friendly message.
- secret/binary scanner rejects forbidden fixtures.
- schema validation passes.

## AI work

- Generate boilerplate.
- create cross-platform wrappers.
- draft initial documentation.
- generate CI workflows.
- review build warnings.

## Exit gate

A clean clone builds the host shell and test suite without a ROM.

## Deliverables

- repository skeleton
- CI
- developer setup guide
- issue templates
- initial dashboard

---

# Phase 3 — Feasibility spikes and unknowns inventory

## Objective

Resolve the risks that could invalidate the chosen architecture before investing in polish.

## Spike A: ELF and N64Recomp metadata

- Feed `build/jfg.us.elf` to N64Recomp.
- inventory missing metadata.
- detect invalid functions and data symbols.
- create the initial `jfg.us.toml`.
- identify required stubs and ignored pseudo-functions.
- validate entry point.

## Spike B: overlays and runlink behavior

- Enumerate every overlay.
- classify static vs relocatable.
- map ROM ranges, VRAM ranges, BSS, relocations, exports, and references.
- instrument load/unload.
- verify function-pointer lookup requirements.
- inspect dynamic-code or runlink routines.
- identify whether any code is generated or patched at runtime.

## Spike C: RSP and graphics microcode

- inventory graphics and audio microcode.
- identify `F3DDKR_GBI` behavior.
- determine RT64 support path.
- determine whether custom RT64 integration or RSP recompilation is needed.
- determine whether any RSP overlays exist.
- capture representative tasks in an emulator.

## Spike D: native runtime gaps

- direct RCP register access.
- kseg0/kseg1 assumptions.
- TLB mappings.
- cache operations.
- PI DMA.
- decompression.
- timers.
- message queues.
- Controller Pak/save devices.
- anti-tamper/trap paths.

## Tests

- static overlay validator.
- synthetic relocation test.
- indirect-call lookup test.
- RSP task manifest validator.
- runtime capability matrix test.
- unknown direct-register access report.
- save-device probe tests.
- trap/anti-tamper path inventory.

## AI work

- cluster unsupported instructions and functions.
- compare code patterns with DKR decomp knowledge.
- generate overlay diagrams.
- classify each risk by evidence.
- propose minimum viable patches.
- create one issue per blocker.

## Exit gate

A written feasibility report answers:

- Can all CPU code sections be represented?
- Can all overlays be mapped?
- Is there a viable graphics/RSP path?
- Is there a viable audio path?
- Are save devices supportable?
- Are anti-tamper/trap paths understood enough to proceed?
- What N64Recomp/runtime/RT64 upstream work is required?

## Go/no-go rule

Do not proceed to broad port implementation while a fundamental microcode or dynamic-code blocker remains unbounded. A blocker may remain unresolved only if there is a tested fallback path.

## Deliverables

- `docs/feasibility-report.md`
- overlay manifest
- RSP manifest
- runtime-gap matrix
- prioritized blocker backlog
- revised planning range

---

# Phase 4 — Generate and compile the complete CPU recompilation

## Objective

Produce native host object code for every required CPU function and overlay, even if the program does not yet boot.

## Tasks

- Finalize N64Recomp configuration.
- Generate functions.
- generate overlay lookup tables.
- compile generated functions into static libraries.
- use deterministic symbol naming.
- generate unresolved-call reports.
- minimize stubs.
- add strict patch mode where supported.
- establish separate baseline and patch libraries.
- retain a callable alias for generated functions that may later be replaced.

## Tests

- every expected executable symbol generated.
- no duplicate native symbol.
- every direct call resolves.
- every indirect-call range represented.
- every overlay listed.
- generated-code compile with Clang and MSVC/GCC where applicable.
- no undefined behavior found by static analysis in handwritten bridges.
- generated manifest reproducible.
- configuration change causes expected generated diff only.

## AI work

- classify generation failures.
- propose corrected symbol boundaries.
- identify pseudo-functions/data.
- generate names only when evidence exists.
- draft upstream symbol corrections.

## Exit gate

The full generated CPU code and overlay tables compile and link with a minimal test runtime.

## Deliverables

- `config/jfg.us.toml`
- generated manifest
- unresolved-symbol report at zero or approved exceptions
- baseline generated library

---

# Phase 5 — Build the deterministic test kernel

## Objective

Create a headless executable that can run selected generated functions and controlled runtime events deterministically.

## Tasks

- Implement cloneable RDRAM/context worlds.
- implement virtual time.
- implement deterministic queues and timers.
- implement deterministic scheduling.
- implement side-effect journals.
- implement state hash schemas.
- implement function capture/replay.
- implement first-divergence reports.
- implement feature-flag profiles.
- implement test-only fake renderer/audio/storage.
- implement corpus compression and minimization.
- implement exact-repeat nondeterminism detector.

## Tests

- world clone produces identical hashes.
- same function replayed twice is bit-identical.
- scheduler replay repeats event order.
- side-effect journal is stable.
- dirty-page tracker identifies exact writes.
- first-divergence tool reports a seeded one-byte difference.
- test runtime rejects unsupported host calls.
- corpus round-trip is lossless.
- private corpus cannot be uploaded by CI.

## AI work

- generate harness code.
- generate property tests.
- review state exclusions.
- analyze nondeterminism.
- minimize failing fixtures.

## Human review required

- state hash exclusions.
- scheduler model.
- tolerance policy.
- private data handling.

## Exit gate

At least 100 representative generated functions can be captured and replayed deterministically, and seeded faults are localized to the first divergence.

## Deliverables

- `jfg-test`
- function differential framework
- replay format v1
- state hash format v1
- first-divergence report format v1

---

# Phase 6 — Boot to scheduler and first VI activity

## Objective

Run from the original entry point through initialization until stable VI/scheduler activity occurs.

## Tasks

- Initialize RDRAM and ROM mappings.
- implement required libultra/runtime bridges.
- bring up threads and queues.
- implement PI DMA.
- handle initial decompression.
- load initial overlays.
- handle RSP task submission.
- reach repeated VI events.
- instrument every stub and unsupported access.
- compare boot sequence with emulator trace.

## Tests

- reset-to-entrypoint replay.
- deterministic boot event log.
- expected thread creation order.
- expected overlay/DMA sequence.
- no unresolved call.
- no unbounded busy loop.
- repeated boot hash consistency.
- emulator/native boot checkpoint comparison.
- boot under sanitizers.
- boot with intentionally invalid ROM fails safely.

## AI work

- triage the first unsupported operation.
- explain boot functions.
- cluster stubs by root cause.
- generate minimal required patches.
- maintain boot-sequence documentation.

## Exit gate

The native build reaches stable VI/scheduler activity repeatedly with no nondeterministic divergence.

## Deliverables

- boot trace
- emulator comparison
- remaining-stub ledger
- M2 milestone build

---

# Phase 7 — First rendered frame and graphics vertical slice

## Objective

Render the boot/title path and one representative gameplay frame through the chosen renderer.

## Tasks

- integrate RT64.
- register renderer callbacks.
- support the identified graphics microcode path.
- handle framebuffers.
- handle RSP/RDP synchronization.
- add graphics-command logging.
- add RT64 frame debugger access in developer builds.
- compare initial frames with emulator captures.
- classify every missing or incorrect command.

## Tests

- graphics task submission.
- command-stream hash.
- framebuffer address/dimension checks.
- boot/title golden frames.
- first gameplay golden frame.
- repeated-frame determinism on reference runner.
- renderer backend smoke.
- no simulation-state change when renderer is disabled.
- no simulation-state change between supported renderer backends.

## AI work

- classify visual differences from command traces.
- map commands to source functions.
- propose RT64 extended-command patches only when needed.
- generate visual test manifests.

## Exit gate

Boot/title and one gameplay scene render consistently, and graphics can be disabled without changing simulation hashes.

## Deliverables

- first-frame build
- graphics compatibility report
- custom microcode integration documentation
- visual baseline v1

---

# Phase 8 — Input, audio, saves, menus, and process restart

## Objective

Make the application meaningfully interactive and persistent.

## Tasks

- controller input callbacks.
- remapping layer.
- controller connect/disconnect.
- audio output path.
- save-device implementation.
- native filesystem mapping.
- ROM selection/validation UI.
- configuration persistence.
- title/menu navigation.
- process restart and save reload.
- controller-pak/accessory support as required by the game.

## Tests

- menu navigation replay.
- input sampling timing.
- analog boundary tests.
- disconnect/reconnect.
- audio command and PCM tests.
- audio soak.
- save create/load/overwrite/corrupt/full-device matrix.
- restart-to-resume scenario.
- settings migration.
- invalid path and read-only filesystem.
- two-controller and four-controller detection as applicable.

## AI work

- generate input-state tests.
- analyze audio drift.
- recover save structures.
- fuzz save error paths.
- draft UI plumbing.

## Exit gate

A user can launch the port, navigate menus, start gameplay, hear audio, save, exit, relaunch, and resume.

## Deliverables

- M3/M4 interactive build
- save schema and compatibility tests
- input/audio subsystem documentation

---

# Phase 9 — One complete campaign vertical slice

## Objective

Complete one bounded, representative route containing gameplay, combat, level transition, save/load, cutscene, and overlay changes.

Maintainer priority addition (2026-09-06): the next enabling workstream is
[Phase 9.5: Autonomous gameplay exploration](phase9-5-autonomous-exploration.md).
Begin it while Phase 9 is open to remove the manual-play bottleneck through
state-aware navigation, combat, branch exploration, and generated regressions.
It does not replace the Phase 9 exit gate or the Phase 10/11 campaign scope.
The restartable, coding-agent-neutral execution design for Phase 9.5 through
release is the [full-scope autonomy plan](autonomous-full-scope-execution.md);
it does not modify any acceptance or human-approval gate in this master plan.

## Tasks

- select a route that touches:
  - player control,
  - enemies,
  - weapons,
  - collision,
  - camera,
  - animation,
  - particles,
  - audio,
  - cutscene,
  - level transition,
  - save.
- record emulator and native replays.
- add canonical checkpoints.
- instrument all active overlays.
- fix first divergences only.
- build function-call corpora for the active subsystems.
- document every compatibility patch.

## Tests

- reset-to-slice-completion replay.
- save/restart mid-slice.
- death/retry.
- pause/unpause.
- controller disconnect.
- different RNG seeds where valid.
- all active overlay reloads.
- visual/audio references at key moments.
- repeated deterministic execution.
- fuzz around transitions.

## AI work

- continuously select smallest first-divergence tasks.
- generate function tests from captured calls.
- map unknown structs.
- cluster route failures.
- produce daily route-health report.

## Exit gate

The selected slice completes 100 consecutive deterministic runs with identical approved checkpoints and no crash.

## Deliverables

- first complete vertical-slice replay
- subsystem corpora
- route dashboard
- revised finishable-game estimate

---

# Phase 10 — Expand to a finishable single-player campaign

## Objective

Reach credits in compatibility mode.

## Tasks

- build the campaign manifest from game data, decomp knowledge, and verified guides.
- divide the campaign into short replayable segments.
- create checkpoint save states between segments.
- add every level, character route, boss, progression gate, collectible requirement, special mission, and final sequence required for completion.
- prioritize blockers by earliest route position.
- test alternate valid progression orders where the game permits them.
- maintain one clean end-to-end route.

## Tests

- one scenario per campaign segment.
- one full chained route.
- fresh new-game route.
- route from imported intermediate saves.
- death/retry at every boss.
- save/reload before and after every major transition.
- inventory/progression invariants.
- missing-collectible failure behavior.
- credits and post-game state.
- long-session audio and memory.
- all campaign overlays.

## AI work

- generate scenario manifests.
- convert human play recordings into deterministic scripts.
- minimize long replays into failing segments.
- identify untested functions reached by new content.
- generate branch-targeted function cases.

## Exit gate

Compatibility mode reaches credits reliably from a clean new game, and every segment can be run independently.

## Deliverables

- M5 finishable build
- complete campaign route manifest
- full campaign replay v1
- blocker count at zero

---

# Phase 11 — Complete modes, optional content, and robustness

## Objective

Move from “finishable” to “complete and robust.”

## Tasks

- test all local multiplayer modes.
- test every playable character and alternate route.
- test optional missions and content selected for release coverage.
- test all menus and settings.
- test all save slots/accessory paths.
- test game-over, quit, restart, and completion states.
- test resource exhaustion.
- test unusual but valid progression.
- test long-running sessions.
- test supported controller counts.
- resolve remaining overlay coverage gaps.

## Tests

- multiplayer scenario matrix.
- split-screen render matrix.
- optional-content segment suite.
- maximum/minimum inventory states.
- save-slot matrix.
- repeated campaign transitions.
- 8-hour soak.
- random input fuzz from safe checkpoints.
- full overlay coverage.
- no-test-flake repeated runs.

## AI work

- discover unvisited code from coverage.
- propose scenarios for uncovered overlays and branches.
- triage fuzz failures.
- generate stress cases.

## Exit gate

Every release-scoped game mode is covered by scenarios, no release-blocking overlay or branch is untested, and compatibility mode is stable.

## Deliverables

- M6 complete compatibility build
- coverage report
- robustness report
- zero release-blocking parity defects

---

# Phase 12 — Ultrawide and arbitrary aspect-ratio support

## Objective

Support modern aspect ratios without changing simulation.

## Tasks

- identify all projection construction.
- identify fixed viewport/scissor assumptions.
- identify culling tied to 4:3.
- identify 2D/HUD positioning.
- identify screen-space effects.
- identify cutscene masks and letterboxing.
- identify aim/reticle behavior.
- identify split-screen layouts.
- use RT64 extended commands where they provide cleaner integration.
- add user-selectable HUD safe-area behavior.

## Tests

For each release-scoped scene category:

- 4:3 compatibility.
- 16:9.
- 21:9.
- 32:9.
- split-screen combinations.
- cutscenes.
- menus.
- subtitles/text.
- aiming.
- framebuffer/depth effects.
- culling at screen edges.
- no mission/simulation hash change between aspect ratios.
- no HUD element outside configured safe bounds.

## AI work

- locate aspect constants.
- analyze projection math.
- group visual differences.
- generate screenshot manifests.
- propose minimal per-effect patches.

## Exit gate

All route scenarios pass at supported aspect ratios, simulation hashes match compatibility mode, and visual exceptions are documented and nonblocking.

## Deliverables

- M7 ultrawide build
- aspect-ratio patch ledger
- visual matrix report

---

# Phase 13 — High-frame-rate presentation and frame pacing

## Objective

Render smoothly at modern refresh rates while preserving original simulation behavior.

## Tasks

- keep fixed original simulation cadence initially.
- integrate RT64 visual interpolation.
- tag transforms and discontinuities as required.
- patch HUD/texture scrolling/effects that need high-rate metadata.
- reset interpolation on teleports, loads, camera cuts, and overlay transitions.
- improve input sampling without adding simulation updates.
- implement frame limiter and presentation settings.
- profile latency and pacing.

## Tests

- simulation hash equality across display rates.
- 30/60/90/120/144/165/240 Hz matrix.
- camera-cut reset.
- teleport/load reset.
- pause/unpause.
- slow motion or special effects.
- cutscene synchronization.
- audio synchronization.
- HUD animation.
- split-screen.
- long frame-pacing capture.
- no added RNG calls.
- no progression timing change.

## AI work

- identify frame-based counters.
- find transform construction sites.
- analyze interpolation artifacts from captures.
- generate rate-matrix reports.
- propose tagging patches.

## Exit gate

Approved scenarios run at all supported display rates with identical simulation checkpoints and acceptable visual/frame-pacing results.

## Deliverables

- M7 HFR build
- HFR invariant report
- latency/frame-pacing dashboard

---

# Phase 14 — Mod support and gradual readable-source adoption

## Objective

Expose a stable mod surface and replace generated code where doing so creates real value.

## Tasks

- define mod ABI/versioning.
- define exported symbols and events.
- create symbol package.
- create mod template.
- create safe lifecycle events:
  - boot,
  - menu,
  - level load,
  - pre/post simulation tick,
  - player spawn,
  - save/load,
  - render tagging.
- document compatibility guarantees.
- add mod sandbox/safety policy as appropriate.
- begin importing matched upstream functions when permission allows.
- maintain baseline generated aliases for differential tests.
- selectively clean up proven replacements.

## Tests

- mod load/unload.
- dependency/version errors.
- deterministic no-mod baseline.
- two mods with compatible hooks.
- conflicting mod behavior.
- save compatibility with mods disabled.
- exported-symbol stability.
- every readable replacement passes function differential tests.
- ABI compatibility across patch releases.

## AI work

- generate API documentation.
- generate example mods.
- propose event locations from call traces.
- translate matched functions into port patches.
- create differential corpora.
- review ABI changes.

## Exit gate

A documented mod template can add a small feature without modifying the core repository, and all readable replacements retain evidence-backed compatibility.

## Deliverables

- mod SDK v1
- symbol package
- replacement ledger
- example mods
- ABI policy

---

# Phase 15 — Release hardening and public launch

## Objective

Turn the engineering build into a supportable public release.

## Tasks

- finalize installer/archive packaging.
- finalize first-run ROM flow.
- finalize settings and saves.
- build Windows/Linux packages.
- test Steam Deck.
- add migration tests.
- add crash diagnostics.
- write user documentation.
- conduct dependency and license audit.
- verify no game assets are included.
- run release candidate soak.
- freeze high-risk changes.
- create rollback plan.

## Tests

- clean-machine installation.
- no-admin install where supported.
- Unicode and long paths.
- read-only and low-disk conditions.
- upgrade from previous candidate.
- save preservation.
- portable mode if offered.
- controller database.
- graphics backend fallback.
- full campaign compatibility route.
- full campaign enhanced route.
- multiplayer matrix.
- release artifact scan.
- dependency SBOM.

## AI work

- generate release notes.
- classify crash reports.
- check documentation consistency.
- automate package smoke tests.
- produce known-issues drafts.

## Human-only decisions

- final release approval.
- legal sign-off.
- severity classification.
- public statements and branding.

## Exit gate

Every release checklist item is complete, all blocking issues are closed, and the release candidate survives the defined soak period without a new blocker.

## Deliverables

- M8 public release
- signed/checksummed packages
- release notes
- support playbook
- post-release triage process

---

# 10. Function-by-function replacement path

## 10.1 Replacement is optional, not the initial finish line

A generated function that is correct and causes no maintenance problem may remain generated indefinitely.

Replace a function when at least one is true:

- It must change for a PC feature.
- It blocks deterministic testing.
- It is a high-value mod hook.
- It is performance critical.
- It contains a portability problem.
- It has already been matched and documented upstream.
- It is a central type/struct boundary whose readability unlocks many tasks.
- It repeatedly causes difficult bugs.

## 10.2 Replacement order

Recommended order:

1. Pure math and conversions.
2. Table lookups.
3. known SDK/libultra helpers.
4. simple data-structure operations.
5. camera/projection helpers.
6. input transformations.
7. save serialization helpers.
8. object/animation leaf functions.
9. isolated state-machine steps.
10. subsystem coordinators.
11. global loops.
12. scheduler, allocator, overlays, and anti-tamper only with strong need and evidence.

## 10.3 Exact adoption pipeline from matching decomp

When a function becomes matched upstream:

1. Pin the upstream commit.
2. Record source provenance.
3. confirm the function matches the original MIPS in the decomp.
4. confirm types and globals.
5. copy only if licensing permits.
6. compile it through the patch pipeline.
7. retain generated original under an alias.
8. capture real invocation corpus.
9. run exact differential tests.
10. run caller/subsystem tests.
11. run route smoke.
12. merge as a compatibility replacement.
13. optionally create a later cleanup PR.
14. contribute any corrected understanding upstream.

## 10.4 Cleanup after exact adoption

Do not combine exact adoption and cleanup.

PR A:

```text
matching upstream C -> native patch
```

PR B:

```text
typed cleanup/refactor with exact or approved semantic tests
```

This separation makes regressions attributable.

## 10.5 Replacement status ledger

```yaml
symbol: Camera_BuildProjection
generated_baseline: retained
upstream_match:
  status: matched
  commit: "<sha>"
native_replacement:
  status: exact
  commit: "<sha>"
cleanup:
  status: modernized
  feature_flag: widescreen_projection
tests:
  function_cases: 823
  branch_coverage: 100%
  replay_scenarios: 19
last_verified: "<commit>"
```

---

# 11. Full-game route and content coverage

## 11.1 Build the manifest from evidence

Do not rely on memory when enumerating the game.

Create a content inventory from:

- level and object tables.
- overlay tables.
- progression flags.
- save structures.
- menu/state tables.
- decomp symbols.
- verified player guides.
- human exploratory play.

Each entry receives:

```yaml
id: content-...
kind: level|boss|mission|menu|multiplayer|cutscene|save-path
required_for_credits: true|false
entry_conditions: [...]
exit_conditions: [...]
overlays: [...]
save_flags: [...]
scenario_ids: [...]
coverage_status: not_started|partial|complete
```

## 11.2 Route segmentation

A full route should be divided into segments short enough to replay and debug independently.

Recommended segment length:

- 30 seconds to 10 minutes of deterministic simulation.
- checkpoint before and after each major transition.
- no segment should cross multiple unrelated systems when avoidable.

## 11.3 Required route categories

### Boot and menus

- cold boot.
- title.
- file select.
- settings.
- new game.
- continue.
- controller configuration.
- multiplayer entry.
- credits/post-game.

### Campaign

- every required world/level.
- every required playable-character route.
- every required boss.
- every required collection/progression gate.
- every required special mission.
- final sequence.
- credits.
- post-completion save state.

### Failure and recovery

- death.
- retry.
- quit to menu.
- process exit.
- corrupted/missing save.
- controller disconnect.
- failed mission.
- full inventory/resource edge.

### Multiplayer

- each supported mode.
- 2/3/4-player configurations as applicable.
- each arena/map.
- match completion.
- rematch.
- quit.
- split-screen aspect matrices.

### Enhancements

Every compatibility scenario should be runnable with:

- 4:3/original presentation.
- ultrawide.
- HFR.
- ultrawide + HFR.
- modern input enabled/disabled.

## 11.4 Route health score

```text
route health =
  completed_segments / required_segments
  adjusted by:
    deterministic pass rate
    checkpoint parity
    visual pass rate
    audio pass rate
    overlay coverage
    save/restart coverage
```

Do not report only “percentage of functions decompiled.” Player-route health is the primary product metric.

---

# 12. Progress metrics and control dashboard

## 12.1 Milestone dashboard

| Milestone | Meaning | Primary gate |
|---|---|---|
| M0 | Upstream reproducible | Stable verified ELF |
| M1 | CPU recomp complete | All required generated code compiles |
| M2 | Deterministic boot | Stable scheduler/VI trace |
| M3 | First frame | Reference scene renders |
| M4 | First playable slice | Interactive saveable vertical slice |
| M5 | Finishable | Clean new game reaches credits |
| M6 | Complete compatibility | All release-scoped modes covered |
| M7 | Enhanced | Ultrawide and HFR pass matrices |
| M8 | Release | Packaging, soak, legal, and support complete |

## 12.2 Weekly metrics

### Build and static

- upstream commit age.
- toolchain pins.
- generated symbol count.
- unresolved direct calls.
- unresolved indirect calls.
- unclassified functions/data.
- overlay manifest completeness.
- RSP program coverage.
- stub count.
- instruction-patch count.

### Testing

- deterministic repeat pass rate.
- function corpus count.
- unique path signatures.
- function branch coverage.
- subsystem coverage.
- route segment completion.
- overlay execution coverage.
- save-matrix coverage.
- graphics-command baseline coverage.
- visual-reference coverage.
- audio-reference coverage.
- fuzz executions and unique reproducible defects.
- flaky test count.

### Product

- furthest clean route point.
- clean route completion rate.
- crash-free scenario count.
- save/restart pass rate.
- supported aspect-ratio scene count.
- supported refresh-rate scene count.
- supported platform package count.

### Quality

- open blocker count.
- first-divergence age.
- average files changed per PR.
- average task size.
- reverted AI patches.
- AI patches accepted without revision.
- tests added per production change.
- unresolved knowledge questions.
- technical-debt waivers.

## 12.3 Red flags that force refocusing

Pause feature work when:

- flaky tests > 0 for more than one workday.
- full compatibility route is red.
- unresolved stubs increase.
- instruction patches increase without removal plans.
- generated symbol drift is unexplained.
- nondeterministic repeats exceed the threshold.
- a route failure lacks a first-divergence report.
- more than two milestones are active.
- AI PRs regularly exceed scope budgets.
- golden updates outnumber compatibility fixes.
- enhancement patches change simulation hashes.
- private ROM-derived data appears in public CI.

---

# 13. Work-item and issue design

## 13.1 Issue types

- `milestone`
- `blocker`
- `reverse-engineering`
- `runtime`
- `overlay`
- `rsp`
- `graphics`
- `audio`
- `input`
- `save`
- `compatibility`
- `route`
- `test-infrastructure`
- `function-replacement`
- `ultrawide`
- `hfr`
- `modding`
- `platform`
- `legal`
- `documentation`

## 13.2 Required issue fields

```yaml
problem:
first_observed_in:
first_divergence:
affected_scenarios:
affected_symbols:
affected_overlays:
reproduction:
expected:
actual:
oracle:
current_evidence:
unknowns:
test_to_add:
scope_limit:
exit_criteria:
risk:
owner:
```

## 13.3 PR size policy

Default limits:

- One root cause.
- One subsystem.
- No more than 5 production files unless approved.
- No more than 500 production lines unless generated.
- Tests may be larger than implementation.
- Generated changes isolated from handwritten changes.
- No compatibility and enhancement code in the same PR.
- No golden update bundled with unrelated code.

These are defaults, not arbitrary hard limits. Exceptions require an explicit reason.

## 13.4 Bug-fix workflow

1. Add deterministic reproduction.
2. find first divergence.
3. identify owning subsystem.
4. add focused failing test.
5. fix smallest cause.
6. run focused/subsystem/replay tests.
7. add permanent corpus case.
8. update symbol/subsystem notes.
9. close only when the original route passes.

---

# 14. Staffing and ownership model

## 14.1 Minimum viable experienced team

A strong 3–5 person team could divide ownership as:

1. **Recomp/runtime lead**
   - N64Recomp configuration.
   - CPU execution.
   - overlays.
   - scheduler.
   - DMA.

2. **Graphics/RSP lead**
   - custom microcode.
   - RT64.
   - ultrawide.
   - HFR.
   - visual tests.

3. **Game/reverse-engineering lead**
   - symbols.
   - structs.
   - decomp synchronization.
   - function replacement.
   - progression.

4. **Test/automation lead**
   - deterministic runtime.
   - replays.
   - differential harness.
   - fuzzing.
   - CI.

5. **Platform/product lead**
   - input.
   - audio.
   - saves.
   - UI.
   - packaging.
   - release.

Roles can overlap, but every critical area needs a named owner.

## 14.2 Solo or two-person mode

A solo developer should enforce stronger WIP limits:

- One active milestone.
- One active blocker.
- No mod support before finishable.
- Windows or Linux first, not both simultaneously.
- Compatibility mode before enhancements.
- AI used for parallel analysis, not parallel uncontrolled code changes.
- Weekly full-route health check.
- Stop large refactors when route progress stalls.

## 14.3 Human review classes

| Risk | Examples | Approval |
|---|---|---|
| Low | docs, pure helper, test tooling | independent AI or one human |
| Medium | function replacement, renderer tag | one human maintainer |
| High | scheduler, overlay loader, save format, instruction patch | two maintainers where possible |
| Restricted | legal, golden policy, release, data distribution | designated human owner |

---

# 15. Planning ranges and re-estimation gates

These are planning ranges, not commitments. The unknown graphics/RSP and overlay work can move them substantially.

## 15.1 One experienced developer, serious part-time

- Reproducible foundation and feasibility: 1–3 months.
- First deterministic native execution/boot progress: 2–6 months.
- First playable vertical slice: 6–12 months.
- Finishable compatibility build: 12–24 months.
- Complete, polished ultrawide/HFR release: 24–48 months.

## 15.2 One experienced developer, near full-time

- Feasibility and first native execution: 1–3 months.
- First playable vertical slice: 3–8 months.
- Finishable compatibility build: 9–18 months.
- Polished enhanced release: 15–30 months.

## 15.3 Three-to-five-person experienced team

- Feasibility and first native execution: 1–2 months.
- First playable vertical slice: 2–6 months.
- Finishable compatibility build: 6–12 months.
- Complete enhanced public beta: 9–18 months.
- Polished release: 12–24 months.

## 15.4 Mandatory re-estimation points

Re-estimate after:

1. Phase 3 feasibility report.
2. first stable VI/scheduler trace.
3. first correct rendered gameplay frame.
4. first complete vertical slice.
5. first route to credits.
6. first ultrawide/HFR content matrix.

Do not keep an old estimate after evidence changes.

## 15.5 What AI changes

AI can materially reduce time spent on:

- code explanation.
- boilerplate.
- instrumentation.
- test generation.
- trace analysis.
- documentation.
- repetitive leaf-function work.

AI does not eliminate:

- unknown hardware behavior.
- deterministic scheduler design.
- legal decisions.
- full-route validation.
- visual judgment.
- difficult custom microcode.
- obscure late-game state interactions.

The project should measure actual AI throughput after the first 20 task packets and revise staffing assumptions from data.

---

# 16. Risk register

| Risk | Impact | Early detection | Mitigation |
|---|---|---|---|
| Custom DKR graphics behavior unsupported | Critical | Phase 3 RSP/RT64 spike | upstream RT64 work, RSP recomp, custom integration, fallback |
| RSP overlays or unsupported microcode pattern | Critical | complete microcode inventory | upstream N64Recomp contribution or alternate execution path |
| Dynamic overlay/runlink behavior | Critical | overlay manifest and load traces | explicit relocation tables, deterministic lookup tests |
| Anti-tamper/trap paths | High | boot trace and static inventory | reproduce faithfully, document, avoid blind stubs |
| Controller Pak/save gap | High | save-device spike | implement native accessory layer and full matrix |
| Scheduler nondeterminism | High | repeat test mode | deterministic scheduler/journal |
| Timing tied to VI | High | cross-rate simulation hashes | fixed simulation and interpolation |
| AI produces plausible wrong rewrites | High | differential harness | bounded tasks, independent review, exact oracle |
| Test corpus misses rare states | High | coverage and fuzzing | route expansion, branch targeting, permanent regression corpus |
| Visual goldens vary across GPUs | Medium | multi-run reference captures | command-stream oracle, pinned reference runner, explicit tolerances |
| Public test artifacts contain game data | High | artifact scanner | local/private regeneration, no-upload policy |
| Upstream symbols drift | Medium | sync diff | pinned commits, provenance, migration files |
| Upstream license unclear | Critical | Phase 0 review | maintainer permission, legal review, local-path integration |
| Tool upstream changes break build | Medium | scheduled sync dry run | pinned dependencies, controlled upgrades |
| Port becomes enhancement-first | High | route dashboard | compatibility gate and WIP limits |
| Excessive instruction patches | Medium | patch ledger | prefer function overrides, removal plans |
| Full route too long to debug | Medium | segment design | short checkpointed scenarios |
| Test suite becomes too slow | Medium | CI timing | tiered lanes, corpus minimization, sharding |
| Mod ABI freezes bad interfaces | Medium | delay mod v1 | expose events after stable subsystem understanding |
| Generated code build time is excessive | Medium | build metrics | caching, unity/grouped build if supported, distributed CI |
| Original bug vs port bug confusion | Medium | emulator oracle | compatibility mode and intentional-change proposals |

Every risk has:

- owner.
- evidence.
- next experiment.
- fallback.
- review date.
- closure criteria.

---

# 17. Initial 30/60/90-day execution sequence

This is a sequencing template. It should be adjusted after Phase 0 and team availability.

## First 30 days

### Governance

- Contact upstream maintainer.
- settle repository boundaries.
- inventory licenses.
- create ROM and corpus policy.

### Reproducibility

- build the US decomp.
- verify ROM and ELF.
- pin tools.
- generate static reports.

### New repository

- create CMake shell.
- create CI.
- add test framework.
- add schemas and patch ledger.
- add public/private corpus separation.

### Feasibility start

- create first N64Recomp config.
- enumerate CPU sections.
- enumerate overlays.
- inventory RSP programs.
- inventory save devices and direct hardware access.

### Day-30 gate

A written report lists every critical unknown, and the team can reproducibly produce the upstream ELF.

## Days 31–60

### Static recomp

- generate CPU functions.
- resolve symbol/config failures.
- compile generated functions.
- construct overlay lookup tables.

### Test kernel

- implement cloneable world.
- virtual time.
- event journal.
- deterministic function replay.
- first-divergence report.

### Risk spikes

- execute representative RSP task.
- prove renderer path.
- prove one overlay relocation.
- prove one save-device operation path.
- prove trap/anti-tamper handling strategy.

### Day-60 gate

Generated CPU code compiles, selected functions replay deterministically, and no unbounded architecture blocker remains.

## Days 61–90

### Boot

- run entry point.
- bring up queues/threads.
- implement PI DMA.
- reach stable VI activity.
- compare boot events with emulator.

### Graphics

- integrate RT64.
- submit first graphics task.
- render first frame or produce a bounded blocker report.

### Automation

- ROM-backed secured CI.
- nightly repeat tests.
- AI task loop.
- dashboard.

### Day-90 gate

One of the following must be true:

1. The native port reaches stable VI and a first frame, or
2. The team has a precise, evidenced blocker with a validated fallback or upstream work plan.

If neither is true, stop feature work and revisit architecture.

---

# 18. Release acceptance checklist

## Compatibility

- [ ] Supported ROM is validated by hash.
- [ ] Clean boot is reliable.
- [ ] Title and menus work.
- [ ] New game works.
- [ ] Full campaign reaches credits.
- [ ] All required progression paths work.
- [ ] All required bosses work.
- [ ] All release-scoped overlays are exercised.
- [ ] Save/create/load/restart works.
- [ ] Save failure modes are handled.
- [ ] Audio remains synchronized.
- [ ] All release-scoped local multiplayer modes work.
- [ ] No release-blocking deterministic crash.
- [ ] Compatibility route checkpoints are stable.
- [ ] No flaky release test.

## Ultrawide

- [ ] 16:9 matrix passes.
- [ ] 21:9 matrix passes.
- [ ] 32:9 matrix passes or documented supported maximum.
- [ ] Projection is correct.
- [ ] Culling is correct.
- [ ] HUD remains usable.
- [ ] Menus and text remain usable.
- [ ] Cutscenes remain usable.
- [ ] split-screen remains usable.
- [ ] Simulation hashes match 4:3 compatibility mode.

## High frame rate

- [ ] 60 Hz passes.
- [ ] 120 Hz passes.
- [ ] 144 Hz passes.
- [ ] 165 Hz passes where supported.
- [ ] 240 Hz passes where supported.
- [ ] Frame pacing meets target.
- [ ] Camera cuts reset interpolation.
- [ ] Teleports/load transitions reset interpolation.
- [ ] HUD/effects are handled.
- [ ] Audio remains synchronized.
- [ ] Simulation hashes are display-rate independent.
- [ ] RNG call counts remain unchanged.

## Platform

- [ ] Windows clean-machine test.
- [ ] Linux clean-machine test.
- [ ] Steam Deck test.
- [ ] graphics backend fallback.
- [ ] controller database.
- [ ] long/unicode path tests.
- [ ] settings migration.
- [ ] save migration.
- [ ] package checksums.
- [ ] no proprietary assets in packages.

## Engineering

- [ ] All dependency commits pinned.
- [ ] SBOM produced.
- [ ] licenses reviewed.
- [ ] patch ledger complete.
- [ ] instruction patches documented.
- [ ] golden changes approved.
- [ ] no secrets or private corpus in artifacts.
- [ ] source and build instructions verified.
- [ ] crash diagnostics redacted.
- [ ] rollback release prepared.
- [ ] known issues published.

---

# 19. Appendices

## Appendix A — Example scenario manifest

```yaml
schema: 1
id: campaign-segment-001
title: "New game to first controlled gameplay"
category: campaign
rom:
  version: us
  sha1: 493ced9008dbe932d6e91179b68e8630cf23a023
build:
  decomp_commit: "<sha>"
  recomp_commit: "<sha>"
mode:
  compatibility: true
  aspect_ratio: "4:3"
  display_hz: 30
start:
  reset: true
input:
  file: "private/campaign-segment-001.inputs"
clock:
  vi_rate: original
  deterministic_schedule: true
checkpoints:
  - id: title
    trigger:
      event: title_menu_ready
    hashes:
      core: "..."
      overlay: "..."
  - id: first_control
    trigger:
      event: player_control_enabled
    hashes:
      core: "..."
      rng: "..."
expect:
  end_event: player_control_enabled
  max_ticks: 30000
  no_unhandled_runtime_calls: true
  no_audio_underruns: true
artifacts:
  graphics_commands: true
  audio_commands: true
  screenshots:
    - checkpoint: title
    - checkpoint: first_control
```

## Appendix B — Example function capture format

```yaml
schema: 1
symbol: squadsGetClosestPlayer
address: 0x80000000
overlay:
  id: 146
  load_base: 0x...
call:
  index: 78122
  tick: 24109
  caller: overlay146_func_...
context:
  registers_file: "private/case-001.ctx"
memory:
  page_size: 4096
  pages_file: "private/case-001.pages.zst"
runtime:
  virtual_time: 24109
  rng_state: "..."
  event_journal_prefix: "private/case-001.events"
expected:
  context_file: "private/case-001.expected.ctx"
  dirty_pages_file: "private/case-001.expected.pages.zst"
  events_file: "private/case-001.expected.events"
path_signature: "..."
public:
  manifest_hash: "..."
  body_available: false
```

## Appendix C — Example first-divergence report

```text
Scenario: campaign-segment-014
Build: 9f8...
First divergent tick: 184220
First divergent call: Camera_Update @ call 1284
Active overlay: 73 @ 0x...
First differing subsystem: camera
First differing RDRAM page: 0x803A0000
First differing bytes: +0x128..+0x133
Expected RNG calls: 2238
Actual RNG calls: 2238
Previous runtime event: VI retrace
Feature flags: widescreen_projection=true; hfr=false
Likely owner: graphics/camera
Minimal replay: artifacts/min-014
```

## Appendix D — Example intentional-behavior proposal

```yaml
id: JFG-BEHAVIOR-0007
title: "Allow HUD safe-area anchoring on ultrawide"
original_behavior: "HUD uses fixed 4:3 pixel positions"
new_behavior: "HUD can remain centered in a configurable 16:9 safe area"
compatibility_mode_changed: false
enhanced_mode_only: true
save_impact: none
simulation_impact: none
tests:
  - hud-4x3
  - hud-16x9
  - hud-21x9
  - hud-32x9
  - campaign-route-core-hash
approvals:
  design: required
  graphics: required
```

## Appendix E — AI prompt: reverse-engineering analysis

```text
You are analyzing one bounded Jet Force Gemini function.

Do not write production code yet.

Inputs:
- generated N64Recomp C
- MIPS disassembly
- upstream decomp source if legally permitted
- symbol card
- callers/callees
- captured invocation summaries
- first-divergence report

Produce:
1. likely purpose
2. explicit and hidden inputs
3. outputs and side effects
4. globals and memory ranges read/written
5. RNG/timing/overlay dependencies
6. pointer aliasing risks
7. integer/float/undefined-behavior risks
8. proposed typed signature
9. tests required for every branch
10. unknowns that require instrumentation
11. smallest safe implementation scope

Do not claim certainty without evidence.
Do not alter tests or golden outputs.
Stop if an unknown memory dependency prevents a bounded implementation.
```

## Appendix F — AI prompt: first-divergence triage

```text
Analyze the attached deterministic first-divergence bundle.

Prioritize the earliest observable difference, not the later crash.

Return:
1. the most likely owning subsystem
2. the smallest set of symbols that could cause the difference
3. evidence for each hypothesis
4. one instrumentation change that best distinguishes hypotheses
5. one focused regression test
6. a stop condition
7. whether this should be a code-fix task or a research task

Do not propose a broad refactor.
Do not weaken comparison thresholds.
Do not update golden outputs.
```

## Appendix G — AI prompt: independent review

```text
Review this patch independently.

You receive:
- task packet
- diff
- tests
- coverage
- replay results
- divergence reports
- symbol cards

Check:
- scope compliance
- hidden globals
- pointer aliasing
- side-effect order
- RNG changes
- timing changes
- overlay lifetime
- save compatibility
- undefined behavior
- exact-vs-tolerant comparisons
- weakened tests
- missing callers or branches
- legal provenance

Reject the patch if evidence is insufficient even when the code looks plausible.
```

## Appendix H — Recommended first issue backlog

1. Clarify upstream reuse/license.
2. Reproduce US decomp build.
3. Pin upstream/toolchain versions.
4. Validate `build/jfg.us.elf`.
5. Export complete CPU symbol inventory.
6. Build overlay manifest.
7. Build RSP/microcode manifest.
8. Build save-device/accessory manifest.
9. Inventory direct RCP/kseg/TLB accesses.
10. Inventory trap and anti-tamper paths.
11. Create initial `jfg.us.toml`.
12. Generate first 100 CPU functions.
13. Compile generated-function smoke library.
14. Implement cloneable recomp context/RDRAM world.
15. Implement virtual clock.
16. Implement deterministic event journal.
17. Implement function differential runner.
18. Implement first-divergence reporter.
19. Recompile full CPU symbol set.
20. Prove one relocatable overlay.
21. Prove one graphics RSP task.
22. Prove one audio RSP task.
23. Reach original entry point.
24. Reach first thread creation.
25. Reach first VI event.
26. Integrate RT64 shell.
27. Render first boot/title frame.
28. Add first emulator/native boot replay.
29. Add first menu input replay.
30. Add first save/restart test.

---

# 20. Primary technical references

The plan is based on the following primary project documentation as available on 2026-08-03.

[^jfg-decomp]: [Ryan-Myers/Jet-Force-Gemini](https://github.com/Ryan-Myers/Jet-Force-Gemini) — current decomp repository, US/kiosk build setup, DKR-engine relationship, `decomp.yaml`, symbol and overlay files.

[^jfg-makefile]: [Jet Force Gemini Makefile](https://github.com/Ryan-Myers/Jet-Force-Gemini/blob/master/Makefile) — matching compiler configuration and the `F3DDKR_GBI` define.

[^n64recomp]: [N64Recomp/N64Recomp](https://github.com/N64Recomp/N64Recomp) — static recompilation model, ELF metadata, overlay handling, patch configuration, single-file patch output, and RSP recompilation.

[^modern-runtime]: [N64Recomp/N64ModernRuntime](https://github.com/N64Recomp/N64ModernRuntime) — ultramodern/librecomp runtime responsibilities and supported libultra-facing services.

[^rt64]: [rt64/rt64](https://github.com/rt64/rt64) — native-port renderer, arbitrary aspect-ratio support, high-frame-rate interpolation, extended commands, and deferred frame architecture.

[^zelda-recomp]: [Zelda64Recomp/Zelda64Recomp](https://github.com/Zelda64Recomp/Zelda64Recomp) — mature N64Recomp port architecture, RT64 integration, enhancements, patches, and mod support.

[^zelda-syms]: [Zelda64Recomp/Zelda64RecompSyms](https://github.com/Zelda64Recomp/Zelda64RecompSyms) — precedent for a separate symbol repository tied to a specific decomp commit.

---

## Final operating summary

The project should optimize for a continuous sequence of proven, playable states:

```text
reproducible ELF
    ->
complete generated CPU code
    ->
deterministic test kernel
    ->
stable boot
    ->
first frame
    ->
first playable slice
    ->
finishable compatibility route
    ->
complete game-mode coverage
    ->
ultrawide
    ->
high-frame-rate presentation
    ->
mods and readable replacements
    ->
polished release
```

At every step:

```text
small task
    ->
failing or missing test
    ->
minimal implementation
    ->
differential evidence
    ->
route evidence
    ->
independent review
    ->
merge
```

That process is the realistic way to use AI aggressively without allowing it to carry the project far in a plausible but incorrect direction.
