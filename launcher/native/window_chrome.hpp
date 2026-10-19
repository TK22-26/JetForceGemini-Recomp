#pragma once
#include <windows.h>
#include <dwmapi.h>
namespace jfg::frontend {
// Same native dark title bar as the Scooby launcher. Windows owns caption
// buttons, snap layouts and rounded Windows 11 corners; no custom frame.
inline void apply_window_chrome(HWND window) {
  const BOOL dark=TRUE;
  DwmSetWindowAttribute(window,20,&dark,sizeof(dark));
}
}
