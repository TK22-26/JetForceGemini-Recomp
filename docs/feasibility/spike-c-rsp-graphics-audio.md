# Phase 3 Spike C: RSP, graphics, and audio

> Historical Phase 3 spike. Its original graphics and audio blockers were
> subsequently closed for G2 by the signed Phase 4 aggregate. It does not
> describe current project status; see `docs/dashboard.md`. Rendering and
> first-frame acceptance remain later Phase 7/M3 work.

- Status: graphics output blocked; audio control flow viable
- Evidence scope: pinned-source inspection plus a maintainer-attested private, local, ROM-backed boot capture
- Tracked data rule: aggregate metadata only; task bodies, generated microcode code, buffers, framebuffers, addresses, paths, and raw names remain untracked

## Outcome

The audio route has a representative control-flow candidate. The pinned RSP recompiler generated code for the custom audio program, the generated code compiled against the pinned runtime interface, and all 196 captured boot-window audio command streams exited normally. This does not establish the proposed native path or sample correctness: the output was not compared against an audio reference, no referenced memory closure was captured, and the second overlay variant was not exercised in the boot window.

The pinned renderer has no native handler for the game's custom graphics family. The pinned RSP recompiler is not a graphics fallback because generation stops on an unsupported display-processor register read. A Mupen64Plus run configured with GLideN64 advanced through 900 emulated frames and submitted nine graphics tasks. Every captured graphics microcode window matched GLideN64's public JFG detector fingerprint. This proves configuration, identification, task submission, and frame progression; it does not prove correct rendering.

The shipping direction is therefore a project-authored RT64 extension for this bounded graphics family. The GLideN64 implementation remains a local research reference only; its GPL source is not copied, linked, generated into, or committed to this repository. A render-validating graphics fallback has not yet been established.

## Static inventory and overlays

| Program | Container bytes | Captured active bytes | Captured data bytes | Overlay disposition |
|---|---:|---:|---:|---|
| Boot loader | 384 | 0 | 0 | None observed; statically inventoried only |
| Audio primary | 6,208 | 4,096 | 2,048 | One slot and two variants confirmed by generation; no boot-window switch observed |
| Graphics primary | 4,752 | 4,096 | 2,048 | Container exceeds IMEM; exact overlay topology is still unproven |

The current [N64Recomp pin](https://github.com/N64Recomp/N64Recomp/tree/ffb39cdad1da5de07eaaa48bd1db4a89a7986771) implements overlay slots and permutation dispatch despite older overview text implying otherwise. The generated audio wrapper contained two permutations for one slot and compiled successfully.

## Representative task evidence

The ignored local capture ended with an explicit count of 205 unique tasks over the boot window:

| Task class | Count | Frame range | Unique command bodies | Unique active programs | Unique program-data windows |
|---|---:|---:|---:|---:|---:|
| Graphics | 9 | 48-668 | 9 | 1 | 1 |
| Audio | 196 | 34-900 | 196 | 1 | 1 |

The framebuffer evidence was audited and rejected. The emulator screenshot was black, and the correctly decoded big-endian VI-origin RDRAM sample was all zero. A previously noted nonzero RDRAM sample used an invalid little-endian interpretation of the VI register and was not a framebuffer. Under GPU HLE, the lack of RDRAM writeback is not itself evidence of rendering either way. The tracked manifest therefore records render output as `not-established`.

All screenshot and memory bodies remain `PRIVATE_REGENERABLE` and ignored. The aggregate capture result is explicitly `maintainer-attested`; no regenerating capture or execution harness is tracked yet. A deterministic Git-index blob scan provides defense in depth against body-like fields and encodings, while the closed manifest validator rejects body, path, address, source-name, and symbol fields. The generic scan is not proof that arbitrary encoding is impossible. A current-pin canonical lock also rejects self-consistent changes to attested counts or narrative evidence; it is change control, not independent proof of the private capture.

## Graphics behavior and RT64 gap

The custom graphics family is a Fast3D-relative dialect with a small, bounded custom surface. Inspection of the [GLideN64 family implementation](https://github.com/gonetz/GLideN64/tree/020b6ab5de1f13d8e673c0a23529f1de1e507c9d/src/uCodes) found seven base custom handlers and one game-variant override, with remaining behavior delegated to shared Fast3D machinery. These counts define scope; no implementation text, names, opcodes, or game data are copied.

At the pinned [RT64 commit](https://github.com/rt64/rt64/tree/5473732a822a4423b5696e7cb18fecc425a59875), the microcode registry has no entry for this family. The project now has an original bounded semantic fallback for the reviewed custom surface, without an RT64 patch. A shared base-family visual renderer or RT64 binding still must be added and verified using only sanitized results from private execution.

The executed task-path candidate was BizHawk commit `bdddf4a58aa1a022afb11dc73294a81a5aa7bbd5` (tag 2.11.1), whose source tree pins GLideN64 commit `4f1f88a415630481a9ce58f11279e6ec94bbe2d1`. The private run used its Mupen64Plus core with plug-in enum value 4; the [matching BizHawk tag](https://github.com/TASEmulators/BizHawk/blob/2.11.1/src/BizHawk.Emulation.Cores/Consoles/Nintendo/N64/N64SyncSettings.cs) maps that value to GLideN64. A byte-order-correct local check confirmed that the executed GLideN64 pin contains the detector record matching the captured program. The manifest binds this result to the official package and packaged plug-in SHA-256 values.

The seven-base-plus-one-variant scope estimate comes from a separately inspected, newer GLideN64 commit, `020b6ab5de1f13d8e673c0a23529f1de1e507c9d`; it is not represented as the executed binary. The tracked manifest retains only commit and artifact hashes, aggregate counts, and boolean match results. It records the private fingerprint algorithm and oracle match without disclosing the small-domain digest.

The newer bounded fallback has also completed one ignored private transaction with brokered referenced-memory closure and an independently generated exact semantic match. The tracked evidence records only that allowlisted aggregate. This satisfies the binding G2 graphics clauses for a real task through the proposed native path and tested `F3DDKR_GBI` bounded fallback. It does not publish task data and does not establish pixels, visual correctness, full task coverage, or shipping integration; those are later Phase 6 and Phase 7/M3 concerns. The external implementations remain research references, and human license review remains mandatory before any integration decision.

## Audio path

The pinned RSP tool was built under WSL, generated a two-permutation audio
implementation, and produced compilable C++ against the pinned runtime
interface. The project-owned worker and adapter expose referenced memory only
through the checked broker and stage all mutable/output writes transactionally.
Ignored local harnesses load the private inputs without printing or tracking
them.

Results:

- Generation and strict compilation: pass.
- One approved real primary task: broker closure, complete transactional output,
  exact independent oracle comparison, and completion ordering pass.
- Both internal permutations: synthetic success coverage passes.
- Generated secondary fallback: real generated entry, bounded broker access,
  explicit unsupported-return rejection, zero completion, and rollback pass.
- Real secondary task: not observed and retained as useful non-gating coverage.

This satisfies the binding G2 audio clause for one real task through the
proposed native worker. Phase 6 later connects the same worker to the full
scheduler; a real task from the second permutation is not an additional G2
requirement.

## Decision and next gate

Spike C's graphics and audio G2 mechanisms are proven; the trusted overall G2
bundle and unrelated requirements remain pending:

1. Bind the proven real primary audio execution and tested secondary fallback into the trusted overall G2 bundle; a real secondary task remains useful non-gating coverage.
2. Bind the proven graphics fallback execution into the trusted overall G2 bundle. Phase 6 later integrates scheduler/VI behavior; Phase 7/M3 implements the visual renderer or RT64 binding and presentation.
3. During Phase 7, run the required private frame corpus through the visual path and compare pixels with an independent local oracle; do not treat semantic records as rendered output.
4. Keep every task body, generated microcode body, display list, framebuffer, and unrestricted log in ignored local storage. Only the schema-validated aggregate result may cross into Git or GitHub.

The full G2 decision remains separate because this spike does not close the
other required mechanisms or the trusted evidence bundle. Renderer integration,
gameplay coverage, broader audio fidelity, and packaging remain later work.
