#pragma once
#include <string_view>
#if defined(_WIN32)
#ifndef NOMINMAX
#define NOMINMAX
#endif
#include <windows.h>
#endif

namespace jfg {
// This separate stream contains only host diagnostic categories, never guest
// bytes or paths. It is opened/flushed per event so process crashes retain it.
inline void support_event(const std::string_view event) noexcept {
#if defined(_WIN32)
    if (event.empty() || event.size() > 160U ||
        event.find_first_not_of("abcdefghijklmnopqrstuvwxyz0123456789=_-/") != std::string_view::npos) return;
    wchar_t path[32768]{};
    const DWORD length = GetEnvironmentVariableW(L"JFG_SUPPORT_LOG", path, 32768U);
    if (length == 0U || length >= 32768U) return;
    HANDLE file = CreateFileW(path, FILE_APPEND_DATA | GENERIC_READ, FILE_SHARE_READ | FILE_SHARE_WRITE,
                              nullptr, OPEN_ALWAYS, FILE_ATTRIBUTE_NORMAL, nullptr);
    if (file == INVALID_HANDLE_VALUE) return;
    LARGE_INTEGER size{};
    if (GetFileSizeEx(file, &size) && size.QuadPart <= 65536 - 162) {
        char line[162]{};
        for (std::size_t i = 0; i < event.size(); ++i) line[i] = event[i];
        line[event.size()] = '\n';
        DWORD written = 0;
        (void)WriteFile(file, line, static_cast<DWORD>(event.size() + 1U), &written, nullptr);
        (void)FlushFileBuffers(file);
    }
    CloseHandle(file);
#else
    (void)event;
#endif
}
} // namespace jfg
