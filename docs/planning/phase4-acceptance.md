# Phase 4 CPU-generation acceptance contract

- Status: binding acceptance criteria for local Phase 4 work
- Scope: G3/M1 CPU generation and minimal link only
- Data boundary: generated and ROM-backed bodies remain ignored and local

This contract resolves ambiguous wording in the master plan without weakening
its gates. Phase 4 may be developed in parallel with focused feasibility work,
but it cannot be reported complete before G2 passes. A successful compiler run
alone is not Phase 4 completion.

## Completion rule

Phase 4 is complete only when all tasks and tests in the master plan pass, the
full generated CPU code and overlay tables compile and link with the minimal
test runtime, every required deliverable exists locally or as a sanitized
tracked attestation, and G2 and G3 are both closed with executable evidence.

The whole-program result is normative. The weaker G3 phrase about unexplained
entries "on the boot path" does not permit unexplained non-boot CPU failures in
a Phase 4 completion claim.

A completion claim is fail-closed evidence, not a self-reported status flag. It
must carry an OpenSSH Ed25519 signature that verifies with the anonymous project
public key pinned in `config/phase4-completion-signing.json`. The signing key is
local-only under the ignored `tools/` tree. A caller-selected key, an HMAC key
provided beside the manifest, or the unsigned synthetic example cannot
authenticate completion. Verification also requires the actual public-safe G2
`go` evidence body, validates all fixed G2 requirement classes, recomputes its
digest, and proves that its input pins match the Phase 4 run. Public inspection
can authenticate that the signed manifest contains a private-evidence digest
without receiving the body, but no trusted completion verdict is returned
without the ignored body and a local digest recomputation. Trusted validation
loads both repository-owned schemas internally; supplied schema objects are
accepted only when they are canonically identical to those contracts and can
never weaken them.

## Authoritative denominators

The private generated manifest derives one denominator from the pinned input
and records only closed aggregates publicly:

- A **required CPU body** is a word-aligned, positive-size executable function
  selected by the authoritative local symbol model, including validated manual
  size recovery.
- A zero-size name at an already covered address is an alias, not another code
  body. It must map deterministically to the covered body or have an approved
  alias exclusion.
- A pseudo-function or data range may be excluded only when bounded evidence
  classifies it as non-code. A generation failure is never an exclusion.
- A runtime-provided ABI function is an external bridge, not generated game
  code. Every such function must appear in the closed bridge denominator and
  resolve during the forced-object link audit.
- The overlay denominator is every discovered slot, including empty slots;
  code-coverage totals separately reconcile every populated executable module.

Approved exclusion categories are limited to `covered-alias`,
`validated-non-code`, and `runtime-abi`. Each exclusion needs a stable opaque
identifier, evidence class, owner role, and deterministic reason code in the
private ledger. Public evidence exposes category counts only.

## Resolution and stub policy

- Every direct call resolves to a generated body, approved runtime ABI bridge,
  or explicit fail-closed runtime disposition. Unclassified direct calls are
  zero.
- Every statically discovered indirect-transfer site is represented by a
  bounded lookup range or an explicit fail-closed disposition. Trace-observed
  sites are a coverage subset, not the denominator.
- Every populated overlay participates in the generated lookup/lifetime table.
  Empty and exceptional slots have explicit fail-closed entries.
- Every instruction relocation is resolved or has an approved fail-closed
  disposition. HI/LO pairs are atomic: a partially handled pair is forbidden.
- Every R32 data relocation is represented and resolved by the generated
  relocation table; it has no fail-closed omission at completion. The lookup,
  lifecycle, and relocation tables all participate in the forced-object audit.
- Generated game-function stubs are zero at completion. Runtime ABI bridges do
  not count as stubs when they implement their documented minimal-link behavior
  or an intentional fail-closed trap.
- Duplicate native definitions, ambiguous aliases, and unowned exceptions are
  zero.

## Baseline, patch, and alias model

Generated sources are compiled as C. Handwritten runtime and audit code may be
C or C++ but must expose the N64Recomp ABI with C linkage.

Each unmodified generated body is emitted as a distinct `<symbol>_recomp`
archive member and has a separate normal callable wrapper member. The
generated-body, replaceable-function, wrapper-member, and callable-alias counts
must be identical. Deterministic alternate-entry thunks and the generated overlay
lookup, lifecycle, relocation, section-count, and bounded section-initializer
functions are classified as support members.
Patch archives are linked before the baseline archive. Forced-object audit
executables link every baseline and patch object directly so lazy archive
extraction cannot conceal missing or duplicate symbols.

The sanitized aggregates cross-reconcile these denominators: generated game
bodies equal unmodified `_recomp` body members; replaceable functions equal
normal callable wrapper members and both expected and emitted callable aliases;
alternate entries equal deterministic thunk members; each generated table class
equals its support-member class; runtime-ABI exclusions equal the minimal
runtime's required and resolved bridge set; and approved patch functions equal
approved replacement members. Baseline totals equal body plus wrapper plus
support members. Patch totals equal approved replacements plus the fixed
non-game anchor/support members, with zero patch callable wrappers. Support,
thunk, table, and anchor members cannot make up a game-function shortfall or
inflate authoritative body/patch counts.

Strict patch mode rejects a patch without a matching baseline symbol, a patch
that replaces more than its manifest declares, a missing baseline alias, an
unsupported instruction patch, or a duplicate patch definition. An empty
strict patch set is a valid Phase 4 baseline when no game patch is needed; a
deterministic support anchor may keep the physical archive nonempty for uniform
cross-platform auditing.

## Minimal runtime boundary

The Phase 4 runtime exists only to compile, force-link, and smoke-test the
generated ABI and overlay tables. It provides checked memory helpers, relocation
address state, function lookup, fail-closed trap handling, and the closed set of
required host bridge symbols. It does not claim Phase 5 scheduling, replay,
virtual time, device emulation, rendering, audio, save behavior, or boot.

Target runtime-ABI game-symbol exclusions are a separate denominator from the
fixed minimal host's N64Recomp helper-function and ABI-data exports. Completion
evidence closes all three roles independently, proves strong object ownership,
and records the generated section count against the fixed public capacity. The
bounded initializer must pass at the exact required count, reject insufficient
capacity before writing, and initialize every recorded section address.

## Required compiler and analysis matrix

Before completion, the same normalized generated source set must compile and
force-link with:

- Clang on a supported host;
- MSVC on Windows; and
- GCC on Linux.

Exact compiler identities and option-set digests are recorded in private
evidence and reduced to allowlisted family/version facts in the public
attestation. Generated targets may scope warnings required by the pinned
N64Recomp ABI header, but handwritten bridges use warnings-as-errors. Clang
static analysis and the available compiler sanitizers must report no undefined
behavior in handwritten bridges.

The analysis record requires Clang static analysis specifically and explicit
AddressSanitizer and UndefinedBehaviorSanitizer results. Each result binds to
the same normalized handwritten bridge source inventory; declaring another
analyzer alone is not sufficient.

## Reproducibility and expected diffs

Two runs with identical pinned inputs, configuration, and tool patch set must
produce identical normalized manifests, symbol inventories, overlay-table
digests, report digests, source-file inventories, and archive-member
inventories. Absolute paths, timestamps, filesystem order, locale, and process
IDs are excluded from normalized material.

`phase4-run-payload-v1` is the normalized run record: it contains the canonical
relative source inventory, aggregate reports, and lookup/lifecycle/relocation
table inventories, but no self-digest, signature, absolute path, timestamp,
locale, process ID, or filesystem enumeration order. The baseline and patch
archive-member inventories have separate digests and must each match across
runs.

A configuration mutation test declares its expected categories before running.
The resulting normalized diff may change only those categories. Unexpected
symbol additions, removals, renames, section movement, lookup changes, patch
changes, or compiler-option changes fail closed.

The public aggregate records the predeclared expectation digest plus closed
expected and observed category maps. Both maps must match exactly, their totals
must reconcile, at least one declared change must be exercised, and the base
configuration digest must match the pinned Phase 4 configuration. The
predeclared expectation digest is the SHA-256 of the canonical expected-category
map, so it cannot be an unrelated decorative value.

## Deliverable locations

Tracked, public-safe deliverables:

- `config/jfg.us.toml` with no private coordinates;
- project-authored generation/build orchestration;
- a strict schema and validator for the sanitized manifest;
- a pinned anonymous completion-signing policy/public key and a closed G2
  completion-evidence schema;
- synthetic compile/link, patch, alias, overlay, reproducibility, and privacy
  tests;
- sanitized G2/G3 evidence and dashboard state after the gates pass.

Ignored, local-only deliverables:

- authoritative detailed symbol and relocation metadata;
- generated CPU source and overlay tables;
- baseline and patch static libraries;
- detailed unresolved, indirect-call, stub, exclusion, patch, and failure
  ledgers;
- unrestricted build logs and ROM-backed proof bodies;
- the anonymous Phase 4 completion private signing key.

Every trusted-completion entry point requires the private evidence body to be
a regular non-symlink file outside the repository or beneath a Git-ignored path,
and recomputes its digest before returning success. Public inspection may omit
that private body, but cannot produce a completion verdict. Signing and
verification subprocesses use bounded timeouts, and
OpenSSH `ssh-keygen` with `-Y` signature support is a required Phase 4 validation
dependency.

The tracked attestation signs the canonical public aggregate and binds the
canonical private evidence digest. It contains only fixed-schema aggregate
counts, booleans, pins, digests, and the public signature. Structural or schema
validation deliberately rejects a completion record unless the trusted
signature and supplied G2 evidence body are verified together; neither a schema
pass, a caller-substituted schema, nor a caller-supplied key substitutes for the
authenticated private run.
Obvious repeated-character placeholder commits or digests are forbidden
throughout both trusted evidence bodies, including individual G2 results.
