# Revised planning range after the Phase 3 spikes

> Historical planning snapshot from the Phase 3 checkpoint. G2, Phase 4, and
> the local Phase 6 M2 gate were subsequently completed; the dashboard is the
> current status authority. The ranges below are retained for provenance.

These ranges start at the current Phase 3 checkpoint. They are deliberately
wider than the original optimistic cases because the spikes found a large CPU
stub boundary, custom dual-table overlays, missing native graphics support,
and required runtime/save/trap work. They assume the legal and dependency
architecture is resolved without a full runtime replacement.

The G2 range is anchored to the blocker backlog rather than an aspirational
date. The bounded engineering items total 24–62 engineer-weeks at P0 and
6–16 engineer-weeks at P1. This schedule includes both bands (30–78
engineer-weeks) because the P1 proofs are required to close G2 or immediately
complete its selected path. The legal decision has no engineering estimate and
can extend calendar time independently.

| Milestone | Solo, about 15 hr/week | Solo full-time | Two experienced FTE | Four experienced FTE |
|---|---:|---:|---:|---:|
| Clear G2 feasibility | 18–48 months | 7–18 months | 4–10 months | 3–6 months |
| M2 stable repeated VI/runtime checkpoints | 24–54 months | 10–24 months | 6–14 months | 4–9 months |
| M3 first validated rendered frame | 30–66 months | 13–30 months | 8–18 months | 5–12 months |
| M4 complete vertical slice | 42–84 months | 20–40 months | 12–26 months | 8–18 months |
| M5 route reaches credits | 60–108 months | 32–60 months | 20–40 months | 13–28 months |
| M6 complete compatibility build | 72–132 months | 42–78 months | 28–52 months | 18–36 months |
| M8 polished enhanced release | 90–156 months | 54–96 months | 36–66 months | 24–46 months |

## Assumptions

- Experienced C++/MIPS/N64 contributors own the critical workstreams.
- The supported image, private captures, and local oracle remain available.
- The bounded custom graphics surface can be implemented without replacing the
  renderer.
- The custom overlay model can be integrated without runtime host-code patching.
- No new dynamic-code generator or unclassified anti-tamper mechanism appears.
- Licensing permits the selected runtime and distribution design.
- A full-time engineering month is approximately 4.33 engineer-weeks; the
  part-time column assumes about 15 productive hours per week.
- Team columns include coordination and critical-path allowances. Dividing the
  solo range by headcount would be too optimistic because legal, CPU/overlay,
  renderer, and integration decisions contain serial dependencies.

If a full renderer or runtime replacement is required, these ranges no longer
apply; create a replacement-specific estimate instead of adding a fixed buffer.
Re-estimate after G2, the first stable runtime trace, the first validated frame,
and the first full save/restart cycle.
