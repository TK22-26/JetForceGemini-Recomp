#pragma once
#if defined(_WIN32) && defined(JFG_PHASE8_LIVE_RUNTIME)
#ifndef NOMINMAX
#define NOMINMAX
#endif
#include "jfg/runtime/mouse_input_diagnostics.hpp"
#include "jfg/runtime/window_input_mailbox.hpp"
#include <array>
#include <atomic>
#include <thread>
#include <windows.h>
namespace jfg::boot::native::detail {
class LiveRt64Window final {
public:
  static constexpr UINT kAspectMessage = WM_APP + 22U;
  LiveRt64Window(jfg::WindowInputMailbox &input, std::atomic<bool> &captured,
                 jfg::MouseInputDiagnostics &diagnostics, const bool visible);
  ~LiveRt64Window();
  LiveRt64Window(const LiveRt64Window &) = delete;
  LiveRt64Window &operator=(const LiveRt64Window &) = delete;
  [[nodiscard]] bool raw_available() const noexcept;
  [[nodiscard]] HWND get() const noexcept;
  [[nodiscard]] DWORD thread_id() const noexcept;

private:
  static LRESULT CALLBACK window_proc(HWND window, UINT message, WPARAM wparam,
                                      LPARAM lparam);
  static constexpr UINT kStopMessage = WM_APP + 23U;
  static constexpr wchar_t kClassName[] = L"JfgPhase8LiveRt64Window";
  jfg::WindowInputMailbox &input_;
  std::atomic<bool> &captured_;
  jfg::MouseInputDiagnostics &diagnostics_;
  std::array<bool, 256> buttons_{};
  bool raw_available_ = false;
  HINSTANCE instance_ = nullptr;
  ATOM atom_ = 0U;
  HWND window_ = nullptr;
  DWORD thread_id_ = 0;
  std::thread owner_;
};
} // namespace jfg::boot::native::detail
#endif
