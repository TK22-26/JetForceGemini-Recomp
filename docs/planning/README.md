# Plans and acceptance contracts

## Current work

- [Quarry audio timing and performance findings](quarry-audio-sync-findings.md): confirmed causes, candidate fixes, replay evidence, and remaining limits.
- [Project roadmap](JFG_RECOMP_MASTER_PLAN.md): compatibility, campaign, enhancements, and release gates.
- [Campaign slice](phase9-acceptance.md): remaining route and regression coverage.
- [Automated gameplay exploration](phase9-5-autonomous-exploration.md): scenario and recovery requirements.
- [Automation delivery plan](autonomous-full-scope-execution.md): remaining engineering-loop work.
- [Tester onboarding](tester-onboarding.md): documentation and reporting delivery checkpoint.

## PC enhancements

- [PC controls and Perfect Dark references](../upstream/perfect-dark-pc-reference.md): implemented keyboard/mouse bindings and experimental separate-stick manual aim; full movement/strafing and camera integration remain open. Pinned host sources are retained locally.

## Operational requirements

- [Production progress guard](autonomy-progress-guard.md).
- [Trusted continuation rules](autonomy-guard-continuation.md).
- [Automation guide](../development/automation.md).

## Retained acceptance contracts

| Area | Contract |
|---|---|
| CPU generation | [Phase 4](phase4-acceptance.md) |
| Deterministic kernel | [Phase 5](phase5-acceptance.md) |
| Native boot | [Phase 6](phase6-acceptance.md), [native record](phase6-native-boot-addendum.md), [completion ledger](phase6-native-boot-remaining.md) |
| Rendering | [Phase 7](phase7-acceptance.md), [renderer integration](phase7-renderer-integration.md) |
| Interactive runtime | [Phase 8](phase8-acceptance.md) |

Some contracts are read by tests or bound into signed manifests. Their phase
names and historical wording are retained for verification. Changing a contract
requires an explicit version/evidence decision; documentation cleanup must not
rewrite a signed result. Historical license/publication wording in those
contracts does not describe the current public preview: original project work
uses [MIT](../../LICENSE). See the [evidence guide](../../evidence/README.md).

Technical timing notes linked by source provenance remain at their existing
paths and are indexed in the [runtime summary](../development/runtime-research.md).
Superseded journals are recoverable through [Git history](../history.md).
