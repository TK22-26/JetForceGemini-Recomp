#include "jfg/evidence/g2_trap_probe_runtime.hpp"

#include <csetjmp>
#include <csignal>
#include <cstdio>

using jfg::evidence::trap_probe::Callback;
using jfg::evidence::trap_probe::RunOptions;
using jfg::evidence::trap_probe::RunOutcome;
using jfg::evidence::trap_probe::RunResult;

namespace {

sigjmp_buf g_probe_jump;
volatile sig_atomic_t g_probe_signal = 0;
void* g_probe_address = nullptr;

void phase4_probe_signal(
    const int signal_number,
    siginfo_t* const information,
    void*) noexcept {
    g_probe_signal = signal_number;
    g_probe_address = information == nullptr ? nullptr : information->si_addr;
    siglongjmp(g_probe_jump, 1);
}

}  // namespace

extern "C" RunResult phase4_direct_run_isolated(
    Callback callback, void* context, const RunOptions&) noexcept
    asm("__wrap__ZN3jfg8evidence10trap_probe12run_isolatedEPFvPvES2_RKNS1_10RunOptionsE");

extern "C" RunResult phase4_direct_run_isolated(
    Callback callback, void* context, const RunOptions&) noexcept {
    const auto* const invocation_bytes = static_cast<const unsigned char*>(context);
    void* const rdram = context == nullptr
        ? nullptr
        : *reinterpret_cast<void* const*>(invocation_bytes + 2U * sizeof(void*));
    struct sigaction action {};
    action.sa_sigaction = phase4_probe_signal;
    action.sa_flags = SA_SIGINFO;
    sigemptyset(&action.sa_mask);
    struct sigaction old_segv {};
    struct sigaction old_bus {};
    struct sigaction old_ill {};
    struct sigaction old_abrt {};
    (void)sigaction(SIGSEGV, &action, &old_segv);
    (void)sigaction(SIGBUS, &action, &old_bus);
    (void)sigaction(SIGILL, &action, &old_ill);
    (void)sigaction(SIGABRT, &action, &old_abrt);
    g_probe_signal = 0;
    g_probe_address = nullptr;
    RunResult result{};
    if (sigsetjmp(g_probe_jump, 1) == 0) {
        callback(context);
        result.outcome = RunOutcome::kNormalReturn;
        result.child_status = 0;
    } else {
        std::fprintf(
            stderr,
            "phase4 direct probe: signal=%d address=%p rdram=%p delta=%lld\n",
            static_cast<int>(g_probe_signal),
            g_probe_address,
            rdram,
            static_cast<long long>(
                static_cast<const unsigned char*>(g_probe_address) -
                static_cast<const unsigned char*>(rdram)));
        result.outcome = RunOutcome::kUnexpectedTermination;
        result.child_status = static_cast<int>(g_probe_signal);
    }
    (void)sigaction(SIGSEGV, &old_segv, nullptr);
    (void)sigaction(SIGBUS, &old_bus, nullptr);
    (void)sigaction(SIGILL, &old_ill, nullptr);
    (void)sigaction(SIGABRT, &old_abrt, nullptr);
    return result;
}
