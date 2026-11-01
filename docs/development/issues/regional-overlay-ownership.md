# Regional overlay ownership migration

- Status: original qualification and descriptor tests pass; all three original-OS new-slot/reload checks pass; complete feature validation pending.
- Affected: regional native architecture candidate on develop, original and host feature observers.
- Severity: compatibility blocker for regional feature qualification.

## Evidence and cause

The host used US generated section ordinals as module identities. PAL/JP have
a separate entry section, and empty original module slots do not become
executable sections. A constant regional index delta therefore cannot identify
every module. The private original-model inventory records all three layouts.

Original module 7 is hint text, 23 is day/night, 32 is Mr. Hints, 117 is region
ID and 137 is reflections. Their generated owners must come from the selected
descriptor. The old Mr. Hints diagnostic explicitly used section 32 while the
new US corpus assigns original module 32 to section 31; source review proves
that observer mismatch, but does not prove a user-visible dialogue regression.

## Candidate and validation

Named OriginalModule IDs now resolve through descriptor overlay-slot identity.
Native owner checks, active-section checks and table indexing use that result.
Missing or duplicate owners are rejected; no ordinal fallback exists. Synthetic
tests cover independent ordinal/slot coordinates, overlapping linked addresses,
missing owners and duplicate owners. Original guest module loading is unchanged.

This change selects the correct module; it does not qualify every offset inside
that module. Animation, dialogue, menus, fog and hook return-site layouts still
need original per-revision witnesses and live validation. No PAL/JP feature or
release acceptance follows from the descriptor tests. The separate v6 source
snapshot was captured before this candidate and cannot validate it.

Keep code/data coordinates tied to original module identity and a live overlay
owner. Never treat a generated filename or section number as a stable game ABI.

Seventeen native overlay observation/dispatch sites now use named original
code references. Recipes require the original module slot, exact function-body
hash and size, and a checked callable entry in each regional model. Identical
bytes in another overlay cannot satisfy the recipe. Discovery matched unique
complete instruction shapes within the same original module; exact selected
body bytes remain the generation guard. Linked dispatch tokens are identities,
not RAM addresses or callable pointers; execution retains the existing runtime
lifetime/dependency lease. Remaining overlay code sites and module-internal
data/layout assumptions remain open. All three original model qualifications
passed. Synthetic wrong-owner checks passed after correcting the fixture to
include the model-required main section and ROM extent. Native build and feature
behavior of this migration are pending.

## Current shared binding checkpoint

The four-hour continuation expanded named original-qualified bindings across
renderer, menu/Floyd state, dialogue, camera, rain/blur/shadow, native operations
and diagnostic observers. The current recipes qualify 435 code, 225 data and
210 instruction references per revision. Live overlay data uses a checked
owner/domain/extent view, and credits uses its actual region-specific ending
flag offset. The generated ordinal remains an implementation coordinate.

All three v16 original-OS candidates create and reload a private save into
Goldwood. All three later v21 enhanced native compile preflights pass; that
source was superseded by explicit PAL presentation/audio clock composition
before full native acceptance. These results do not close every overlay feature
or residual actor-specific binary layout. The [regional issue](regional-rom-support.md)
owns the current source/build identity and remaining implementation matrix.
