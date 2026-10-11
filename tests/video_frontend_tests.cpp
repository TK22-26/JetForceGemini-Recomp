#define WIN32_LEAN_AND_MEAN
#define NOMINMAX
#include "../launcher/native/video_settings_resource.h"
#include "jfg/renderer/video_settings.hpp"
#include <filesystem>
#include <fstream>
#include <iostream>
#include <string>
#include <windows.h>
namespace fs = std::filesystem;
struct Search {
  DWORD pid;
  const wchar_t *caption;
  const wchar_t *cls;
  HWND window = nullptr;
};
BOOL CALLBACK find_window(HWND window, LPARAM value) {
  auto &search = *reinterpret_cast<Search *>(value);
  DWORD pid = 0;
  GetWindowThreadProcessId(window, &pid);
  wchar_t caption[128]{}, cls[128]{};
  GetWindowTextW(window, caption, 128);
  GetClassNameW(window, cls, 128);
  if (IsWindowVisible(window) && pid == search.pid &&
      (!search.caption || std::wstring(caption) == search.caption) &&
      (!search.cls || std::wstring(cls) == search.cls))
    search.window = window;
  return TRUE;
}
HWND wait_window(HDESK desktop, DWORD pid, const wchar_t *caption,
                 const wchar_t *cls) {
  for (unsigned i = 0; i < 250; ++i) {
    Search search{pid, caption, cls};
    EnumDesktopWindows(desktop, find_window, reinterpret_cast<LPARAM>(&search));
    if (search.window)
      return search.window;
    Sleep(20);
  }
  return nullptr;
}
std::string read(const fs::path &path) {
  std::ifstream file(path, std::ios::binary);
  return {std::istreambuf_iterator<char>(file), {}};
}
int wmain(int argc, wchar_t **argv) {
  if (argc != 3 && argc != 4)
    return 2;
  const bool live = argc == 4;
  const fs::path launcher = argv[1], profile = argv[2];
  fs::create_directories(profile);
  const std::wstring desktopName =
      L"JfgVideoFrontend-" + std::to_wstring(GetCurrentProcessId());
  HDESK desktop = CreateDesktopW(desktopName.c_str(), nullptr, nullptr, 0,
                                 GENERIC_ALL, nullptr);
  if (!desktop || !SetThreadDesktop(desktop))
    return 3;
  std::wstring command = L"\"" + launcher.wstring() + L"\" --profile \"" +
                         profile.wstring() + L"\"";
  if (live)
    command += L" --play --input-replay \"" + std::wstring(argv[3]) +
               L"\" --progress-output \"" +
               (profile / L"progress.json").wstring() + L"\"";
  auto retraces = [&]() {
    const auto progress = read(profile / L"progress.json");
    const auto start = progress.find("\"vi_retraces\":");
    std::uint64_t value = 0;
    if (start != std::string::npos)
      std::from_chars(progress.data() + start + 14,
                      progress.data() + progress.size(), value);
    return value;
  };
  STARTUPINFOW startup{};
  startup.cb = sizeof(startup);
  startup.lpDesktop = const_cast<wchar_t *>(desktopName.c_str());
  PROCESS_INFORMATION child{};
  if (!CreateProcessW(launcher.c_str(), command.data(), nullptr, nullptr, FALSE,
                      CREATE_UNICODE_ENVIRONMENT, nullptr,
                      launcher.parent_path().c_str(), &startup, &child))
    return 4;
  unsigned failures = 0;
  auto check = [&](bool ok, const char *name) {
    if (!ok) {
      ++failures;
      std::cerr << "FAIL: " << name << '\n';
    }
  };
  HWND frontend =
      wait_window(desktop, child.dwProcessId, nullptr, L"JfgFrontend");
  check(frontend != nullptr, "production launcher window");
  if (frontend) {
    // Exercise the real Video menu's keyboard route, with targeted messages
    // confined to the fixture desktop (no physical keyboard/mouse injection).
    if (live) {
      for (unsigned i = 0; i < 6000 && retraces() < 4000; ++i)
        Sleep(20);
      check(retraces() >= 4000, "live gameplay reaches the camera fixture");
    }
    for (unsigned i = 0; !live && i < 500; ++i) {
      if (read(profile / L"frontend-status.txt").find("Import your ROM once") !=
          std::string::npos)
        break;
      Sleep(20);
    }
    Sleep(300); // Let the launcher consume the initialization completion.
    PostMessageW(frontend, WM_SYSKEYDOWN, 'V', 1LL << 29);
    PostMessageW(frontend, WM_SYSKEYUP, 'V',
                 (1LL << 29) | (1LL << 30) | (1LL << 31));
    Sleep(250);
    PostMessageW(frontend, WM_KEYDOWN, VK_HOME, 0);
    PostMessageW(frontend, WM_KEYUP, VK_HOME, 0);
    PostMessageW(frontend, WM_KEYDOWN, VK_RETURN, 0);
    PostMessageW(frontend, WM_KEYUP, VK_RETURN, 0);
    HWND dialog =
        wait_window(desktop, child.dwProcessId, L"Video Settings", L"#32770");
    check(dialog != nullptr, "Video menu opens native dialog");
    if (dialog) {
      check(GetWindow(dialog, GW_OWNER) == frontend &&
                !IsWindowEnabled(frontend),
            "owned modal disables launcher");
      check(GetPropW(frontend, L"JfgFrontendPause") != nullptr,
            "settings request cooperative pause");
      if (live) {
        for (unsigned i = 0;
             i < 100 && !GetPropW(frontend, L"JfgFrontendPaused"); ++i)
          Sleep(20);
        check(GetPropW(frontend, L"JfgFrontendPaused") != nullptr,
              "runtime acknowledges the video dialog pause");
        Sleep(200);
        const auto paused = retraces();
        Sleep(300);
        check(paused > 0 && retraces() == paused,
              "guest VI clock stops while native dialog is open");
      }
      auto choose = [&](int id, int value) {
        SendDlgItemMessageW(dialog, id, CB_SETCURSEL,
                            static_cast<WPARAM>(value), 0);
        SendMessageW(dialog, WM_COMMAND, MAKEWPARAM(id, CBN_SELCHANGE),
                     reinterpret_cast<LPARAM>(GetDlgItem(dialog, id)));
      };
      choose(IDC_VIDEO_FRAME_MODE, 1);
      const auto textResult =
          SendMessageW(GetDlgItem(dialog, IDC_VIDEO_FPS_EDIT), WM_SETTEXT, 0,
                       reinterpret_cast<LPARAM>(L"360"));
      wchar_t entry[32]{};
      SendMessageW(GetDlgItem(dialog, IDC_VIDEO_FPS_EDIT), WM_GETTEXT, 32,
                   reinterpret_cast<LPARAM>(entry));
      std::wcout << L"Before Apply: mode="
                 << SendDlgItemMessageW(dialog, IDC_VIDEO_FRAME_MODE,
                                        CB_GETCURSEL, 0, 0)
                 << L" edit=" << entry << L" textResult=" << textResult
                 << L'\n';
      SendDlgItemMessageW(dialog, IDC_VIDEO_VSYNC, BM_CLICK, 0, 0);
      SendMessageW(dialog, WM_COMMAND, IDC_VIDEO_APPLY, 0);
      auto saved = jfg::load_video_settings(profile / L"video.ini");
      check(saved && saved->mode == jfg::FrameRateMode::custom &&
                saved->fps == 360 && !saved->vsync,
            "Apply persists video configuration used by runtime");
      const auto before = read(profile / L"video.ini");
      if (!saved || saved->fps != 360 ||
          saved->mode != jfg::FrameRateMode::custom)
        std::cerr << "Saved: " << before;
      SendMessageW(GetDlgItem(dialog, IDC_VIDEO_FPS_EDIT), WM_SETTEXT, 0,
                   reinterpret_cast<LPARAM>(L"59"));
      wchar_t invalid[32]{};
      SendMessageW(GetDlgItem(dialog, IDC_VIDEO_FPS_EDIT), WM_GETTEXT, 32,
                   reinterpret_cast<LPARAM>(invalid));
      check(std::wstring(invalid) == L"59",
            "invalid-value fixture reached the edit control");
      SendMessageW(dialog, WM_COMMAND, IDC_VIDEO_APPLY, 0);
      check(read(profile / L"video.ini") == before,
            "invalid input preserves saved configuration");
      choose(IDC_VIDEO_FRAME_MODE, 2);
      SendMessageW(dialog, WM_COMMAND, IDCANCEL, 0);
      check(read(profile / L"video.ini") == before,
            "Cancel preserves last Apply");
      Sleep(100);
      check(IsWindowEnabled(frontend) &&
                !GetPropW(frontend, L"JfgFrontendPause"),
            "closing releases modal pause");
      if (live) {
        for (unsigned i = 0;
             i < 100 && GetPropW(frontend, L"JfgFrontendPaused"); ++i)
          Sleep(20);
        check(!GetPropW(frontend, L"JfgFrontendPaused"),
              "runtime acknowledges resume");
        const auto resumed = retraces();
        for (unsigned i = 0; i < 200 && retraces() <= resumed; ++i)
          Sleep(20);
        check(retraces() > resumed,
              "guest VI clock resumes after closing the dialog");
      }
      // Native command ID is stable after the existing commands (100-115).
      PostMessageW(frontend, WM_COMMAND, 116, 0);
      dialog =
          wait_window(desktop, child.dwProcessId, L"Video Settings", L"#32770");
      check(dialog && SendDlgItemMessageW(dialog, IDC_VIDEO_FRAME_MODE,
                                          CB_GETCURSEL, 0, 0) == 1,
            "reopened dialog reads persisted mode");
      if (dialog) {
        SendDlgItemMessageW(dialog, IDC_VIDEO_FRAME_MODE, CB_SETCURSEL, 2, 0);
        SendMessageW(dialog, WM_COMMAND, IDOK, 0);
      }
      saved = jfg::load_video_settings(profile / L"video.ini");
      check(saved && saved->mode == jfg::FrameRateMode::unlimited &&
                !saved->vsync,
            "OK saves Unlimited and closes");
    }
    PostMessageW(frontend, WM_CLOSE, 0, 0);
  }
  const DWORD ended = WaitForSingleObject(child.hProcess, 10000);
  check(ended == WAIT_OBJECT_0, "launcher shuts down after dialog use");
  if (ended != WAIT_OBJECT_0)
    TerminateProcess(child.hProcess, 9);
  CloseHandle(child.hThread);
  CloseHandle(child.hProcess);
  std::cout << "Production launcher video integration: " << failures
            << " failures\n";
  return failures ? 1 : 0;
}
