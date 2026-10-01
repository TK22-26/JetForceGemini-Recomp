# Phase 5 deterministic-test-kernel acceptance contract

- Status: binding acceptance criteria for local Phase 5 work
- Scope: deterministic test kernel v0 and the `jfg-test` headless runner
- Data boundary: captured corpora derived from ROM-backed execution remain
  ignored and local under `corpus/private/` and `captures/private/`

This contract resolves the conflict between the master plan's Phase 5 exit
gate and the scope assessment's required sequencing changes without weakening
either document's data or determinism guarantees.

## Scope resolution

The scope assessment (Required sequencing changes) splits the deterministic
kernel into v0 and v1 and replaces the pre-boot "100 representative
functions" requirement with 20–30 risk-weighted boundary functions, deferring
100 captured functions to M4. That amendment is normative for Phase 5.

**Kernel v0 (gating, this phase):**

- cloneable RDRAM/context worlds with exact dirty-page tracking
- virtual time
- deterministic queues, timers, and scheduling
- side-effect journal with canonical serialization
- state-hash schema v1 with pinned, human-approved exclusions
- function capture/replay format v1
- first-divergence report format v1
- test-only fake renderer/audio/storage that journal every host effect and
  reject unsupported host calls fail-closed
- corpus container format v1 with lossless round-trip
- exact-repeat nondeterminism detector

**Kernel v1 (explicitly non-gating, deferred to boot/slice work):**

- scheduler model of the game's thread/queue semantics
- captured-call minimization beyond page-level reduction
- subsystem hashes
- feature-flag profiles beyond the deterministic-mode switch
- corpus compression beyond the deterministic sparse-page encoding

A v1 item implemented early is welcome but can never substitute for a v0
item, and its absence can never block Phase 5 completion.

## Completion rule

Phase 5 is complete only when all of the following hold:

1. Every kernel v0 component above exists, builds in the default ROM-free
   configuration, and is exercised by at least one CTest.
2. All nine master-plan Phase 5 test obligations pass, mapped as follows:
   - world clone produces identical hashes → `jfg.testkernel.world`
   - same function replayed twice is bit-identical → `jfg.testkernel.replay`
   - scheduler replay repeats event order → `jfg.testkernel.scheduler`
   - side-effect journal is stable → `jfg.testkernel.journal`
   - dirty-page tracker identifies exact writes → `jfg.testkernel.world`
   - first-divergence tool reports a seeded one-byte difference →
     `jfg.testkernel.divergence`
   - test runtime rejects unsupported host calls → `jfg.testkernel.fakes`
   - corpus round-trip is lossless → `jfg.testkernel.corpus`
   - private corpus cannot be uploaded by CI → `jfg.policy.corpus_privacy`
3. The `jfg-test` executable runs the kernel self-check headlessly, replays a
   corpus file, and repeats a run N times reporting the exact-repeat verdict,
   all without a ROM, a window, or network access.
4. The state-hash exclusion list and the divergence tolerance policy are
   pinned tracked artifacts (`config/state-hash-schema-v1.json`,
   `config/divergence-tolerance-v1.json`) approved by the human owner. A test
   passing against an unpinned or empty schema does not count. The v0
   tolerance policy is exact: zero tolerated divergence in deterministic
   mode. Any loosening is a new human-approved revision of the pinned file.
5. **Boundary-function gate:** at least 20 risk-weighted boundary functions
   from the Phase 4 generated set are captured and replayed bit-identically
   through the kernel, and a seeded one-byte pre-state fault in each is
   localized by the first-divergence tool. This evidence is ROM-derived and
   therefore private: it follows the Phase 4 fail-closed pattern — a local
   ledger under the ignored tree, a public sanitized manifest carrying only
   counts and digests, and an OpenSSH Ed25519 signature verifying against the
   pinned project key in `config/phase4-completion-signing.json`. The master
   plan's "100 representative functions" figure is deferred to M4 per the
   scope assessment and is not a Phase 5 gate.
6. The public repository, CI logs, and tracked evidence contain no
   ROM-derived bytes. `corpus/private/` and `captures/private/` stay ignored,
   and the policy test proves no CI workflow uploads them.

A completion claim is fail-closed evidence, not a self-reported status flag,
under the same verification rules as `docs/planning/phase4-acceptance.md`.

## Entry precondition — the oracle

The scope assessment moved emulator-trace and function-capture tooling into
G1/G2 because differential corpora need an oracle. Phase 5 work may begin on
kernel v0 immediately, but the boundary-function gate (rule 5) cannot be
attempted before a working capture path exists: pre-state, invocation, and
post-state of a generated function recorded from the minimal-link runtime.
If no such path exists when rule 5 is attempted, building it is Phase 5 work
and blocks completion; it is never waived.

## Determinism definition

Deterministic means bit-identical across repeated runs on the same host,
build, and inputs: identical state hashes at every checkpoint, identical
journal bytes, and identical event order. Cross-host and cross-compiler
identity is a v1 goal, not a v0 gate, but any observed cross-run divergence
on one host is a hard failure.

## Human review checkpoints

Per the master plan: state-hash exclusions, the scheduler model, the
tolerance policy, and private-data handling require human owner approval.
The pinned config files record that approval; changing them requires a new
approval, never a silent edit.
