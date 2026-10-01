# Phase 4 private execution evidence

## Status and boundary

The Phase 4 completion validator uses a repository-owned, byte-pinned production
harness for every required execution kind. This is validation infrastructure,
not a completion claim. No private bundle or signed completion record is
published by this contract, and generated code, ROM-backed inputs, unrestricted
logs, binaries, and detailed inventories remain ignored and local.

Trusted validation rejects the harness until its exact bytes are tracked by
Git. A working-tree file, a caller-supplied runner, or a test harness policy
cannot satisfy that check. The production harness is
`scripts/phase4_evidence_harness.py`; its byte identity is pinned outside the
private bundle by `scripts/validate_phase4_private_evidence.py`.

## Closed execution matrix

The private schema requires exactly these executions:

- generation;
- compiler-clang, compiler-gcc, and compiler-msvc;
- forced-object-link-audit;
- clang-static-analysis;
- address-sanitizer and undefined-behavior-sanitizer;
- reproducibility-run-a and reproducibility-run-b; and
- configuration-mutation.

Each execution binds the exact pre-G2 G3 product projection, the exact Phase 4
pin set, the selected public record, every SHA-256 result field within that
record, the input and declaration identities, its environment, every artifact,
and one structured result. The projection is an allowlist of the ten aggregate
core inputs plus the product-derived `compilers` field: eleven derived product
fields in total. Completion metadata, the predecessor G2 digest, the private
body digest, schema/kind labels, attestation, and signature do not affect this
projection. The final completion validator authenticates those fields
separately. Private evidence cannot replace any projected product value.

## Command-free production audit plan

Each execution has one canonical JSON configuration artifact with this closed
shape:

```json
{
  "schema_version": 1,
  "kind": "jfg-phase4-production-audit",
  "evidence_kind": "generation",
  "products": [
    {
      "product_kind": "generated-source-archive",
      "artifact_path": "production/generation/generated.zip"
    }
  ]
}
```

The real plan must list the exact product set fixed for its evidence kind. All
paths remain below `production/<evidence-kind>/`, refer to artifacts already
bound by the private bundle, and are globally unique. Unknown keys, duplicate
products, missing products, unplanned output or log artifacts, commands,
argument vectors, environment assignments, and shell fragments fail closed.

Structured public-result products use the following canonical wrapper. The
`observed` object is the corresponding public record with its self-referential
`result_sha256` field removed; the wrapper's raw SHA-256 becomes that public
result digest.

```json
{
  "schema_version": 1,
  "kind": "jfg-phase4-public-result",
  "product_kind": "compiler-result",
  "observed": {}
}
```

File inventories contain sorted canonical relative paths, sizes, and SHA-256
digests. Archive-member inventories contain the actual deterministic `ar`/COFF
member order, member names, sizes, and digests. The harness opens products with
bounded, identity-checked reads and independently parses ZIP and static-library
containers rather than accepting a log's pass flag.

## Independent checks by kind

| Execution | Independently verified products |
| --- | --- |
| generation | The private nine-file input ZIP and inventory must contain the exact pinned ELF, supported original ROM, overlay layout, regenerated ELF contexts, transformed ROM/symbol/runtime inputs, and ABI header. The harness verifies the ELF against the public pin, reruns the fixed N64Recomp context dump with ELF-derived size recovery, byte-compares both contexts, reruns the tracked private-input transformer, byte-compares all three transformed inputs, executes the fixed N64Recomp generator, runs the tracked normalizer, and requires the complete normalized tree to equal the generated-source ZIP. It then recounts generated bodies/wrappers and reconciles every public inventory/table/report denominator. The ZIP and every detailed input remain ignored; public evidence receives only fixed-schema commitments. |
| compiler-clang, compiler-gcc, compiler-msvc | The exact generated-source ZIP must equal the shared source inventory. The harness checks a byte-pinned repository build closure, selects the hash-bound compiler from fixed host locations, verifies its family/version and fixed option-set digest, configures the repository-owned CMake/Ninja build, recompiles the complete source set, runs the object-shape audit, and executes the link-smoke, baseline whole-object, and patch whole-object probes. A separately staged fixed-name smoke executable must also contain the required generated support and emit a nonce-bound proof. No compiler may reuse another family's archive as evidence. |
| forced-object-link-audit | The generated-source ZIP again equals the shared inventory. Both selected audit libraries and their result records, minimal-runtime result, host inventories, overlay tables, and relocation table match public hashes. The harness selects the authenticated Clang compiler record and reruns the complete repository-owned CMake/Ninja build plus all three whole-object targets against the exact source ZIP. A fixed-name nonce-bound probe remains supplementary; it cannot substitute for compilation and forced linking of the real source closure. |
| clang-static-analysis | The analysis source ZIP and inventory must equal the tracked `phase4-handwritten-bridges-analysis-v2` policy: the minimal runtime, generated-overlay runtime, custom-overlay relocator, both project headers, the fixed synthetic ABI header, and one fixed include translation unit for each bridge. The hardcoded Clang lookup must find the exact public toolchain bytes; Clang analysis is rerun independently for all three translation units and every plist must contain no diagnostics. |
| address-sanitizer, undefined-behavior-sanitizer | The same exact source archive/inventory and structured result match the public record. The harness—not the request—selects the pinned Ubuntu-24.04 GCC/Clang toolchain, compiles the bound bridge with fixed ASan/UBSan flags and a repository-owned probe, requires a real negative-control diagnostic, and then runs the clean nonce-bound probe. Caller-supplied marker binaries are not products and fail the closed product set. |
| reproducibility-run-a, reproducibility-run-b | Each run independently performs the same pinned-ELF context, private transform, N64Recomp generation, normalization, and complete-tree comparison as the generation execution. Its private input ZIP/inventory, generated-source ZIP, normalized run payload, generated and CPU-section inventories, three overlay/relocation products, report set, source inventory, and both archive-member inventories are canonical and match the same public digest set. The outer validator additionally requires the two executions to share the same case, inputs, declaration, pins, and environment while remaining distinct executions. |
| configuration-mutation | The base configuration, mutated-configuration set, and predeclared expectation match public hashes. The harness derives additions, removals, renames, section moves, lookup changes, patch changes, and compiler-option changes from canonical base and mutated observations and requires exact equality with both the declaration and public result. |

PE probes execute from verified private copies on Windows. ELF probes execute
from verified private copies on a POSIX host or through a verified copy of the
absolute `C:/Windows/System32/wsl.exe` boundary and fixed `Ubuntu-24.04`
distribution. The request cannot select a distribution, compiler, command,
argument, or environment. Compiler, analyzer, and sanitizer identities are rechecked
around their replays. Child time and output are bounded; detached work is not
accepted. The full-source compiler replay and outer harness limits are 1,800
seconds per execution; ordinary probes retain the 20-second child limit.

## Acyclic order and preconditions for a trusted completion run

The construction order is deliberately acyclic:

1. Commit the production harness and its validator pin together. Trusted
   execution requires the worktree bytes, Git index blob, and `HEAD` blob to be
   identical, in addition to the fixed SHA-256 pin.
2. Run the pin-identity test so the committed harness bytes and pinned SHA-256
   are identical.
3. Produce all eleven product sets from the same exact private inputs and public
   pins. Do not reuse one compiler environment as another.
4. Preserve separate A and B reproducibility artifacts even when their bound
   normalized digests match.
5. Build and validate the ignored Phase 4 private audit plus its strict
   non-completion G3 projection, without any G2 input.
6. Derive the G2 CPU case from that validated pair, then close every G2
   requirement with its own trusted private evidence.
7. Obtain the human acceptance required by the dependency architecture ADR.
8. Add the validated G2 digest and private-body digest to the final public
   completion record, validate both private bodies and their CPU cross-binding,
   and only then sign with the ignored project completion key.

After the harness commit exists and the coordinated artifacts have been placed
under the ignored results tree, the exact repository-root invocation is:

```powershell
tools\venv\Scripts\python.exe scripts\validate_phase4_manifest.py `
  --manifest tools/results/phase4/completion/phase4-completion.json `
  --schema schemas/phase4-generated-manifest.schema.json `
  --g2-evidence tools/results/phase4/completion/g2-public.json `
  --g2-private-evidence tools/results/phase4/completion/g2-private.json `
  --g2-schema schemas/g2-completion-evidence.schema.json `
  --private-evidence tools/results/phase4/completion/phase4-private.json
```

Success from a direct harness invocation is only a product audit. Only the
command above combines the tracked harness, structured private bodies, public
schemas, G2 gate, exact cross-pins, raw private-body digest, and anonymous
completion signature into a trusted Phase 4 verdict.

## Reproducible product preparation

`scripts/prepare_phase4_products.py` replaces hand-built production trees with
one bounded preparation step. Its ignored recipe has this closed top-level
shape:

```json
{
  "schema_version": 1,
  "kind": "jfg-phase4-product-preparation",
  "sources": [],
  "executions": []
}
```

Each source is exactly one of:

- `{"id":"...","path":"relative/file"}` for an existing bounded file;
- `{"id":"...","directory":"relative/tree","preparation":"deterministic-zip"}`
  for a source tree packaged in sorted order with fixed ZIP metadata;
- `{"id":"...","source":"...","preparation":"zip-file-inventory"}`; or
- `{"id":"...","source":"...","preparation":"archive-member-inventory"}`.

Each execution contains exactly `evidence_kind` and a `products` object mapping
the fixed product kinds in the closed matrix to source IDs. The recipe must
contain all eleven evidence kinds exactly once. It cannot contain a command,
argument vector, shell fragment, environment assignment, pass claim, or
execution transcript. Public-result wrappers, analyzer/sanitizer outputs,
normalized run payloads, mutation observations, and probe executables must
already have been produced by their real build or test job. The helper never
creates them.

From the repository root, after placing the recipe and real outputs beneath an
ignored source root, run:

```powershell
tools\venv\Scripts\python.exe scripts\prepare_phase4_products.py `
  --recipe tools\results\phase4\production-recipe.json `
  --source-root tools\results\phase4\raw `
  --bundle-root tools\results\phase4\completion
```

The bundle root must not already exist. The helper will not overwrite prior
evidence. It writes `production/<evidence-kind>/audit-plan.json`, all fixed-name
products, and `phase4-prepared-products.json`. The index contains exact
artifact descriptors and SHA-256 identities for a later private-body builder;
it contains no source paths or private commands. All reads, entry counts,
expanded archive sizes, individual artifact sizes, and the aggregate staged
size are bounded. Source links/reparse points and escaped paths fail closed.

The real prerequisites are:

1. one private nine-file generation-input tree, its deterministic ZIP/inventory,
   and the exact generated source tree/ZIP from the pinned generator and inputs;
2. real canonical generation/table/report products;
3. baseline and patch archives plus the build-produced library/runtime result
   wrappers and host inventories;
4. distinct Clang, GCC, and MSVC result wrappers, the same exact generated
   source archive/inventory in each compiler execution, and runnable smoke
   probes; the harness itself rebuilds and whole-object-links all three;
5. a forced-object executable that was linked using the audited object set;
6. the exact nine-file `phase4-handwritten-bridges-analysis-v2` source tree,
   Clang result wrapper, and real analyzer tool whose bytes match the public
   pin;
7. ASan and UBSan result wrappers for pinned Linux GCC/Clang. The harness builds
   both negative and positive probes itself from the bound bridge source;
8. distinct A/B normalized reproducibility outputs from identical pins; and
9. base/mutated observations, the predeclared expectation, and the mutation
   result wrapper.

The helper derives only deterministic ZIPs, ZIP file inventories, static
archive member inventories, artifact digests, audit plans, and the prepared
index. It does not synthesize semantic success. The pinned production harness
independently reparses those containers, executes the probes/analyzer controls,
and compares all public bindings during trusted private-evidence validation.

## Private body assembly after the harness commit

`scripts/build_phase4_private_evidence.py` consumes the prepared index and runs
all eleven pinned production audits before it may write `phase4-private.json`
and `phase4-g3-product-projection.json`. This is a pre-G2 product audit, not a
completion claim. Its ignored recipe contains only this closed shape:

```json
{
  "schema_version": 1,
  "kind": "jfg-phase4-private-body-preparation",
  "identity_sources": [{"path": "relative/input.bin"}],
  "executions": [
    {
      "evidence_kind": "generation",
      "id": "generation-production-01",
      "case_id": "pinned-generation-case",
      "environment": {
        "environment_id": "generator-windows-x64",
        "platform_id": "windows-x64",
        "architecture_id": "x86-64",
        "toolchain_sha256": "<real 64-hex tool identity>"
      }
    }
  ]
}
```

The recipe must contain all eleven kinds exactly once and distinct execution
IDs. Reproducibility A/B use the same case and environment; Clang/GCC/MSVC use
distinct environments. `identity_sources` supplies only raw inputs whose
digests are not already present among prepared products, normally the input ELF
and compiler option-set artifacts. Paths are relative to the ignored identity
root. Commands, argument vectors, `passed`, result records, and transcripts are
not accepted recipe fields.

After the harness and its exact validator pin have been committed together,
run:

```powershell
tools\venv\Scripts\python.exe scripts\build_phase4_private_evidence.py `
  --recipe tools\results\phase4\private-body-recipe.json `
  --identity-root tools\results\phase4\raw `
  --prepared-index tools\results\phase4\completion\phase4-prepared-products.json `
  --patch-provenance tools\results\phase4\completion\n64recomp-patch-provenance.json
```

There is no user-authored aggregate core. The builder derives all eleven G3
fields from the exact prepared semantic products, repository dependency lock,
fixed generator executable, generation input archive, and the ignored
successful patch-applicator record. Missing patch provenance, any public-result
count that differs from the semantic inventories, or any host/member ownership
disagreement fails closed before a production harness runs. The emitted
projection has a strict non-completion kind, `completion: false`, no gate or
predecessor claim, and a private-body digest that is excluded from the Phase 4
public-claim hash to avoid circularity. The later G2 CPU product binding
separately commits that exact digest, all eleven projection fields, and stable
identities for all eleven private executions. Final completion exposes the same
digest under its attestation and rejects any cross-binding mismatch.

The builder derives public record/result-set bindings, pins,
input/output/artifact sets, and structured result records. It invokes the
clean-HEAD production harness for every execution and accepts only the exact
nonce/binding transcript, then reruns repository-owned full private validation
before writing either canonical body. Thus its `passed: true` fields are
emitted after execution, never copied from the recipe. It refuses existing
private assembly/projection outputs; partial ignored execution artifacts are
diagnostic products and are not a completion claim.

## Canonical public completion claim

The final tracked location is `evidence/phase4-completion.json`; the unsigned
synthetic example is not a completion template. Finalization independently
re-derives the same eleven-field core from the prepared products and ignored
patch provenance; it accepts no aggregate values from its caller. Derivation
covers:

- all three compiler records;
- analyzer and ASan/UBSan records;
- baseline, patch, and minimal-runtime records;
- the configuration-diff record;
- generated/source/analysis/member inventories;
- lookup, lifecycle, relocation, report, normalized-run, base-config,
  mutated-config-set, and predeclared-expectation digests.

Finalization is deliberately unavailable until the tracked production harness
and pin have been committed, the private Phase 4 body binds the derived public
claim, and all of these G2/ADR conditions are true:

- ADR 0003 contains the exact explicit status line
  ``- Status: Accepted by `TK22-26` ``;
- the public G2 body passes the pinned G2 schema and binds the accepted ADR's
  exact byte digest;
- the ignored G2 private body passes every pinned executable G2 audit;
- the public G2 and Phase 4 `jfg_decomp_commit`, `n64recomp_commit`,
  `supported_input_id`, and `dependency_lock_sha256` pins match; the exact G2
  ROM digest remains only in the ignored G2 private body; and
- the final gate's `predecessor_g2_evidence_sha256` is derived from the
  canonical validated G2 public body.

After those prerequisites and the Phase 4 private body exist, the final command
is:

```powershell
tools\venv\Scripts\python.exe scripts\build_phase4_completion_manifest.py `
  --prepared-index tools\results\phase4\completion\phase4-prepared-products.json `
  --patch-provenance tools\results\phase4\completion\n64recomp-patch-provenance.json `
  --private-evidence tools\results\phase4\completion\phase4-private.json `
  --g2-evidence tools\results\phase4\completion\g2-public.json `
  --g2-private-evidence tools\results\phase4\completion\g2-private.json `
  --private-key tools\keys\phase4-completion-signing-key
```

The builder executes both trusted private validators before signing, derives
the private-body and G2-public digests, signs with the pinned anonymous policy,
reruns central trusted completion validation, and only then creates the
previously absent canonical tracked manifest. It refuses to overwrite an
existing claim.

Verification and signing select `ssh-keygen` only from fixed absolute system
locations, never from ambient `PATH`, and execute a private staged copy whose
byte identity is rechecked after use so the tool cannot be swapped during a
run. The tracked policy does not pin a host-specific binary digest: OpenSSH
builds legitimately differ across the Windows and Linux validation hosts, and
a cross-host pin would make one platform's signature verification permanently
fail closed.
