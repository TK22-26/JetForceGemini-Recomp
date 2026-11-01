# ROM-REGIONS: PAL and Japanese ROM support

- Status: matching regional metadata implemented and verified on 2026-11-01; playable native PAL/JP support remains open.
- Severity: compatibility limitation; the native game still supports only the pinned US revision.
- Affected: ROM generation, regional host address/timing assumptions, launcher/runtime admission and gameplay qualification.

## Original-game evidence

The owner reconfirmed **no music leaving Walkway on NTSC N64 hardware**, then heard music in the
original PAL ROM in EmuHawk after loading Juno in Walkway. PAL hardware and Japanese music behavior
remain untested. This regional difference is not evidence of a native NTSC bug. The copied PAL save
worked in that one review session; it does not prove general cross-region save compatibility.
[Music evidence and rollback](flight-transition-missing-music.md) preserve the original correction.

## Implemented regional foundation

[ROM profiles](../../../scripts/build/rom_profiles.py) identify the exact original revisions below,
normalize the three standard N64 storage byte orders for metadata preparation, and reject unknown,
truncated or modified images. The input file is never rewritten. Recognition is distinct from native
runtime admission: both native build entry points continue to reject PAL/JP before generation.

| Profile | Normalized SHA-1 | Matching reconstruction | Executable overlays after bounded expansion |
|---|---|---|---|
| US | `493ced9008dbe932d6e91179b68e8630cf23a023` | Existing US pipeline | Existing qualified US generated inventory |
| PAL | `50651c4e0c46332f7f0b45870263f0a8b9a49602` | Byte-for-byte verified | 155 |
| Japan / Star Twins | `15099233760b36e7afad7da36b9464da1512c4b1` | Byte-for-byte verified | 155 |

[prepare_regional_metadata.py](../../../scripts/build/prepare_regional_metadata.py) clones the pinned
decomp into a new private workspace, extracts original instructions, builds ELF/map metadata and
requires the rebuilt ROM to match every input byte. It writes an explicit `native_playable: false`
manifest with remaining work. No ROM, generated game code, ELF, personal save or capture is committed.
The upstream checkout and dependency pin remain unchanged. The
[overlay metadata helper](../../../scripts/build/regional_overlays.py) reads all 157 linker slots,
requires the expected 155 populated overlays, checks ordered bounds, entry points and relocation
record sizes, and describes original text/data/BSS separately. Relocation lengths are **bytes**;
using them as record counts would overrun adjacent content. No extracted game body is copied into
public source.

Run this prerequisite in WSL/Linux with the normal MIPS build tools installed:

```sh
python3 scripts/build/prepare_regional_metadata.py \
  --rom /private/input/region.n64 --workspace /private/new-regional-workspace
```

The workspace must be new, private and contain no spaces in its path. The command accepts only the
PAL and Japanese hashes above. It is a metadata developer tool, not a Play command or launcher option.

## Actual failures, causes and remedies

The pinned decomp is `b49aa4791e8fb1e7acd3bba10346876358d0a9a7`. Initial stock regional builds failed:
regional object enumeration omitted top-level assembly, common SDK source compilation was unrelated
to the regional linker input, and Japanese C files depended on incomplete regional headers. The
metadata tool enumerates regional assembly and reconstructs C-marked segments directly from the
original instructions. It does not substitute US game bodies or invent missing overlay definitions.

PAL additionally referenced five shared linker aliases whose named asset/overlay segments do not
exist in its basic map. Removing those unused aliases in the private clone permits an exact rebuild;
the asset lookup-table extent remains unqualified. Japanese reconstruction initially differed by
10,605 bytes. Its opaque executable prefix at ROM offset `0x9E4D0` was classified as DATA and moved
after the following audio microcode. Classifying that original prefix as TEXTBIN preserves section
order and produces an exact hash match. The tool checks the pinned input shape before applying this
adjustment; an unexpected future metadata layout fails closed.

Private probes also exposed a helper named `queue.py` shadowing Python's standard module and a
transient WSL `/tmp` workspace disappearing between invocations. Isolated Python execution and
persistent private workspaces resolved those orchestration failures. No production guard setting,
investigation identity or accounting counter was changed to retry them.

## Validation and remaining work

The committed metadata tool was run from fresh workspaces against both original regional images.
Both builds pass the upstream SHA-1 check and an independent byte-for-byte comparison. Regional
byte-order, rejection and metadata-boundary tests pass. Private evidence ID:
`reorganization-followups-20261101`, including failed stock builds, mismatch classification and
`regional-full-tool-pal.json` / `regional-full-tool-jpn.json` from the final tool.
The first matching stage exposed only zero PAL overlays and one Japanese overlay; exact byte
reconstruction alone therefore did not establish usable code coverage. The completed expansion
now reconstructs all 155 code overlays in each image, with the same byte-for-byte check.

A further private run with the pinned, patched N64Recomp successfully dumps both ELF contexts.
Each has **157 executable sections** (entry, main and 155 overlays), compared with the current
US transform's 156-section contract. Main relocation tables have 520 entries each; total parsed
relocations are 28,432 PAL and 27,914 Japanese. The generated contexts describe 2,920 PAL and 2,928
Japanese executable function symbols. These are regional inventories, not substitutes for the US
signed denominators or proof that every function boundary is correct.

The pinned maps name 0 of the boot bridge's 69 SDK entry points for PAL and 41 for Japan. A missing
name is missing identification, not proof that a routine is absent from the ROM. No US address is
used as a guessed replacement. The private `regional-context-results.json` records the contexts,
linker boundaries and exact missing-name lists.

This does **not** complete native regional support. Function-boundary qualification, missing SDK
identification, CPU/RSP generation, the regional static-section layout and per-region host hooks
are still required. The US transformer deliberately retains its closed identity and inventory
checks; changing its expected counts would not establish regional correctness. US-specific addresses, bootstrap/timing,
audio and presentation assumptions must be ported and validated, followed by real native boot,
controller/save and normal/skipped-transition qualification. Neither regional ROM was run by the
native recomp in this work. No regional gameplay acceptance, release or support claim is made.

## Audio program identity

A bounded comparison found one exact occurrence in each regional ROM of the complete 6,208-byte
US audio microcode program and its 704-byte companion data. The existing DMA/command-table parser
accepts that shared program layout. Private regional-audio-identity.json records hashes and unique
locations. This narrows future RSP work; it does not qualify regional task submission, timing,
sequence assets or the cause of the Walkway music difference.

## Transferable lesson

Keep ROM identity, exact reconstruction, generated-code coverage, host integration and gameplay
qualification separate. A matching ROM rebuilt from opaque binary segments can have very incomplete
executable metadata. A known hash or successful emulator session cannot authorize using US host
addresses with a different regional image.
