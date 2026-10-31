#include "jfg/evidence/g2_trap_probe_runtime.hpp"

#include <array>
#include <atomic>
#include <cstddef>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <thread>

#if JFG_G2_TRAP_PROBE_LINUX
#include <cerrno>
#include <csignal>
#include <fcntl.h>
#include <linux/seccomp.h>
#include <sys/syscall.h>
#include <sys/time.h>
#include <sys/wait.h>
#include <sys/prctl.h>
#include <unistd.h>
#endif

namespace trap = jfg::evidence::trap_probe;

namespace {

#if JFG_G2_TRAP_PROBE_LINUX
inline constexpr std::uint32_t kFunctionalDeadlineMilliseconds = 2000U;
inline constexpr std::uint32_t kTimeoutDeadlineMilliseconds = 250U;
// The escape probe forks a sandboxed child that performs several syscalls and
// a pipe write before returning. On a loaded CI runner that work can take far
// longer in wall-clock time than on a quiet machine, and the functional
// deadline is a wall-clock limit; too tight a bound kills the child by
// deadline rather than by any security decision, which reads as a spurious
// escape failure. Give the escape child a generous deadline so only a real
// denial or a real escape — never scheduling pressure — decides the outcome.
inline constexpr std::uint32_t kEscapeDeadlineMilliseconds = 60000U;

[[nodiscard]] trap::RunOptions options(
    const bool allow_normal_return = false,
    const std::uint32_t deadline_milliseconds = kFunctionalDeadlineMilliseconds
) {
    trap::RunOptions value{};
    value.deadline_milliseconds = deadline_milliseconds;
    value.allow_normal_return = allow_normal_return;
    for (std::size_t index = 0; index < value.candidate_token.size(); ++index) {
        value.candidate_token[index] = static_cast<std::byte>(index + 1U);
    }
    return value;
}

[[nodiscard]] trap::RunOptions timeout_options() {
    return options(false, kTimeoutDeadlineMilliseconds);
}

void trigger_reserved(void*) {
    reserved_instruction(nullptr, nullptr, 0U, 0U);
}

void trigger_syscall(void*) {
    recomp_syscall_handler(nullptr, nullptr, 0);
}

void trigger_break(void*) {
    do_break(0U);
}

void trigger_switch(void*) {
    switch_error(nullptr, 0U, 0U);
}

void return_normally(void*) {}

void do_not_return(void*) {
    for (;;) {
        (void)pause();
    }
}

struct DuplicateContext final {
    trap::TrapProbeEvent event;
};

struct EventSequenceContext final {
    std::array<trap::TrapProbeEvent, 2U> events;
};

void write_event_or_exit(const trap::TrapProbeEvent& event) {
    const ssize_t written = write(
        trap::configured_event_fd_for_test(),
        &event,
        sizeof(event)
    );
    if (written != static_cast<ssize_t>(sizeof(event))) {
        _exit(126);
    }
}

void emit_duplicate_then_break(void* const opaque) {
    const auto* const context = static_cast<const DuplicateContext*>(opaque);
    write_event_or_exit(context->event);
    do_break(0U);
}

void emit_forged_then_return(void* const opaque) {
    const auto* const context = static_cast<const DuplicateContext*>(opaque);
    write_event_or_exit(context->event);
}

void emit_forged_then_abort(void* const opaque) {
    const auto* const context = static_cast<const DuplicateContext*>(opaque);
    write_event_or_exit(context->event);
    std::abort();
}

void exceed_event_cap_then_abort(void* const opaque) {
    const auto* const context = static_cast<const EventSequenceContext*>(opaque);
    write_event_or_exit(context->events[0]);
    write_event_or_exit(context->events[1]);
    std::abort();
}

struct EscapeContext final {
    int report_fd = -1;
};

struct EscapeReport final {
    std::array<int, 4U> results{};
    std::array<int, 4U> errors{};
    int seccomp_mode = 0;
};

void attempt_escape_then_return(void* const opaque) {
    const auto* const context = static_cast<const EscapeContext*>(opaque);
    EscapeReport report{};
    report.seccomp_mode = prctl(PR_GET_SECCOMP);
#ifdef __NR_clone
    report.results[0] = static_cast<int>(syscall(__NR_clone, 0U, nullptr, nullptr, nullptr, 0U));
#else
    report.results[0] = static_cast<int>(fork());
#endif
    report.errors[0] = errno;
    report.results[1] = static_cast<int>(setsid());
    report.errors[1] = errno;
    report.results[2] = setpgid(0, 0);
    report.errors[2] = errno;
#ifdef __NR_unshare
    report.results[3] = static_cast<int>(syscall(__NR_unshare, 0U));
    report.errors[3] = errno;
#else
    report.results[3] = -1;
    report.errors[3] = EPERM;
#endif
    // Each operation is made independently to ensure a denial does not stop
    // the callback before exercising the remaining escape paths.
    if (write(context->report_fd, &report, sizeof(report)) != static_cast<ssize_t>(sizeof(report))) {
        _exit(127);
    }
}

volatile std::sig_atomic_t g_signal_interruptions = 0;

extern "C" void interrupt_probe_wait(const int) {
    g_signal_interruptions = 1;
}

void claim_once(std::atomic<unsigned int>* const claimed) {
    if (trap::claim_event_emission_for_test()) {
        claimed->fetch_add(1U, std::memory_order_relaxed);
    }
}

[[nodiscard]] bool observed(
    const trap::Callback callback,
    const trap::TrapKind kind,
    const char* const label
) {
    const trap::RunResult result = trap::run_isolated(callback, nullptr, options());
    const bool success = result.outcome == trap::RunOutcome::kObservedFatal && result.event.kind == kind &&
                         result.event.disposition == trap::TrapDisposition::kFatalAbort;
    if (!success) {
        std::fprintf(
            stderr,
            "%s trap observation failed: outcome=%u child_status=%d\n",
            label,
            static_cast<unsigned int>(result.outcome),
            result.child_status
        );
    }
    return success;
}
#endif

} // namespace

namespace {
[[nodiscard]] int fail_step(const int code) {
    std::fprintf(stderr, "trap runtime test failed at step %d\n", code);
    return code;
}
}  // namespace

int main() {
#if !JFG_G2_TRAP_PROBE_LINUX
    trap::RunOptions unavailable_options{};
    if (trap::configure_event_fd(0, unavailable_options.candidate_token) ||
        trap::configured_event_fd_for_test() != -1 ||
        trap::run_isolated(nullptr, nullptr, unavailable_options).outcome != trap::RunOutcome::kUnavailable) {
        return fail_step(10);
    }
    return 0;
#else
    if (!observed(trigger_reserved, trap::TrapKind::kReservedInstruction, "reserved") ||
        !observed(trigger_syscall, trap::TrapKind::kSyscall, "syscall") ||
        !observed(trigger_break, trap::TrapKind::kDoBreak, "break") ||
        !observed(trigger_switch, trap::TrapKind::kSwitchError, "switch")) {
        return fail_step(1);
    }

    const trap::RunResult timed_out = trap::run_isolated(do_not_return, nullptr, timeout_options());
    if (trap::run_isolated(return_normally, nullptr, options()).outcome != trap::RunOutcome::kUnexpectedReturn ||
        trap::run_isolated(return_normally, nullptr, options(true)).outcome != trap::RunOutcome::kNormalReturn ||
        timed_out.outcome != trap::RunOutcome::kTimeout ||
        !WIFSIGNALED(timed_out.child_status) || WTERMSIG(timed_out.child_status) != SIGKILL) {
        return fail_step(2);
    }

    const trap::RunOptions duplicate_options = options();
    const DuplicateContext duplicate{{
        trap::kEventMagic,
        trap::kEventVersion,
        trap::TrapKind::kDoBreak,
        trap::TrapDisposition::kFatalAbort,
        duplicate_options.candidate_token,
        {},
    }};
    if (trap::run_isolated(emit_duplicate_then_break, const_cast<DuplicateContext*>(&duplicate), duplicate_options).outcome !=
        trap::RunOutcome::kProtocolFailure) {
        return fail_step(3);
    }

    const DuplicateContext forged{duplicate};
    if (trap::run_isolated(emit_forged_then_return, const_cast<DuplicateContext*>(&forged), duplicate_options).outcome !=
        trap::RunOutcome::kProtocolFailure) {
        return fail_step(4);
    }

    if (trap::run_isolated(emit_forged_then_abort, const_cast<DuplicateContext*>(&forged), duplicate_options).outcome !=
        trap::RunOutcome::kProtocolFailure) {
        return fail_step(8);
    }

    const trap::RunResult no_event_abort = trap::run_isolated([](void*) { std::abort(); }, nullptr, duplicate_options);
    if (no_event_abort.outcome != trap::RunOutcome::kUnexpectedTermination) {
        return fail_step(11);
    }

    const EventSequenceContext over_cap{{duplicate.event, duplicate.event}};
    if (trap::run_isolated(exceed_event_cap_then_abort, const_cast<EventSequenceContext*>(&over_cap), duplicate_options).outcome !=
        trap::RunOutcome::kProtocolFailure) {
        return fail_step(5);
    }

    trap::set_clock_successes_before_failure_for_test(1);
    const trap::RunResult clock_failed = trap::run_isolated(do_not_return, nullptr, options());
    trap::set_clock_successes_before_failure_for_test(-1);
    if (clock_failed.outcome != trap::RunOutcome::kSetupFailure || !WIFSIGNALED(clock_failed.child_status) ||
        WTERMSIG(clock_failed.child_status) != SIGKILL) {
        return fail_step(9);
    }

    trap::reset_event_emission_for_test();
    std::atomic<unsigned int> claims{0U};
    std::array<std::thread, 16U> claimers{};
    for (std::thread& claimer : claimers) {
        claimer = std::thread(claim_once, &claims);
    }
    for (std::thread& claimer : claimers) {
        claimer.join();
    }
    if (claims.load(std::memory_order_relaxed) != 1U || trap::claim_event_emission_for_test()) {
        return fail_step(12);
    }

    int escape_pipe[2]{-1, -1};
    if (pipe(escape_pipe) != 0) {
        return fail_step(13);
    }
    EscapeContext escape_context{escape_pipe[1]};
    const trap::RunResult escape_result = trap::run_isolated(
        attempt_escape_then_return,
        &escape_context,
        options(true, kEscapeDeadlineMilliseconds)
    );
    (void)close(escape_pipe[1]);
    EscapeReport escape_report{};
    const ssize_t report_bytes = read(escape_pipe[0], &escape_report, sizeof(escape_report));
    (void)close(escape_pipe[0]);
    if (report_bytes != static_cast<ssize_t>(sizeof(escape_report)) ||
        escape_result.outcome != trap::RunOutcome::kNormalReturn) {
        std::fprintf(
            stderr,
            "escape probe: report_bytes=%zd outcome=%u child_status=%d\n",
            static_cast<ssize_t>(report_bytes),
            static_cast<unsigned int>(escape_result.outcome),
            escape_result.child_status
        );
        return fail_step(14);
    }
    if (escape_report.seccomp_mode != SECCOMP_MODE_FILTER) {
        return fail_step(15);
    }
    for (const std::size_t index : {0U, 1U, 2U, 3U}) {
        if (escape_report.results[index] != -1) {
            return static_cast<int>(16U + index);
        }
        if (escape_report.errors[index] != EPERM) {
            return static_cast<int>(21U + index);
        }
    }

    struct sigaction action{};
    action.sa_handler = interrupt_probe_wait;
    sigemptyset(&action.sa_mask);
    struct sigaction prior_action{};
    if (sigaction(SIGALRM, &action, &prior_action) != 0) {
        return fail_step(16);
    }
    itimerval interval{};
    interval.it_value = {0, 1000};
    interval.it_interval = {0, 1000};
    g_signal_interruptions = 0;
    if (setitimer(ITIMER_REAL, &interval, nullptr) != 0) {
        (void)sigaction(SIGALRM, &prior_action, nullptr);
        return fail_step(17);
    }
    const trap::RunResult interrupted_timeout = trap::run_isolated(do_not_return, nullptr, timeout_options());
    const itimerval disabled{};
    (void)setitimer(ITIMER_REAL, &disabled, nullptr);
    (void)sigaction(SIGALRM, &prior_action, nullptr);
    if (g_signal_interruptions == 0 || interrupted_timeout.outcome != trap::RunOutcome::kTimeout ||
        !WIFSIGNALED(interrupted_timeout.child_status) || WTERMSIG(interrupted_timeout.child_status) != SIGKILL) {
        return fail_step(15);
    }

    int descriptors[2]{-1, -1};
    if (pipe(descriptors) != 0 || trap::configure_event_fd(-1, duplicate_options.candidate_token) ||
        trap::configure_event_fd(descriptors[1], duplicate_options.candidate_token)) {
        if (descriptors[0] >= 0) { (void)close(descriptors[0]); }
        if (descriptors[1] >= 0) { (void)close(descriptors[1]); }
        return fail_step(18);
    }
    const int flags = fcntl(descriptors[1], F_GETFL);
    if (flags < 0 || fcntl(descriptors[1], F_SETFL, flags | O_NONBLOCK) != 0 ||
        !trap::configure_event_fd(descriptors[1], duplicate_options.candidate_token) ||
        trap::configured_event_fd_for_test() != descriptors[1]) {
        trap::clear_event_fd();
        (void)close(descriptors[0]);
        (void)close(descriptors[1]);
        return fail_step(19);
    }
    trap::clear_event_fd();
    (void)close(descriptors[0]);
    (void)close(descriptors[1]);
    return 0;
#endif
}
