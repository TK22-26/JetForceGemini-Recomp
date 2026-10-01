#pragma once

#include <array>
#include <cstddef>
#include <cstdint>
#include <span>

namespace jfg {

inline constexpr std::size_t kMaximumGraphicsActiveProgramBytes = 4096U;
inline constexpr std::size_t kMaximumGraphicsProgramDataBytes = 4096U;
inline constexpr std::size_t kMaximumGraphicsCommandStreamBytes =
    1024U * 1024U;
inline constexpr std::size_t kGraphicsInstructionAlignmentBytes = 4U;
inline constexpr std::size_t kGraphicsCommandAlignmentBytes = 8U;
inline constexpr std::size_t kMaximumGraphicsParsedCommandCount =
    kMaximumGraphicsCommandStreamBytes / kGraphicsCommandAlignmentBytes;
inline constexpr std::size_t kGraphicsBaseCustomHandlerCount = 7U;
inline constexpr std::size_t kGraphicsVariantOverrideCount = 1U;
inline constexpr std::size_t kMaximumGraphicsReferencedRegionCount = 256U;
inline constexpr std::size_t kMaximumGraphicsReferencedMemoryBytes =
    8U * 1024U * 1024U;
inline constexpr std::size_t kMaximumGraphicsMemoryAccessCount =
    kMaximumGraphicsCommandStreamBytes;
inline constexpr std::size_t kMaximumGraphicsMemoryAccessBytes =
    64U * 1024U * 1024U;
inline constexpr std::size_t kMaximumGraphicsOutputDimension = 8192U;
inline constexpr std::size_t kMaximumGraphicsOutputBytes =
    64U * 1024U * 1024U;

enum class GraphicsFamily {
    unknown,
    bounded_custom,
};

enum class GraphicsOutputKind {
    unknown,
    semantic_submission,
    rendered_pixels,
};

enum class GraphicsTaskError {
    none,
    empty_active_program,
    active_program_too_large,
    active_program_misaligned,
    empty_program_data,
    program_data_too_large,
    empty_command_stream,
    command_stream_too_large,
    command_stream_misaligned,
    empty_referenced_memory,
    too_many_referenced_regions,
    invalid_referenced_region,
    referenced_memory_too_large,
    unsupported_family,
    incomplete_handler_surface,
    backend_rejected,
    parse_incomplete,
    unsupported_commands,
    referenced_memory_open,
    output_not_observed,
    invalid_output,
    output_rejected,
    output_oracle_not_independent,
    invalid_backend_report,
    backend_exception,
    output_oracle_exception,
    completion_rejected,
    completion_exception,
};

struct GraphicsTaskView {
    GraphicsFamily family = GraphicsFamily::bounded_custom;
    std::span<const std::byte> active_program;
    std::span<const std::byte> program_data;
    std::span<const std::byte> command_stream;
};

struct GraphicsBackendCapabilities {
    GraphicsFamily family = GraphicsFamily::bounded_custom;
    GraphicsOutputKind output_kind = GraphicsOutputKind::unknown;
    std::size_t base_custom_handler_count = 0;
    std::size_t variant_override_count = 0;
    bool shared_base_delegate = false;
    bool unknown_commands_fail_closed = false;
};

struct GraphicsReferencedMemoryRegion {
    // The identifier is an adapter-owned opaque handle, not a target address.
    std::uint32_t id = 0U;
    std::span<const std::byte> bytes;
};

class GraphicsMemoryBroker final {
public:
    GraphicsMemoryBroker(const GraphicsMemoryBroker&) = delete;
    GraphicsMemoryBroker& operator=(const GraphicsMemoryBroker&) = delete;
    GraphicsMemoryBroker(GraphicsMemoryBroker&&) = delete;
    GraphicsMemoryBroker& operator=(GraphicsMemoryBroker&&) = delete;

    // A future native adapter must route every command-triggered memory read
    // through this method. Invalid or over-budget access permanently closes
    // the transaction and returns an empty view.
    [[nodiscard]] std::span<const std::byte> read(
        std::uint32_t region_id,
        std::size_t offset,
        std::size_t length) noexcept;

    [[nodiscard]] bool closed() const noexcept;
    [[nodiscard]] std::size_t access_count() const noexcept;
    [[nodiscard]] std::size_t accessed_bytes() const noexcept;

private:
    friend class GraphicsTaskBridge;

    explicit GraphicsMemoryBroker(
        std::span<const GraphicsReferencedMemoryRegion> regions) noexcept;

    std::span<const GraphicsReferencedMemoryRegion> regions_;
    std::array<bool, kMaximumGraphicsReferencedRegionCount> observed_regions_{};
    std::size_t access_count_ = 0U;
    std::size_t accessed_bytes_ = 0U;
    std::size_t observed_region_count_ = 0U;
    bool failed_ = false;
};

struct GraphicsOutputView {
    GraphicsOutputKind kind = GraphicsOutputKind::unknown;
    std::size_t width = 0U;
    std::size_t height = 0U;
    std::size_t row_pitch_bytes = 0U;
    std::size_t bytes_per_pixel = 0U;
    // The adapter keeps this view alive until submit returns. The bridge does
    // not copy, hash, log, or persist its contents.
    std::span<const std::byte> bytes;
};

struct GraphicsBackendReport {
    bool accepted = false;
    bool parse_complete = false;
    std::size_t parsed_command_count = 0;
    std::size_t unsupported_command_count = 0;
    GraphicsOutputView output;
};

class GraphicsTaskBackend {
public:
    virtual ~GraphicsTaskBackend() = default;

    [[nodiscard]] virtual GraphicsBackendCapabilities capabilities() const = 0;
    [[nodiscard]] virtual GraphicsBackendReport execute(
        const GraphicsTaskView& task,
        GraphicsMemoryBroker& memory) = 0;
};

class GraphicsOutputOracle {
public:
    virtual ~GraphicsOutputOracle() = default;

    // This is deliberately separate from the renderer adapter so the adapter
    // cannot authorize its own output. Private validation may compare the view
    // with an approved local oracle; tracked tests use only synthetic bytes.
    [[nodiscard]] virtual bool validate(
        const GraphicsOutputView& output) = 0;
};

class GraphicsCompletionSink {
public:
    virtual ~GraphicsCompletionSink() = default;

    // Preparation occurs only after parsing, broker closure, and output
    // validation succeed. It must not emit a completion signal. Once it
    // accepts, commit_renderer_complete is the no-fail commit point so an
    // externally visible completion cannot be followed by a failure result.
    [[nodiscard]] virtual bool prepare_renderer_complete(
        std::size_t parsed_command_count) = 0;
    virtual void commit_renderer_complete(
        std::size_t parsed_command_count) noexcept = 0;
};

struct GraphicsTaskResult {
    GraphicsTaskError error = GraphicsTaskError::none;
    std::size_t parsed_command_count = 0;
    bool completion_authorized = false;

    [[nodiscard]] bool ok() const noexcept {
        return error == GraphicsTaskError::none && completion_authorized;
    }
};

// A project-owned, ROM-free boundary between game task submission and a
// renderer adapter. Family decoding lives in a separate backend.
// Command-triggered memory reads are brokered, output is checked by an oracle
// independent of the backend, and the completion sink is called last. Any
// malformed, unsupported, incomplete, rejected, or exception path fails closed.
// These contracts do not prove that a visual adapter routes every real access
// correctly or that a private oracle accepts rendered pixels; those remain G2
// evidence requirements.
class GraphicsTaskBridge final {
public:
    [[nodiscard]] GraphicsTaskResult submit(
        const GraphicsTaskView& task,
        std::span<const GraphicsReferencedMemoryRegion> referenced_memory,
        GraphicsTaskBackend& backend,
        GraphicsOutputOracle& output_oracle,
        GraphicsCompletionSink& completion_sink) const noexcept;
};

[[nodiscard]] const char* graphics_task_error_message(
    GraphicsTaskError error) noexcept;

}  // namespace jfg
