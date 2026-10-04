# Patches

The [N64Recomp patch series](n64recomp/README.md) supports local generation.
`scripts/apply_n64recomp_patchset.py` applies the maintained series to its
pinned upstream revision. Retain patch ordering and upstream license notices.

`rt64/`, `plume/`, and `cic/` retain notices for third-party material used in
the project. See [third-party notices](../THIRD_PARTY_NOTICES.md).

## Game patch manifests

The manifest schema supports `required`, `compatibility`, `widescreen`, `hfr`,
`input`, `save`, `fix`, `mod`, and `debug` categories. Each patch records original
behavior, supporting evidence, owner, tests, and rollback.

Enhancements require explicit feature flags and must preserve the compatibility
baseline. Keep compatibility fixes and enhancements in separate pull requests.
The [example manifest](../examples/patch-manifest.example.json) is a validation
fixture, not a shipped game patch.
