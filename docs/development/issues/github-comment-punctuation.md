# Approved GitHub replies lost punctuation during posting

- Status: corrected and read back from GitHub on 2026-10-22 UTC.
- Severity: public communication formatting; no game or package behavior change.
- Affected: owner-approved v1.4.0 replies posted to #30–#40; #25 retained its punctuation.

Smart apostrophes and dashes embedded in a PowerShell here-string were converted
to question marks when piped into Python under the active console encoding.
The resulting comment files therefore already contained incorrect characters.
Separately, exact-body verification compared Windows CRLF against LF and failed
after successful posts and closures. Retrying a failed verifier by posting again
would have created duplicate comments, so the existing comment IDs were recovered.

The repair rebuilt the approved text from an explicitly UTF-8 file, serialized
GitHub PATCH payloads with JSON Unicode escapes, and edited only those same
owner-authored comments. It then fetched every comment, normalized line endings
only, compared the complete approved text and verified each requested issue state.
All twelve bodies now match. #15/#19 closure created no additional comments.
Private before/after receipts preserve the failure and correction; the public
discussion links are in each issue record and the desktop follow-up plan.

Future posting must avoid Unicode shell-to-process pipes for body construction,
preserve approved body text in a file, and verify the remote result with explicit
encoding and line-ending treatment. A failed post-verification step is not proof
that the external mutation failed; inspect the existing remote object before retrying.
