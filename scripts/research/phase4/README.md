# Phase 4 research tooling

One-off helpers written during Phase 4 CPU generation and evidence
production. They were previously kept in the git-ignored `tools/` tree, which
meant project-authored code could not be reviewed or recovered from the
repository. They are tracked here for provenance only:

- They are not part of any build, test, evidence closure, or pinned harness.
- They reference private result trees under `tools/results/phase4/` that are
  not tracked, so they will not run from a fresh checkout.
- They are not maintained; treat them as a record of how the private Phase 4
  investigations were carried out, not as supported tools.

| File | Purpose |
|---|---|
| `phase4_run_private_stress.py` | repeated execution of a pinned producer over a private case, hashing outputs |
| `phase4_scan_private_plan.py`, `.sh` | parallel scan of a private evidence plan for structural mismatches |
| `phase4_upgrade_private_v3.py` | one-time upgrade of a private binary module/suite layout to the v3 struct format |
| `v3_corrected_build.sh` | WSL rebuild of the corrected v3 normalized tree in a scratch copy of the repository |
| `phase4_*_trace.cpp` | throwaway probes used while diagnosing dispatch traps and exception propagation |
