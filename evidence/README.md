# Completion evidence

This directory retains milestone aggregates and signatures at their recorded
source revisions. They describe bounded results; they do not certify every
later build, a complete campaign, or a release.

| Record | Purpose |
|---|---|
| [Phase 4](phase4-completion.json) | CPU-generation and G2/G3 completion aggregate |
| [Phase 5](phase5-completion.json) | Deterministic-kernel completion aggregate |
| [Phase 6](phase6-completion.json) | Local native-boot completion aggregate |
| [Phase 7](phase7-completion.json) | Rendering acceptance summary |
| [Phase 8](phase8-completion.json) | Interactive-runtime acceptance summary |
| [RT64 smoke](phase7-rt64-task-smoke.json) | Intermediate task-submission result |
| [Boot/title](phase7-boot-title.json), [gameplay](phase7-gameplay.json) | Accepted scene aggregates |

Contracts are indexed in [planning](../docs/planning/README.md). Some Markdown
contracts and source files are bound by digest or read directly by validators.
Preserve their bytes when reorganizing documentation. Do not re-sign historical
claims or replace pinned digests to make a cleanup pass.

`examples/` contains unsigned synthetic validation fixtures, not completion
claims. Keep those fixtures and the signing public key. Detailed inputs,
generated bodies, local evidence, and private signing material remain outside
tracked source under the [corpus policy](../docs/legal/test-corpus-policy.md).
