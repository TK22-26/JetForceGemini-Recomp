#include "jfg/evidence/g2_trap_probe_runtime.hpp"

#include <chrono>
#include <cstdio>
#include <cstdlib>
#include <thread>

using jfg::evidence::trap_probe::Callback;
using jfg::evidence::trap_probe::RunOptions;
using jfg::evidence::trap_probe::RunResult;

extern "C" RunResult phase4_real_run_isolated(
    Callback callback, void* context, const RunOptions& options) noexcept
    asm("__real__ZN3jfg8evidence10trap_probe12run_isolatedEPFvPvES2_RKNS1_10RunOptionsE");

extern "C" RunResult phase4_wrap_run_isolated(
    Callback callback, void* context, const RunOptions& options) noexcept
    asm("__wrap__ZN3jfg8evidence10trap_probe12run_isolatedEPFvPvES2_RKNS1_10RunOptionsE");

extern "C" RunResult phase4_wrap_run_isolated(
    Callback callback, void* context, const RunOptions& options) noexcept {
    const RunResult result = phase4_real_run_isolated(callback, context, options);
    if (const char* const delay_text = std::getenv("JFG_PHASE4_TRACE_DELAY_MS")) {
        const long delay = std::strtol(delay_text, nullptr, 10);
        if (delay > 0) {
            std::this_thread::sleep_for(std::chrono::milliseconds(delay));
        }
    }
    std::fprintf(
        stderr,
        "phase4 probe: deadline=%u outcome=%u status=%d\n",
        options.deadline_milliseconds,
        static_cast<unsigned int>(result.outcome),
        result.child_status);
    return result;
}
