#define WIN32_LEAN_AND_MEAN
#define NOMINMAX
#include "../launcher/native/video_settings_protocol.hpp"
#include "jfg/renderer/video_settings.hpp"
#include <cmath>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <map>
#include <sstream>
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
  if (IsWindowVisible(window) && (search.pid == 0 || pid == search.pid) &&
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
  SetProcessDpiAwarenessContext(DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2);
  if (argc != 4 && argc != 5)
    return 2;
  const bool live = argc == 5;
  const fs::path launcher = argv[1], profile = argv[2];
  std::map<std::string, std::pair<double, double>> coordinates;
  {
    std::ifstream file(argv[3]);
    std::string id;
    double x = 0, y = 0;
    while (file >> id >> x >> y)
      coordinates[id] = {x, y};
  }
  if (coordinates.empty())
    return 2;
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
    command += L" --play --input-replay \"" + std::wstring(argv[4]) +
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
    HWND dialog = wait_window(desktop, 0, L"Video Settings", L"JfgRmlLiveTool");
    check(dialog != nullptr, "Video menu opens separate RmlUi window");
    auto prepareDialog = [&] {
      if (!dialog)
        return;
      const auto dpi = GetDpiForWindow(dialog);
      RECT before{};
      GetClientRect(dialog, &before);
      std::cout << "Initial video client " << before.right << " x "
                << before.bottom << " dpi=" << dpi << std::endl;
      RECT frame{0, 0, MulDiv(720, dpi, 96), MulDiv(700, dpi, 96)};
      AdjustWindowRectExForDpi(&frame, WS_OVERLAPPEDWINDOW, FALSE, 0, dpi);
      SetWindowPos(dialog, nullptr, 20, 20, frame.right - frame.left,
                   frame.bottom - frame.top, SWP_NOZORDER | SWP_NOACTIVATE);
      Sleep(250);
      RECT after{};
      GetClientRect(dialog, &after);
      check(after.right == MulDiv(720, dpi, 96) &&
                after.bottom == MulDiv(700, dpi, 96),
            "fixture client matches measured RmlUi coordinates");
    };
    prepareDialog();
    auto waitClosed = [&] {
      for (unsigned i = 0;
           i < 250 && (IsWindow(dialog) || !IsWindowEnabled(frontend) ||
                       GetPropW(frontend, L"JfgFrontendPause"));
           ++i)
        Sleep(20);
      check(!IsWindow(dialog) && IsWindowEnabled(frontend) &&
                !GetPropW(frontend, L"JfgFrontendPause"),
            "closing restores owner and releases pause");
    };
    if (dialog) {
      Sleep(300);
      check(GetWindow(dialog, GW_OWNER) == frontend &&
                !IsWindowEnabled(frontend),
            "owned RmlUi window disables launcher");
      check(GetPropW(frontend, L"JfgFrontendPause") != nullptr,
            "video settings request pause");
      if (live) {
        for (unsigned i = 0;
             i < 100 && !GetPropW(frontend, L"JfgFrontendPaused"); ++i)
          Sleep(20);
        check(GetPropW(frontend, L"JfgFrontendPaused") != nullptr,
              "runtime acknowledges RmlUi settings pause");
        Sleep(200);
        const auto paused = retraces();
        Sleep(300);
        check(paused > 0 && paused == retraces(),
              "VI clock is stopped during settings");
      }
      auto click = [&](const char *id) {
        const auto found = coordinates.find(id);
        check(found != coordinates.end(), id);
        if (found == coordinates.end())
          return;
        const double dpi = GetDpiForWindow(dialog) / 96.0;
        const LPARAM position =
            MAKELPARAM(int(std::lround(found->second.first * dpi)),
                       int(std::lround(found->second.second * dpi)));
        SendMessageW(dialog, WM_MOUSEMOVE, 0, position);
        SendMessageW(dialog, WM_LBUTTONDOWN, MK_LBUTTON, position);
        SendMessageW(dialog, WM_LBUTTONUP, 0, position);
        Sleep(100);
      };
      click("video-custom");
      click("video-preset-360");
      click("video-vsync");
      click("video-apply");
      auto saved = jfg::load_video_settings(profile / L"video.ini");
      check(saved && saved->mode == jfg::FrameRateMode::custom &&
                saved->fps == 360 && !saved->vsync,
            "actual RmlUi Apply persists custom FPS and VSync");
      if (saved)
        std::cout << "After Apply: " << jfg::serialize_video_settings(*saved);
      click("video-fullscreen");
      click("video-pause");
      click("video-apply");
      check((GetWindowLongPtrW(frontend, GWL_STYLE) & WS_POPUP) != 0,
            "fullscreen applies to live owner immediately");
      check(read(profile / L"frontend-pause-inactive.txt") == "1",
            "pause preference persists immediately");
      click("video-windowed");
      click("video-pause");
      click("video-apply");
      check((GetWindowLongPtrW(frontend, GWL_STYLE) & WS_OVERLAPPEDWINDOW) ==
                WS_OVERLAPPEDWINDOW,
            "windowed applies without game restart");
      const auto before = read(profile / L"video.ini");
      click("video-unlimited");
      click("video-cancel");
      waitClosed();
      check(read(profile / L"video.ini") == before,
            "Cancel discards unsaved mode");
      if (live) {
        for (unsigned i = 0;
             i < 100 && GetPropW(frontend, L"JfgFrontendPaused"); ++i)
          Sleep(20);
        check(!GetPropW(frontend, L"JfgFrontendPaused"),
              "runtime acknowledges resume");
        const auto resumed = retraces();
        for (unsigned i = 0; i < 200 && retraces() <= resumed; ++i)
          Sleep(20);
        check(retraces() > resumed, "VI clock resumes");
      }
      PostMessageW(frontend, WM_COMMAND, 116, 0);
      dialog = wait_window(desktop, 0, L"Video Settings", L"JfgRmlLiveTool");
      check(dialog != nullptr, "RmlUi settings reopen");
      if (dialog) {
        prepareDialog();
        click("video-unlimited");
        click("video-ok");
        waitClosed();
      }
      saved = jfg::load_video_settings(profile / L"video.ini");
      check(saved && saved->mode == jfg::FrameRateMode::unlimited &&
                saved->fps == 360 && !saved->vsync,
            "OK persists Unlimited with remembered custom cap");
      // Verify recovery if only the supervised settings process fails.
      PostMessageW(frontend, WM_COMMAND, 116, 0);
      dialog = wait_window(desktop, 0, L"Video Settings", L"JfgRmlLiveTool");
      if (dialog) {
        prepareDialog();
        DWORD pid = 0;
        GetWindowThreadProcessId(dialog, &pid);
        HANDLE process =
            OpenProcess(PROCESS_TERMINATE | SYNCHRONIZE, FALSE, pid);
        check(process != nullptr, "fixture owns settings process");
        if (process) {
          TerminateProcess(process, 7);
          WaitForSingleObject(process, 3000);
          CloseHandle(process);
        }
        waitClosed();
      }
    }

    PostMessageW(frontend, WM_CLOSE, 0, 0);
  }
  const DWORD ended = WaitForSingleObject(child.hProcess, 10000);
  check(ended == WAIT_OBJECT_0, "launcher shuts down after dialog use");
  if (ended != WAIT_OBJECT_0)
    TerminateProcess(child.hProcess, 9);
  CloseHandle(child.hThread);
  CloseHandle(child.hProcess);
  std::cout << "RmlUi launcher video integration: " << failures
            << " failures\n";
  return failures ? 1 : 0;
}
