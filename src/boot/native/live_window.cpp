#include "live_window.hpp"
#if defined(_WIN32) && defined(JFG_PHASE8_LIVE_RUNTIME)
#include "jfg/renderer/actor_lod_presentation.hpp"
#include "jfg/renderer/fog_settings.hpp"
#include "jfg/renderer/shadow_settings.hpp"
#include <cstdlib>
#include <future>
namespace jfg::boot::native::detail {
LiveRt64Window::LiveRt64Window(jfg::WindowInputMailbox &input,
                               std::atomic<bool> &captured,
                               std::atomic<bool> &requested,
                               jfg::MouseInputDiagnostics &diagnostics,
                               const bool visible)
    : input_(input), captured_(captured), requested_(requested), diagnostics_(diagnostics) {
  // No guest state is accessed by this thread. A window move/resize can enter
  // Win32's modal loop for arbitrarily long without parking the guest CPU.
  std::promise<void> ready;
  auto initialized = ready.get_future();
  owner_ = std::thread([this, visible, &ready] {
    thread_id_ = GetCurrentThreadId();
    instance_ = GetModuleHandleW(nullptr);
    WNDCLASSW window_class{};
    window_class.lpfnWndProc = window_proc;
    window_class.hIcon = LoadIconW(instance_, MAKEINTRESOURCEW(1));
    window_class.hInstance = instance_;
    window_class.hCursor = LoadCursorW(nullptr, MAKEINTRESOURCEW(32512));
    window_class.lpszClassName = kClassName;
    atom_ = RegisterClassW(&window_class);
    if (atom_ != 0U) {
      wchar_t parent_text[32]{};
      HWND parent = nullptr;
      if (GetEnvironmentVariableW(L"JFG_FRONTEND_PARENT", parent_text, 32) >
          0) {
        wchar_t *end = nullptr;
        const auto value = wcstoull(parent_text, &end, 10);
        parent = reinterpret_cast<HWND>(static_cast<std::uintptr_t>(value));
        if (!end || *end || !IsWindow(parent) ||
            !GetPropW(GetAncestor(parent, GA_ROOT), L"JfgFrontend")) {
          ready.set_value();
          UnregisterClassW(kClassName, instance_);
          return;
        }
      }
      const DWORD style = parent ? WS_CHILD | WS_VISIBLE | WS_CLIPSIBLINGS
                                 : WS_OVERLAPPEDWINDOW;
      RECT rectangle{0, 0, 640, 480};
      if (parent)
        GetClientRect(parent, &rectangle);
      if (parent || AdjustWindowRectEx(&rectangle, style, FALSE, 0U)) {
        window_ = CreateWindowExW(
            0U, kClassName, L"Jet Force Gemini Recomp", style,
            parent ? 0 : CW_USEDEFAULT, parent ? 0 : CW_USEDEFAULT,
            rectangle.right - rectangle.left, rectangle.bottom - rectangle.top,
            parent, nullptr, instance_, this);
      }
      if (window_) {
        SetTimer(window_, kCaptureTimer, 16U, nullptr);
        // The render child and launcher root belong to separate processes.
        // Foreground-only delivery depends on which hosted window receives
        // the pointer. Subscribe explicitly, then gate consumption by our
        // foreground root and capture state in WM_INPUT.
        RAWINPUTDEVICE mouse{0x01, 0x02, RIDEV_INPUTSINK, window_};
        raw_available_ =
            RegisterRawInputDevices(&mouse, 1, sizeof(mouse)) != FALSE;
        diagnostics_.registration(raw_available_,
                                  raw_available_ ? 0U : GetLastError());
        if (parent)
          PostMessageW(GetAncestor(parent, GA_ROOT), WM_APP + 20,
                       reinterpret_cast<WPARAM>(window_), 0);
        if (visible) {
          ShowWindow(window_, SW_SHOW);
          UpdateWindow(window_);
        }
      }
    }
    ready.set_value();
    if (window_) {
      MSG message{};
      while (GetMessageW(&message, nullptr, 0U, 0U) > 0) {
        TranslateMessage(&message);
        DispatchMessageW(&message);
      }
      requested_.store(false);
      relative_mouse_.release();
      captured_.store(false);
      diagnostics_.capture(relative_mouse_.state());
      KillTimer(window_, kCaptureTimer);
      DestroyWindow(window_);
    }
    if (atom_)
      UnregisterClassW(kClassName, instance_);
  });
  initialized.get(); // Publishes the initialized HWND and owner thread ID.
}

LiveRt64Window::~LiveRt64Window() {
  if (window_)
    PostMessageW(window_, kStopMessage, 0, 0);
  if (owner_.joinable())
    owner_.join();
}

bool LiveRt64Window::raw_available() const noexcept { return raw_available_; }

HWND LiveRt64Window::get() const noexcept { return window_; }

DWORD LiveRt64Window::thread_id() const noexcept { return thread_id_; }

void LiveRt64Window::sync_mouse_capture() noexcept {
  captured_.store(relative_mouse_.update(window_, requested_.load() && !capture_suspended_));
  diagnostics_.capture(relative_mouse_.state());
}

LRESULT CALLBACK LiveRt64Window::window_proc(HWND window, UINT message,
                                             WPARAM wparam, LPARAM lparam) {
  if (message == WM_NCCREATE) {
    const auto *create = reinterpret_cast<const CREATESTRUCTW *>(lparam);
    SetWindowLongPtrW(window, GWLP_USERDATA,
                      reinterpret_cast<LONG_PTR>(create->lpCreateParams));
  }
  auto *self = reinterpret_cast<LiveRt64Window *>(
      GetWindowLongPtrW(window, GWLP_USERDATA));
  if (!self)
    return DefWindowProcW(window, message, wparam, lparam);
  if (message == WM_TIMER && wparam == kCaptureTimer) {
    self->sync_mouse_capture();
    return 0;
  }
  if (message == WM_ENTERSIZEMOVE || message == WM_EXITSIZEMOVE) {
    self->capture_suspended_ = message == WM_ENTERSIZEMOVE;
    self->sync_mouse_capture();
  }
  if (message == WM_APP + 28 && wparam <= 1 &&
      reinterpret_cast<HWND>(lparam) == GetAncestor(window, GA_ROOT)) {
    jfg::configure_shadow_quality(wparam ? jfg::ShadowQuality::enhanced
                                         : jfg::ShadowQuality::original);
    return 1;
  }
  if (message == WM_APP + 27 && wparam <= 1 &&
      reinterpret_cast<HWND>(lparam) == GetAncestor(window, GA_ROOT)) {
    jfg::configure_actor_lod(wparam ? jfg::ActorLod::high
                                    : jfg::ActorLod::original);
    return 1;
  }
  if (message == WM_APP + 26 && wparam <= 100 &&
      reinterpret_cast<HWND>(lparam) == GetAncestor(window, GA_ROOT)) {
    jfg::configure_fog_strength(static_cast<unsigned>(wparam));
    return 1;
  }
  if (message == WM_INPUT) {
    RAWINPUT raw{};
    UINT size = sizeof(raw);
    const bool read_ok =
        GetRawInputData(reinterpret_cast<HRAWINPUT>(lparam), RID_INPUT, &raw,
                        &size, sizeof(RAWINPUTHEADER)) != UINT(-1);
    const DWORD error = read_ok ? 0U : GetLastError();
    const bool mouse = read_ok && raw.header.dwType == RIM_TYPEMOUSE;
    const bool absolute =
        mouse && (raw.data.mouse.usFlags & MOUSE_MOVE_ABSOLUTE) != 0;
    const bool captured = self->captured_.load();
    self->diagnostics_.raw(
        read_ok, mouse, absolute, captured,
        mouse && (raw.data.mouse.lLastX != 0 || raw.data.mouse.lLastY != 0),
        GET_RAWINPUT_CODE_WPARAM(wparam) == RIM_INPUTSINK, error);
    const HWND root = GetAncestor(window, GA_ROOT);
    if (read_ok && mouse && !absolute && captured &&
        GetForegroundWindow() == root && !GetPropW(root, L"JfgSettingsOpen"))
      self->input_.motion(raw.data.mouse.lLastX, raw.data.mouse.lLastY);
  }
  // The render child can receive activation messages while the launcher
  // root is already foreground. Keep those clicks; only a click returning
  // from another application is consumed to avoid firing on focus return.
  if (message == WM_MOUSEACTIVATE && LOWORD(lparam) == HTCLIENT)
    return GetForegroundWindow() == GetAncestor(window, GA_ROOT)
               ? MA_ACTIVATE
               : MA_ACTIVATEANDEAT;
  // Always restore the client cursor after a nonclient resize hit. Leave
  // resize borders to DefWindowProc, including during gameplay capture.
  if (message == WM_SETCURSOR && LOWORD(lparam) == HTCLIENT) {
    SetCursor(self->captured_.load()
                  ? nullptr
                  : LoadCursorW(nullptr, MAKEINTRESOURCEW(32512)));
    return TRUE;
  }
  if (message == WM_MOUSELEAVE || message == WM_SIZE)
    self->input_.pointer_leave();
  if (message == WM_MOUSEMOVE) {
    RECT r{};
    GetClientRect(window, &r);
    self->input_.pointer(static_cast<short>(LOWORD(lparam)),
                         static_cast<short>(HIWORD(lparam)), r.right, r.bottom);
    TRACKMOUSEEVENT track{sizeof(TRACKMOUSEEVENT), TME_LEAVE, window, 0};
    TrackMouseEvent(&track);
  }
  if (message >= WM_MOUSEFIRST && message <= WM_MOUSELAST) {
    int key = 0;
    bool down = false;
    switch (message) {
    case WM_LBUTTONDOWN:
    case WM_LBUTTONUP:
      key = VK_LBUTTON;
      down = message == WM_LBUTTONDOWN;
      break;
    case WM_RBUTTONDOWN:
    case WM_RBUTTONUP:
      key = VK_RBUTTON;
      down = message == WM_RBUTTONDOWN;
      break;
    case WM_MBUTTONDOWN:
    case WM_MBUTTONUP:
      key = VK_MBUTTON;
      down = message == WM_MBUTTONDOWN;
      break;
    case WM_XBUTTONDOWN:
    case WM_XBUTTONUP:
      key = HIWORD(wparam) == XBUTTON1 ? VK_XBUTTON1 : VK_XBUTTON2;
      down = message == WM_XBUTTONDOWN;
      break;
    case WM_MOUSEWHEEL:
      self->input_.wheel(static_cast<short>(HIWORD(wparam)));
      break;
    default:
      break;
    }
    if (key) {
      if (down && GetFocus() != window) {
        const bool foreground =
            GetForegroundWindow() == GetAncestor(window, GA_ROOT);
        SetFocus(window);
        if (!foreground)
          return message == WM_XBUTTONDOWN ? TRUE : 0;
      }
      // Reacquiring our own capture emits WM_CAPTURECHANGED and clears
      // held buttons. A second button (RMB aim + LMB fire) shares capture.
      if (down && GetCapture() != window)
        SetCapture(window);
      self->buttons_[static_cast<std::size_t>(key)] = down;
      if (key == VK_LBUTTON || key == VK_RBUTTON) {
        RECT r{};
        GetClientRect(window, &r);
        self->input_.pointer(static_cast<short>(LOWORD(lparam)),
                             static_cast<short>(HIWORD(lparam)), r.right,
                             r.bottom, key, down);
      } else
        self->input_.key(static_cast<std::size_t>(key), down);
      if (!down && GetCapture() == window && !self->buttons_[VK_LBUTTON] &&
          !self->buttons_[VK_RBUTTON] && !self->buttons_[VK_MBUTTON] &&
          !self->buttons_[VK_XBUTTON1] && !self->buttons_[VK_XBUTTON2])
        ReleaseCapture();
      return message == WM_XBUTTONDOWN || message == WM_XBUTTONUP ? TRUE : 0;
    }
  }
  if (message == WM_CAPTURECHANGED)
    for (auto key :
         {VK_LBUTTON, VK_RBUTTON, VK_MBUTTON, VK_XBUTTON1, VK_XBUTTON2}) {
      self->buttons_[static_cast<std::size_t>(key)] = false;
      self->input_.key(static_cast<std::size_t>(key), false);
    }
  if ((message == WM_KEYDOWN || message == WM_KEYUP ||
       message == WM_SYSKEYDOWN || message == WM_SYSKEYUP) &&
      wparam < 256U) {
    // Alt is bindable, but Alt+F4 remains a window-manager shortcut.
    if ((message == WM_SYSKEYDOWN || message == WM_SYSKEYUP) && wparam == VK_F4)
      return DefWindowProcW(window, message, wparam, lparam);
    const bool down = message == WM_KEYDOWN || message == WM_SYSKEYDOWN;
    if (GetParent(window) && down &&
        (wparam == VK_F11 || wparam == VK_ESCAPE)) {
      PostMessageW(GetAncestor(window, GA_ROOT), WM_APP + 21, wparam, 0);
      return 0;
    }
    self->input_.key(static_cast<std::size_t>(wparam), down,
                     (lparam & (LPARAM(1) << 30)) != 0);
    return 0;
  }
  if (message == WM_KILLFOCUS || (message == WM_ACTIVATEAPP && !wparam)) {
    self->diagnostics_.increment(jfg::MouseCount::focus_lost);
    self->requested_.store(false);
    self->captured_.store(false);
    self->relative_mouse_.release();
    self->diagnostics_.capture(self->relative_mouse_.state());
    self->buttons_.fill(false);
    if (GetCapture() == window)
      ReleaseCapture();
    self->input_.lose_focus();
    return 0;
  }
  if (message == WM_CLOSE) {
    self->capture_suspended_ = true;
    self->requested_.store(false);
    self->sync_mouse_capture();
    self->input_.close();
    return 0;
  }
  if (message == kStopMessage) {
    PostQuitMessage(0);
    return 0;
  }
  if (message == kAspectMessage) {
    if (wparam == 320U && (lparam == 180 || lparam == 240)) {
      SetPropW(window, L"JfgGameAspectWidth", reinterpret_cast<HANDLE>(wparam));
      SetPropW(window, L"JfgGameAspectHeight",
               reinterpret_cast<HANDLE>(lparam));
      if (GetParent(window))
        PostMessageW(GetAncestor(window, GA_ROOT), WM_APP + 24,
                     reinterpret_cast<WPARAM>(window), 0);
    }
    RECT client{};
    if (!GetParent(window) && wparam != 0U && lparam > 0 && !IsZoomed(window) &&
        !IsIconic(window) && GetClientRect(window, &client) &&
        client.bottom > client.top) {
      const LONG height = client.bottom - client.top;
      const LONG width =
          static_cast<LONG>((std::uint64_t(height) * wparam +
                             static_cast<std::uint64_t>(lparam) / 2U) /
                            static_cast<std::uint64_t>(lparam));
      RECT outer{0, 0, width, height};
      if (AdjustWindowRectEx(
              &outer, static_cast<DWORD>(GetWindowLongPtrW(window, GWL_STYLE)),
              FALSE,
              static_cast<DWORD>(GetWindowLongPtrW(window, GWL_EXSTYLE))))
        SetWindowPos(window, nullptr, 0, 0, outer.right - outer.left,
                     outer.bottom - outer.top,
                     SWP_NOMOVE | SWP_NOZORDER | SWP_NOACTIVATE);
    }
    return 0;
  }
  return DefWindowProcW(window, message, wparam, lparam);
}
} // namespace jfg::boot::native::detail
#endif
