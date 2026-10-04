#pragma once
#if defined(_WIN32)
#ifndef NOMINMAX
#define NOMINMAX
#endif
#include <windows.h>
#include <psapi.h>
#include <cstdio>
#include <cstdint>
#include <cstring>
#include <cwchar>

namespace jfg {
// The exported format contains only module identities and relative code locations.
// Context registers and memory used while unwinding never reach the output.
inline bool support_sibling(const wchar_t *name, wchar_t (&path)[32768]) noexcept {
    const DWORD n = GetEnvironmentVariableW(L"JFG_SUPPORT_LOG", path, 32768);
    if (n == 0 || n >= 32768) return false;
    wchar_t *last = std::wcsrchr(path, L'\\');
    wchar_t *slash = std::wcsrchr(path, L'/');
    if (slash != nullptr && (last == nullptr || slash > last)) last = slash;
    if (last == nullptr || static_cast<std::size_t>(last - path) + std::wcslen(name) + 2 >= 32768) return false;
    std::memcpy(last + 1, name, (std::wcslen(name) + 1) * sizeof(wchar_t)); return true;
}
inline HANDLE support_file(const wchar_t *name, DWORD disposition = CREATE_ALWAYS) noexcept {
    wchar_t path[32768]{};
    if (!support_sibling(name, path)) return INVALID_HANDLE_VALUE;
    return CreateFileW(path, GENERIC_WRITE, FILE_SHARE_READ | FILE_SHARE_WRITE, nullptr, disposition, FILE_ATTRIBUTE_NORMAL, nullptr);
}
inline void support_line(HANDLE output, const char *line) noexcept {
    DWORD count = 0;
    (void)WriteFile(output, line, static_cast<DWORD>(std::strlen(line)), &count, nullptr);
}
inline bool support_read(HANDLE process, std::uint64_t address, void *buffer, SIZE_T size) noexcept {
    SIZE_T read = 0;
    return ReadProcessMemory(process, reinterpret_cast<const void *>(address), buffer, size, &read) != 0 && read == size;
}
inline bool support_frame(HANDLE output, HANDLE process, DWORD thread, unsigned index, std::uint64_t pc) noexcept {
    MEMORY_BASIC_INFORMATION memory{};
    if (!VirtualQueryEx(process, reinterpret_cast<const void *>(pc), &memory, sizeof(memory)) || memory.Type != MEM_IMAGE) return false;
    const auto base = reinterpret_cast<std::uint64_t>(memory.AllocationBase);
    IMAGE_DOS_HEADER dos{}; IMAGE_NT_HEADERS64 nt{};
    if (!support_read(process, base, &dos, sizeof(dos)) || dos.e_magic != IMAGE_DOS_SIGNATURE || dos.e_lfanew < 0 || dos.e_lfanew > 1048576 ||
        !support_read(process, base + static_cast<unsigned>(dos.e_lfanew), &nt, sizeof(nt)) || nt.Signature != IMAGE_NT_SIGNATURE ||
        nt.OptionalHeader.Magic != IMAGE_NT_OPTIONAL_HDR64_MAGIC || pc < base || pc - base >= nt.OptionalHeader.SizeOfImage) return false;
    wchar_t path[32768]{}; char name[97]{};
    GetModuleFileNameExW(process, static_cast<HMODULE>(memory.AllocationBase), path, 32768);
    const wchar_t *leaf = std::wcsrchr(path, L'\\'); leaf = leaf == nullptr ? path : leaf + 1;
    unsigned n = 0;
    for (; leaf[n] != 0 && n < 96; ++n) {
        wchar_t c = leaf[n]; if (c >= L'A' && c <= L'Z') c += L'a' - L'A';
        name[n] = (c >= L'a' && c <= L'z') || (c >= L'0' && c <= L'9') || c == L'.' || c == L'-' || c == L'_' ? static_cast<char>(c) : '_';
    }
    if (n == 0) std::memcpy(name, "unknown", 8);
    char line[256]{};
    std::snprintf(line, sizeof(line), "frame=%lu/%u/%s/%08lx/%08lx/%08llx\n", static_cast<unsigned long>(thread), index, name,
        static_cast<unsigned long>(nt.FileHeader.TimeDateStamp), static_cast<unsigned long>(nt.OptionalHeader.SizeOfImage), static_cast<unsigned long long>(pc - base));
    support_line(output, line); return true;
}
inline void support_unwind(HANDLE file, CONTEXT context) noexcept {
    // Fault-context unwind, not a stack captured from inside the exception handler.
    // SEH guards corrupt stack/unwind metadata. Do not add C++ objects requiring unwinding here.
    __try {
        for (unsigned i = 0; i < 48 && context.Rip != 0; ++i) {
            (void)support_frame(file, GetCurrentProcess(), GetCurrentThreadId(), i, context.Rip);
            const DWORD64 old_rip = context.Rip, old_rsp = context.Rsp;
            DWORD64 base = 0; PRUNTIME_FUNCTION function = RtlLookupFunctionEntry(context.Rip, &base, nullptr);
            if (function != nullptr) {
                PVOID data = nullptr; DWORD64 establisher = 0;
                RtlVirtualUnwind(UNW_FLAG_NHANDLER, base, context.Rip, function, &context, &data, &establisher, nullptr);
            } else {
                if (!support_read(GetCurrentProcess(), context.Rsp, &context.Rip, sizeof(context.Rip))) break;
                context.Rsp += sizeof(DWORD64);
            }
            if (context.Rsp <= old_rsp || context.Rsp - old_rsp > 16 * 1024 * 1024 || (context.Rip == old_rip && context.Rsp == old_rsp)) break;
        }
    } __except(EXCEPTION_EXECUTE_HANDLER) { support_line(file, "diagnostic=stack-partial\n"); }
}
inline void support_crash(EXCEPTION_POINTERS *exception) noexcept {
    static LONG entered = 0;
    if (InterlockedCompareExchange(&entered, 1, 0) != 0) return;
    HANDLE output = support_file(L"crash.log");
    if (output == INVALID_HANDLE_VALUE) return;
    support_line(output, "snapshot=crash-v1\n");
    char line[80]{};
    SYSTEMTIME utc{}; GetSystemTime(&utc);
    std::snprintf(line, sizeof(line), "utc=%04u-%02u-%02uT%02u:%02u:%02uZ\n", utc.wYear, utc.wMonth, utc.wDay, utc.wHour, utc.wMinute, utc.wSecond); support_line(output, line);
    if (exception != nullptr && exception->ExceptionRecord != nullptr) {
        std::snprintf(line, sizeof(line), "native_exception=0x%08lx\n", static_cast<unsigned long>(exception->ExceptionRecord->ExceptionCode)); support_line(output, line);
    }
    if (exception != nullptr && exception->ContextRecord != nullptr) support_unwind(output, *exception->ContextRecord);
    support_line(output, "capture=complete\n"); FlushFileBuffers(output); CloseHandle(output);
}
inline void support_breadcrumb(std::uint64_t frames, std::uint64_t retraces, std::uint64_t polls) noexcept {
    static ULONGLONG last = 0, origin = GetTickCount64();
    static unsigned cursor = 0, count = 0;
    static char ring[60][128]{};
    const ULONGLONG now = GetTickCount64();
    if (now - last < 1000) return; last = now;
    wchar_t enabled[32768]{}; if (!support_sibling(L"breadcrumbs.log", enabled)) return;
    std::snprintf(ring[cursor], sizeof(ring[cursor]), "breadcrumb=%llu/%llu/%llu/%llu\n",
        static_cast<unsigned long long>(now - origin), static_cast<unsigned long long>(frames),
        static_cast<unsigned long long>(retraces), static_cast<unsigned long long>(polls));
    cursor = (cursor + 1) % 60; if (count < 60) ++count;
    HANDLE output = support_file(L"breadcrumbs.log"); if (output == INVALID_HANDLE_VALUE) return;
    for (unsigned i = 0; i < count; ++i) support_line(output, ring[(cursor + 60 - count + i) % 60]);
    CloseHandle(output);
}
} // namespace jfg
#else
namespace jfg { inline void support_breadcrumb(unsigned long long, unsigned long long, unsigned long long) noexcept {} }
#endif
