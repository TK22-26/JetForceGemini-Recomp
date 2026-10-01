# Pinned Upstream Baseline

The authoritative machine-readable pins are in `dependencies.lock.json`.

| Component | Commit | Use |
|---|---|---|
| JFG decomp | `b49aa4791e8fb1e7acd3bba10346876358d0a9a7` | Local analysis/build only |
| N64Recomp | `ffb39cdad1da5de07eaaa48bd1db4a89a7986771` | Local generation tool |
| N64ModernRuntime | `589bbf018a3e6d3646ddf7de1e7919f1b7e99bb1` | Candidate runtime |
| RT64 | `5473732a822a4423b5696e7cb18fecc425a59875` | Candidate renderer |
| RecompFrontend | `9ef9cdfdead7649247ab4957f43517f44c33931d` | Excluded pending permission |

The JFG build requires Linux/WSL, a user-supplied US retail ROM with SHA-1
`493ced9008dbe932d6e91179b68e8630cf23a023`, and the versions recorded in
the lockfile.

## Phase 1 equivalence contract

Phase 1 was reproduced in clean Ubuntu 22.04 and Ubuntu 24.04 WSL2
environments. Each environment performed setup, extraction, and two clean
verified builds. The schema-validated, public-safe result is recorded in
`phase1-build-evidence.json`.

Two clean environment results are equivalent only when:

- Both generated ROMs match the supported ROM SHA-1.
- Their ELF SHA-256 hashes match.
- All 326 ELF section records and normalized section-table hashes match.
- Allocated sections do not overlap and every linker-map record present in both
  representations agrees.
- Defined global/weak names have no conflicting values and every shared map
  symbol agrees.
- Symbol, binding/type, and relocation counts match.
- The validated aggregate `build/report.json` measures match.
- The 157-slot ROM overlay table and 155-entry splat overlay layout pass their
  bounds, identity, and range checks and produce matching aggregate evidence.
- The pinned source tree, submodule pins, downloaded IDO/objdiff artifacts,
  and resolved build-tool versions are recorded.

The two 16-bit relocation-size fields in each overlay header are byte lengths,
not entry counts. Phase 1 validates eight-byte alignment, records both byte and
derived entry totals, includes primary and secondary tables in each ROM span,
and requires all 155 populated spans to remain in bounds and non-overlapping.
The table and data coordinates are runtime-provided through a private layout
file outside the checkout or under an ignored path. They are deliberately not
embedded in tracked code, documentation, or aggregate evidence. Public evidence
records only successful range-validation predicates, counts, totals, and
cryptographic commitments to the private detailed manifests.

Raw linker-map hashes are recorded per environment because binutils 2.38 and
2.42 format equivalent maps differently. Their parsed section and symbol
consistency results must still be identical and mismatch-free. Map consistency
is explicitly bounded to the checked intersection: section coverage is complete
at 167 of 167 candidates, while symbol coverage is partial at 9,933 of 14,603
candidates. The 4,670 missing symbol records are not claimed to have been
map-verified; they remain covered by the independently hashed ELF symbol-table
aggregate and the cross-environment build comparison.

The ELF parser accepts both decimal and `0x`-prefixed hexadecimal symbol sizes,
requires each readelf symbol table to contain exactly its declared number of
entries, and requires indices to cover the declared range. This prevents a
large hexadecimal-sized symbol from being silently omitted from the aggregate.

## Evidence verification boundary

Repository CI can validate the public JSON schema, environment-ID
correspondence, hash shape, category totals, map coverage arithmetic, overlay
population arithmetic, relocation byte-to-entry conversions, and the recorded
success verdict. It cannot rebuild or inspect the ignored ROM-dependent
artifacts because the required input ROM, ELF, linker maps, and detailed
environment records are deliberately not tracked.

The four clean-build results and their equivalence are therefore a maintainer
attestation derived from the two local environment records. The tracked
document labels that distinction directly under `verification`. Its schema can
also represent a failed or divergent comparison with `equivalent: false` and
explicit divergence reasons; the standalone semantic validator requires the
published baseline itself to remain successful:

```text
python3 scripts/compare_phase1_evidence.py --validate-aggregate docs/upstream/phase1-build-evidence.json
```

Full ELF files, symbol exports, build ROMs, extracted assets, and raw progress
reports remain local. Only aggregate counts and cryptographic hashes may be
promoted after the repository hygiene check.

The master plan names Phase 1 helpers under `tools/`, but this repository
reserves all of `tools/` for ignored third-party/local material. Project-owned
equivalents therefore live under tracked `scripts/`:

- `scripts/build_upstream.py`
- `scripts/validate_elf.py`
- `scripts/parse_upstream_report.py`
- `scripts/summarize_overlays.py`
- `scripts/compare_phase1_evidence.py`
