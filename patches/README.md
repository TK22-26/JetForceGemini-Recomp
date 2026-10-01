# Patch Categories

Handwritten game patches are not part of the Phase 2 skeleton. When patches
begin, each must have a validated manifest and belong to exactly one category:

- `required`
- `compatibility`
- `widescreen`
- `hfr`
- `input`
- `save`
- `fix`
- `mod`
- `debug`

Every manifest records the original behavior, a non-copying upstream evidence
reference, an accountable owner, tests, and rollback. Enhancement categories
(`widescreen`, `hfr`, `input`, `mod`, and `debug`) require a nonempty feature
flag; they cannot silently alter the compatibility baseline.

Compatibility and enhancement changes may not share a pull request.
