# NAV-EXIT-SENTINEL: absent destination high byte read as a level number

- Status: source-proven defect; ordinary/FF destination, relocated-field and both-memory-layout regression tests pass; all-three final native builds pass; affected live-route verification remains pending.
- Severity: navigation metadata can identify an invalid destination; native transition code is unaffected.
- Affected: navigation exit reader before this regional architecture continuation, all three revisions.

The original `controlPlayer` reads a low destination byte and a high byte from
an exit definition. A high byte of `0xFF` means to retain only the low byte.
Our reader always ORed the high byte into the result: `34 FF` became `0xFF34`
instead of level `0x34`. This was discovered during original-record review,
not reported as a reproduced campaign or native-hardware defect. The frequency
of affected authored exits has not been measured.

Original US/PAL instruction sequences have the same local position; JP inserts
two earlier instructions. Each owner is independently hashed, the member sites
are pinned separately, and generation checks the complete sentinel decision.
The candidate reader uses qualified definition fields and the original sentinel
rule. Tests cover ordinary high bytes, zero, `FF`, both memory layouts and
relocated record fields. Damaged original-schema fixtures must reject generation.

Private evidence: `regional-architecture-20261101-owner5h`,
`remaining-record-consumer-review-v1` and `reviewed-member-bindings-v12.json`.
The complete 111-test host suite and all-three original binding qualification pass. No live route or release pass is implied. The shared
[regional issue](regional-rom-support.md) owns integration/build acceptance.

Lesson: adjacent bytes are not necessarily an unconditional integer. Preserve
sentinel behavior from the original consumer, including region-specific instruction
positions, before exposing the value as navigation or modification input.
