#include "jfg/runtime/support_snapshot.hpp"
#include <cstdlib>

LONG WINAPI fixture_crash(EXCEPTION_POINTERS *exception) {
    jfg::support_crash(exception); ExitProcess(17);
}
__declspec(noinline) void crash_leaf() { volatile int *bad = nullptr; *bad = 1; }
__declspec(noinline) void crash_parent() { crash_leaf(); volatile int keep = 1; (void)keep; }
int wmain(int argc, wchar_t **argv) {
    SetErrorMode(SEM_FAILCRITICALERRORS | SEM_NOGPFAULTERRORBOX);
    if (argc == 2 && std::wcscmp(argv[1], L"crash") == 0) {
        SetUnhandledExceptionFilter(fixture_crash); crash_parent(); return 1;
    }
    // A blocked worker plus a main thread that keeps writing a heartbeat proves
    // the capture collected thread stacks and did not leave the process suspended.
    if (argc == 2 && std::wcscmp(argv[1], L"hang") == 0) {
        for (unsigned i = 0; i < 300; ++i) { jfg::support_breadcrumb(i, i, i); std::puts("alive"); std::fflush(stdout); Sleep(100); }
        return 0;
    }
    return 64;
}
