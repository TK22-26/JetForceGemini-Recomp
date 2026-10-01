# Contributing

The repository is private and is not accepting public contributions yet.
Invited contributors must follow these rules.

## Data boundary

- Never commit or upload a ROM, extracted asset, generated recompilation
  output, decompilation output, memory dump, save state, audio/video capture,
  or other ROM-derived expressive material.
- Keep external clones and downloaded programs under the ignored `tools/`
  directory.
- Keep private test material outside the checkout when practical, otherwise
  under an ignored private-data path.
- Run `python scripts/check_repository_hygiene.py --history` before pushing.

## Change workflow

1. Start from an approved issue or bounded task packet.
2. Use an `agent/<description>` or human feature branch.
3. Keep compatibility changes separate from enhancements.
4. Add ROM-free tests for all behavior available without private data.
5. Run project validation, the CMake build, and CTest.
6. Open a draft pull request with evidence and unresolved risks.

Do not update golden baselines to make a failure disappear. Do not mix
generated files with handwritten changes.

## Optional dependency-free pre-commit check

Run the first-party hygiene check immediately before committing:

```sh
python scripts/check_repository_hygiene.py --history
```

The command uses only Python's standard library and Git. It scans tracked and
non-ignored candidate files plus reachable history; it deliberately does not
open ignored private-data or external-tool directories.

## Upstream contribution rule

The currently evaluated N64 recompilation projects state that AI-generated
upstream contributions are not accepted. Project work produced with AI
assistance must not be submitted upstream as though it were human-authored.
Any required upstream contribution needs a genuinely human-authored and
independently reviewed implementation that follows that upstream project's
policy.

## Licensing

No material may be copied from an unlicensed repository. Until the repository
license changes, contributors must have an explicit written contribution
agreement with the project owner.
