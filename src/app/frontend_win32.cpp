// Native window ownership is independent of the ROM-derived game process.
#define WIN32_LEAN_AND_MEAN
#define NOMINMAX
#include <windows.h> // Must precede commdlg.h and shellapi.h.

#include <algorithm>
#include <cstdint>
#include <commdlg.h>
#include <filesystem>
#include <fstream>
#include <memory>
#include <shellapi.h>
#include <shlobj.h>
#include <string>
#include <vector>
namespace fs = std::filesystem;
namespace {
constexpr UINT kReady = WM_APP + 20, kHotkey = WM_APP + 21;
enum : UINT {
  Play = 100,
  Stop,
  Setup,
  Cancel,
  Rom,
  Runtime,
  Controllers,
  Audio,
  Fullscreen,
  Map,
  Inventory,
  Support,
  Saves,
  Guide,
  Quit,
  Mods
};
struct Process {
  HANDLE handle = nullptr, job = nullptr;
  void release() {
    if (handle)
      CloseHandle(handle);
    if (job)
      CloseHandle(job);
    handle = job = nullptr;
  }
  bool running() const {
    return handle && WaitForSingleObject(handle, 0) == WAIT_TIMEOUT;
  }
  ~Process() { release(); }
};
struct App {
  HWND window = nullptr, viewport = nullptr, render = nullptr, status = nullptr,
       rom = nullptr, runtime = nullptr;
  std::vector<HWND> home;
  HMENU menu = nullptr;
  HFONT font = nullptr, titleFont = nullptr;
  HBRUSH background = CreateSolidBrush(RGB(18, 27, 40));
  fs::path profile, helper;
  Process session, dialog;
  std::vector<std::unique_ptr<Process>> tools;
  bool playing = false, setting = false, fullscreen = false, closing = false,
       mods = false;
  bool stopRequested = false, initializing = true;
  ULONGLONG startedAt = 0;
  UINT dpi = 96;
  WINDOWPLACEMENT placement{sizeof(WINDOWPLACEMENT)};
  std::wstring lastStatus;
} app;
std::wstring wide(const std::string &text) {
  if (text.empty())
    return {};
  const int n = MultiByteToWideChar(CP_UTF8, MB_ERR_INVALID_CHARS, text.data(),
                                    static_cast<int>(text.size()), nullptr, 0);
  if (n <= 0)
    return {};
  std::wstring result(static_cast<std::size_t>(n), L'\0');
  MultiByteToWideChar(CP_UTF8, MB_ERR_INVALID_CHARS, text.data(),
                      static_cast<int>(text.size()), result.data(), n);
  return result;
}
std::string utf8(const std::wstring &text) {
  const int n = WideCharToMultiByte(CP_UTF8, 0, text.data(),
                                    static_cast<int>(text.size()), nullptr, 0,
                                    nullptr, nullptr);
  std::string result(static_cast<std::size_t>(n), '\0');
  WideCharToMultiByte(CP_UTF8, 0, text.data(), static_cast<int>(text.size()),
                      result.data(), n, nullptr, nullptr);
  return result;
}
std::wstring read(const wchar_t *name) {
  std::ifstream stream(app.profile / name, std::ios::binary | std::ios::ate);
  if (!stream || stream.tellg() > 65536)
    return {};
  stream.seekg(0);
  std::string value{std::istreambuf_iterator<char>(stream), {}};
  while (!value.empty() && (value.back() == '\r' || value.back() == '\n'))
    value.pop_back();
  return wide(value);
}
bool write(const wchar_t *name, const std::wstring &value) {
  const auto path = app.profile / name;
  const auto temporary = fs::path(path.wstring() + L".tmp");
  {
    std::ofstream file(temporary, std::ios::binary | std::ios::trunc);
    file << utf8(value);
    file.flush();
    if (!file)
      return false;
  }
  return MoveFileExW(temporary.c_str(), path.c_str(),
                     MOVEFILE_REPLACE_EXISTING | MOVEFILE_WRITE_THROUGH) !=
         FALSE;
}
std::wstring text(HWND control) {
  int n = GetWindowTextLengthW(control);
  std::wstring value(static_cast<std::size_t>(n + 1), L'\0');
  GetWindowTextW(control, value.data(), n + 1);
  value.resize(static_cast<std::size_t>(n));
  return value;
}
std::wstring quote(const std::wstring &value) {
  std::wstring out = L"\"";
  std::size_t slashes = 0;
  for (wchar_t ch : value) {
    if (ch == L'\\') {
      ++slashes;
      continue;
    }
    out.append(slashes * (ch == L'"' ? 2 : 1), L'\\');
    slashes = 0;
    if (ch == L'"')
      out += L'\\';
    out += ch;
  }
  out.append(slashes * 2, L'\\');
  return out + L"\"";
}
void status(const std::wstring &value) {
  app.lastStatus = value;
  SetWindowTextW(app.status, value.c_str());
}
bool launch(Process &process, const wchar_t *action, HWND owner) {
  if (process.running())
    return false;
  process.release();
  std::wstring command =
      quote(app.helper.wstring()) + L" --frontend-worker " + action + L" " +
      quote(app.profile.wstring()) + L" " +
      std::to_wstring(reinterpret_cast<std::uintptr_t>(owner));
  STARTUPINFOW start{};
  start.cb = sizeof(start);
  PROCESS_INFORMATION child{};
  HANDLE job = CreateJobObjectW(nullptr, nullptr);
  JOBOBJECT_EXTENDED_LIMIT_INFORMATION limits{};
  limits.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE;
  if (!job || !SetInformationJobObject(job, JobObjectExtendedLimitInformation,
                                       &limits, sizeof(limits))) {
    if (job)
      CloseHandle(job);
    status(L"Cannot create a supervised session.");
    return false;
  }
  if (!CreateProcessW(app.helper.c_str(), command.data(), nullptr, nullptr,
                      FALSE, CREATE_NO_WINDOW | CREATE_SUSPENDED, nullptr,
                      app.helper.parent_path().c_str(), &start, &child)) {
    CloseHandle(job);
    status(
        L"The setup helper is missing. Extract the complete launcher package.");
    return false;
  }
  if (!AssignProcessToJobObject(job, child.hProcess)) {
    TerminateProcess(child.hProcess, 1);
    CloseHandle(child.hThread);
    CloseHandle(child.hProcess);
    CloseHandle(job);
    status(L"Cannot supervise the session.");
    return false;
  }
  process.handle = child.hProcess;
  process.job = job;
  ResumeThread(child.hThread);
  CloseHandle(child.hThread);
  return true;
}
int scaled(int value) { return MulDiv(value, static_cast<int>(app.dpi), 96); }
void fonts() {
  HFONT oldFont = app.font, oldTitle = app.titleFont;
  app.font =
      CreateFontW(-scaled(18), 0, 0, 0, FW_NORMAL, FALSE, FALSE, FALSE,
                  DEFAULT_CHARSET, 0, 0, CLEARTYPE_QUALITY, 0, L"Segoe UI");
  app.titleFont =
      CreateFontW(-scaled(38), 0, 0, 0, FW_SEMIBOLD, FALSE, FALSE, FALSE,
                  DEFAULT_CHARSET, 0, 0, CLEARTYPE_QUALITY, 0, L"Segoe UI");
  for (HWND control : app.home)
    SendMessageW(control, WM_SETFONT, reinterpret_cast<WPARAM>(app.font), TRUE);
  if (!app.home.empty())
    SendMessageW(app.home.front(), WM_SETFONT,
                 reinterpret_cast<WPARAM>(app.titleFont), TRUE);
  if (app.status)
    SendMessageW(app.status, WM_SETFONT, reinterpret_cast<WPARAM>(app.font),
                 TRUE);
  if (oldFont)
    DeleteObject(oldFont);
  if (oldTitle)
    DeleteObject(oldTitle);
}
void layout() {
  RECT area{};
  GetClientRect(app.window, &area);
  const int w = MulDiv(area.right, 96, static_cast<int>(app.dpi));
  const int footer =
      (app.fullscreen && app.render && IsWindow(app.render)) ? 0 : 44;
  ShowWindow(app.status, footer ? SW_SHOW : SW_HIDE);
  MoveWindow(app.status, scaled(20), std::max<LONG>(0, area.bottom - scaled(36)),
             std::max<LONG>(1, area.right - scaled(40)), scaled(28), TRUE);
  MoveWindow(app.viewport, 0, 0, std::max<LONG>(1, area.right),
             std::max<LONG>(1, area.bottom - scaled(footer)), TRUE);
  if (app.render && IsWindow(app.render))
    MoveWindow(app.render, 0, 0, std::max<LONG>(1, area.right),
               std::max<LONG>(1, area.bottom - scaled(footer)), TRUE);
  if (app.home.size() >= 10) {
    const int left = 40, width = std::max(250, w - 80);
    auto move = [](HWND control, int x, int y, int width, int height) {
      MoveWindow(control, scaled(x), scaled(y), scaled(width), scaled(height),
                 TRUE);
    };
    move(app.home[0], left, 38, width, 58);
    move(app.home[1], left, 104, width, 48);
    move(app.home[2], left, 178, width, 24);
    move(app.rom, left, 210, std::max(90, width - 120), 30);
    move(app.home[4], w - 150, 208, 110, 34);
    move(app.home[5], left, 264, width, 24);
    move(app.runtime, left, 296, std::max(90, width - 120), 30);
    move(app.home[7], w - 150, 294, 110, 34);
    move(app.home[8], left, 366, 190, 46);
    move(app.home[9], left + 210, 366, 190, 46);
  }
}

void showHome(bool show) {
  for (HWND control : app.home) {
    ShowWindow(control, show ? SW_SHOW : SW_HIDE);
    EnableWindow(control, !app.session.running());
  }
  ShowWindow(app.viewport, show ? SW_HIDE : SW_SHOW);
  EnableMenuItem(app.menu, Play,
                 MF_BYCOMMAND |
                     (app.session.running() ? MF_GRAYED : MF_ENABLED));
  EnableMenuItem(app.menu, Stop,
                 MF_BYCOMMAND | (app.playing ? MF_ENABLED : MF_GRAYED));
  EnableMenuItem(app.menu, Setup,
                 MF_BYCOMMAND |
                     (app.session.running() ? MF_GRAYED : MF_ENABLED));
  DrawMenuBar(app.window);
  layout();
}
void fullscreen() {
  if (!app.fullscreen) {
    GetWindowPlacement(app.window, &app.placement);
    MONITORINFO monitor{sizeof(monitor)};
    GetMonitorInfoW(MonitorFromWindow(app.window, MONITOR_DEFAULTTONEAREST),
                    &monitor);
    app.fullscreen = true;
    SetMenu(app.window, nullptr);
    SetWindowLongPtrW(app.window, GWL_STYLE,
                      WS_POPUP | WS_VISIBLE | WS_CLIPCHILDREN);
    SetWindowPos(app.window, nullptr, monitor.rcMonitor.left,
                 monitor.rcMonitor.top,
                 monitor.rcMonitor.right - monitor.rcMonitor.left,
                 monitor.rcMonitor.bottom - monitor.rcMonitor.top,
                 SWP_NOZORDER | SWP_FRAMECHANGED);
  } else {
    app.fullscreen = false;
    SetMenu(app.window, app.menu);
    SetWindowLongPtrW(app.window, GWL_STYLE,
                      WS_OVERLAPPEDWINDOW | WS_VISIBLE | WS_CLIPCHILDREN);
    SetWindowPlacement(app.window, &app.placement);
    SetWindowPos(app.window, nullptr, 0, 0, 0, 0,
                 SWP_NOMOVE | SWP_NOSIZE | SWP_NOZORDER | SWP_FRAMECHANGED);
  }
  CheckMenuItem(app.menu, Fullscreen,
                MF_BYCOMMAND | (app.fullscreen ? MF_CHECKED : MF_UNCHECKED));
  layout();
}
void pick(bool rom) {
  std::vector<wchar_t> path(32768);
  OPENFILENAMEW dialog{};
  dialog.lStructSize = sizeof(dialog);
  dialog.hwndOwner = app.window;
  dialog.lpstrFile = path.data();
  dialog.nMaxFile = static_cast<DWORD>(path.size());
  dialog.lpstrFilter = rom ? L"N64 ROM\0*.z64;*.n64;*.v64\0All files\0*.*\0"
                           : L"Native game build\0jfg-native-boot.exe\0";
  dialog.Flags = OFN_FILEMUSTEXIST | OFN_PATHMUSTEXIST | OFN_NOCHANGEDIR;
  if (GetOpenFileNameW(&dialog))
    SetWindowTextW(rom ? app.rom : app.runtime, path.data());
}
void capture(bool enabled) {
  app.setting = enabled;
  if (enabled)
    SetPropW(app.window, L"JfgSettingsOpen", reinterpret_cast<HANDLE>(1));
  else {
    RemovePropW(app.window, L"JfgSettingsOpen");
    if (app.render && IsWindow(app.render))
      SetFocus(app.render);
  }
}
void settings(const wchar_t *action) {
  if (app.dialog.running())
    return;
  capture(true);
  if (!launch(app.dialog, action, app.window))
    capture(false);
}
void popup() {
  capture(true);
  HMENU menu = CreatePopupMenu();
  AppendMenuW(menu, MF_STRING, Controllers, L"Controllers");
  AppendMenuW(menu, MF_STRING, Audio, L"Audio");
  AppendMenuW(menu, MF_STRING, Fullscreen, L"Toggle fullscreen");
  AppendMenuW(menu, MF_SEPARATOR, 0, nullptr);
  AppendMenuW(menu, MF_STRING, Stop, L"Stop game / return home");
  POINT p{40, 40};
  ClientToScreen(app.window, &p);
  UINT command = static_cast<UINT>(TrackPopupMenu(
      menu, TPM_RETURNCMD | TPM_LEFTALIGN, p.x, p.y, 0, app.window, nullptr));
  DestroyMenu(menu);
  capture(false);
  if (command)
    PostMessageW(app.window, WM_COMMAND, command, 0);
}
void persist() {
  write(L"frontend-rom.txt", text(app.rom));
  write(L"frontend-runtime.txt", text(app.runtime));
  write(L"frontend-mods.txt", app.mods ? L"1" : L"0");
  if (!app.fullscreen)
    GetWindowPlacement(app.window, &app.placement);
  const RECT &r = app.placement.rcNormalPosition;
  write(L"frontend-window.txt", std::to_wstring(r.left) + L" " +
                                    std::to_wstring(r.top) + L" " +
                                    std::to_wstring(r.right - r.left) + L" " +
                                    std::to_wstring(r.bottom - r.top) + L" " +
                                    (app.fullscreen ? L"1" : L"0"));
}
void stop() {
  app.stopRequested = true;
  if (app.render && IsWindow(app.render)) {
    PostMessageW(app.render, WM_CLOSE, 0, 0);
    status(L"Stopping game and flushing saves...");
  } else if (app.session.running())
    status(L"Cancelling game startup...");
}
HWND control(const wchar_t *cls, const wchar_t *label, DWORD style, int id) {
  HWND h = CreateWindowExW(cls == std::wstring(L"EDIT") ? WS_EX_CLIENTEDGE : 0,
                           cls, label, WS_CHILD | WS_VISIBLE | style, 0, 0, 100,
                           28, app.window,
                           reinterpret_cast<HMENU>(static_cast<INT_PTR>(id)),
                           GetModuleHandleW(nullptr), nullptr);
  SendMessageW(h, WM_SETFONT, reinterpret_cast<WPARAM>(app.font), TRUE);
  return h;
}
void menus() {
  app.menu = CreateMenu();
  auto add =
      [&](const wchar_t *name,
          std::initializer_list<std::pair<UINT, const wchar_t *>> items) {
        HMENU m = CreatePopupMenu();
        for (auto [id, label] : items)
          AppendMenuW(m, id ? MF_STRING : MF_SEPARATOR, id, label);
        AppendMenuW(app.menu, MF_POPUP, reinterpret_cast<UINT_PTR>(m), name);
      };
  add(L"&Game", {{Play, L"&Play"},
                 {Stop, L"&Stop / return home"},
                 {Setup, L"Set up and &build"},
                 {Cancel, L"Cancel setup"},
                 {0, nullptr},
                 {Mods, L"Navigation testing mod"},
                 {Quit, L"&Quit"}});
  add(L"&Controllers", {{Controllers, L"Player 1–4 assignments and mappings"}});
  add(L"&Video", {{Fullscreen, L"&Fullscreen\tF11"}});
  add(L"&Audio", {{Audio, L"&Volume and mute"}});
  add(L"&Tools", {{Map, L"Live map"},
                  {Inventory, L"Live inventory"},
                  {Support, L"Support report"},
                  {Saves, L"Open saves"}});
  add(L"&Help", {{Guide, L"Setup guide"}});
  SetMenu(app.window, app.menu);
}
LRESULT CALLBACK procedure(HWND window, UINT message, WPARAM wparam,
                           LPARAM lparam) {
  switch (message) {
  case WM_CREATE: {
    app.window = window;
    SetPropW(window, L"JfgFrontend", reinterpret_cast<HANDLE>(1));
    app.dpi = GetDpiForWindow(window);
    fonts();
    menus();
    app.viewport =
        CreateWindowExW(0, L"STATIC", L"", WS_CHILD | WS_CLIPCHILDREN, 0, 0, 1,
                        1, window, nullptr, GetModuleHandleW(nullptr), nullptr);
    app.home.push_back(control(L"STATIC", L"JET FORCE GEMINI", 0, 0));
    SendMessageW(app.home.back(), WM_SETFONT,
                 reinterpret_cast<WPARAM>(app.titleFont), TRUE);
    app.home.push_back(
        control(L"STATIC",
                L"Your game. Your controllers. Ready to play.\nChoose a ROM "
                L"once; your settings and saves stay here.",
                0, 0));
    app.home.push_back(control(L"STATIC", L"GAME ROM", 0, 0));
    app.rom = control(L"EDIT", read(L"frontend-rom.txt").c_str(),
                      ES_AUTOHSCROLL | WS_TABSTOP, 0);
    app.home.push_back(app.rom);
    app.home.push_back(
        control(L"BUTTON", L"Browse...", BS_PUSHBUTTON | WS_TABSTOP, Rom));
    app.home.push_back(control(L"STATIC", L"LOCAL GAME BUILD", 0, 0));
    app.runtime = control(L"EDIT", read(L"frontend-runtime.txt").c_str(),
                          ES_AUTOHSCROLL | WS_TABSTOP, 0);
    app.home.push_back(app.runtime);
    app.home.push_back(
        control(L"BUTTON", L"Browse...", BS_PUSHBUTTON | WS_TABSTOP, Runtime));
    app.home.push_back(
        control(L"BUTTON", L"Play", BS_DEFPUSHBUTTON | WS_TABSTOP, Play));
    app.home.push_back(control(L"BUTTON", L"Set up and build",
                               BS_PUSHBUTTON | WS_TABSTOP, Setup));
    app.status = control(L"STATIC", L"Preparing your profile...", SS_LEFT, 0);
    app.mods = read(L"frontend-mods.txt") == L"1";
    CheckMenuItem(app.menu, Mods,
                  MF_BYCOMMAND | (app.mods ? MF_CHECKED : MF_UNCHECKED));
    launch(app.session, L"init", window);
    SetTimer(window, 1, 200, nullptr);
    showHome(true);
    return 0;
  }
  case WM_DPICHANGED: {
    app.dpi = HIWORD(wparam);
    fonts();
    const auto *suggested = reinterpret_cast<RECT *>(lparam);
    SetWindowPos(window, nullptr, suggested->left, suggested->top,
                 suggested->right - suggested->left,
                 suggested->bottom - suggested->top,
                 SWP_NOZORDER | SWP_NOACTIVATE);
    layout();
    return 0;
  }
  case WM_SIZE:
    layout();
    return 0;
  case WM_GETMINMAXINFO: {
    auto *info = reinterpret_cast<MINMAXINFO *>(lparam);
    info->ptMinTrackSize = {scaled(700), scaled(540)};
    return 0;
  }
  case WM_CTLCOLORSTATIC: {
    HDC dc = reinterpret_cast<HDC>(wparam);
    SetTextColor(dc, RGB(225, 234, 245));
    SetBkColor(dc, RGB(18, 27, 40));
    return reinterpret_cast<LRESULT>(app.background);
  }
  case WM_ERASEBKGND: {
    RECT r{};
    GetClientRect(window, &r);
    FillRect(reinterpret_cast<HDC>(wparam), &r, app.background);
    return 1;
  }
  case WM_ENTERMENULOOP:
    capture(true);
    return 0;
  case WM_EXITMENULOOP:
    if (!app.dialog.running())
      capture(false);
    return 0;
  case WM_KEYDOWN:
    if (wparam == VK_F11) {
      fullscreen();
      return 0;
    }
    if (wparam == VK_ESCAPE) {
      popup();
      return 0;
    }
    break;
  case kHotkey:
    if (wparam == VK_F11)
      fullscreen();
    else
      popup();
    return 0;
  case kReady: {
    HWND render = reinterpret_cast<HWND>(wparam);
    if (GetParent(render) != app.viewport)
      return 0;
    app.render = render;
    app.playing = true;
    showHome(false);
    if (app.stopRequested)
      stop();
    else
      SetFocus(render);
    return 0;
  }
  case WM_SETFOCUS:
    if (app.render && IsWindow(app.render) && !app.setting)
      SetFocus(app.render);
    return 0;
  case WM_TIMER: {
    std::erase_if(app.tools, [](const auto &tool) { return !tool->running(); });
    const auto messageText = read(L"frontend-status.txt");
    if (!messageText.empty() && messageText != app.lastStatus)
      status(messageText);
    if (app.stopRequested && app.session.running() && !app.render &&
        GetTickCount64() - app.startedAt > 15000) {
      // No render window means the guest has not entered play; cancel only this
      // launch tree.
      TerminateJobObject(app.session.job, 1);
      write(L"frontend-status.txt", L"Game startup cancelled. You can retry.");
    }
    if (app.session.handle && !app.session.running()) {
      app.session.release();
      app.render = nullptr;
      app.playing = false;
      app.stopRequested = false;
      app.initializing = false;
      showHome(true);
      SetWindowTextW(app.rom, read(L"frontend-rom.txt").c_str());
      SetWindowTextW(app.runtime, read(L"frontend-runtime.txt").c_str());
      if (app.closing)
        DestroyWindow(window);
    }
    if (app.dialog.handle && !app.dialog.running()) {
      app.dialog.release();
      capture(false);
    }
    return 0;
  }
  case WM_COMMAND:
    switch (LOWORD(wparam)) {
    case Rom:
      pick(true);
      break;
    case Runtime:
      pick(false);
      break;
    case Play:
    case Setup:
      if (app.session.running() || app.dialog.running())
        break;
      if (LOWORD(wparam) == Setup &&
          MessageBoxW(
              window,
              L"Setup downloads source and missing build tools. The first "
              L"setup may download several GB and require administrator "
              L"approval or a restart. Your ROM stays on this PC. Continue?",
              L"Set up game", MB_OKCANCEL | MB_ICONINFORMATION) != IDOK)
        break;
      persist();
      app.playing = LOWORD(wparam) == Play;
      app.stopRequested = false;
      app.startedAt = GetTickCount64();
      if (launch(app.session, app.playing ? L"play" : L"setup",
                 app.playing ? app.viewport : window))
        status(app.playing ? L"Starting game..." : L"Starting setup...");
      else
        app.playing = false;
      showHome(true);
      break;
    case Stop:
      stop();
      break;
    case Cancel:
      if (app.session.running() && !app.playing &&
          MessageBoxW(
              window,
              L"Cancel setup? Completed downloads are retained for retry.",
              L"Cancel setup", MB_OKCANCEL) == IDOK) {
        TerminateJobObject(app.session.job, 1);
        status(L"Setup cancelled.");
        write(L"frontend-status.txt", L"Setup cancelled. You can retry.");
      }
      break;
    case Fullscreen:
      fullscreen();
      break;
    case Controllers:
      settings(L"controllers");
      break;
    case Audio:
      settings(L"audio");
      break;
    case Support:
      settings(L"support");
      break;
    case Map:
    case Inventory: {
      auto tool = std::make_unique<Process>();
      if (launch(*tool, LOWORD(wparam) == Map ? L"map" : L"inventory", window))
        app.tools.push_back(std::move(tool));
      break;
    }
    case Saves:
      ShellExecuteW(window, L"open", app.profile.c_str(), nullptr, nullptr,
                    SW_SHOWNORMAL);
      break;
    case Guide:
      ShellExecuteW(window, L"open",
                    L"https://github.com/TK22-26/JetForceGemini-Recomp/blob/"
                    L"develop/docs/development/launcher.md",
                    nullptr, nullptr, SW_SHOWNORMAL);
      break;
    case Mods:
      if (!app.session.running()) {
        app.mods = !app.mods;
        CheckMenuItem(app.menu, Mods,
                      MF_BYCOMMAND | (app.mods ? MF_CHECKED : MF_UNCHECKED));
        persist();
      } else
        status(L"Stop the game before changing testing mods.");
      break;
    case Quit:
      PostMessageW(window, WM_CLOSE, 0, 0);
      break;
    }
    return 0;
  case WM_CLOSE:
    if (!app.initializing)
      persist();
    if (app.session.running()) {
      if (app.initializing) {
        app.closing = true;
      } else if (app.playing) {
        app.closing = true;
        stop();
      } else
        MessageBoxW(window, L"Finish or cancel setup before closing.",
                    L"Jet Force Gemini", MB_OK);
    } else
      DestroyWindow(window);
    return 0;
  case WM_DESTROY:
    KillTimer(window, 1);
    RemovePropW(window, L"JfgFrontend");
    RemovePropW(window, L"JfgSettingsOpen");
    PostQuitMessage(0);
    return 0;
  }
  return DefWindowProcW(window, message, wparam, lparam);
}
} // namespace
int WINAPI wWinMain(HINSTANCE instance, HINSTANCE, PWSTR, int show) {
  HANDLE singleton = CreateMutexW(nullptr, TRUE, L"Local\\JFGUnifiedFrontend");
  if (!singleton || GetLastError() == ERROR_ALREADY_EXISTS) {
    if (singleton)
      CloseHandle(singleton);
    MessageBoxW(nullptr, L"The JFG frontend is already open.",
                L"Jet Force Gemini", MB_OK);
    return 0;
  }
  auto dpi = reinterpret_cast<BOOL(WINAPI *)(HANDLE)>(GetProcAddress(
      GetModuleHandleW(L"user32.dll"), "SetProcessDpiAwarenessContext"));
  if (dpi)
    dpi(reinterpret_cast<HANDLE>(-4)); // same DPI context as hosted renderer
  wchar_t module[32768]{};
  GetModuleFileNameW(nullptr, module, 32768);
  app.helper = fs::path(module).parent_path() / L"JFG-Setup.exe";
  PWSTR local = nullptr;
  if (FAILED(SHGetKnownFolderPath(FOLDERID_LocalAppData, 0, nullptr, &local)))
    return 1;
  app.profile = fs::path(local) / L"JFGRecomp" / L"profiles" / L"default";
  CoTaskMemFree(local);
  int argc = 0;
  LPWSTR *argv = CommandLineToArgvW(GetCommandLineW(), &argc);
  for (int i = 1; i < argc; ++i)
    if (std::wstring(argv[i]) == L"--profile" && i + 1 < argc)
      app.profile = fs::path(argv[++i]);
  LocalFree(argv);
  HRSRC resource = FindResourceW(instance, MAKEINTRESOURCEW(101), RT_RCDATA);
  if (resource) {
    HGLOBAL loaded = LoadResource(instance, resource);
    DWORD size = SizeofResource(instance, resource);
    const auto *bytes = static_cast<const char *>(LockResource(loaded));
    if (!bytes || size == 0 || size > 4 * 1024 * 1024)
      return 1;
    std::uint64_t hash = 1469598103934665603ULL;
    for (DWORD i = 0; i < size; ++i) {
      hash ^= static_cast<unsigned char>(bytes[i]);
      hash *= 1099511628211ULL;
    }
    fs::path helperFolder =
        app.profile / L"frontend-helper" / std::to_wstring(hash);
    std::error_code helperError;
    fs::create_directories(helperFolder, helperError);
    if (helperError)
      return 1;
    app.helper = helperFolder / L"JFG-Setup.exe";
    std::ifstream existing(app.helper, std::ios::binary | std::ios::ate);
    std::string previous;
    if (existing && existing.tellg() == static_cast<std::streamoff>(size)) {
      existing.seekg(0);
      previous.assign(std::istreambuf_iterator<char>(existing), {});
    }
    existing.close();
    if (previous.size() != size ||
        !std::equal(previous.begin(), previous.end(), bytes)) {
      const fs::path tmp = helperFolder / L"JFG-Setup.tmp";
      std::ofstream output(tmp, std::ios::binary | std::ios::trunc);
      output.write(bytes, size);
      output.close();
      if (!output ||
          !MoveFileExW(tmp.c_str(), app.helper.c_str(),
                       MOVEFILE_REPLACE_EXISTING | MOVEFILE_WRITE_THROUGH))
        return 1;
    }
  }
  std::error_code error;
  fs::create_directories(app.profile, error);
  if (error) {
    MessageBoxW(nullptr, L"Cannot open the profile directory.",
                L"Jet Force Gemini", MB_OK | MB_ICONERROR);
    return 1;
  }
  WNDCLASSW wc{};
  wc.lpfnWndProc = procedure;
  wc.hInstance = instance;
  wc.lpszClassName = L"JfgFrontend";
  wc.hCursor = LoadCursorW(nullptr, IDC_ARROW);
  wc.hbrBackground = app.background;
  RegisterClassW(&wc);
  HWND window = CreateWindowExW(
      0, wc.lpszClassName, L"Jet Force Gemini",
      WS_OVERLAPPEDWINDOW | WS_CLIPCHILDREN, CW_USEDEFAULT, CW_USEDEFAULT,
      MulDiv(960, static_cast<int>(GetDpiForSystem()), 96),
      MulDiv(650, static_cast<int>(GetDpiForSystem()), 96), nullptr, nullptr,
      instance, nullptr);
  if (!window)
    return 1;
  int x = 0, y = 0, w = 0, h = 0, full = 0;
  if (swscanf_s(read(L"frontend-window.txt").c_str(), L"%d %d %d %d %d", &x, &y,
                &w, &h, &full) == 5 &&
      w >= 700 && h >= 540) {
    RECT r{x, y, x + w, y + h};
    if (MonitorFromRect(&r, MONITOR_DEFAULTTONULL))
      SetWindowPos(window, nullptr, x, y, w, h, SWP_NOZORDER);
  }
  ShowWindow(window, show);
  UpdateWindow(window);
  if (full)
    fullscreen();
  MSG msg{};
  while (GetMessageW(&msg, nullptr, 0, 0) > 0) {
    if (msg.message == WM_KEYDOWN && msg.wParam == VK_F11) {
      fullscreen();
      continue;
    }
    if (msg.message == WM_KEYDOWN && msg.wParam == VK_ESCAPE) {
      popup();
      continue;
    }
    if (!IsDialogMessageW(window, &msg)) {
      TranslateMessage(&msg);
      DispatchMessageW(&msg);
    }
  }
  app.dialog.release();
  app.session.release();
  DeleteObject(app.font);
  DeleteObject(app.titleFont);
  DeleteObject(app.background);
  DestroyMenu(app.menu);
  ReleaseMutex(singleton);
  CloseHandle(singleton);
  return 0;
}
