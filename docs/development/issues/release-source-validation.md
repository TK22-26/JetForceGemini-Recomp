# BUILD-003: Release source validation

Status: candidate remediation, qualification in progress for 1.2.0.

Release validation found unregistered controller-prototype rasterizations and launcher screenshots, numeric opcode/section identifiers mistaken for hex payloads, synthetic compiler fixtures mistaken for generated game code, and a repeatedly mis-encoded prototype filename inflating one feature-note line beyond 3 MB. These block publication, not gameplay.

The filename is repaired in the current document; historical evidence remains intact. Exact SHA-256 and Git blob records in `scripts/reviewed_hygiene_bodies.json` document the inspected assets and narrowly scoped historical false positives. No suffix-wide binary exemption or credential/ROM/archive exemption is introduced. Mutated fixtures and artwork must fail again. The controller artwork originates in the owner-provided editable prototype documented beside its SVGs; screenshots show the project launcher/settings.

The all-object local history scan additionally sees private stash objects that are never part of a pushed release. Qualification will scan a clean isolated clone of the committed release history, preserving the local stash and all original counters. No history rewrite is performed. Initial failed policy logs remain in the private release qualification directory.

Lesson: register exact UI asset provenance when adding rasterizations, and keep generated game bodies out of public fixtures. Preserve UTF-8 explicitly when updating documents. Release-history scans must be performed on the actual publishable clone, not confused with private local stash objects.

## Verified candidate scope

Current policy, exact-body mutation regression tests and schema validation pass. The external-output launcher test harness is corrected; the first link probe was missing input_stick.cpp and its corrected link passes. The complete published-history clone remains a pre-push check.
