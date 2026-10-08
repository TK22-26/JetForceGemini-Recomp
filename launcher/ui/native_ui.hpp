#pragma once
#include <filesystem>
#include <functional>
#include <string>
#include <windows.h>
struct FrontendUiState {
  bool playing = false, busy = false, fullscreen = false, mods = false;
  std::wstring rom, runtime, status;
};
bool FrontendUiInit(HWND, const std::filesystem::path &,
                    std::function<void(const std::string &)>);
void FrontendUiShutdown();
void FrontendUiFrame(const FrontendUiState &);
void FrontendUiResize();
void FrontendUiMessage(UINT, WPARAM, LPARAM);
void FrontendUiPanel(const std::string &);
bool FrontendUiCapturing();
