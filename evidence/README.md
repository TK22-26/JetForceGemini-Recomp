# Public completion evidence

The canonical tracked Phase 4 completion claim is
`evidence/phase4-completion.json`. It does not exist until all private Phase 4
and G2 products pass their repository-pinned executable audits, ADR 0003 is
explicitly accepted by `TK22-26`, and the aggregate is signed with the ignored
project completion key.

`examples/phase4-generated-manifest.example.json` remains an unsigned synthetic
schema fixture. It is never promoted, copied, or renamed into this directory.
The final manifest is created only by
`scripts/build_phase4_completion_manifest.py`, which revalidates both ignored
private evidence bodies before writing the claim.

Only the public-safe signed aggregate belongs here. Product trees, generated
sources, binaries, ROM-backed inputs, unrestricted logs, private evidence
bodies, and the private signing key remain beneath ignored `tools/` paths and
must never be committed.

The same rule applies to Phase 6. Its tracked public summary contains only
safe counters and hashes. Trusted completion verification additionally reads
the ignored native evidence body, rechecks its clean ancestor revision and
source closure, and validates its executable, generated-corpus, emulator,
probe, MMIO, determinism, and original-entry sanitizer bindings.

Phase 7 is governed by `config/phase7-acceptance.json` and is complete.
`phase7-completion.json` records the two required visual scenes, deterministic
repetitions, zero unsupported commands, and renderer-independent simulation
hashes. The Phase 7 validator reconciles that summary against the closed
contract.

`phase7-rt64-task-smoke.json` is an intermediate sanitized aggregate. It proves
one unclassified private task reached the pinned renderer through the registered
bridge path; its explicit negative claims prevent it from being mistaken for
pixel, presentation, scene-pair, or Phase 7 completion evidence.

`phase7-boot-title.json` and `phase7-gameplay.json` are the accepted scene
aggregates. They record exact task-submission captures paired with their later
VI double-buffer swaps, independent semantic acceptance, deterministic GPU
readback, and fixed-threshold pixel comparison. They contain no task, command,
address, path, image, or ROM body.
