# Draft: Upstream Permission and Coordination Request

Status: deferred and unsent under `phase0-decisions.md`; do not send automatically.

Suggested subject: Coordination and permission request for a separate Jet Force Gemini static-recompilation project

---

Hello Jet Force Gemini decompilation maintainers,

We are exploring a separate native PC project that would use static recompilation rather than treating the decompiled C source as the port itself. The intended application would require each user to provide a lawfully obtained supported ROM. We do not intend to distribute ROM data, extracted game assets, private test captures, or other proprietary game content.

We would like to coordinate with you early, respect the decompilation project's boundaries, and return useful symbol or reverse-engineering corrections upstream where appropriate. We are currently evaluating against decomp commit `b49aa4791e8fb1e7acd3bba10346876358d0a9a7`; that pin is only a reproducibility reference and does not imply permission to reuse material.

The repository does not currently appear to contain a root license file, so could you clarify what use, if any, you authorize for a separate recompilation project?

In particular, may the project:

1. Build the decompilation locally to obtain a verified ELF from the user's own ROM?
2. Use and publish non-ROM symbol names, addresses, section boundaries, relocation descriptions, and overlay metadata derived from the project?
3. Reuse headers, type declarations, structure definitions, constants, or macros? If so, under what license and attribution requirements?
4. Reuse matched C functions selectively for native patches? If so, under what license, provenance, and contribution requirements?
5. Publish N64Recomp configuration derived from the project's symbol/section metadata? If any material you control would be incorporated into generated recompilation output, what permission and attribution would apply to that material?
6. Pin the repository as a development dependency or submodule, or should developers supply a separate local checkout?
7. Publish a separate symbol package tied to a specific decomp commit?
8. Share corrected symbols, structures, overlay information, or matched functions back through pull requests? Are there preferred contribution rules?

We would also appreciate guidance on:

- any planned license for the decompilation repository;
- material that should remain strictly local or private;
- preferred attribution and project description;
- the preferred communication channel for architecture questions;
- whether you would like advance review before any public source or binary release; and
- any naming or branding boundaries you want the separate project to observe.

If broad reuse is not authorized, we can maintain a stricter boundary: local decomp builds only, no copied source or headers, independently maintained recompilation metadata, and public artifacts limited to material that has a clear distribution basis. Please tell us if that still raises concerns.

This request is intended to establish permission and collaboration expectations, not to ask you for ROMs, extracted assets, private files, or a commitment to support the port. We are happy to document the agreed boundary in the new project's governance files and preserve per-file/per-symbol provenance.

We understand that permission from the decompilation maintainers can cover only material you have authority to license. It would not grant rights to original game code or assets, and we would evaluate those separate questions independently before any public distribution.

Thank you for the reverse-engineering work already invested in Jet Force Gemini. We would value your guidance before moving beyond private feasibility experiments.

Regards,

`[Project contact — fill in manually before sending]`

---

## Human review checklist

- [ ] Confirm the project contact and reply address.
- [ ] Remove any request the project does not actually need.
- [ ] Confirm that the described ROM/data policy matches the committed policy.
- [ ] Confirm that no permission is implied until a clear written response is received.
- [ ] Record the response, scope, date, and authorized party in a governance decision record.
- [ ] Obtain legal review before relying on an ambiguous response for public distribution.
