# Phase 3 prioritized blocker backlog

> Historical Phase 3 backlog. The Phase 3/G2 gate was subsequently closed;
> use `docs/dashboard.md` and signed evidence for current status. Entries remain
> here to preserve the risk and estimation record, not as active blockers.

Estimates are focused engineering effort after the current checkpoint, not
calendar commitments. Owners are roles; assignment to a person requires an
explicit maintainer decision.

## P0 — blocks G2 and broad implementation

| ID | Owner role | Blocker and required executable proof | Estimate |
|---|---|---|---:|
| P3-CPU-001 | CPU/toolchain | Bound the N64Recomp jump-table scan, add a synthetic regression, then classify every remaining CPU-generation failure without the conservative release stub set. | 2–6 engineer-weeks |
| P3-OVL-001 | CPU/runtime | Ingest all custom relocation metadata and run a difficult real overlay through load, relocation, indirect lookup, unload, and same-base reload with stale-generation rejection. | 4–10 engineer-weeks |
| P3-GFX-001 | Graphics/RT64 | Implement the bounded custom graphics family independently in the candidate renderer and validate at least one private real task with approved semantic or render-hash evidence. | 6–16 engineer-weeks |
| P3-RUN-001 | Runtime | Trace and prototype reachable direct-register, address-alias, TLB, cache, PI, decompression, runlink, and code-mutation behavior; every unknown must fail closed. | 6–14 engineer-weeks |
| P3-TRP-001 | CPU/runtime | Classify reachable break, syscall, switch-bound, and self-check paths and give each an explicit tested disposition. | 3–8 engineer-weeks |
| P3-SAV-001 | Platform/save | Connect the tested logical Controller Pak layer to discovery and reproduce allocation, enumeration, read/write, delete, capacity, repair, and failure behavior against the private oracle. | 3–8 engineer-weeks |
| P3-LIC-001 | Human maintainer/legal | Select the runtime and renderer distribution architecture, including GPL consequences and whether external HLE code remains research-only. | Human decision; external review schedule |

## P1 — required before G2 closure or immediately after its P0 path

| ID | Owner role | Work and proof | Estimate |
|---|---|---|---:|
| P3-RSP-001 | RSP/audio | Exercise the second audio overlay variant and classify the exact graphics overlay topology. | 1–3 engineer-weeks |
| P3-AUD-001 | Audio/test | Capture referenced-memory closure privately and compare sanitized output metrics for representative audio tasks. | 2–5 engineer-weeks |
| P3-SAV-002 | Platform/save | Validate FlashRAM erase, buffered write, read, status, persistence, interruption, and failure behavior. | 1–3 engineer-weeks |
| P3-SCH-001 | Runtime/test | Prove timer, queue, jam-order, blocking, cancellation, wrap, and completion ordering semantics. | 1–3 engineer-weeks |
| P3-EVD-001 | Test/evidence | Turn each private P0 proof into a regenerable aggregate record with explicit completion markers and no tracked bodies. | 1–2 engineer-weeks |

## P2 — follows the architecture decision

| ID | Owner role | Work and proof | Estimate |
|---|---|---|---:|
| P3-UP-001 | Maintainer | Prepare independently authored upstream fixes only after contribution policy, AI disclosure, and explicit authorization are resolved. | Per accepted scope |
| P3-CI-001 | Test/CI | Add an owner-controlled private ROM-backed lane only if the corpus owner approves storage, runner, retention, and log-redaction controls. | 2–4 engineer-weeks |

## Ordering

P3-LIC-001 should be decided before shipping integration work. P3-CPU-001 and
P3-OVL-001 can proceed in parallel with P3-GFX-001. P3-RUN-001 and P3-TRP-001
share trace infrastructure. P3-SAV-001 can use the already proven private
checker-persistence route as its first oracle case.
