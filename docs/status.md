# Project status

This page describes the repository as reviewed on 2026-11-01. Release availability is recorded in
[version qualification](releases/qualification-1.4.0.md); source changes on `develop` are not automatically released.

| State | What is established |
|---|---|
| Published v1.4.0 | Playable Windows x64 bundle; supported US ROM import; campaign, original local multiplayer, Modern controls for P1-P4, cutscene skipping, Floyd controls and recorded camera/rendering fixes |
| Accepted locally, unreleased | The replacement standalone Audio settings window opens immediately in the owner's review. The old delay's underlying cause remains unknown. See the issue index and changelog for the exact local scope. |
| Candidate or still open | Post-release controls additions and reporter-specific failures retain the verification status of their individual issue records. Builds and component checks are not owner acceptance. |
| Corrected reference finding | Leaving Walkway has no music on the owner's NTSC N64; the PAL ROM does have music in EmuHawk. The US Walkway override is removed from source and rebuilt; scoped native replays pass. Older previews retain the superseded insertion. |
| Regional foundation, native work open | PAL/JP metadata reconstructs both original ROMs and all 155 overlays per region exactly. SDK identification, generation, host integration and gameplay qualification remain; neither region is a supported Play profile. |

Use [known issues](known-issues.md) for player-facing limitations, [issue records](development/issues/README.md)
for cause/evidence/status, and [original-game findings](original-game/README.md) for hardware bugs and region differences.
The recorded campaign run used infinite-health/enemy auto-kill testing mods and a save with all Tribals
unlocked. That establishes the recorded playthrough, not exhaustive original-console parity.

## Engineering milestones

Records describe bounded results at their recorded revisions; they do not
certify later builds or close broader roadmap gates. See the
[evidence guide](../evidence/README.md).

| Milestone | Recorded result | Reference |
|---|---|---|
| Reproducible upstream builds | Two environments, repeated deterministic builds | [Phase 1 aggregate](upstream/phase1-build-evidence.json) |
| CPU and overlay feasibility | G2 go decision | [Feasibility record](feasibility/README.md) |
| CPU generation and link | Phase 4 complete (signed) | [Phase 4 aggregate](../evidence/phase4-completion.json) |
| Deterministic test kernel | Phase 5 complete (signed) | [Phase 5 aggregate](../evidence/phase5-completion.json) |
| Native boot | Phase 6 M2 complete (signed) | [Phase 6 aggregate](../evidence/phase6-completion.json) |
| First rendered scenes | Phase 7 accepted | [Phase 7 summary](../evidence/phase7-completion.json) |
| Interactive runtime | Phase 8 accepted | [Phase 8 summary](../evidence/phase8-completion.json) |
| Original timing in the unified runtime | Opening and Quarry runs with zero audio underruns | [Timing validation](../evidence/unified-original-timing-validation.json) |
| Deterministic campaign slice (G6) | Open | [Phase 9 tracker](planning/phase9-acceptance.md) |
| Automated exploration and repair | Partial capabilities; acceptance open | [Exploration plan](planning/phase9-5-autonomous-exploration.md) |

The formal gates are stricter than a manual playthrough: G4 needs fifty
deterministic boot repeats and ten reference captures, and G6 needs a hundred
consecutive deterministic completions of a slice. The only hundred-run batch
so far is a 1,794-retrace startup prefix, not a gameplay slice.

## Automated gameplay

Earlier work demonstrated startup, checkpoint restoration, generated
navigation, selected destinations and bounded combat/death/retry cases; ten
seeded jobs varied their objectives. The launcher's [navigation mod](features/navigation-mod.md)
adds live room-to-room exploration, jumps, chests and NPC rewards. None of this
proves general varied-path exploration, native snapshot resume or complete
native/reference parity. The recorded original-OS comparison matched 1,908
consecutive selected update states ([boundary record](planning/phase9-execution-frontier-1909.md)).

## Remaining work

- Complete the deterministic campaign slice and its recovery and parity coverage.
- Extend formal G7/reference-parity evidence beyond the retained campaign run.
- Resolve documented performance/camera issues and improve support diagnostics.
- Continue physical-device and fresh-PC compatibility testing of modern controls.
- Extend qualification of ultrawide, high-refresh presentation and optional Mods across
  more encounters and devices; these features already exist with documented limits.

The [roadmap](planning/JFG_RECOMP_MASTER_PLAN.md) defines the goals and gates.
