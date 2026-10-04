# Development guide

For playing the preview, start with [getting started](../getting-started.md).
For reporting a problem, use [playtesting](../playtesting.md).

## Build and test

- [ROM build setup](rom-bootstrap.md) produces the playable Windows runtime.
- [Development setup](setup.md) builds and tests source without a ROM.
- [Launcher guide](launcher.md) covers setup, controls, saves, and support reports.
- [Contributing](../../CONTRIBUTING.md) describes focused pull requests and validation.
- [Test quarantine](../tests/quarantine.md) records the Linux runner exception.

## Source layout

| Location | Purpose |
|---|---|
| `src/`, `include/jfg/` | Native runtime, boot, rendering, audio, and host interfaces |
| `launcher/windows/` | Windows launcher and setup workflow |
| `scripts/` | Build orchestration, validation, and diagnostic tools |
| `scripts/autonomy/` | Guarded job scheduling and execution |
| `tests/` | Source tests and synthetic fixtures |
| `config/`, `schemas/`, `examples/` | Versioned contracts and validation fixtures |
| `patches/` | Maintained dependency patches and upstream notices |
| `evidence/` | Milestone summaries and signatures |
| `docs/planning/` | Current roadmap and acceptance requirements |

Generated output, dependencies, local inputs, and job results use ignored
directories. Files under `examples/` are used by validation; phase-numbered
scripts may still be part of the public build.

## Engineering references

- [Recent gameplay fixes](boot-gameplay-fix.md).
- [Runtime research summary](runtime-research.md).
- [Automation operation and boundaries](automation.md).
- [Execution profiles](../adr/0002-execution-profiles.md).
- [Dependency architecture](../adr/0003-phase4-dependency-architecture.md).
- [Progress](../dashboard.md) and [plans](../planning/README.md).

Automated work must follow [AGENTS.md](../../AGENTS.md). Historical experiments
are available through [Git history](../history.md).
