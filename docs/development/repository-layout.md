# Repository layout and retention policy

Default to removal when a file has no current consumer, unique engineering knowledge, distribution
obligation or evidence contract. Merge useful information into its canonical home before removing
a duplicate. A zero-reference search alone is not proof of dead code: many tools and tests are selected
dynamically. Git retains removed history; ignored private evidence and the production ledger are separate.

| Location | Ownership and reason to retain |
|---|---|
| `include/jfg/`, `src/boot/`, `src/runtime/` | Public host contracts and native execution; generated ABI and thread ownership constrain further splits |
| `src/app/` | Runtime CLI entry points, not launcher UI |
| `launcher/native/` | Windows frontend shell and settings dialogs; local `tests/` owns its C++ checks |
| `launcher/ui/` | RmlUi views, resources, fonts, notices and integration fixtures |
| `launcher/windows/` | Embedded managed services and compatibility models with current test/build consumers |
| `scripts/build/` | Dependency/bootstrap, source generation and build orchestration |
| `scripts/release/` | Playable bundle packaging, source/version metadata and publication validation |
| `scripts/validation/` | Repository, schema, policy and milestone validation |
| `scripts/evidence/` | Evidence producers and manifests; phase names identify contracts |
| `scripts/diagnostics/` | Traces, comparison tools, Lua/assembly probe families |
| `scripts/exploration/`, `scripts/verification/` | Navigation experiments and focused verification tools |
| `scripts/autonomy/` | Production supervisor, guard and job execution; never reset by cleanup |
| `tests/<domain>/` | Discoverable Python/C++ tests grouped by responsibility; `fixtures/` retains synthetic inputs |
| `cmake/renderer/` | Renderer target integration and patches; `NativeTargets.cmake` owns generated/native targets |
| `tests/cmake/` | Renderer and synthetic-generated test target groups |
| `config/`, `schemas/`, `symbols/`, `evidence/` | Versioned contracts, symbolic mappings and provenance; required bytes/paths remain pinned |
| `patches/`, `examples/` | Maintained upstream changes and consumed synthetic examples |
| `docs/` | Task-oriented documentation, issue history and reference; see its index |

## Compatibility surface

The established Python `scripts.<tool>` import API resolves tools in their domain folders. Direct
commands use the domain path. Seven small root CLI entries remain for published setup workflows:
`build_from_rom.py`, `generate_from_rom.py`, `build_windows.py`, `bootstrap_tools.py`, `doctor.py`,
`validate_project.py`, and `check_repository_hygiene.py`. New tools belong in a domain. Avoid importing
the same tool through two module names in one process; use the established `scripts.<tool>` API in shared code.

The broken Quarry shortcut and launcher-only packager were removed. Playable packaging retains its
shared release metadata checks. Generic controller art aliases the Xbox payload; resource 215 remains
reserved so later resource numbers do not shift. Licenses with separate distribution roles and the
separate baseline/patch link probes remain even when bytes match.

`src/boot/native_boot.cpp` coordinates child startup and the run loop. Its private `native/` modules
own guest memory, host audio/window input, overlay adaptation, save storage, live tasks, reporting
and guest execution. [Module responsibilities and qualification](issues/native-runtime-modularization.md)
record the ABI/thread checks. Shared State and the large guest-dispatch implementation remain coupled;
this is not a claim that every game hook is independently designed or region-neutral.

## Working data

Builds, downloaded dependencies, generated bodies, ROMs, personal saves and private captures are not
source deliverables. Regenerable Python caches are disposable after checking their origin. Reparse
points, retained evidence, dependency repositories and the external production ledger remain protected.
[Audit record](issues/folder-architecture-audit.md) and [file dispositions](repository-audit.csv)
explain the concrete decisions.
