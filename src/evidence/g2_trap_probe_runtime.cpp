#include "jfg/evidence/g2_trap_probe_runtime.hpp"

#include <atomic>
#include <cstddef>
#include <cstdlib>

#if JFG_G2_TRAP_PROBE_LINUX
#include <cerrno>
#include <csignal>
#include <cstring>

#include <dirent.h>

#include <fcntl.h>
#include <linux/audit.h>
#include <linux/filter.h>
#include <linux/seccomp.h>
#include <poll.h>
#include <sys/prctl.h>
#include <sys/random.h>
#include <sys/socket.h>
#include <sys/syscall.h>
#include <sys/types.h>
#include <sys/wait.h>
#include <time.h>
#include <unistd.h>
#endif

namespace jfg::evidence::trap_probe {

#if JFG_G2_TRAP_PROBE_LINUX
namespace {

int g_event_fd = -1;
CandidateToken g_candidate_token{};
std::array<std::byte, kRunProofBytes> g_run_proof{};
// atomic_flag is the one C++ atomic type guaranteed lock-free.  The bridge is
// not a signal handler, but this remains allocation-free and race-free when a
// callback creates concurrent threads that reach a trap bridge.
std::atomic_flag g_event_emitted = ATOMIC_FLAG_INIT;

#if defined(JFG_G2_TRAP_PROBE_TESTING)
int g_clock_successes_before_failure_for_test = -1;
#endif

[[nodiscard]] bool claim_event_emission() noexcept {
    return !g_event_emitted.test_and_set(std::memory_order_relaxed);
}

[[nodiscard]] bool emit_fatal_event(const TrapKind kind) noexcept {
    if (g_event_fd < 0 || !claim_event_emission()) {
        return false;
    }
    const TrapProbeEvent event{
        kEventMagic,
        kEventVersion,
        kind,
        TrapDisposition::kFatalAbort,
        g_candidate_token,
        g_run_proof,
    };
    // AF_UNIX SOCK_DGRAM preserves one fixed-size event per write.  The socket
    // is nonblocking, so a full queue fails closed instead of delaying abort.
    return write(g_event_fd, &event, sizeof(event)) == static_cast<ssize_t>(sizeof(event));
}

[[nodiscard]] bool descriptor_is_nonblocking(const int fd) noexcept {
    const int flags = fcntl(fd, F_GETFL);
    return flags >= 0 && (flags & O_NONBLOCK) != 0;
}

[[nodiscard]] bool set_nonblocking(const int fd) noexcept {
    const int flags = fcntl(fd, F_GETFL);
    return flags >= 0 && fcntl(fd, F_SETFL, flags | O_NONBLOCK) == 0;
}

[[nodiscard]] bool set_close_on_exec(const int fd) noexcept {
    const int flags = fcntl(fd, F_GETFD);
    return flags >= 0 && fcntl(fd, F_SETFD, flags | FD_CLOEXEC) == 0;
}

[[nodiscard]] bool monotonic_milliseconds(std::uint64_t& result) noexcept {
#if defined(JFG_G2_TRAP_PROBE_TESTING)
    if (g_clock_successes_before_failure_for_test == 0) {
        return false;
    }
    if (g_clock_successes_before_failure_for_test > 0) {
        --g_clock_successes_before_failure_for_test;
    }
#endif
    timespec value{};
    if (clock_gettime(CLOCK_MONOTONIC, &value) != 0) {
        return false;
    }
    result = static_cast<std::uint64_t>(value.tv_sec) * 1000U +
             static_cast<std::uint64_t>(value.tv_nsec / 1000000L);
    return true;
}

// Cleanup must retain a real monotonic deadline even when a test injects a
// failure into the probe's main deadline clock.
[[nodiscard]] bool cleanup_monotonic_milliseconds(std::uint64_t& result) noexcept {
    timespec value{};
    if (clock_gettime(CLOCK_MONOTONIC, &value) != 0) {
        return false;
    }
    result = static_cast<std::uint64_t>(value.tv_sec) * 1000U +
             static_cast<std::uint64_t>(value.tv_nsec / 1000000L);
    return true;
}

[[nodiscard]] bool deadline_from_now(
    const std::uint64_t duration_milliseconds,
    std::uint64_t& deadline
) noexcept {
    std::uint64_t now = 0U;
    if (!monotonic_milliseconds(now) || now > UINT64_MAX - duration_milliseconds) {
        return false;
    }
    deadline = now + duration_milliseconds;
    return true;
}

[[nodiscard]] bool single_threaded_caller() noexcept {
    // There is no portable race-free way to make fork safe in a process with
    // arbitrary host threads.  Linux exposes the best available preflight in
    // /proc: reject setup unless precisely one task exists now.  The public
    // API documents the remaining caller-side ownership requirement.
    DIR* const directory = opendir("/proc/self/task");
    if (directory == nullptr) {
        return false;
    }
    unsigned int tasks = 0U;
    bool valid = true;
    errno = 0;
    while (const dirent* const entry = readdir(directory)) {
        const char* name = entry->d_name;
        if (name[0] == '.') {
            continue;
        }
        for (const char* cursor = name; *cursor != '\0'; ++cursor) {
            if (*cursor < '0' || *cursor > '9') {
                valid = false;
                break;
            }
        }
        if (!valid || ++tasks > 1U) {
            valid = false;
            break;
        }
    }
    const int saved_errno = errno;
    if (closedir(directory) != 0) {
        return false;
    }
    return valid && saved_errno == 0 && tasks == 1U;
}

[[nodiscard]] bool fill_run_proof(std::array<std::byte, kRunProofBytes>& proof) noexcept {
#if defined(__APPLE__)
    arc4random_buf(proof.data(), proof.size());
    return true;
#elif defined(__linux__)
    auto* cursor = reinterpret_cast<unsigned char*>(proof.data());
    std::size_t remaining = proof.size();
    while (remaining != 0U) {
        const ssize_t count = getrandom(cursor, remaining, GRND_NONBLOCK);
        if (count > 0) {
            cursor += static_cast<std::size_t>(count);
            remaining -= static_cast<std::size_t>(count);
            continue;
        }
        if (count < 0 && errno == EINTR) {
            continue;
        }
        return false;
    }
    return true;
#else
    const int random_fd = open("/dev/urandom", O_RDONLY | O_CLOEXEC | O_NONBLOCK);
    if (random_fd < 0) {
        return false;
    }
    auto* cursor = reinterpret_cast<unsigned char*>(proof.data());
    std::size_t remaining = proof.size();
    bool success = true;
    while (remaining != 0U) {
        const ssize_t count = read(random_fd, cursor, remaining);
        if (count > 0) {
            cursor += static_cast<std::size_t>(count);
            remaining -= static_cast<std::size_t>(count);
            continue;
        }
        if (count < 0 && errno == EINTR) {
            continue;
        }
        success = false;
        break;
    }
    (void)close(random_fd);
    return success;
#endif
}

[[nodiscard]] bool event_is_valid(
    const TrapProbeEvent& event,
    const CandidateToken& token,
    const std::array<std::byte, kRunProofBytes>& run_proof
) noexcept {
    return event.magic == kEventMagic && event.version == kEventVersion &&
           event.disposition == TrapDisposition::kFatalAbort && event.candidate_token == token &&
           event.run_proof == run_proof &&
           (event.kind == TrapKind::kReservedInstruction || event.kind == TrapKind::kSyscall ||
            event.kind == TrapKind::kDoBreak || event.kind == TrapKind::kSwitchError);
}

[[nodiscard]] bool configure_event_fd_with_proof(
    const int event_fd,
    const CandidateToken& token,
    const std::array<std::byte, kRunProofBytes>& run_proof
) noexcept {
    if (event_fd < 0 || !descriptor_is_nonblocking(event_fd)) {
        return false;
    }
    g_event_fd = event_fd;
    g_candidate_token = token;
    g_run_proof = run_proof;
    g_event_emitted.clear(std::memory_order_relaxed);
    return true;
}

[[nodiscard]] bool direct_child_owns_event(
    msghdr& message,
    const pid_t direct_child
) noexcept {
    bool saw_credentials = false;
    for (cmsghdr* control = CMSG_FIRSTHDR(&message); control != nullptr;
         control = CMSG_NXTHDR(&message, control)) {
        if (control->cmsg_level != SOL_SOCKET || control->cmsg_type != SCM_CREDENTIALS ||
            control->cmsg_len != CMSG_LEN(sizeof(ucred)) || saw_credentials) {
            return false;
        }
        const auto* credentials = reinterpret_cast<const ucred*>(CMSG_DATA(control));
        if (credentials->pid != direct_child) {
            return false;
        }
        saw_credentials = true;
    }
    return saw_credentials;
}

enum class ReceiveResult : std::uint8_t {
    kNone,
    kEvent,
    kProtocolFailure,
};

[[nodiscard]] ReceiveResult receive_event(
    const int event_fd,
    const pid_t direct_child,
    TrapProbeEvent& event
) noexcept {
    std::array<std::byte, CMSG_SPACE(sizeof(ucred))> control{};
    iovec payload{&event, sizeof(event)};
    msghdr message{};
    message.msg_iov = &payload;
    message.msg_iovlen = 1U;
    message.msg_control = control.data();
    message.msg_controllen = control.size();
    const ssize_t received = recvmsg(event_fd, &message, MSG_DONTWAIT);
    if (received < 0 && (errno == EAGAIN || errno == EWOULDBLOCK)) {
        return ReceiveResult::kNone;
    }
    if (received < 0 && errno == EINTR) {
        return ReceiveResult::kNone;
    }
    if (received != static_cast<ssize_t>(sizeof(event)) ||
        (message.msg_flags & (MSG_TRUNC | MSG_CTRUNC)) != 0 ||
        !direct_child_owns_event(message, direct_child)) {
        return ReceiveResult::kProtocolFailure;
    }
    return ReceiveResult::kEvent;
}

inline constexpr std::uint64_t kCleanupDeadlineMilliseconds = 1000U;

[[nodiscard]] bool cleanup_deadline_from_now(std::uint64_t& deadline) noexcept {
    std::uint64_t now = 0U;
    if (!cleanup_monotonic_milliseconds(now) ||
        now > UINT64_MAX - kCleanupDeadlineMilliseconds) {
        return false;
    }
    deadline = now + kCleanupDeadlineMilliseconds;
    return true;
}

[[nodiscard]] bool sleep_briefly_until(const std::uint64_t deadline) noexcept {
    for (;;) {
        std::uint64_t now = 0U;
        if (!cleanup_monotonic_milliseconds(now) || now >= deadline) {
            return false;
        }
        const std::uint64_t remaining = deadline - now;
        const std::uint64_t pause_milliseconds = remaining > 10U ? 10U : remaining;
        timespec pause{
            static_cast<time_t>(pause_milliseconds / 1000U),
            static_cast<long>((pause_milliseconds % 1000U) * 1000000U),
        };
        if (nanosleep(&pause, nullptr) == 0) {
            return true;
        }
        if (errno != EINTR) {
            return false;
        }
        // The caller owns the absolute deadline.  Yield after every signal
        // interruption so it can recheck its condition (for example, a child
        // might already have exited) instead of repeatedly restarting this
        // relative pause until the deadline expires.
        std::uint64_t interrupted_now = 0U;
        if (!cleanup_monotonic_milliseconds(interrupted_now) || interrupted_now >= deadline) {
            return false;
        }
        return true;
    }
}

[[nodiscard]] bool reap_direct_child_bounded(const pid_t child, int& status) noexcept {
    std::uint64_t deadline = 0U;
    if (!cleanup_deadline_from_now(deadline)) {
        return false;
    }
    for (;;) {
        const pid_t waited = waitpid(child, &status, WNOHANG);
        if (waited == child) {
            return true;
        }
        if (waited < 0 && errno != EINTR) {
            return false;
        }
        if (!sleep_briefly_until(deadline)) {
            return false;
        }
    }
}

[[nodiscard]] bool process_group_is_gone_bounded(const pid_t group) noexcept {
    std::uint64_t deadline = 0U;
    if (!cleanup_deadline_from_now(deadline)) {
        return false;
    }
    for (;;) {
        if (kill(-group, 0) != 0 && errno == ESRCH) {
            return true;
        }
        if (!sleep_briefly_until(deadline)) {
            return false;
        }
    }
}

[[nodiscard]] bool install_callback_seccomp_policy() noexcept {
#if defined(__x86_64__)
    constexpr std::uint32_t expected_architecture = AUDIT_ARCH_X86_64;
#elif defined(__aarch64__)
    constexpr std::uint32_t expected_architecture = AUDIT_ARCH_AARCH64;
#elif defined(__i386__)
    constexpr std::uint32_t expected_architecture = AUDIT_ARCH_I386;
#else
    // This is an evidence boundary: do not run an unrestricted callback on an
    // architecture whose seccomp audit value was not reviewed here.
    return false;
#endif

    // This is deliberately only the small containment boundary the probe
    // requires, not a claim of general-purpose sandboxing. The callback needs
    // its normal generated-runtime ABI plus a direct credentialed datagram
    // send and abort, but cannot create descendants or leave the direct
    // child's process group/session. no_new_privs makes the filter
    // irrevocable, including across exec.
    static const sock_filter filter[] = {
        BPF_STMT(BPF_LD | BPF_W | BPF_ABS, offsetof(seccomp_data, arch)),
        BPF_JUMP(BPF_JMP | BPF_JEQ | BPF_K, expected_architecture, 1, 0),
        BPF_STMT(BPF_RET | BPF_K, SECCOMP_RET_KILL_PROCESS),
        BPF_STMT(BPF_LD | BPF_W | BPF_ABS, offsetof(seccomp_data, nr)),
#ifdef __NR_clone
        BPF_JUMP(BPF_JMP | BPF_JEQ | BPF_K, __NR_clone, 0, 1),
        BPF_STMT(BPF_RET | BPF_K, SECCOMP_RET_ERRNO | EPERM),
#endif
#ifdef __NR_clone3
        BPF_JUMP(BPF_JMP | BPF_JEQ | BPF_K, __NR_clone3, 0, 1),
        BPF_STMT(BPF_RET | BPF_K, SECCOMP_RET_ERRNO | EPERM),
#endif
#ifdef __NR_fork
        BPF_JUMP(BPF_JMP | BPF_JEQ | BPF_K, __NR_fork, 0, 1),
        BPF_STMT(BPF_RET | BPF_K, SECCOMP_RET_ERRNO | EPERM),
#endif
#ifdef __NR_vfork
        BPF_JUMP(BPF_JMP | BPF_JEQ | BPF_K, __NR_vfork, 0, 1),
        BPF_STMT(BPF_RET | BPF_K, SECCOMP_RET_ERRNO | EPERM),
#endif
#ifdef __NR_setsid
        BPF_JUMP(BPF_JMP | BPF_JEQ | BPF_K, __NR_setsid, 0, 1),
        BPF_STMT(BPF_RET | BPF_K, SECCOMP_RET_ERRNO | EPERM),
#endif
#ifdef __NR_setpgid
        BPF_JUMP(BPF_JMP | BPF_JEQ | BPF_K, __NR_setpgid, 0, 1),
        BPF_STMT(BPF_RET | BPF_K, SECCOMP_RET_ERRNO | EPERM),
#endif
#ifdef __NR_unshare
        BPF_JUMP(BPF_JMP | BPF_JEQ | BPF_K, __NR_unshare, 0, 1),
        BPF_STMT(BPF_RET | BPF_K, SECCOMP_RET_ERRNO | EPERM),
#endif
        BPF_STMT(BPF_RET | BPF_K, SECCOMP_RET_ALLOW),
    };
    const sock_fprog program{
        static_cast<unsigned short>(sizeof(filter) / sizeof(filter[0])),
        const_cast<sock_filter*>(filter),
    };
    return prctl(PR_SET_NO_NEW_PRIVS, 1, 0, 0, 0) == 0 &&
           prctl(PR_SET_SECCOMP, SECCOMP_MODE_FILTER, &program) == 0;
}

[[nodiscard]] bool terminate_and_reap_group(
    const pid_t child,
    int& status,
    bool& direct_child_reaped
) noexcept {
    if (kill(-child, SIGKILL) != 0 && errno != ESRCH) {
        return false;
    }
    if (!direct_child_reaped) {
        if (!reap_direct_child_bounded(child, status)) {
            return false;
        }
        direct_child_reaped = true;
    }
    return process_group_is_gone_bounded(child);
}

[[nodiscard]] bool terminate_and_reap_unconfigured_child(const pid_t child, int& status) noexcept {
    if (kill(child, SIGKILL) != 0 && errno != ESRCH) {
        return false;
    }
    return reap_direct_child_bounded(child, status);
}

} // namespace
#endif

// Only test builds expose manual configuration.  Production setup is private
// to run_isolated so a callback cannot replace its per-run proof.
#if defined(JFG_G2_TRAP_PROBE_TESTING)
bool configure_event_fd(const int event_fd, const CandidateToken& token) noexcept {
#if JFG_G2_TRAP_PROBE_LINUX
    return configure_event_fd_with_proof(event_fd, token, {});
#else
    (void)event_fd;
    (void)token;
    return false;
#endif
}

void clear_event_fd() noexcept {
#if JFG_G2_TRAP_PROBE_LINUX
    g_event_fd = -1;
    g_candidate_token = {};
    g_run_proof = {};
    g_event_emitted.clear(std::memory_order_relaxed);
#endif
}

int configured_event_fd_for_test() noexcept {
#if JFG_G2_TRAP_PROBE_LINUX
    return g_event_fd;
#else
    return -1;
#endif
}

bool claim_event_emission_for_test() noexcept {
#if JFG_G2_TRAP_PROBE_LINUX
    return claim_event_emission();
#else
    return false;
#endif
}

void reset_event_emission_for_test() noexcept {
#if JFG_G2_TRAP_PROBE_LINUX
    g_event_emitted.clear(std::memory_order_relaxed);
#endif
}

void set_clock_successes_before_failure_for_test(const int successes) noexcept {
#if JFG_G2_TRAP_PROBE_LINUX
    g_clock_successes_before_failure_for_test = successes;
#else
    (void)successes;
#endif
}
#endif

RunResult run_isolated(
    const Callback callback,
    void* const callback_context,
    const RunOptions& options
) noexcept {
    RunResult result{};
#if !JFG_G2_TRAP_PROBE_LINUX
    (void)callback;
    (void)callback_context;
    (void)options;
    result.outcome = RunOutcome::kUnavailable;
    return result;
#else
    if (callback == nullptr || options.deadline_milliseconds == 0U || !single_threaded_caller()) {
        return result;
    }
    std::array<std::byte, kRunProofBytes> run_proof{};
    if (!fill_run_proof(run_proof)) {
        return result;
    }
    int fds[2]{-1, -1};
    int pass_credentials = 1;
    if (socketpair(AF_UNIX, SOCK_DGRAM, 0, fds) != 0 ||
        setsockopt(fds[0], SOL_SOCKET, SO_PASSCRED, &pass_credentials, sizeof(pass_credentials)) != 0 ||
        !set_nonblocking(fds[0]) || !set_nonblocking(fds[1]) ||
        !set_close_on_exec(fds[0]) || !set_close_on_exec(fds[1])) {
        if (fds[0] >= 0) { (void)close(fds[0]); }
        if (fds[1] >= 0) { (void)close(fds[1]); }
        return result;
    }
    const pid_t child = fork();
    if (child < 0) {
        (void)close(fds[0]);
        (void)close(fds[1]);
        return result;
    }
    if (child == 0) {
        if (setpgid(0, 0) != 0) {
            _exit(124);
        }
        (void)close(fds[0]);
        if (!configure_event_fd_with_proof(fds[1], options.candidate_token, run_proof)) {
            _exit(125);
        }
        if (!install_callback_seccomp_policy()) {
            // An unrestricted probe callback is never an acceptable fallback:
            // setup failure must be distinguishable from an observed trap.
            _exit(126);
        }
        callback(callback_context);
        _exit(0);
    }

    (void)close(fds[1]);
    // Both parent and child request this process group.  Do not run an
    // ungrouped callback: group termination is what prevents descendants from
    // outliving a failed, timed-out, or normally-returning probe.
    (void)setpgid(child, child);
    if (getpgid(child) != child) {
        (void)terminate_and_reap_unconfigured_child(child, result.child_status);
        (void)close(fds[0]);
        return result;
    }

    bool direct_child_reaped = false;
    bool received_event = false;
    TrapProbeEvent received{};
    auto terminate = [&](const RunOutcome requested) noexcept -> RunResult {
        if (!terminate_and_reap_group(child, result.child_status, direct_child_reaped)) {
            result.outcome = RunOutcome::kSetupFailure;
        } else {
            result.outcome = requested;
        }
        (void)close(fds[0]);
        return result;
    };
    std::uint64_t deadline = 0U;
    if (!deadline_from_now(options.deadline_milliseconds, deadline)) {
        return terminate(RunOutcome::kSetupFailure);
    }
    while (!direct_child_reaped) {
        for (;;) {
            TrapProbeEvent event{};
            const ReceiveResult receive_result = receive_event(fds[0], child, event);
            if (receive_result == ReceiveResult::kNone) {
                break;
            }
            if (receive_result == ReceiveResult::kProtocolFailure || received_event) {
                return terminate(RunOutcome::kProtocolFailure);
            }
            received = event;
            received_event = true;
            // A second queued datagram is rejected on the next iteration.
            if (received_event) {
                continue;
            }
        }

        const pid_t waited = waitpid(child, &result.child_status, WNOHANG);
        if (waited == child) {
            direct_child_reaped = true;
            break;
        }
        if (waited < 0 && errno != EINTR) {
            return terminate(RunOutcome::kSetupFailure);
        }
        std::uint64_t now = 0U;
        if (!monotonic_milliseconds(now)) {
            return terminate(RunOutcome::kSetupFailure);
        }
        if (now >= deadline) {
            return terminate(RunOutcome::kTimeout);
        }
        const std::uint64_t remaining = deadline - now;
        pollfd descriptor{fds[0], POLLIN | POLLHUP, 0};
        const int poll_result = poll(&descriptor, 1U, static_cast<int>(remaining > 50U ? 50U : remaining));
        if (poll_result < 0 && errno != EINTR) {
            return terminate(RunOutcome::kSetupFailure);
        }
    }

    for (;;) {
        TrapProbeEvent event{};
        const ReceiveResult receive_result = receive_event(fds[0], child, event);
        if (receive_result == ReceiveResult::kNone) {
            break;
        }
        if (receive_result == ReceiveResult::kProtocolFailure || received_event) {
            return terminate(RunOutcome::kProtocolFailure);
        }
        received = event;
        received_event = true;
        if (received_event) {
            continue;
        }
    }
    if (!terminate_and_reap_group(child, result.child_status, direct_child_reaped)) {
        (void)close(fds[0]);
        result.outcome = RunOutcome::kSetupFailure;
        return result;
    }
    (void)close(fds[0]);

    if (received_event) {
        result.event = received;
        if (!event_is_valid(result.event, options.candidate_token, run_proof)) {
            result.outcome = RunOutcome::kProtocolFailure;
            return result;
        }
    }
    if (WIFSIGNALED(result.child_status)) {
        if (WTERMSIG(result.child_status) == SIGABRT && received_event) {
            result.outcome = RunOutcome::kObservedFatal;
        } else {
            result.outcome = RunOutcome::kUnexpectedTermination;
        }
        return result;
    }
    if (WIFEXITED(result.child_status) && WEXITSTATUS(result.child_status) == 0) {
        if (received_event) {
            // A fatal event without the matching fatal termination is never a
            // successful observation.  Treat it as a malformed protocol,
            // rather than permitting a callback to forge a passing event.
            result.outcome = RunOutcome::kProtocolFailure;
        } else {
            result.outcome = options.allow_normal_return ? RunOutcome::kNormalReturn : RunOutcome::kUnexpectedReturn;
        }
        return result;
    }
    result.outcome = RunOutcome::kUnexpectedTermination;
    return result;
#endif
}

#if JFG_G2_TRAP_PROBE_LINUX
[[noreturn]] void report_fatal_bridge(const TrapKind kind) noexcept {
    (void)emit_fatal_event(kind);
    std::abort();
}
#else
[[noreturn]] void report_fatal_bridge(const TrapKind kind) noexcept {
    (void)kind;
    std::abort();
}
#endif

} // namespace jfg::evidence::trap_probe

extern "C" {

void reserved_instruction(std::uint8_t* const rdram, recomp_context* const ctx, const std::uint32_t vram, const std::uint32_t word) {
    (void)rdram;
    (void)ctx;
    (void)vram;
    (void)word;
    jfg::evidence::trap_probe::report_fatal_bridge(jfg::evidence::trap_probe::TrapKind::kReservedInstruction);
}

void switch_error(const char* const func, const std::uint32_t vram, const std::uint32_t jtbl) {
    (void)func;
    (void)vram;
    (void)jtbl;
    jfg::evidence::trap_probe::report_fatal_bridge(jfg::evidence::trap_probe::TrapKind::kSwitchError);
}

void do_break(const std::uint32_t vram) {
    (void)vram;
    jfg::evidence::trap_probe::report_fatal_bridge(jfg::evidence::trap_probe::TrapKind::kDoBreak);
}

void recomp_syscall_handler(std::uint8_t* const rdram, recomp_context* const ctx, const std::int32_t instruction_vram) {
    (void)rdram;
    (void)ctx;
    (void)instruction_vram;
    jfg::evidence::trap_probe::report_fatal_bridge(jfg::evidence::trap_probe::TrapKind::kSyscall);
}

} // extern "C"
