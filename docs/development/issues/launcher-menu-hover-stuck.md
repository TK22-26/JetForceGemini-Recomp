# UI-008: Menu hover and dropdown pointer routing

- Severity: minor original hover defect; functional dropdown regression in the first candidate.
- Status: corrected source passes native UI checks; owner confirms the revised menu fix; unreleased.
- Reported: 2026-10-20.
- Affected: Windows native launcher with a hosted game, Cutscene Audio Review / Audio Fix previews.
- Evidence: owner screenshot hMEsxE, SHA256 6fda104a1574912ea22bbc048af1c608646572abc482e8b28847a26834820a2a.

## Symptoms and reproduction

Hover Controllers, then move into the hosted game: the hover highlight remains.
The first candidate forwarded WM_MOUSELEAVE, fixing missing delivery but causing
another owner-reported failure: dropdown items no longer select reliably.

## Cause and attempted remedies

The parent launcher and its child input shield share one RmlUi context.
The shield receives input over the game whenever a dropdown or modal is open.
The generic Win32 backend assumes a single input HWND and tracked the parent,
including when the parent was processing a forwarded child mouse move.
Forwarding parent leave notifications without identifying their source cleared
RmlUi's current hit target while the pointer was over a dropdown item.

The initial launcher build passed but did not exercise this child-window handoff.
Owner review rejected that candidate. A new offscreen native-input test reproduced
the failure: move from the menu to a dropdown item through the shield, deliver
the queued parent leave, then click. The selection callback did not fire.

## Corrected implementation

The UI surface now tracks mouse movement/leave for the actual input HWND.
The shield maps coordinates into the UI root and retains its source identity.
When input moves between parent and shield, old tracking is cancelled; a stale
leave from the other HWND cannot erase the new hover target. A leave arriving
before the next move checks the current pointer window and preserves UI ownership
only for the parent or registered shield. Entering the hosted game or leaving
the UI clears hover normally. Capture, button, keyboard and focus policy remain
on their existing paths. Live tool windows use the same per-surface tracking.

Sources: launcher/ui/native_ui.cpp, launcher/ui/native_ui.hpp,
src/app/frontend_win32.cpp, launcher/ui/live_tool_window.cpp.

## Validation and remaining limits

- Baseline regression reproduced using native Win32/RmlUi message delivery.
- Corrected menu input suite: 55 checks pass, including Video/Game/Help selections,
  stale leave in both directions, actual UI exit, host dismissal and F10.
- Existing Modern controls UI suite: 790 checks pass.
- Launcher build succeeds.
- Tests use offscreen nonactivating windows, with no desktop input or gameplay.
- One new fixture assertion initially expected the UI layer itself to handle
  Escape; the host owns that behavior. The fixture was corrected to use the
  host dismissal API. This was not a product keyboard regression.
- Owner confirms "fixed" in the revised Menu Fix Preview. This verifies the
  reported hover/dropdown behavior; no release or exhaustive menu coverage is claimed.

Private evidence ID: v131-rnd-20261019/menu-hover, including
baseline-dropdown/error.txt, verified-dropdown/result.json and
verified-modern-controls/result.json. The owner separately confirmed the audio
effect fix in the same preview; that confirmation does not approve the menu.

## Transferable lesson

An embedded application's input child and parent can share a UI context without
sharing mouse-leave ownership. Preserve event source identity across forwarding;
a successful build alone cannot validate transitions between these windows.

Owner menu acceptance (2026-10-20): "fixed - whats next?". This supersedes the
failed first hover candidate and is separate from the earlier audio acceptance.
