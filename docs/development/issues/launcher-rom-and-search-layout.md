# UI-LAYOUT-20261107: ROM buttons and Video search field have inconsistent sizing

## Candidate and verification - 2026-11-07

Status: implemented and checked; owner visual acceptance pending. The old main
ROM control and dropdown shared `action-rom`, causing the main button's size and
font rules to apply to Select ROM. The library control is now `rom-library-import`
while its action remains `rom`; the dropdown keeps normal row styling. Explicit
line height centers the main label, and Video search uses a 32dp border-box height,
20dp line height and 5dp vertical padding.

An initial flex-text candidate rendered an empty narrow button despite existing
DOM-text checks passing. Framebuffer inspection caught it; normal block text flow
restored the label. A usable-width/click check now supplements distinct-ID and
equal-menu-row-height assertions. ROM library checks (70) and Video checks (247)
pass on Windows and actual GE-Proton. Final Windows images at 100/150 percent
(ROM) and 125 percent (search) were inspected. No owner or release acceptance is
inferred. Updated E: bundle provenance and environment limits are in the
[Proton record](github-steam-deck-proton-startup.md).

The source observations and initial disposition below are preserved history.


- Severity: minor visual/usability defects.
- Status: local candidate verified in scoped UI checks; owner review pending.
- Reported and last updated: 2026-11-07.
- Affected profile: current native launcher during the Bazzite #40 handoff review;
  the owner explicitly says these layout issues also affect Windows. Exact DPI,
  scaling and window dimensions were not supplied.
- Evidence origin: three owner screenshots; no original-N64 comparison applies.
- Related: [regional ROM selector](launcher-regional-rom-selection.md) and
  [separate Proton game-hiding defect](github-steam-deck-proton-startup.md).

## Symptoms and reproduction

1. Inspect the selected cartridge's **Change USA ROM...** button on the launcher
   start screen: the text sits high within a tall button rather than appearing
   vertically balanced. The owner also sees this on Windows.
2. Open **Game**: **Select ROM...** is noticeably taller/bolder than neighboring
   entries, although it should use the same dropdown-row dimensions.
3. Open **Video Settings**: **Search settings** sits near the top of an overly
   tall search field. The owner requests a shorter field with centered text.

## Evidence and source observations

Private artifact: `gh40-owner-feedback-20261107`. Original copied bytes verified
with SHA-256; screenshot capture platform is not inferred individually.

| Attachment | File | SHA-256 |
|---|---|---|
| Main ROM button | `codex-clipboard-oN1MuU.png` | `cd4985373f0c0e9e8f60f87d113096296c6482fefa349f3e2ecdd98520f234f8` |
| Game dropdown | `codex-clipboard-3JAeKs.png` | `f0c4b70990fe02a8d81580d7b8b760981b613a3cc4f36c3a19a13c75b976490b` |
| Video search | `codex-clipboard-dhMcIu.png` | `0e6e4f3ad66c4763faf8dac51b17aa574d9f36cf2604e41f65678e94345c507e` |

[`main.rml`](../../../launcher/ui/assets/main.rml) names the main ROM button
`action-rom`. The generic action-button builder in
[`native_ui.cpp`](../../../launcher/ui/native_ui.cpp) uses that same ID for the
Game menu's ROM action. The global `#action-rom` rule in
[`theme.rcss`](../../../launcher/ui/assets/theme.rcss) specifies a 34dp height,
zero vertical padding and bold text. This is a source-supported explanation for
the dropdown inheriting main-screen dimensions, with duplicate-ID lookup risk.
It has not yet been isolated by a controlled visual comparison.

[`video-settings.rcss`](../../../launcher/ui/assets/video-settings.rcss) gives
`#video-search` a 38dp height and zero vertical padding. Exact computed text
metrics and scaling behavior have not been measured. Do not attribute all three
symptoms to Proton or claim a verified root cause from screenshots alone.

## Attempts and disposition

| Date | Action | Result |
|---|---|---|
| 2026-11-07 | Preserve screenshots and inspect shared markup/style rules | Documented likely selector collision and fixed-height controls; no code change, build or UI replay |

Resolution pending. Intended work is to scope the main-screen ROM button's
identity/styles separately from dropdown actions, center its label, and reduce
and align the Video search field. Shared Windows/Proton layout should be checked
at representative scaling and focus/hover states. No preview or release contains
a new correction from this report.

## Lessons and compatibility

Action routing can be shared without sharing DOM IDs or component-specific size
rules. A dropdown and a main-screen button need independent layout ownership.
Treat text alignment as a rendered-layout check rather than assuming a height
and zero padding center the font automatically.
