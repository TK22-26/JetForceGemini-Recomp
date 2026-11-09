#pragma once
#include <windows.h>
namespace jfg::frontend {
// DirectComposition can place UI over the game and its input shield. An HWND
// swap chain cannot: WS_CLIPCHILDREN excludes even an unpainted child rectangle.
// Its panels use an owned popup surface; the game stays visible during capture.
inline HWND sync_ui_capture_windows(HWND root, HWND viewport, HWND render,
                                    HWND shield, bool composition, bool capturing) {
    if (!composition && viewport) {
        const bool show_game=render && IsWindow(render);
        if ((IsWindowVisible(viewport)!=FALSE)!=show_game)
            ShowWindow(viewport,show_game?SW_SHOWNOACTIVATE:SW_HIDE);
    }
    const bool show_shield=composition && capturing;
    if (shield && (IsWindowVisible(shield)!=FALSE)!=show_shield)
        ShowWindow(shield,show_shield?SW_SHOWNOACTIVATE:SW_HIDE);
    if (show_shield)
        SetWindowPos(shield,HWND_TOP,0,0,0,0,SWP_NOMOVE|SWP_NOSIZE|SWP_NOACTIVATE);
    return show_shield?shield:root;
}
}
