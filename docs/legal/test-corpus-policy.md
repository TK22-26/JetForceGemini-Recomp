# Test corpus and isolated execution

This policy covers developer fixtures, replay inputs, snapshots, reference
captures, and golden baselines. Public playtest reports follow the separate
[reporting guide](../playtesting.md).

## Classification

| Class | Contents and handling |
|---|---|
| `PUBLIC_SAFE` | Project-authored input recipes, synthetic fixtures, schemas, reviewed hashes and aggregates; may be tracked after review. |
| `PRIVATE_REGENERABLE` | ROM-backed snapshots, generated code, captures, save bodies, detailed traces, or dumps containing game data; local/isolated storage only. |
| `PROHIBITED` | Unknown-origin or unauthorized material, or material that cannot meet isolation requirements; do not retain/process its contents. Escalate metadata to a maintainer. |

Each corpus manifest records its classification, stable ID, generator/schema,
recipe, expected digest, permitted output fields, retention, and owner.
Use repository-relative recipe paths without personal paths, secrets, or raw data.
Minimization does not change classification.

`TK22-26` owns corpus access, retention, deletion, and backup decisions. Keep
private bodies ignored, access-restricted, and read-only during normal tests.
Use fresh scratch output. GitHub/cloud artifacts and shared caches are not
private-corpus backups; new off-machine storage requires owner authorization.

## Trusted ROM-backed runners

Public PR CI uses synthetic inputs without a ROM. A ROM-backed runner requires:

1. A human-approved trusted commit and workflow from a human-controlled branch.
2. A fresh ephemeral VM or equivalent disposable instance.
3. No outbound network or inbound service, tokens, keys, or cloud credentials.
4. Read-only private inputs mounted only after trust verification.
5. Disposable private scratch storage, destroyed after the job.
6. No caches, artifact uploads, core dumps, unrestricted logs, or job summaries.
7. An allowlisted validating output gateway for fixed-schema aggregates only.
8. Harmless isolation canaries covering file, path, environment, log, artifact,
   cache, and network disclosure. Failed isolation blocks execution.

Fork heads, issue commands, unreviewed dependency changes, and unreviewed agent
branches must not execute inside that boundary. Reconstruct reviewed external
contributions on a trusted branch before exposing private inputs.

The gateway rejects free-form process output, source/stack contents, memory
ranges, filenames, and binary attachments. Permitted aggregates include
pass/fail, test IDs, schema versions, approved hashes, and divergence ticks.

## Baselines

Bind results to exact source, inputs, tools, profiles, and producer identities.
Keep original failures and their evidence before minimization. Golden updates,
tolerances, state-hash exclusions, and scheduler/save semantics require explicit
review; never change them merely to make a failing test pass.

See [data handling](rom-and-assets-policy.md), [execution profiles](../adr/0002-execution-profiles.md),
and [security](../../SECURITY.md). Automated work also follows the
[production guard](../planning/autonomy-progress-guard.md).
