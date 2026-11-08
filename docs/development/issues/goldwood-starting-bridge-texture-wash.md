# N64-002: Texture wash over the Goldwood starting bridge

- Severity: minor visual artifact; no gameplay effect reported.
- Status: owner-reported native NTSC bug; documented and intentionally preserved.
- Reported and last updated: 2026-11-07.
- Affected version: NTSC, as identified by the owner; exact ROM revision/hash
  and capture build/settings unspecified. PAL and JP were not compared.
- Evidence origin: owner statement that the bug exists in the native game, plus
  two screenshots. Physical console/display, emulator or recomp capture origin
  was not specified; the screenshots alone do not establish hardware provenance.
- Native-game decision: **preserve; no fix requested**.
- Catalog: [original-game bugs](../../original-game/bugs.md#n64-002-texture-wash-over-the-goldwood-starting-bridge-ntsc).

## Symptoms and reproduction

The owner reports "a weird texture like washes over the goldwood starting
bridge" and identifies the behavior as a native-game bug in NTSC. The supplied
screenshots show the bridge deck and side walls from nearby viewpoints. The
reported wash is a visual change over the existing bridge surface; no collision,
progression or other gameplay problem was reported.

The known location is the starting bridge in Goldwood. Exact movement, camera
angle, timing and repeatability were not supplied. The still images document
appearance but do not establish the motion or trigger of the wash.

## Evidence and hypotheses

The owner's report was supplied during the issue #35 manual-review exchange,
after a v35 launcher link was provided. That context does not establish which
build or device produced these screenshots, nor a separate hardware test date.
The NTSC native-game classification is attributed to the owner.

The two unmodified screenshots are preserved in private artifact set
`native-game-notes-20261107/goldwood-starting-bridge`. Their copied bytes were
verified against the supplied files with SHA-256:

| Attachment | File | SHA-256 |
|---|---|---|
| Image #1 | `codex-clipboard-nKumo3.png` | `8f3f95eb717ca4f804c88b483211c2254f94f9940c6d180a4507470d6d6062bb` |
| Image #2 | `codex-clipboard-CNNyMC.png` | `e2c27dc65f7860363530fcc7e1ac16da02ccac4ebb19ee191d5ab3d1078028eb` |

Actual cause is unknown. No texture, depth, lighting, fog or interpolation cause
has been isolated; none is asserted from the appearance alone.

## Attempts and disposition

| Date | Action | Result and decision |
|---|---|---|
| 2026-11-07 | Record the owner's NTSC report and preserve both supplied screenshots | Documentation only. Owner explicitly says not to fix it; preserve behavior. No experiment, replay, build or code change performed. |

No remedy was attempted. This is an intentional preserve decision, not a claim
that the artifact has been fixed or released as a correction. It does not reopen
the shelved rendering investigation or change its guard allowance.

## Verification and remaining limits

The report and screenshots are retained; no independent gameplay or hardware
verification was performed. PAL/JP behavior, exact trigger, frequency and cause
remain unknown. Further testing is not required for this documentation-only
request, and no live-verification or fix task is scheduled.

## Lessons for future ports and changes

Retain the owner's native-game attribution and explicit preserve decision when
reviewing later rendering reports. Keep region and evidence provenance explicit;
do not generalize an NTSC observation to PAL/JP or change rendering to remove
this artifact without a new owner request.
