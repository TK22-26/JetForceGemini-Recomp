# Development progress

[Build status](https://github.com/TK22-26/JetForceGemini-Recomp/actions/workflows/ci.yml)
checks source and tests without a ROM. Start with [getting started](getting-started.md)
to play, or [known issues](known-issues.md) to check a problem.

## Playable preview

The Windows preview provides native rendering and audio, keyboard and XInput
controls, persistent saves, and a setup launcher. A maintainer playtest completed
Goldwood and reached SS Anubis. Full campaign completion, all original modes,
and original-console accuracy remain unverified.

We need reports of crashes, freezes, progression blockers, save failures, and
incorrect controls, graphics, or audio across more PCs. Follow the
[playtesting guide](playtesting.md); successful sessions do not need reports.

## Engineering milestones

These records describe bounded acceptance results at their recorded revisions.
They do not certify every later build or close broader roadmap requirements.

| Milestone | Recorded result | Reference |
|---|---|---|
| Reproducible upstream builds | Two environments, repeated deterministic builds | [Build evidence](upstream/phase1-build-evidence.json) |
| CPU and overlay feasibility | G2 aggregate records a go decision | [CPU/overlay evidence](feasibility/phase3-cpu-overlay-evidence.json) |
| CPU generation and link | Phase 4 completion recorded | [Signed aggregate](../evidence/phase4-completion.json) |
| Deterministic test kernel | Phase 5 completion recorded | [Signed aggregate](../evidence/phase5-completion.json) |
| Native boot | Local Phase 6 M2 completion recorded | [Signed aggregate](../evidence/phase6-completion.json) |
| First rendered scenes | Phase 7 acceptance recorded | [Scene summary](../evidence/phase7-completion.json) |
| Interactive runtime | Phase 8 acceptance recorded | [Interactive summary](../evidence/phase8-completion.json) |
| Complete campaign slice | Open | [Acceptance tracker](planning/phase9-acceptance.md) |
| Automated exploration and repair | Partial capabilities; acceptance open | [Automation plan](planning/autonomous-full-scope-execution.md) |

The broader gates still require fifty deterministic boot repeats and ten
reference captures; earlier three-run evidence does not satisfy those counts.
A hundred startup repeats do not establish a hundred complete gameplay slices.

## Remaining work

- Complete the selected campaign slice and its recovery/parity coverage.
- Verify a finishable campaign, original multiplayer, and optional content.
- Improve setup reliability and diagnostics for playtest reports.
- Add ultrawide, smoother presentation, and mod interfaces against a stable
  compatibility baseline.
- Validate packaging, hardware coverage, and release readiness.

The [roadmap](planning/JFG_RECOMP_MASTER_PLAN.md) defines the goals and gates.
The [runtime research summary](development/runtime-research.md) records current
investigation limits. No milestone beyond the interactive runtime is declared
complete by this page.
