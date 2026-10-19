# LAUNCHER-005: Native window chrome differs from Scooby

Status: candidate implemented; native attribute validation passed; owner review pending.
Affected: v1.3 local launcher/settings preview. Severity: presentation.

The owner reported older-looking window chrome compared with the Scooby
launcher. JFG created ordinary native windows without opting into dark DWM
captions; Scooby launcher/app.cpp sets DwmSetWindowAttribute attribute 20 on
its main window and tool panels. This is a caption-theme difference, not an
older RmlUi engine or a custom Windows frame.

The candidate applies the same native dark-caption setting after creation of
the JFG launcher and all live tool windows (Settings, Video, Controls, Map and
Inventory). Caption buttons, resizing, snap behavior and Windows 11 corners
remain owned by Windows. Unsupported Windows versions ignore the optional
DWM request and retain their normal native frame.

Source: launcher/native/window_chrome.hpp, src/app/frontend_win32.cpp,
launcher/ui/live_tool_window.cpp. The storage restart fixture also checks the
actual DWM dark-caption attribute on its main and owned settings windows.
No gameplay code changes are involved. Owner visual approval remains pending.

The isolated native restart fixture read back DWM attribute 20 as enabled on
both main and Settings windows during all three successful migrations.

## Owner acceptance (2026-10-19)

The owner accepts the completed settings preview; local review accepted, unreleased.
