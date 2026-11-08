# UI-ABOUT-WINDOW-20261107: About opens inside the launcher instead of its own window

- Severity: UI behavior / consistency defect.
- Status: corrected local candidate verified on Windows/Proton; owner acceptance pending.
- Reported: 2026-11-07, current private launcher SHA-256
  `a5fe71ccc1a1989ca2f377f556c31a4d7c0ea4d7411459e74a9f6bfd2cd04dfc`.
- Scope: shared launcher UI, not a Proton-only or regional runtime issue.

## Symptoms and reproduction

Open Help > About Jet Force Gemini in the Windows review launcher. The content
appears as a dialog inside the main launcher. The owner expects a separate native
window with normal titlebar, movement, resizing and close behavior. This report
does not accept or reject the separate [opening-delay report](launcher-about-window-delay.md).

## Cause and evidence

The `help` action in [native_ui.cpp](../../../launcher/ui/native_ui.cpp) calls
`modal("help")`, which fills the main document's `dialog-body`. About was never
connected to the [separate-window host](../../../launcher/ui/live_tool_window.cpp)
used by Audio, Video and Controllers. The preceding tests measured how quickly
that embedded panel opened; they did not check the required window architecture.
The owner directly confirms the wrong behavior. No N64 comparison applies.

## Intended correction and verification

Route About to an owned native window, keep its content and project/support links,
and preserve close/reopen and parent lifetime behavior. Verify a separate HWND
and caption, no WS_CHILD style, independent resize and repeated-open reuse; also
check Escape/Done/titlebar close, link routing and parent cleanup on Windows and
Proton. Keep game runtimes and owner settings/saves unchanged.

Implementation, checks and final disposition will be appended as completed.
The existing guard remains enabled on the same investigation. This follow-up
uses remaining time/attempts from the original 90-minute approval, with the
original deadline and no budget increase or counter reset.

## Lesson

Window topology is an acceptance criterion separate from rendering speed. A fast
embedded dialog is not evidence that a requested separate window was implemented.

## Implemented correction and verification

The main `help` action now delegates to the existing native tool-window host.
[about-window.rml](../../../launcher/ui/assets/about-window.rml) is a dedicated
document, without main-screen/menu/modal elements. The native window is owned by
the launcher, modeless and resizable; repeated opens reuse the existing process.
Its Done/Escape/titlebar close behavior and parent-exit cleanup are verified.
About does not start controller polling, audio settings or a live-data helper.
[frontend_commands.hpp](../../../launcher/native/frontend_commands.hpp) shares
existing action IDs so About's links use the launcher's ordinary command paths.
Original IDs remain stable; new About/project commands are appended.

Windows UI161 and fallback UI210 checks pass; actual GE-Proton passes UI210.
Final production launcher checks pass on Windows31 and Proton30: separate HWND
and process, native caption/resize styles, correct owner, main interactivity,
duplicate-open reuse, resize, close/reopen and parent lifetime. Windows used a
private desktop; no physical desktop input was injected. Final opening timings
were 359-375 ms on Windows and 639-752 ms on software-Vulkan Proton (50 ms polling).
These observations do not reproduce or resolve the owner's separate delay cause.
The dedicated rendered layout was inspected. Child-page timing logging remains
bounded and excludes process/device startup; the external probe measures the full
menu-to-first-frame interval.

Guide compatibility: Windows review packages include READ ME.txt, but the USB
game folder includes neither offline guide filename. An initial assertion that
both contained READ ME.txt failed and its dependent check did not execute. The
command now prefers START HERE.txt, then READ ME.txt, then the repository's online
getting-started guide. `guide-targets.json` is authoritative; one reused build-log
success sentence incorrectly says both contain a fallback guide. Link dispatch
is checked without launching external browsers; live website availability is
outside these native checks.

Delivered to the existing Windows review package and E: with backups. Launcher
SHA-256: `2856271638a917e798b3692dcf43281012dc6b53c9cde9d67b1856eae9d2f69a`. Source base develop 067f9a8 plus local
changes; exact closure is in launcher-build.json. Game runtimes, ROMs, saves and
manual audio preferences were not modified. No commit, push or public issue action.
Private evidence: `gh40-about-window-20261107`. User review remains pending.

## Owner-requested GitHub mark follow-up

The owner identified the CSS branch drawing in the Project on GitHub row as a
placeholder and explicitly requested GitHub's SVG. Replaced it with the official
white Invertocat, retaining the downloaded SVG unchanged and deriving the native
texture through the existing SVG-to-TGA asset pipeline. The 24.5 x 24 dp mark
preserves its proportions, uses 4x pixel density and requires no network loading.
Removed the unused branch rules. Source, hashes and attribution are recorded in
[github-mark.md](../../../launcher/ui/assets/github-mark.md). The rendered About page was visually inspected, with Windows161/fallback210
UI checks and actual Proton UI210/production30 checks passing. The Windows review
copy and E: are updated, with attribution and backups retained. Owner visual
acceptance is pending. No regional gameplay change applies.

GitHub-mark delivery SHA-256: `e35e776913be966a24030eef45043ebb241ec4a0466c05beff5d86ae440fd219`.
Private evidence: `gh40-about-github-mark-20261107`. Hygiene and whitespace
checks pass. No commit/push/public issue action.
