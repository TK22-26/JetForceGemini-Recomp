# G2 production evidence boundary

- Status: historical production-boundary design; pinned production executions
  were subsequently accepted in the signed Phase 4/G2 aggregate
- Data boundary: recipes, packed cases, generated bodies, observations, and
  producer binaries remain ignored beneath `tools/` or outside the repository

The language below describes the fail-closed admission design and its
pre-acceptance state. `docs/dashboard.md` and the signed evidence are
authoritative for current gate status.

The G2 validator accepts executable evidence only from a repository-owned
dispatcher whose bytes match both the Git index and committed `HEAD`. Before a
binary can ever be pinned, the validator also requires the complete reviewed
tracked target closure to match the working tree, index, `HEAD`, and a named
ancestor commit. The commit and its tree object are independently verified;
all tracked state must be clean. The closure covers the CMake recipe/modules,
producer, runtime sources, and project headers used to build the target.

A separate build-attestation pin is required alongside any binary pin. It
binds the CMake generator/configuration/defines, producer and generated-code
compiler flags, exact compiler identity and digest, reviewed commit/tree,
tracked closure digest, and opaque private generated-input closure digest.
Adding a binary digest alone therefore cannot authorize an opaque build. The
case configuration carries a canonical
derivation record binding the supported-input digest, bounded-case digest,
private-adapter identifier/version, and that reviewed producer revision. A
case copied without this binding, or a changed source/configuration, is
rejected before the dispatcher can run.

On POSIX, the dispatcher requires a non-reparse staging directory owned by the
effective user with no group/other permissions. It creates independently read
producer and case copies exclusively, handles partial writes, opens without
following symlinks, and rehashes both before launch and after exit. It executes
only the staged producer with a fixed argument vector and sanitized
environment. It accepts
only a canonical response containing a fresh random nonce and the separately
bound observation. Caller-selected commands, PATH tools, marker-only binaries,
raw observation hardcoding, case echoing, and a swap of either checked input
are rejected. Windows production execution is currently disabled: Python mode
and uid fields do not prove owner-only DACLs or safe executable-open semantics,
and no reviewed WSL launcher is pinned. A future native Windows or WSL route
requires explicit DACL/reparse/open-identity enforcement and equivalent
before/after checks.

The dispatcher supplies the canonical case identifier and case digest as fixed
arguments after independently validating both. Producers must use those
arguments for their observation identity and verify the staged case digest;
they must not treat an identifier embedded in `case-input.bin` as evidence
identity. This makes a conflicting or substituted case fail closed.

`PRODUCER_BINARY_SHA256` is now populated for all eleven executable mappings
from the reviewed clean checkpoint, alongside complete source-provenance and
thirteen-field build-attestation records: each producer was built twice from
the same pinned inputs on the fixed WSL Ubuntu-24.04 GCC 13.3 toolchain and
both builds were byte-identical before any digest was recorded. A source pin
or a successful local build still does not authorize a binary by itself; the
registries authorize only the exact reviewed byte identities.

## Overlay lifecycle/R32 producer

The first production-shaped tracked harness is
`src/evidence/g2_overlay_producer.cpp`. It links
the project-owned `GeneratedOverlayRuntime` to the locally generated table ABI
and accepts only a versioned bounded `case-input.bin`. The current V3 case
contains at most seven dependency-closed opaque modules, their ignored
initialized images, complete generated-R32 site inventories, authoritative
custom runlink relocation records, and opaque target bindings. It contains no
expected observation, generated name, command, success flag, or
producer-selected path. Legacy V1/V2 cases remain ROM-free compatibility and
negative-control fixtures; they are not the production candidate.

For an accepted run, the producer must derive and verify all of the following:

- generated table installation and exact private section metadata;
- provider and dependent-overlay load through the checked generated lifecycle;
- initialized-byte copy, BSS clear, and observed relocation writes;
- token-bound and guest-address function lookup;
- dependency invalidation after provider unload and atomic rebind after reload;
- dependent-overlay unload and same-base reload with identical mapped state;
- rejection of the stale lifetime;
- callback re-entry rejection; and
- callback-failure rollback with unchanged live memory and no publication.

The response contains only opaque identifiers, bounded counts, event classes,
and digests. It does not contain private paths, generated names, guest
coordinates, ROM bytes, section images, or relocation bodies.

The V3 adapter and producer now implement the custom-runlink portion of this
proof locally. The adapter binds the ignored generated root to the exact
canonical runtime manifest, maps raw overlay modules to generated section ABI
indices, selects an acyclic dependency-closed suite, and packs the complete
R32 inventory plus real full-word, jump-target, HI16, and LO16 records. The
producer rechecks each R32 descriptor and target formula against the generated
table, applies the custom records through the checked runtime, exercises
provider invalidation/rebind, and performs an actual source unload/reload,
stale-token rejection, state/formula revalidation, and callback-failure
rollback before emitting those event classes. On Linux, it also resolves and
executes a generated body inside the hardened single-child trap boundary with
bounded guest memory and a zero-initialized generated ABI context. Only normal
return or a proof-bound fatal trap-bridge event is accepted; an ordinary
signal, timeout, protocol error, or setup failure rejects the run. The G2
producer remains unavailable on Windows rather than claiming an equivalent
process boundary there.

This successful local path now includes the revocable production invocation
boundary. Generation-checked handles reject stale capabilities; quiescent
unload/repatch scrubs relocated guest words; callback failure rolls back; and
MSVC, Clang, and GCC tests cover the fail-closed paths. It is still not accepted
G2 evidence because the production binary/build provenance, reviewed clean
checkpoint, reproducible rerun, and final pins remain empty. Those are the
remaining explicit pinning blockers.

The target is disabled by default. A private generated build enables it with:

```text
-DJFG_ENABLE_GENERATED_CODE=ON
-DJFG_GENERATED_ROOT=<ignored-or-external-root>
-DJFG_BUILD_G2_PRODUCERS=ON
```

`scripts/prepare_g2_overlay_case.py` packs a strict private recipe and two
regular initialized-image files into the binary case format. The recipe and
every repository-contained input must stay beneath `tools/`; output is
new-file-only and also restricted to `tools/`. The preparer rejects duplicate
JSON keys, extra fields, embedded observations, missing relocation classes,
symlinks, oversized inputs, and an existing output.

`scripts/derive_g2_custom_overlay_case.py` is the V3 production-candidate
adapter. It reads only ignored/external inputs, writes new files only beneath
`tools/`, rejects reparse and tracked paths, verifies the generated-root/runtime
binding, and emits only a private case plus a closed aggregate sidecar. Its
ROM-free synthetic tests cover nonidentity module/section mapping, transitive
dependency closure, cycle rejection, BSS/static geometry, exact R32 matching,
and bounded-search failure.

## Evidence still required before pinning

The ROM-free fixture proves that the tracked source compiles and that the
runtime-derived nonce protocol and negative controls work. A local private
MSVC build also links the tracked producer against the complete ignored
generated set. Neither result closes the mapping.

The deterministic V3 adapter and a local private producer run now exercise the
real custom/R32 lifecycle path, including revocable invocation and quiescent
unload/repatch. Before adding an overlay binary digest, the reviewed source
checkpoint must be clean and two identical production builds/runs must be bound
to the exact compiler identity, private input closure, case derivation, and
hardcode/echo negative controls. The public source pin and build record are
necessary provenance preconditions, not authorization for an opaque binary.
Until every condition is met, the binary pin stays empty and G2 remains no-go.

## CPU, RSP, graphics, audio, save, and trap paths

The CPU case format is V3. Three executions of one reviewed CPU evidence
producer select and report the independently built Clang, GCC, and MSVC G3
products. These are `private-g3-compiler-product-binding` records; they do not
claim that the evidence producer itself was rebuilt or executed in three
compiler environments. Its actual build compiler remains bound separately by
the producer build attestation and execution environment. Each observation
carries a G3 product-set commitment, but the CPU producer is not allowed to
authenticate that commitment. Trusted completion recomputes it from the
independently replayed G3 generation, Clang/GCC/MSVC, forced-link, analyzer,
ASan, UBSan, reproducibility A/B, and configuration-mutation records. It also reconciles the CPU
section/object/lookup/relocation/stub and runtime-bridge counts with the public
G3 product denominators and requires the exact three compiler IDs and
executable digests to match. A structurally valid forged CPU inventory with a
copied commitment is a negative control and is rejected.
`scripts/prepare_g2_cpu_case.py` will emit the V3 case only from the ignored,
explicitly non-completion `phase4-g3-product-projection.json` and its ignored
`phase4-private.json` audit body. It rejects tracked, external, linked,
noncanonical, or shape-changing inputs and reruns the repository-owned private
schema and all eleven pinned Phase 4 harness validations. It never consumes a
final Phase 4 manifest, a G2-bound completion gate, or caller-supplied trust
policy. The preparer locates the generation execution's authenticated
`cpu-section-inventory` product through that execution's fixed audit plan; no
caller-supplied section inventory is accepted.

The product-set commitment includes the exact eleven-field G3 projection, the
exact ignored Phase 4 private-body digest, and stable identities for all eleven
G3 executions: execution/kind/case and harness identities, public
record/result-set, subject/source/declaration, pins, environment, input/output
sets, exit code, and passed state. `result_sha256` and `artifact_set_sha256`
remain outside the stable per-execution projection because they bind the
request-specific public-claim digest; they and every artifact remain indirectly
committed by the exact raw private-body digest, which the full Phase 4 private
validator authenticates before either pre-G2 preparation or final completion.
Final trusted completion extracts that digest from the final attestation and
recomputes the same binding from the final validated Phase 4 private/public
pair. Any changed core product, patch library, execution row, or private body
therefore rejects the G2 CPU records.

```powershell
tools\venv\Scripts\python.exe scripts\prepare_g2_cpu_case.py `
  --phase4-g3-product-projection tools\results\phase4\completion\phase4-g3-product-projection.json `
  --phase4-private-audit tools\results\phase4\completion\phase4-private.json `
  --output tools\results\phase4\completion\g2-cpu-case.bin
```

Trusted completion also requires the G2 rows, including order and every
per-section count, to equal that G3 product exactly, in addition to the
aggregate and compiler cross-checks.

The RSP inventory producer is classification-only. Every reported native
entry, broker access, completion, and exit count must be zero; it cannot turn
caller-supplied program bytes into an execution claim. Trusted G2 validation
instead binds the graphics and both audio classifications to program digests
from the independent graphics/audio native and oracle executions. The
secondary audio classification deliberately binds to the generated fallback
path exercised by the audio adapter rather than claiming that the inventory
producer executed it.
`scripts/prepare_g2_rsp_case.py` packs the representative private program
bytes and reviewed manifest commitment without exporting them.

Graphics and audio use V3 input-only private task cases. Neither case contains
an expected native result or oracle result. The graphics native producer links
the tracked project-owned bounded semantic adapter. It authenticates the exact
active program from brokered task memory, executes the reviewed F3DDKR/F3DJFG
handler surface, and reports one generic backend execution. The separate
graphics oracle executable links only with a distinct ignored oracle ABI and
must match the semantic stream exactly. The fixed
`project-bounded-semantic` path is not rendered pixels, visual correctness, a
first-frame claim, or an RT64 execution claim. The pinned RT64 discovery probe
remains ignored negative feasibility evidence because the inspected revision
has no required custom-family implementation.

The audio native producer likewise requires its ignored generated-wrapper
adapter. It invokes the primary wrapper through `AudioRuntimeTaskWorker`,
reports actual broker operations, and passes the same bounded task input to
the generated secondary fallback so fixed synthetic fallback constants cannot
satisfy the claim. Its oracle executable requires a separate ignored oracle
ABI. All native/oracle paths return the digest of the program bytes they
actually authenticated; the producers compare that binary digest to the
case's active program before emitting evidence. `scripts/prepare_g2_private_task_case.py`
packs both input-only formats new-file-only beneath `tools/`.

Enabling `JFG_BUILD_G2_PRODUCERS` now requires explicit ignored/external roots
for the graphics oracle, audio native adapter/runtime headers, and audio
oracle. The graphics native adapter is tracked project code. CMake rejects
tracked private roots, missing fixed closure files, and an audio native/oracle
pair that resolves to the same root. Public synthetic fixtures test the ABI
and parsers, including negative controls for missing oracle/audio adapters,
false RT64 labels, and coordinated active-program substitution. Real private
execution and reproducible closure attestations are still required before
these producers can support an accepted claim.

The save pair provides real ROM-free runtime coverage. Runtime traps require
separate native and oracle records for the same private case with distinct
producer/build provenance. Every executable path now has an accepted
binary/build pin recorded from the reviewed clean checkpoint, with
reproducible A/B builds and distinct native/oracle private-closure
attestations. The assembled G2 private/public evidence pair passes trusted
validation with zero errors and the public gate records a go decision. On
Windows, the pinned producers execute through the reviewed WSL launcher
route: the fixed absolute system WSL boundary and fixed distribution, with
exclusive staging and before/after byte-identity checks, mirroring the pinned
Phase 4 harness's fixed ELF probe execution.
