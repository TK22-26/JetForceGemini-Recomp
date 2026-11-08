#pragma once
#if defined(_WIN32)
#ifndef NOMINMAX
#define NOMINMAX
#endif
#include <windows.h>
#include <array>
#include <cstdint>

namespace jfg {
// Own on the HWND thread. Gameplay publishes intent; this object owns the
// cursor operations and only confirms capture after checking their result.
class Win32RelativeMouse final {
public:
    using ClipFunction = BOOL (WINAPI *)(const RECT*);
    explicit Win32RelativeMouse(ClipFunction clip = &ClipCursor) noexcept : clip_(clip) {}
    Win32RelativeMouse(const Win32RelativeMouse&) = delete;
    Win32RelativeMouse& operator=(const Win32RelativeMouse&) = delete;
    ~Win32RelativeMouse() { release(); }

    bool update(HWND window, bool requested) noexcept {
        state_[0] = requested ? 1U : 0U;
        state_[2] = state_[3] = state_[4] = state_[5] = state_[7] = 0;
        const HWND root = window ? GetAncestor(window, GA_ROOT) : nullptr;
        if (!requested || !window || GetWindowThreadProcessId(window, nullptr) != GetCurrentThreadId() ||
            GetForegroundWindow() != root || GetFocus() != window || !IsWindowVisible(window) ||
            IsIconic(root) || GetPropW(root, L"JfgSettingsOpen")) {
            leave();
            return false;
        }
        RECT client{};
        if (!GetClientRect(window, &client) || client.right <= client.left || client.bottom <= client.top) {
            state_[7] = ERROR_INVALID_WINDOW_HANDLE;
            leave();
            return false;
        }
        POINT center{client.left + (client.right - client.left) / 2,
                     client.top + (client.bottom - client.top) / 2};
        if (!ClientToScreen(window, &center)) {
            state_[7] = GetLastError();
            leave();
            return false;
        }
        state_[2] = 1;
        // Raw relative motion remains independent of the desktop pointer.
        // Keep that pointer away from client edges and other desktop windows.
        const RECT desired{center.x, center.y, center.x + 1, center.y + 1};
        RECT current{};
        if (!owned_ || !GetClipCursor(&current) || !EqualRect(&current, &desired)) {
            if (state_[6] != UINT32_MAX) ++state_[6];
            SetLastError(ERROR_SUCCESS);
            if (!clip_(&desired)) {
                state_[7] = GetLastError();
                leave();
                return false;
            }
            rectangle_ = desired;
            owned_ = true;
        }
        state_[3] = 1;
        if (!GetClipCursor(&current) || !EqualRect(&current, &desired)) {
            state_[7] = ERROR_INVALID_STATE;
            leave();
            return false;
        }
        state_[4] = 1;
        POINT position{};
        state_[5] = GetCursorPos(&position) && PtInRect(&desired, position) ? 1U : 0U;
        if (!state_[5]) {
            state_[7] = ERROR_INVALID_STATE;
            leave();
            return false;
        }
        if (!hidden_) {
            ShowCursor(FALSE);
            hidden_ = true;
        }
        SetCursor(nullptr);
        state_[1] = 1;
        return true;
    }

    void release() noexcept {
        state_[0] = 0;
        leave();
    }

    // requested,active,geometry,clip_api,rectangle_matches,pointer_inside,
    // clip_attempts,last_error. No positions, handles, keys or device names.
    const std::array<std::uint32_t, 8>& state() const noexcept { return state_; }

private:
    void leave() noexcept {
        if (owned_) {
            RECT current{};
            // Focus changes can let another application acquire a new clip.
            if (GetClipCursor(&current) && EqualRect(&current, &rectangle_)) clip_(nullptr);
            owned_ = false;
        }
        if (hidden_) {
            ShowCursor(TRUE);
            SetCursor(LoadCursorW(nullptr, MAKEINTRESOURCEW(32512)));
            hidden_ = false;
        }
        state_[1] = 0;
    }
    ClipFunction clip_;
    RECT rectangle_{};
    bool owned_ = false, hidden_ = false;
    std::array<std::uint32_t, 8> state_{};
};
} // namespace jfg
#endif
