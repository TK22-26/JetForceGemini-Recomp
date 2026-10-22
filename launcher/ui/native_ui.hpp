#pragma once
#include <filesystem>
#include <functional>
#include <string>
#include <windows.h>
struct FrontendUiState {
  bool playing = false, busy = false, fullscreen = false, mods = false;
  std::wstring rom, runtime, status;
  bool pauseInactive = false;
};
bool FrontendUiInit(HWND, const std::filesystem::path &,
                    std::function<void(const std::string &)>, const std::string &tool = "", bool previewUpdate = false);
int FrontendLiveToolEntry(HINSTANCE, int);
void FrontendUiShutdown();
// Window swap chains cannot place transparent UI above a hosted game child.
bool FrontendUiCanOverlayGame();
void FrontendUiFrame(const FrontendUiState &);
void FrontendUiResize();
// Mouse coordinates stay relative to the UI root; source identifies its input child.
void FrontendUiMessage(UINT, WPARAM, LPARAM, HWND source = nullptr);
void FrontendUiInputChild(HWND);
void FrontendUiPanel(const std::string &);
bool FrontendUiCapturing();
void FrontendUiToggleMute();

bool FrontendUiModalOpen();
