#pragma once

#include <array>
#include <cstddef>
#include <cstdint>

// This bridge is deliberately separate from minimal_runtime.cpp.  A private
// generated-code probe can link this implementation in its place, but never
// alongside it: both implementations export the generated ABI trap symbols.
#if defined(__unix__) || defined(__APPLE__)
#define JFG_G2_TRAP_PROBE_POSIX 1
#else
#define JFG_G2_TRAP_PROBE_POSIX 0
#endif

// Authenticated sender credentials are a prerequisite for a passing probe.
// Linux supplies them for AF_UNIX datagrams through SO_PASSCRED/SCM_CREDENTIALS.
// The Linux child also installs a fail-closed no_new_privs seccomp filter before
// the callback, rejecting process/thread creation and process-group/session
// escape. Other platforms deliberately report the mechanism as unavailable
// rather than treating an inherited descriptor as proof of the direct child's
// identity.
#if defined(__linux__)
#define JFG_G2_TRAP_PROBE_LINUX 1
#else
#define JFG_G2_TRAP_PROBE_LINUX 0
#endif

struct recomp_context;

namespace jfg::evidence::trap_probe {

inline constexpr std::size_t kCandidateTokenBytes = 32U;
inline constexpr std::size_t kRunProofBytes = 16U;
inline constexpr std::uint32_t kEventMagic = 0x4A465450U; // "JFTP"
inline constexpr std::uint16_t kEventVersion = 1U;

enum class TrapKind : std::uint16_t {
    kReservedInstruction = 1U,
    kSyscall = 2U,
    kDoBreak = 3U,
    kSwitchError = 4U,
};

enum class TrapDisposition : std::uint32_t {
    kFatalAbort = 1U,
};

// The event is intentionally fixed-size and contains no guest address,
// generated symbol, callback path, diagnostic string, or ROM-derived bytes.
struct TrapProbeEvent final {
    std::uint32_t magic;
    std::uint16_t version;
    TrapKind kind;
    TrapDisposition disposition;
    std::array<std::byte, kCandidateTokenBytes> candidate_token;
    // Generated privately by run_isolated.  It is deliberately not accepted
    // from RunOptions, so an ordinary probe callback has no capability to
    // synthesize a passing fatal event.
    std::array<std::byte, kRunProofBytes> run_proof;
};
static_assert(sizeof(TrapProbeEvent) == 60U);

using CandidateToken = std::array<std::byte, kCandidateTokenBytes>;
using Callback = void (*)(void*);

enum class RunOutcome : std::uint8_t {
    kObservedFatal,
    kNormalReturn,
    kUnexpectedReturn,
    kTimeout,
    kProtocolFailure,
    kUnexpectedTermination,
    kSetupFailure,
    kUnavailable,
};

struct RunOptions final {
    std::uint32_t deadline_milliseconds = 1000U;
    bool allow_normal_return = false;
    CandidateToken candidate_token{};
};

struct RunResult final {
    RunOutcome outcome = RunOutcome::kSetupFailure;
    TrapProbeEvent event{};
    int child_status = 0;
};

#if defined(JFG_G2_TRAP_PROBE_TESTING)
// Test-only fault injection.  These declarations are absent from production
// builds so a normal probe callback cannot obtain the event descriptor or
// control the parent clock.
    [[nodiscard]] bool configure_event_fd(int event_fd, const CandidateToken& token) noexcept;
    void clear_event_fd() noexcept;
    [[nodiscard]] int configured_event_fd_for_test() noexcept;
    [[nodiscard]] bool claim_event_emission_for_test() noexcept;
    void reset_event_emission_for_test() noexcept;
    void set_clock_successes_before_failure_for_test(int successes) noexcept;
#endif

// Producer contract: invoke this only from the single-threaded private
// evidence process. POSIX provides no race-free way for this library to prove
// that another host thread cannot appear between a pre-fork inspection and
// fork(), and executing a callback in a post-fork child of a multithreaded
// process is not safe. The caller must therefore establish single-threaded
// ownership before calling; this precondition is not evidence by itself.
[[nodiscard]] RunResult run_isolated(
    Callback callback,
    void* callback_context,
    const RunOptions& options = {}
) noexcept;

} // namespace jfg::evidence::trap_probe

extern "C" {

// Alternate recomp ABI bridge.  Link this translation unit instead of
// src/runtime/recomp_support/minimal_runtime.cpp for a private probe only.
void reserved_instruction(std::uint8_t* rdram, recomp_context* ctx, std::uint32_t vram, std::uint32_t word);
void switch_error(const char* func, std::uint32_t vram, std::uint32_t jtbl);
void do_break(std::uint32_t vram);
void recomp_syscall_handler(std::uint8_t* rdram, recomp_context* ctx, std::int32_t instruction_vram);

}
