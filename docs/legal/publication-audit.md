# Public source snapshot audit

Prepared 2026-10-01 for the owner-authorized separate public repository.
This review covers the exported source and its new Git history. It does not
certify that the project is copyright-free or approve distribution of a game.

## Publication boundary

Only tracked source at the private development tip was exported. No original
Git objects, refs, tags, pull requests, comments, workflow archives, or ignored
local files were copied. The public repository starts with one root commit
using the generic maintainer no-reply identity and UTC timestamps. The old
personal email remains only in the original private repository's history.

ROMs, assets, generated game code, saves, dumps, private evidence, executable
builds and external source checkouts are excluded. The five files below were
also excluded because licensing of their GPL-covered modifications remains
unresolved. They are absent even from the first public commit:

- `scripts/oracle_cpu_boundaries.patch`
- `scripts/oracle_device_events.patch`
- `scripts/oracle_guest_links.patch`
- `scripts/oracle_instruction_effects.patch`
- `scripts/oracle_round_even.patch`

The associated Mupen64Plus notice inventory is omitted because those patches
are absent. Maintainer diagnostics and some producer-identity tests refer to
these inputs and cannot run from this snapshot alone. Historical documentation
describes their use without distributing the patches or their outputs.

## Retained licensed material

N64Recomp patch context and embedded RT64/Plume compatibility edits retain their
pinned MIT notices. The CIC-NUS-6105 algorithm is conservatively treated as
derived from X-Scale's published implementation; its complete copyright,
redistribution conditions, disclaimer and views paragraph are now included
in the source and `patches/cic/LICENSE.upstream`. This addresses attribution
without claiming the algorithm was independently authored. The exact pinned
source and notice scope appear in [THIRD_PARTY_NOTICES](../../THIRD_PARTY_NOTICES.md).

No unlicensed JFG decompilation or RecompFrontend source tree is included.
The earlier comparison of 723 project source files against 683 decomp files
and 134 frontend files found no eight-line normalized matches of at least
240 characters. This limited heuristic misses shorter or transformed copying
and does not prove authorship. Project provenance attestations remain evidence
of the authors' stated method, not an independent guarantee.

The initial snapshot withheld a reuse license. On 2026-10-01 the owner
selected [MIT](../../LICENSE) for original contributions. Third-party terms
remain separate; this grants no rights to game content or generated output.

## Verification limits

The export is checked for forbidden paths, ROM and archive signatures, generated
game-code markers, credentials, personal paths, and the known personal email
and name. Git metadata is checked across the complete fresh history. Exact
results are recorded in [the publication handoff](../governance/publication-handoff.md).

Passing these checks establishes a bounded technical scan result. No automated
scan can certify that every possible copyright or privacy concern is absent.
New commits, dependencies, releases and attachments require their own review.
