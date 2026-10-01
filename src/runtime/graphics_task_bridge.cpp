#include "jfg/runtime/graphics_task_bridge.hpp"

namespace jfg {
namespace {

[[nodiscard]] GraphicsTaskResult failure(
    const GraphicsTaskError error) noexcept {
    return {error, 0U, false};
}

[[nodiscard]] GraphicsTaskError validate_task(
    const GraphicsTaskView& task) noexcept {
    if (task.family != GraphicsFamily::bounded_custom) {
        return GraphicsTaskError::unsupported_family;
    }
    if (task.active_program.empty()) {
        return GraphicsTaskError::empty_active_program;
    }
    if (task.active_program.size() > kMaximumGraphicsActiveProgramBytes) {
        return GraphicsTaskError::active_program_too_large;
    }
    if ((task.active_program.size() % kGraphicsInstructionAlignmentBytes) != 0U) {
        return GraphicsTaskError::active_program_misaligned;
    }
    if (task.program_data.empty()) {
        return GraphicsTaskError::empty_program_data;
    }
    if (task.program_data.size() > kMaximumGraphicsProgramDataBytes) {
        return GraphicsTaskError::program_data_too_large;
    }
    if (task.command_stream.empty()) {
        return GraphicsTaskError::empty_command_stream;
    }
    if (task.command_stream.size() > kMaximumGraphicsCommandStreamBytes) {
        return GraphicsTaskError::command_stream_too_large;
    }
    if ((task.command_stream.size() % kGraphicsCommandAlignmentBytes) != 0U) {
        return GraphicsTaskError::command_stream_misaligned;
    }
    return GraphicsTaskError::none;
}

[[nodiscard]] GraphicsTaskError validate_referenced_memory(
    const std::span<const GraphicsReferencedMemoryRegion> regions) noexcept {
    if (regions.empty()) {
        return GraphicsTaskError::empty_referenced_memory;
    }
    if (regions.size() > kMaximumGraphicsReferencedRegionCount) {
        return GraphicsTaskError::too_many_referenced_regions;
    }

    std::size_t total_bytes = 0U;
    for (std::size_t index = 0U; index < regions.size(); ++index) {
        const GraphicsReferencedMemoryRegion& region = regions[index];
        if (region.bytes.empty()) {
            return GraphicsTaskError::invalid_referenced_region;
        }
        if (region.bytes.size() >
            kMaximumGraphicsReferencedMemoryBytes - total_bytes) {
            return GraphicsTaskError::referenced_memory_too_large;
        }
        total_bytes += region.bytes.size();

        for (std::size_t earlier = 0U; earlier < index; ++earlier) {
            if (regions[earlier].id == region.id) {
                return GraphicsTaskError::invalid_referenced_region;
            }
        }
    }
    return GraphicsTaskError::none;
}

[[nodiscard]] GraphicsTaskError validate_capabilities(
    const GraphicsTaskView& task,
    const GraphicsBackendCapabilities& capabilities) noexcept {
    if (capabilities.family != task.family) {
        return GraphicsTaskError::unsupported_family;
    }
    if (capabilities.output_kind == GraphicsOutputKind::unknown ||
        capabilities.base_custom_handler_count !=
            kGraphicsBaseCustomHandlerCount ||
        capabilities.variant_override_count !=
            kGraphicsVariantOverrideCount ||
        !capabilities.shared_base_delegate ||
        !capabilities.unknown_commands_fail_closed) {
        return GraphicsTaskError::incomplete_handler_surface;
    }
    return GraphicsTaskError::none;
}

[[nodiscard]] GraphicsTaskError validate_report(
    const GraphicsTaskView& task,
    const GraphicsBackendCapabilities& capabilities,
    const GraphicsBackendReport& report) noexcept {
    if (!report.accepted) {
        return GraphicsTaskError::backend_rejected;
    }
    if (report.parsed_command_count == 0U ||
        report.parsed_command_count > kMaximumGraphicsParsedCommandCount ||
        report.unsupported_command_count > report.parsed_command_count) {
        return GraphicsTaskError::invalid_backend_report;
    }
    if (!report.parse_complete) {
        return GraphicsTaskError::parse_incomplete;
    }
    if (report.unsupported_command_count != 0U) {
        return GraphicsTaskError::unsupported_commands;
    }
    if (report.output.kind != capabilities.output_kind) {
        return GraphicsTaskError::invalid_backend_report;
    }
    // At least the submitted top-level command stream must have been observed.
    // Nested lists may make the parsed count larger, so equality is not
    // required. This arithmetic is checked above before multiplication.
    if (report.parsed_command_count * kGraphicsCommandAlignmentBytes <
        task.command_stream.size()) {
        return GraphicsTaskError::invalid_backend_report;
    }
    return GraphicsTaskError::none;
}

[[nodiscard]] GraphicsTaskError validate_output(
    const GraphicsOutputView& output) noexcept {
    if (output.bytes.empty()) {
        return GraphicsTaskError::output_not_observed;
    }
    if (output.kind == GraphicsOutputKind::unknown ||
        output.width == 0U || output.height == 0U ||
        output.bytes_per_pixel == 0U ||
        output.width > kMaximumGraphicsOutputDimension ||
        output.height > kMaximumGraphicsOutputDimension ||
        output.bytes.size() > kMaximumGraphicsOutputBytes) {
        return GraphicsTaskError::invalid_output;
    }
    if (output.width >
        kMaximumGraphicsOutputBytes / output.bytes_per_pixel) {
        return GraphicsTaskError::invalid_output;
    }
    const std::size_t minimum_row_bytes =
        output.width * output.bytes_per_pixel;
    if (output.row_pitch_bytes < minimum_row_bytes ||
        output.row_pitch_bytes > kMaximumGraphicsOutputBytes ||
        output.height >
            kMaximumGraphicsOutputBytes / output.row_pitch_bytes) {
        return GraphicsTaskError::invalid_output;
    }
    const std::size_t required_bytes =
        output.row_pitch_bytes * output.height;
    if (output.bytes.size() != required_bytes) {
        return GraphicsTaskError::invalid_output;
    }
    return GraphicsTaskError::none;
}

}  // namespace

GraphicsMemoryBroker::GraphicsMemoryBroker(
    const std::span<const GraphicsReferencedMemoryRegion> regions) noexcept
    : regions_(regions) {}

std::span<const std::byte> GraphicsMemoryBroker::read(
    const std::uint32_t region_id,
    const std::size_t offset,
    const std::size_t length) noexcept {
    if (failed_ || length == 0U ||
        access_count_ >= kMaximumGraphicsMemoryAccessCount ||
        length > kMaximumGraphicsMemoryAccessBytes - accessed_bytes_) {
        failed_ = true;
        return {};
    }

    for (std::size_t index = 0U; index < regions_.size(); ++index) {
        const GraphicsReferencedMemoryRegion& region = regions_[index];
        if (region.id != region_id) {
            continue;
        }
        if (offset > region.bytes.size() ||
            length > region.bytes.size() - offset) {
            failed_ = true;
            return {};
        }
        ++access_count_;
        accessed_bytes_ += length;
        if (!observed_regions_[index]) {
            observed_regions_[index] = true;
            ++observed_region_count_;
        }
        return region.bytes.subspan(offset, length);
    }

    failed_ = true;
    return {};
}

bool GraphicsMemoryBroker::closed() const noexcept {
    return !failed_ && access_count_ != 0U &&
        observed_region_count_ == regions_.size();
}

std::size_t GraphicsMemoryBroker::access_count() const noexcept {
    return access_count_;
}

std::size_t GraphicsMemoryBroker::accessed_bytes() const noexcept {
    return accessed_bytes_;
}

GraphicsTaskResult GraphicsTaskBridge::submit(
    const GraphicsTaskView& task,
    const std::span<const GraphicsReferencedMemoryRegion> referenced_memory,
    GraphicsTaskBackend& backend,
    GraphicsOutputOracle& output_oracle,
    GraphicsCompletionSink& completion_sink) const noexcept {
    const GraphicsTaskError task_error = validate_task(task);
    if (task_error != GraphicsTaskError::none) {
        return failure(task_error);
    }

    const GraphicsTaskError memory_error =
        validate_referenced_memory(referenced_memory);
    if (memory_error != GraphicsTaskError::none) {
        return failure(memory_error);
    }
    if (dynamic_cast<const void*>(&backend) ==
        dynamic_cast<const void*>(&output_oracle)) {
        return failure(GraphicsTaskError::output_oracle_not_independent);
    }

    GraphicsBackendReport report;
    GraphicsBackendCapabilities capabilities;
    GraphicsMemoryBroker memory(referenced_memory);
    try {
        capabilities = backend.capabilities();
        const GraphicsTaskError capability_error =
            validate_capabilities(task, capabilities);
        if (capability_error != GraphicsTaskError::none) {
            return failure(capability_error);
        }

        report = backend.execute(task, memory);
        const GraphicsTaskError report_error =
            validate_report(task, capabilities, report);
        if (report_error != GraphicsTaskError::none) {
            return failure(report_error);
        }
    }
    catch (...) {
        return failure(GraphicsTaskError::backend_exception);
    }

    if (!memory.closed()) {
        return failure(GraphicsTaskError::referenced_memory_open);
    }
    const GraphicsTaskError output_error = validate_output(report.output);
    if (output_error != GraphicsTaskError::none) {
        return failure(output_error);
    }
    try {
        if (!output_oracle.validate(report.output)) {
            return failure(GraphicsTaskError::output_rejected);
        }
    }
    catch (...) {
        return failure(GraphicsTaskError::output_oracle_exception);
    }
    try {
        if (!completion_sink.prepare_renderer_complete(
                report.parsed_command_count)) {
            return failure(GraphicsTaskError::completion_rejected);
        }
    }
    catch (...) {
        return failure(GraphicsTaskError::completion_exception);
    }
    completion_sink.commit_renderer_complete(report.parsed_command_count);
    return {GraphicsTaskError::none, report.parsed_command_count, true};
}

const char* graphics_task_error_message(const GraphicsTaskError error) noexcept {
    switch (error) {
    case GraphicsTaskError::none:
        return "no error";
    case GraphicsTaskError::empty_active_program:
        return "active program is empty";
    case GraphicsTaskError::active_program_too_large:
        return "active program exceeds the supported bound";
    case GraphicsTaskError::active_program_misaligned:
        return "active program is not instruction-aligned";
    case GraphicsTaskError::empty_program_data:
        return "program data is empty";
    case GraphicsTaskError::program_data_too_large:
        return "program data exceeds the supported bound";
    case GraphicsTaskError::empty_command_stream:
        return "command stream is empty";
    case GraphicsTaskError::command_stream_too_large:
        return "command stream exceeds the supported bound";
    case GraphicsTaskError::command_stream_misaligned:
        return "command stream is not command-aligned";
    case GraphicsTaskError::empty_referenced_memory:
        return "graphics referenced-memory region set is empty";
    case GraphicsTaskError::too_many_referenced_regions:
        return "graphics referenced-memory region count exceeds the bound";
    case GraphicsTaskError::invalid_referenced_region:
        return "graphics referenced-memory region set is invalid";
    case GraphicsTaskError::referenced_memory_too_large:
        return "graphics referenced-memory set exceeds the byte bound";
    case GraphicsTaskError::unsupported_family:
        return "graphics family is unsupported";
    case GraphicsTaskError::incomplete_handler_surface:
        return "graphics handler surface is incomplete";
    case GraphicsTaskError::backend_rejected:
        return "graphics backend rejected the task";
    case GraphicsTaskError::parse_incomplete:
        return "graphics parse did not complete";
    case GraphicsTaskError::unsupported_commands:
        return "graphics parse encountered unsupported commands";
    case GraphicsTaskError::referenced_memory_open:
        return "graphics referenced-memory closure was not established";
    case GraphicsTaskError::output_not_observed:
        return "graphics output was not observed";
    case GraphicsTaskError::invalid_output:
        return "graphics output view is invalid";
    case GraphicsTaskError::output_rejected:
        return "graphics output oracle rejected the result";
    case GraphicsTaskError::output_oracle_not_independent:
        return "graphics output oracle is not independent of the backend";
    case GraphicsTaskError::invalid_backend_report:
        return "graphics backend returned an inconsistent report";
    case GraphicsTaskError::backend_exception:
        return "graphics backend raised an exception";
    case GraphicsTaskError::output_oracle_exception:
        return "graphics output oracle raised an exception";
    case GraphicsTaskError::completion_rejected:
        return "graphics completion sink rejected the signal";
    case GraphicsTaskError::completion_exception:
        return "graphics completion sink raised an exception";
    }
    return "unknown graphics task error";
}

}  // namespace jfg
