#pragma once

#include <cstddef>
#include <cstdint>
#include <memory>
#include <mutex>
#include <span>

namespace jfg {

inline constexpr std::size_t kMaximumAudioActiveProgramBytes = 4096U;
inline constexpr std::size_t kMaximumAudioProgramDataBytes = 4096U;
inline constexpr std::size_t kMaximumAudioCommandStreamBytes = 1024U * 1024U;
inline constexpr std::size_t kMaximumAudioOutputBytes = 1024U * 1024U;
inline constexpr std::size_t kMaximumAudioReferencedRegionBytes =
    8U * 1024U * 1024U;
inline constexpr std::size_t kMaximumAudioReferencedRegionCount = 32U;
inline constexpr std::size_t kMaximumAudioReferencedBytes =
    16U * 1024U * 1024U;
inline constexpr std::size_t kMaximumAudioMemoryOperationCount = 1024U * 1024U;
inline constexpr std::size_t kMaximumAudioMemoryTrafficBytes =
    64U * 1024U * 1024U;
inline constexpr std::size_t kAudioInstructionAlignmentBytes = 4U;
inline constexpr std::size_t kAudioCommandAlignmentBytes = 8U;
inline constexpr std::size_t kAudioOutputFrameBytes = 4U;
inline constexpr std::size_t kMaximumAudioParsedCommandCount =
    kMaximumAudioCommandStreamBytes / kAudioCommandAlignmentBytes;
inline constexpr std::size_t kAudioProgramVariantCount = 2U;

// Expected or observed internal overlay-permutation class for the single
// generated audio wrapper. The adapter never selects a separate host program.
enum class AudioProgramVariant {
    unknown,
    primary,
    secondary,
};

enum class AudioTaskError {
    none,
    unsupported_variant,
    empty_active_program,
    active_program_too_large,
    active_program_misaligned,
    empty_program_data,
    program_data_too_large,
    empty_command_stream,
    command_stream_too_large,
    command_stream_misaligned,
    empty_output,
    output_too_large,
    output_misaligned,
    missing_referenced_memory,
    too_many_referenced_regions,
    empty_referenced_region,
    referenced_region_too_large,
    referenced_memory_too_large,
    overlapping_memory_regions,
    incomplete_backend_capabilities,
    backend_rejected,
    parse_incomplete,
    unsupported_commands,
    selected_variant_mismatch,
    memory_access_violation,
    referenced_memory_incomplete,
    output_incomplete,
    output_validation_failed,
    invalid_backend_report,
    backend_exception,
};

struct AudioReferencedRegion {
    std::span<const std::byte> bytes;
    // Optional transactional destination for RSP work-buffer writes. Reads see
    // staged writes immediately, but the caller's span is updated only after
    // the complete report and independent output validation succeed.
    std::span<std::byte> writable_bytes;

    constexpr AudioReferencedRegion() noexcept = default;
    constexpr explicit AudioReferencedRegion(
        const std::span<const std::byte> initial_bytes,
        const std::span<std::byte> writable = {}) noexcept
        : bytes(initial_bytes), writable_bytes(writable) {}
};

struct AudioTaskView {
    AudioProgramVariant variant = AudioProgramVariant::unknown;
    std::span<const std::byte> active_program;
    std::span<const std::byte> program_data;
    std::span<const std::byte> command_stream;
    std::span<const AudioReferencedRegion> referenced_regions;
    std::span<std::byte> output;
};

struct AudioBackendCapabilities {
    std::size_t program_variant_count = 0U;
    bool primary_variant_supported = false;
    bool secondary_variant_supported = false;
    bool referenced_memory_broker_only = false;
    bool unknown_commands_fail_closed = false;
};

// Deliberately omits the raw referenced-region and output spans held by
// AudioTaskView. The backend can observe only their aggregate shape; all
// indirect reads and output writes must use AudioMemoryAccess.
struct AudioBackendTaskView {
    AudioProgramVariant variant = AudioProgramVariant::unknown;
    std::span<const std::byte> active_program;
    std::span<const std::byte> program_data;
    std::span<const std::byte> command_stream;
    std::size_t referenced_region_count = 0U;
    std::size_t writable_region_count = 0U;
    std::size_t output_size = 0U;
};

struct AudioBackendReport {
    bool accepted = false;
    bool parse_complete = false;
    AudioProgramVariant selected_variant = AudioProgramVariant::unknown;
    std::size_t parsed_command_count = 0U;
    std::size_t unsupported_command_count = 0U;
    std::size_t input_read_operation_count = 0U;
    std::size_t input_bytes_read = 0U;
    std::size_t region_write_operation_count = 0U;
    std::size_t region_bytes_written = 0U;
    std::size_t output_write_operation_count = 0U;
    std::size_t output_bytes_written = 0U;
};

// The backend receives no host pointer for indirectly referenced memory or the
// output buffer. Every such access must pass through this fail-closed broker.
class AudioMemoryAccess {
public:
    virtual ~AudioMemoryAccess() = default;

    [[nodiscard]] virtual bool read(
        std::size_t region_index,
        std::size_t offset,
        std::span<std::byte> destination) noexcept = 0;
    [[nodiscard]] virtual bool write_region(
        std::size_t region_index,
        std::size_t offset,
        std::span<const std::byte> source) noexcept = 0;
    [[nodiscard]] virtual bool write_output(
        std::size_t offset,
        std::span<const std::byte> source) noexcept = 0;
};

// Project-owned result surface for a brokered generated-RSP program entry.
// The program cannot self-select its variant or authorize scheduler completion;
// the adapter and bridge derive those decisions around this narrower report.
enum class AudioRspExitReason {
    invalid,
    broke,
    imem_overrun,
    unhandled_jump_target,
    unsupported,
    swap_overlay,
    unhandled_resume_target,
};

struct AudioRspProgramReport {
    AudioRspExitReason exit_reason = AudioRspExitReason::invalid;
    bool parse_complete = false;
    // Observed from the generated wrapper's internal overlay dispatch. The
    // adapter must not substitute the caller's expected variant.
    AudioProgramVariant selected_variant = AudioProgramVariant::unknown;
    std::size_t parsed_command_count = 0U;
    std::size_t unsupported_command_count = 0U;
    std::size_t input_read_operation_count = 0U;
    std::size_t input_bytes_read = 0U;
    std::size_t region_write_operation_count = 0U;
    std::size_t region_bytes_written = 0U;
    std::size_t output_write_operation_count = 0U;
    std::size_t output_bytes_written = 0U;
};

class AudioRspProgram {
public:
    virtual ~AudioRspProgram() = default;

    [[nodiscard]] virtual AudioRspProgramReport execute(
        const AudioBackendTaskView& task,
        AudioMemoryAccess& memory) = 0;
};

class AudioTaskBackend {
public:
    virtual ~AudioTaskBackend() = default;

    [[nodiscard]] virtual AudioBackendCapabilities capabilities() const = 0;
    [[nodiscard]] virtual AudioBackendReport execute(
        const AudioBackendTaskView& task,
        AudioMemoryAccess& memory) = 0;
};

// Non-owning adapter for the generated RSP wrapper. N64Recomp's wrapper owns
// internal overlay-permutation dispatch; the caller supplies only the expected
// observed variant and the bridge verifies it against the program report.
class AudioRspTaskAdapter final : public AudioTaskBackend {
public:
    explicit AudioRspTaskAdapter(AudioRspProgram* program) noexcept;

    [[nodiscard]] AudioBackendCapabilities capabilities() const noexcept override;
    [[nodiscard]] AudioBackendReport execute(
        const AudioBackendTaskView& task,
        AudioMemoryAccess& memory) override;

private:
    AudioRspProgram* program_;
};

class AudioOutputValidator {
public:
    virtual ~AudioOutputValidator() = default;

    [[nodiscard]] virtual bool validate(
        std::span<const std::byte> output) = 0;
};

struct AudioTaskResult {
    AudioTaskError error = AudioTaskError::none;
    AudioProgramVariant selected_variant = AudioProgramVariant::unknown;
    std::size_t parsed_command_count = 0U;
    std::size_t input_bytes_read = 0U;
    std::size_t referenced_bytes_written = 0U;
    std::size_t output_bytes_written = 0U;
    bool referenced_memory_closed = false;
    bool output_validated = false;
    bool completion_authorized = false;

    [[nodiscard]] bool ok() const noexcept {
        return error == AudioTaskError::none && referenced_memory_closed &&
            output_validated && completion_authorized;
    }
};

// ROM-free boundary for a future RSP-recompiled audio adapter. Output is staged
// transactionally and is copied to the caller only after the backend report,
// complete broker ledger, and independent output validator all agree.
class AudioTaskBridge final {
public:
    [[nodiscard]] AudioTaskResult submit(
        const AudioTaskView& task,
        AudioTaskBackend& backend,
        AudioOutputValidator& output_validator) const noexcept;
};

class AudioTaskCompletionSink {
public:
    virtual ~AudioTaskCompletionSink() = default;

    // Called only after validated output has been committed to the caller, but
    // before any external completion signal. False or an exception rejects the
    // completion without an externally visible side effect.
    [[nodiscard]] virtual bool prepare_sp_complete(
        const AudioTaskResult& result) = 0;

    // The final externally visible signal. It is infallible and called exactly
    // once only after preparation succeeds.
    virtual void commit_sp_complete(
        const AudioTaskResult& result) noexcept = 0;
};

struct AudioScheduledTaskResult {
    AudioTaskResult task;
    bool completion_emitted = false;

    [[nodiscard]] bool ok() const noexcept {
        return task.ok() && completion_emitted;
    }
};

// Enforces the host-side ordering boundary: failed or unvalidated work never
// reaches the completion sink, and successful output is visible first.
class AudioTaskSchedulerGate final {
public:
    [[nodiscard]] AudioScheduledTaskResult submit(
        const AudioTaskView& task,
        AudioTaskBackend& backend,
        AudioOutputValidator& output_validator,
        AudioTaskCompletionSink& completion_sink) const noexcept;
};

class AudioWorkerInstallation final {
public:
    AudioWorkerInstallation() noexcept = default;
    [[nodiscard]] bool valid() const noexcept {
        return worker_identity != 0U && generation != 0U;
    }

    friend bool operator==(
        const AudioWorkerInstallation&,
        const AudioWorkerInstallation&) = default;

private:
    AudioWorkerInstallation(
        const std::uint64_t worker,
        const std::uint64_t install_generation) noexcept
        : worker_identity(worker), generation(install_generation) {}

    std::uint64_t worker_identity = 0U;
    std::uint64_t generation = 0U;

    friend class AudioRuntimeTaskWorker;
};

enum class AudioWorkerError {
    none,
    invalid_program,
    already_installed,
    not_installed,
    stale_installation,
    busy,
    identity_exhausted,
    internal_failure,
};

struct AudioWorkerInstallResult {
    AudioWorkerError error = AudioWorkerError::none;
    AudioWorkerInstallation installation;

    [[nodiscard]] bool ok() const noexcept {
        return error == AudioWorkerError::none && installation.valid();
    }
};

struct AudioWorkerDispatchResult {
    AudioWorkerError error = AudioWorkerError::none;
    AudioScheduledTaskResult scheduled;

    [[nodiscard]] bool ok() const noexcept {
        return error == AudioWorkerError::none && scheduled.ok();
    }
};

// Owns the installed generated-wrapper interface without owning or exposing any
// generated body. An installation token is bound to both this worker instance
// and one monotonically increasing generation. Dispatch snapshots shared
// ownership after token validation, so uninstall prevents new work while an
// already accepted task can finish without a dangling program pointer.
class AudioRuntimeTaskWorker final {
public:
    AudioRuntimeTaskWorker() noexcept;
    ~AudioRuntimeTaskWorker() = default;

    AudioRuntimeTaskWorker(const AudioRuntimeTaskWorker&) = delete;
    AudioRuntimeTaskWorker& operator=(const AudioRuntimeTaskWorker&) = delete;
    AudioRuntimeTaskWorker(AudioRuntimeTaskWorker&&) = delete;
    AudioRuntimeTaskWorker& operator=(AudioRuntimeTaskWorker&&) = delete;

    [[nodiscard]] AudioWorkerInstallResult install(
        std::unique_ptr<AudioRspProgram> program) noexcept;
    [[nodiscard]] AudioWorkerError uninstall(
        AudioWorkerInstallation installation) noexcept;
    [[nodiscard]] AudioWorkerDispatchResult submit(
        AudioWorkerInstallation installation,
        const AudioTaskView& task,
        AudioOutputValidator& output_validator,
        AudioTaskCompletionSink& completion_sink) noexcept;

private:
    std::uint64_t worker_identity_ = 0U;
    std::uint64_t next_generation_ = 1U;
    AudioWorkerInstallation active_installation_;
    std::shared_ptr<AudioRspProgram> active_program_;
    bool busy_ = false;
    std::mutex mutex_;
};

[[nodiscard]] const char* audio_task_error_message(
    AudioTaskError error) noexcept;
[[nodiscard]] const char* audio_worker_error_message(
    AudioWorkerError error) noexcept;

}  // namespace jfg
