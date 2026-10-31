# Development guide

Start with [ROM-free setup and tests](setup.md) or [building the playable game](rom-bootstrap.md).
The [repository layout](repository-layout.md) identifies each source and tool owner. Changes follow
[CONTRIBUTING.md](../../CONTRIBUTING.md); autonomous work follows [AGENTS.md](../../AGENTS.md).

| Work | Reference |
|---|---|
| Understand runtime boundaries | [Architecture](architecture.md), [runtime reference](runtime/) |
| Diagnose a bug | [Issue records](issues/README.md), [support diagnostics](support-diagnostics.md), [runtime fix log](boot-gameplay-fix.md) |
| Work on controls/UI | [Frontend](../features/frontend.md), [Modern controls design](runtime/modern-controls.md) |
| Verify original-game behavior | [N64 catalog](../original-game/README.md), [pinned upstream review](../upstream/reference-review-2026-10-01.md) |
| Package or maintain | [Maintainer guide](../maintenance/README.md) |
| Plan future work | [Acceptance contracts](../planning/README.md), [project status](../status.md) |

The [launcher guide](launcher.md) and [ROM build guide](rom-bootstrap.md) ship in release packages;
keep their public paths and absolute external links stable. Historical signed milestones remain
revision-specific evidence and do not certify the current source tree.
