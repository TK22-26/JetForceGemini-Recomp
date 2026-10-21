# Modern Floyd controller diagonal range

- Status: corrected in source and preview3; native corner/axis checks and four focused suites pass; owner physical-controller verification pending; unreleased.
- Severity: reduced reach toward co-op reticle corners at default sensitivity; cardinal limits remain correct.
- Affected: local Modern Players and Floyd preview2 controller adapter. Mouse reaches the original square envelope.
- Related: [widescreen bounds](floyd-widescreen-aim-bounds.md), [Floyd #37](github-floyd-cannot-fire.md).

The Modern stick look helper normalizes diagonal input radially. PcFloydLook
maps that absolute response to +/-65 per axis, so a full diagonal produces
approximately +/-46 and native reticle offsets +/-56.615. Cardinal input reaches
the original +/-80 offsets. The native function clamps each axis independently;
EmuHawk raw65/65 reaches +/-80, raw56/56 reaches +/-68.923, and raw46/46 reaches
+/-56.615. Mouse accumulation reaches all square corners.

Reproduction is a synthetic full right-stick diagonal at default100 sensitivity
through the production helper and original native consumer. Both 4:3 and
widescreen, and both generated execution paths, agree. Native original input
trials restore the same joined Floyd checkpoint. Physical controller gate,
other sensitivity settings and a preferred response policy remain unqualified.
Do not equate scripted N64 diagonals with a measured physical N64 gate.

The first comparison incorrectly expected all controller diagonals to reach
square corners and failed. Its failure revealed this separate response issue;
the corrected comparison records it explicitly instead of treating it as a
widescreen or native cardinal-bound failure. No remedy attempted. The owner
authorized findings before implementation; report this and agree on behavior
before changing mapping. A candidate should preserve centre return, existing
inversion and sensitivity semantics, mouse behavior and original outer bounds.

Evidence: D:/JFG-private/floyd-bounds-20261021/native-bounds (failed assertion),
native-bounds-v2/bounds.csv, original-diagonals/results.json. Transferable lesson:
test corners and radial/square transformations separately from axis endpoints.

Owner now explicitly requests follow-up and approves implementation. Candidate maps the radial stick response to Floyd's native square reticle before per-axis gains/inversion. This keeps cardinal response and outer limits, sensitivity/curve/deadzone settings, swapped sticks, neutral return and mouse behavior. Only qualified Floyd input selects square shaping; normal camera/boss controls retain radial shaping. Root and isolated build source updated; validation pending. Same existing one-hour deadline, production guard/root/counters preserved; no new budget.

The first full runtime build failed with MSVC C1060 (compiler heap allocation) while compiling native_boot.cpp, after all64 native-consumer cases passed. Preserve that log; it is not a gameplay/test failure or a delivered fix. Retry uses serial build execution within the same guard/budget, validating focused tests before runtime packaging.

Serial build completed successfully. All4 focused component suites pass, including raw circular diagonals, cardinal parity, deadzones, sensitivity/curves, inversion, swapped sticks and axis-gain isolation. Native consumer64-case qualification already passes (7,810 checks). Owner physical-controller acceptance remains pending.

Preview3 installed into the existing Modern Players and Floyd Preview, with profile/save hashes preserved. Runtime SHA-256 `126b960c5fe0298d2f2498abed25b6a153bdef2d7bf9dd396ac16a7629129dd2`. Original bounds remain x80..240/y40..200 in both screen modes. Four component suites and64 native cases pass (7,810 checks). Runtime protocol, helper setup and package inventory checks pass. Launcher/game not opened by this delivery; owner may use the existing desktop shortcut when ready. No commit/push/release. Evidence: D:/JFG-private/floyd-bounds-20261021/controller-correction/delivery.json.

## Owner corner-reach follow-up

Owner clarifies that mouse can reach corners directly and a held controller stick eventually reaches them. This is partial live confirmation of reach, not full response/centering acceptance. Original EmuHawk at a constant -65/-65 corner target approaches the bound over time: within one source pixel after16 VIs (about0.27s including input polling), numerically exactly -80/+80 after50 VIs. Neutral release returns toward centre. The original native reticle performs this easing; the Modern controller adapter supplies an absolute target and does not accumulate extra range by holding. No speed/bounds change made. A materially longer delay would require the exact physical stick trajectory; the current P1-only recording lacks raw P2 stick samples. Evidence: `floyd-bounds-20261021/hud-overlap-review/original-settling/result.json`.


## Final owner disposition for v1.4.0 (2026-10-21)

The owner states that #37 and the associated Floyd work are fully approved
locally and requests reporter verification after delivery. This supersedes the
earlier local acceptance gates above without inventing additional measured routes
or hardware coverage. The combined v1.4.0 package still needs the requested
SS Anubis final pass. No publication or public reply is implied.
