# Jet Force Gemini repository handoff

Prepared 2026-10-01 for a new contributor or interested playtester. This checkout
preserves the current development source; it does not include a ready-to-run
game package. For playtesting, follow the
[ROM-to-build prototype](rom-bootstrap.md) and [launcher guide](launcher.md).
The first build needs developer tools and your own supported ROM.

## What works and what remains open

The [dashboard](../dashboard.md) records completed local milestones through
Phase 8: native boot, rendering, live input, audio, and persistence. Recorded
Goldwood play exercises control, combat, death/retry, and transitions.

The [Phase 9 tracker](../planning/phase9-acceptance.md) is still open. Neither a
complete campaign slice nor a finishable campaign is accepted. The 100-run
startup result is not 100 completed gameplay routes. Timing and selected-state
differences from the emulator reference remain under investigation; the
[latest documented prefix](../planning/phase9-execution-frontier-1909.md)
matches selected state through update 1908, with the first mismatch at 1909.
Historical milestone evidence does not certify every later working-tree change.

## Build from a source checkout

Use `launcher-preview` for the ROM-to-build prototype, or `main` for the initial
public snapshot. Record `git rev-parse HEAD`
when reporting a result. This repository begins with a fresh history and omits
five emulator diagnostic patches. Historical commit references and local
evidence describe the private development repository and are not public refs.
The omitted patches also prevent the associated oracle producer and identity
tests from running without additional maintainer-local inputs.

Requirements are Git, Python 3.11 or newer, CMake 3.20 or newer, and a C++20
compiler. Windows uses Visual Studio 2022 with the C++ workload and its developer
shell. Linux presets use Ninja. Install the pinned validation dependency in a
local virtual environment using [development setup](setup.md).

```powershell
python -m pip install --require-hashes -r requirements-dev.lock.txt
python scripts/check_repository_hygiene.py --history
python scripts/validate_project.py
cmake --preset windows-msvc
cmake --build --preset windows-msvc
ctest --preset windows-msvc
```

On Linux, substitute the `linux` configure, build, and test presets. The Python
suite is `python -m unittest discover -s tests -p "test_*.py"`. Automated agents
must run builds and tests through the guarded supervisor as described below.
These commands describe the human development workflow, not a guard bypass.

The resulting `jfg` executable is a host shell. Supplying a ROM does not turn
that target into the game. Public CI validates source and synthetic fixtures;
it does not download a ROM or certify a playable build. See
[test quarantine](../tests/quarantine.md) for the existing Linux CI exception.

## Preparing an actual playtest

Each tester must supply their own supported North American retail ROM. Keep it
outside Git, in an ignored local directory or an explicit external location.
Do not attach it to an issue or send it with a source checkout.

The playable target is `jfg-native-boot` with the live runtime enabled. The
[bootstrap recipe](rom-bootstrap.md) downloads pinned dependencies, extracts
your ROM, builds a matching ELF, recovers the required OS symbol metadata,
generates CPU/audio code, and compiles the Windows runtime. The launcher's
**Build from ROM** button invokes that recipe. It needs no maintainer-generated
ELF, overlay layout, CPU output, audio output, or save file.

The existing [manual launcher](../../scripts/launch_phase9_manual_test.ps1)
expects a particular private build layout and existing Flash/Controller Pak
files. It also configures local crash dumps and a scheduled task. Treat it as a
maintainer diagnostic tool. Use the new launcher for this prototype.

Before asking someone to play, select and identify the executable and runtime
profile, establish local input generation or an approved binary handoff, verify
runtime dependencies on a clean machine, and confirm fresh-profile launch and
save/relaunch. Include known issues and a bounded test objective such as reaching
Goldwood and reporting control, graphics, audio, and save behavior. Binary or
generated-output distribution is a separate unresolved project decision.

Recorded keyboard bindings are:

| Keys | Action |
| --- | --- |
| W, A, S, D | Analog movement |
| Shift | Full analog-stick magnitude while moving |
| Space or Z | N64 A / jump |
| X / C | N64 B / N64 Z |
| Enter | Start |
| Q / E | L / R |
| I, J, K, L | C buttons |
| Arrow keys | D-pad |
| Escape | Exit |

These are the bindings recorded in the [Phase 8 contract](../planning/phase8-acceptance.md).

## Reporting a problem

Report the source commit or supplied build identifier, operating system, GPU,
input device, reproduction steps, expected behavior, actual behavior, and whether
it repeats. Describe the scene and symptom in text. Review diagnostics before
sharing: raw traces, saves, screenshots, audio, memory/crash dumps, personal
paths, and ROM-derived content must stay out of GitHub under the current
[data policy](../legal/rom-and-assets-policy.md). Use the
[security process](../../SECURITY.md) for vulnerabilities or private-data exposure.

## Continuing development

Start with [the scope assessment](../planning/JFG_RECOMP_SCOPE_ASSESSMENT.md),
[the Phase 9 tracker](../planning/phase9-acceptance.md), and
[the source baseline handoff](../planning/autonomy-source-baseline-handoff.md).
The latest work includes CPU/device timing diagnostics, instruction observation,
reference microcases, renderer synchronization, and bounded repair automation.
Private evidence links identify maintainer-local records, not downloadable assets.

Keep the production anti-stall guard enabled at all times, including after a
restart, context compaction, or Goal resume. Before autonomous investigation
execution, recover the existing operational ledger, investigation state, and
budget. Experiments, builds, replays, and coding workers must execute through the
guarded supervisor. Read-only status checks and foreground orchestration do not
replace guarded execution.

At the start of this handoff, the production guard was enabled and these
investigations were shelved:

| Investigation | Charged attempts | Charged seconds | Stop reason |
| --- | ---: | ---: | --- |
| native-prefix-parity | 6 | 1400.044 | No verified progress within allowance |
| review-regression-evidence | 2 | 1329.281 | No verified progress within allowance |
| guard-continuation-maintenance | 6 | 3057.509 | Single authorized bootstrap ended |

These are historical observations, not new execution permission. Re-read the
ledger for current status. Never disable the production guard, reset counters,
rename or re-root the same investigation for a new allowance, or execute directly
after a denial. An exhausted investigation must stop. The publication task does
not reopen gameplay or maintenance work. Isolated fixture ledgers may disable the
guard for tests; the operational ledger may not.

The ledger and its evidence remain ignored local data. A clone does not carry
them. Do not create a fresh ledger to continue an exhausted investigation on
another machine. Coordinate preservation of the existing accounting with the
maintainer before resuming that work. See [AGENTS.md](../../AGENTS.md),
[the guard contract](../planning/autonomy-progress-guard.md), and
[continuation rules](../planning/autonomy-guard-continuation.md).

## Publication and licensing

The owner requested preparation for public source visibility on 2026-10-01.
The [publication handoff](../governance/publication-handoff.md) records the
checks and remaining blockers. Public visibility is distinct from an
open-source license or a playable release. The current [license](../../LICENSE)
retains all rights; third-party terms and game rights remain separate.
