# Foundation Dashboard

This dashboard records evidence, not intent.

| Gate | State | Required evidence |
|---|---|---|
| Phase 0 governance | Complete | `docs/governance/phase0-decisions.md` records the deferred upstream request, no-copy boundary, initial license decision, superseded by MIT on 2026-10-01, corpus owner, and manual branch controls |
| Phase 1 reproducible upstream | Complete | Ubuntu 22.04/24.04 each produced two deterministic verified builds; `docs/upstream/phase1-build-evidence.json` validates the cross-environment result |
| Phase 2 repository skeleton | Complete | ROM-free policy validation plus Windows/Linux Debug and Release build/CTest lanes pass |
| Phase 3 feasibility / G2 | Complete — go | The assembled G2 evidence pair passes trusted validation with zero errors: all fourteen requirement slots close with pinned producer binaries, reproducible build attestations, reviewed source provenance, fresh-nonce dispatcher re-execution of every executable slot, and the human-accepted dependency decision; the public gate records `"decision": "go"` |
| Phase 4 CPU generation / G3-M1 | Complete | `evidence/phase4-completion.json` is the signed completion manifest: the eleven-execution G3 product matrix passed its pinned production audits, the G2 CPU case binds the exact G3 product projection, both trusted private validators and the pin cross-checks passed during finalization, and the manifest carries the anonymous project signature; generated bodies and detailed ledgers remain ignored |
| Phase 5 deterministic test kernel | Complete | `evidence/phase5-completion.json` is the signed completion manifest under `docs/planning/phase5-acceptance.md`: kernel v0 (`jfg-test`, replay/state-hash/first-divergence formats v1) is exercised by `jfg.testkernel*` CTests plus the corpus-privacy policy test, the pinned schema and zero-tolerance policy are bound by digest, and twenty risk-weighted boundary functions from the Phase 4 generated set captured, replayed bit-identically across processes, and localized seeded one-byte faults; capture blobs and the ledger remain ignored and participate by digest only |
| Phase 6 native boot / M2 | Complete locally; distribution decision open | `evidence/phase6-completion.json` is the signed completion manifest under `docs/planning/phase6-acceptance.md`. The supported original entry reaches stable deterministic scheduler/VI activity: three native processes match at canonical-output, full-state, and ordered-journal levels; guarded MMIO instrumentation records 22 supported accesses and zero unsupported accesses; a BizHawk 2.11.1 probe observes three real queue-ring/message consumptions; an identified AddressSanitizer build runs the same original-entry checkpoint; and invalid ROMs fail safely. The public summary cryptographically binds the ignored private body, executables, generated inventory, tools, probe, and clean producer source closure. This is M2 boot, not rendering or gameplay, and distribution remains gated on the human legal/license decision. |
| Phase 7 first rendered frame / M3 | Complete | `evidence/phase7-completion.json` passes `scripts/validate_phase7_acceptance.py`: boot/title and representative gameplay tasks reach the pinned RT64 path, three captures per scene meet the fixed pixel thresholds, unsupported commands are zero, and disabled, semantic, and RT64 renderer modes preserve the same simulation hashes. |
| Phase 8 interactive substrate | Complete | `evidence/phase8-completion.json` passes `scripts/validate_phase8_acceptance.py`: the generated CPU, continuous RT64 presentation, timestamped input, audio output, save/accessory path, process restart, and three-repeat deterministic scenarios are bound. This closes the interactive substrate; it does not claim the Phase 9 complete campaign slice. |
| Phase 9 complete campaign slice / G6 | In progress | The Goldwood route reaches live control, combat, death/retry, overlay transitions, graphics, audio, and persistence with zero unsupported accesses on the latest preserved full-render replay. Per-retrace native hashing exists and has already protected runtime refactors. The exit gate remains open until the complete selected slice, oracle-aligned checkpoints, transition perturbations, and 100 consecutive deterministic completions pass. |

No milestone after Phase 8 may be reported complete from this dashboard.

## Remaining full-project scope (2026-09-05)

The completed entries above describe their recorded acceptance contracts, not
blanket satisfaction of every broader scope-assessment gate. In particular,
G4 asks for fifty boot repeats and G5 for ten reference captures, whereas the
summaries above cite three-process/three-capture evidence. Those additional
counts must be reconciled before reporting the entire scope satisfied.

| Phase | Scope status |
|---|---|
| 9: complete campaign slice | Active; see [acceptance tracker](planning/phase9-acceptance.md). The 100-run startup batch is not 100 slice completions. |
| 9.5: autonomous exploration harness | In progress; all gates open. See [plan](planning/phase9-5-autonomous-exploration.md), [evidence](planning/phase9-5-progress.md), and [full-scope autonomy plan](planning/autonomous-full-scope-execution.md). Ten fresh startups, checkpoint restoration, generated navigation, one-command south and east destinations from the same immediate level-47 checkpoint, checkpoint-resumed natural death/retry, three matching south oracle repeats, and an automatic native differential bundle have live evidence. The uninterrupted south run passed fifteen exact-hash route segments, three ordinary pistol kills, level-21 arrival and health pickup with zero intervention. The restartable seeded batch completed 10/10 with south, east, and death/retry objectives, but selects only the objective by seed and uses separate reviewed frontiers. Native parity, varied-path exploration, combined recovery coverage, frontier scheduling/failure reduction, and native snapshots remain open. |
| 10: finishable single-player campaign | Not accepted; segmented routes and three clean new-game runs to credits are still required. |
| 11: complete modes, optional content, robustness | Not accepted; release-scoped content, multiplayer, recovery, overlay coverage, stress and soak remain. |
| 12: ultrawide / arbitrary aspect ratio | Not accepted; rendering, UI, culling and reference validation remain. |
| 13: high-frame-rate presentation / pacing | Not accepted; interpolation and compatibility-preserving simulation checks remain. |
| 14: mod support / readable-source adoption | Not accepted; stable interfaces, mod safety and differential replacement evidence remain. |
| 15: release hardening / public launch | Not accepted; legal decisions, platform/package validation and release acceptance remain. |

The Phase 4/G2 refresh described as blocked in earlier checkpoints was closed
in the fifth hardening-audit pass and committed in `d90bfdb` after producer
re-pinning in `cde8a9c`. This status update does not claim a fresh execution of
all historical private validators.
