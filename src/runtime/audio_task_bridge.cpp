#include "jfg/runtime/audio_task_bridge.hpp"

#include <algorithm>
#include <atomic>
#include <cstdint>
#include <cstring>
#include <limits>
#include <vector>

namespace jfg {
namespace {

std::atomic<std::uint64_t> next_audio_worker_identity{1U};

[[nodiscard]] std::uint64_t allocate_audio_worker_identity() noexcept {
    std::uint64_t current = next_audio_worker_identity.load(
        std::memory_order_relaxed);
    while (current != 0U) {
        const std::uint64_t next =
            current == std::numeric_limits<std::uint64_t>::max()
            ? 0U
            : current + 1U;
        if (next_audio_worker_identity.compare_exchange_weak(
                current,
                next,
                std::memory_order_relaxed,
                std::memory_order_relaxed)) {
            return current;
        }
    }
    return 0U;
}

[[nodiscard]] AudioTaskResult failure(const AudioTaskError error) noexcept {
    AudioTaskResult result{};
    result.error = error;
    return result;
}

[[nodiscard]] bool ranges_overlap(
    const void* const left_data,
    const std::size_t left_size,
    const void* const right_data,
    const std::size_t right_size) noexcept {
    const auto left = reinterpret_cast<std::uintptr_t>(left_data);
    const auto right = reinterpret_cast<std::uintptr_t>(right_data);
    constexpr std::uintptr_t maximum =
        std::numeric_limits<std::uintptr_t>::max();
    if (left_size > maximum - left || right_size > maximum - right) {
        return true;
    }
    const auto left_end = left + left_size;
    const auto right_end = right + right_size;
    return left < right_end && right < left_end;
}

[[nodiscard]] AudioTaskError validate_task(const AudioTaskView& task) noexcept {
    if (task.variant != AudioProgramVariant::primary &&
        task.variant != AudioProgramVariant::secondary) {
        return AudioTaskError::unsupported_variant;
    }
    if (task.active_program.empty()) {
        return AudioTaskError::empty_active_program;
    }
    if (task.active_program.size() > kMaximumAudioActiveProgramBytes) {
        return AudioTaskError::active_program_too_large;
    }
    if ((task.active_program.size() % kAudioInstructionAlignmentBytes) != 0U) {
        return AudioTaskError::active_program_misaligned;
    }
    if (task.program_data.empty()) {
        return AudioTaskError::empty_program_data;
    }
    if (task.program_data.size() > kMaximumAudioProgramDataBytes) {
        return AudioTaskError::program_data_too_large;
    }
    if (task.command_stream.empty()) {
        return AudioTaskError::empty_command_stream;
    }
    if (task.command_stream.size() > kMaximumAudioCommandStreamBytes) {
        return AudioTaskError::command_stream_too_large;
    }
    if ((task.command_stream.size() % kAudioCommandAlignmentBytes) != 0U) {
        return AudioTaskError::command_stream_misaligned;
    }
    if (task.output.empty()) {
        return AudioTaskError::empty_output;
    }
    if (task.output.size() > kMaximumAudioOutputBytes) {
        return AudioTaskError::output_too_large;
    }
    if ((task.output.size() % kAudioOutputFrameBytes) != 0U) {
        return AudioTaskError::output_misaligned;
    }
    if (task.referenced_regions.empty()) {
        return AudioTaskError::missing_referenced_memory;
    }
    if (task.referenced_regions.size() > kMaximumAudioReferencedRegionCount) {
        return AudioTaskError::too_many_referenced_regions;
    }

    std::size_t total_bytes = 0U;
    for (std::size_t index = 0U; index < task.referenced_regions.size(); ++index) {
        const AudioReferencedRegion& region = task.referenced_regions[index];
        if (region.bytes.empty()) {
            return AudioTaskError::empty_referenced_region;
        }
        if (region.bytes.size() > kMaximumAudioReferencedRegionBytes) {
            return AudioTaskError::referenced_region_too_large;
        }
        if (region.bytes.size() > kMaximumAudioReferencedBytes - total_bytes) {
            return AudioTaskError::referenced_memory_too_large;
        }
        if (!region.writable_bytes.empty() &&
            region.writable_bytes.size() != region.bytes.size()) {
            return AudioTaskError::overlapping_memory_regions;
        }
        total_bytes += region.bytes.size();
        if (ranges_overlap(
                region.bytes.data(),
                region.bytes.size(),
                task.output.data(),
                task.output.size())) {
            return AudioTaskError::overlapping_memory_regions;
        }
        for (const std::span<const std::byte> top_level : {
                 task.active_program,
                 task.program_data,
                 task.command_stream,
             }) {
            if (ranges_overlap(
                    region.bytes.data(),
                    region.bytes.size(),
                    top_level.data(),
                    top_level.size())) {
                return AudioTaskError::overlapping_memory_regions;
            }
        }
        if (!region.writable_bytes.empty()) {
            const bool exact_source_alias =
                region.writable_bytes.data() == region.bytes.data();
            if (!exact_source_alias && ranges_overlap(
                    region.bytes.data(),
                    region.bytes.size(),
                    region.writable_bytes.data(),
                    region.writable_bytes.size())) {
                return AudioTaskError::overlapping_memory_regions;
            }
            if (ranges_overlap(
                    region.writable_bytes.data(),
                    region.writable_bytes.size(),
                    task.output.data(),
                    task.output.size())) {
                return AudioTaskError::overlapping_memory_regions;
            }
            for (const std::span<const std::byte> top_level : {
                     task.active_program,
                     task.program_data,
                     task.command_stream,
                 }) {
                if (ranges_overlap(
                        region.writable_bytes.data(),
                        region.writable_bytes.size(),
                        top_level.data(),
                        top_level.size())) {
                    return AudioTaskError::overlapping_memory_regions;
                }
            }
        }
        for (std::size_t prior = 0U; prior < index; ++prior) {
            const AudioReferencedRegion& other = task.referenced_regions[prior];
            for (const std::span<const std::byte> current_span : {
                     region.bytes,
                     std::span<const std::byte>(region.writable_bytes),
                 }) {
                if (current_span.empty()) {
                    continue;
                }
                for (const std::span<const std::byte> other_span : {
                         other.bytes,
                         std::span<const std::byte>(other.writable_bytes),
                     }) {
                    if (!other_span.empty() && ranges_overlap(
                            current_span.data(),
                            current_span.size(),
                            other_span.data(),
                            other_span.size())) {
                        return AudioTaskError::overlapping_memory_regions;
                    }
                }
            }
        }
    }
    for (const std::span<const std::byte> top_level : {
             task.active_program,
             task.program_data,
             task.command_stream,
         }) {
        if (ranges_overlap(
                task.output.data(),
                task.output.size(),
                top_level.data(),
                top_level.size())) {
            return AudioTaskError::overlapping_memory_regions;
        }
    }
    return AudioTaskError::none;
}

[[nodiscard]] AudioTaskError validate_capabilities(
    const AudioBackendCapabilities& capabilities) noexcept {
    if (capabilities.program_variant_count != kAudioProgramVariantCount ||
        !capabilities.primary_variant_supported ||
        !capabilities.secondary_variant_supported ||
        !capabilities.referenced_memory_broker_only ||
        !capabilities.unknown_commands_fail_closed) {
        return AudioTaskError::incomplete_backend_capabilities;
    }
    return AudioTaskError::none;
}

class BoundedAudioMemory final : public AudioMemoryAccess {
public:
    BoundedAudioMemory(
        const std::span<const AudioReferencedRegion> regions,
        const std::size_t output_size)
        : regions_(regions),
          region_observed_(regions.size(), false),
          staged_regions_(regions.size()),
          staged_output_(output_size),
          output_written_(output_size, false) {
        for (std::size_t index = 0U; index < regions.size(); ++index) {
            if (!regions[index].writable_bytes.empty()) {
                staged_regions_[index].assign(
                    regions[index].bytes.begin(), regions[index].bytes.end());
            }
        }
    }

    [[nodiscard]] bool read(
        const std::size_t region_index,
        const std::size_t offset,
        const std::span<std::byte> destination) noexcept override {
        if (violation_ || destination.empty() || region_index >= regions_.size()) {
            violation_ = true;
            return false;
        }
        const std::span<const std::byte> source = staged_regions_[region_index].empty()
            ? regions_[region_index].bytes
            : std::span<const std::byte>(staged_regions_[region_index]);
        if (offset > source.size() || destination.size() > source.size() - offset ||
            !reserve_operation(destination.size())) {
            violation_ = true;
            return false;
        }

        std::memmove(
            destination.data(),
            source.subspan(offset, destination.size()).data(),
            destination.size());
        region_observed_[region_index] = true;
        ++input_read_operation_count_;
        input_bytes_read_ += destination.size();
        return true;
    }

    [[nodiscard]] bool write_region(
        const std::size_t region_index,
        const std::size_t offset,
        const std::span<const std::byte> source) noexcept override {
        if (violation_ || source.empty() || region_index >= regions_.size() ||
            staged_regions_[region_index].empty()) {
            violation_ = true;
            return false;
        }
        std::vector<std::byte>& destination = staged_regions_[region_index];
        if (offset > destination.size() ||
            source.size() > destination.size() - offset ||
            !reserve_operation(source.size())) {
            violation_ = true;
            return false;
        }

        std::memmove(destination.data() + offset, source.data(), source.size());
        region_observed_[region_index] = true;
        ++region_write_operation_count_;
        region_bytes_written_ += source.size();
        return true;
    }

    [[nodiscard]] bool write_output(
        const std::size_t offset,
        const std::span<const std::byte> source) noexcept override {
        if (violation_ || source.empty() || offset > staged_output_.size() ||
            source.size() > staged_output_.size() - offset ||
            !reserve_operation(source.size())) {
            violation_ = true;
            return false;
        }
        const auto first = output_written_.begin() +
            static_cast<std::vector<bool>::difference_type>(offset);
        const auto last = first +
            static_cast<std::vector<bool>::difference_type>(source.size());
        if (std::find(first, last, true) != last) {
            violation_ = true;
            return false;
        }

        std::memmove(
            staged_output_.data() + offset,
            source.data(),
            source.size());
        std::fill(first, last, true);
        ++output_write_operation_count_;
        output_bytes_written_ += source.size();
        return true;
    }

    [[nodiscard]] bool violation() const noexcept {
        return violation_;
    }

    [[nodiscard]] bool all_regions_observed() const noexcept {
        return std::all_of(
            region_observed_.begin(),
            region_observed_.end(),
            [](const bool observed) { return observed; });
    }

    [[nodiscard]] bool output_complete() const noexcept {
        return std::all_of(
            output_written_.begin(),
            output_written_.end(),
            [](const bool written) { return written; });
    }

    [[nodiscard]] std::span<const std::byte> output() const noexcept {
        return staged_output_;
    }

    [[nodiscard]] std::size_t input_read_operation_count() const noexcept {
        return input_read_operation_count_;
    }

    [[nodiscard]] std::size_t input_bytes_read() const noexcept {
        return input_bytes_read_;
    }

    [[nodiscard]] std::size_t output_write_operation_count() const noexcept {
        return output_write_operation_count_;
    }

    [[nodiscard]] std::size_t region_write_operation_count() const noexcept {
        return region_write_operation_count_;
    }

    [[nodiscard]] std::size_t region_bytes_written() const noexcept {
        return region_bytes_written_;
    }

    void commit_regions() noexcept {
        for (std::size_t index = 0U; index < regions_.size(); ++index) {
            if (!staged_regions_[index].empty()) {
                std::memmove(
                    regions_[index].writable_bytes.data(),
                    staged_regions_[index].data(),
                    staged_regions_[index].size());
            }
        }
    }

    [[nodiscard]] std::size_t output_bytes_written() const noexcept {
        return output_bytes_written_;
    }

private:
    [[nodiscard]] bool reserve_operation(const std::size_t bytes) noexcept {
        const std::size_t operation_count =
            input_read_operation_count_ + region_write_operation_count_ +
            output_write_operation_count_;
        if (operation_count >= kMaximumAudioMemoryOperationCount ||
            bytes > kMaximumAudioMemoryTrafficBytes - memory_traffic_bytes_) {
            return false;
        }
        memory_traffic_bytes_ += bytes;
        return true;
    }

    std::span<const AudioReferencedRegion> regions_;
    std::vector<bool> region_observed_;
    std::vector<std::vector<std::byte>> staged_regions_;
    std::vector<std::byte> staged_output_;
    std::vector<bool> output_written_;
    std::size_t input_read_operation_count_ = 0U;
    std::size_t input_bytes_read_ = 0U;
    std::size_t region_write_operation_count_ = 0U;
    std::size_t region_bytes_written_ = 0U;
    std::size_t output_write_operation_count_ = 0U;
    std::size_t output_bytes_written_ = 0U;
    std::size_t memory_traffic_bytes_ = 0U;
    bool violation_ = false;
};

[[nodiscard]] AudioTaskError validate_report(
    const AudioBackendTaskView& task,
    const AudioBackendReport& report,
    const BoundedAudioMemory& memory) noexcept {
    if (!report.accepted) {
        return AudioTaskError::backend_rejected;
    }
    if (report.selected_variant != task.variant) {
        return AudioTaskError::selected_variant_mismatch;
    }
    if (report.parsed_command_count == 0U ||
        report.parsed_command_count > kMaximumAudioParsedCommandCount ||
        report.unsupported_command_count > report.parsed_command_count) {
        return AudioTaskError::invalid_backend_report;
    }
    if (!report.parse_complete) {
        return AudioTaskError::parse_incomplete;
    }
    if (report.unsupported_command_count != 0U) {
        return AudioTaskError::unsupported_commands;
    }
    if (report.parsed_command_count !=
        task.command_stream.size() / kAudioCommandAlignmentBytes) {
        return AudioTaskError::invalid_backend_report;
    }
    if (memory.violation()) {
        return AudioTaskError::memory_access_violation;
    }
    if (report.input_read_operation_count !=
            memory.input_read_operation_count() ||
        report.input_bytes_read != memory.input_bytes_read() ||
        report.region_write_operation_count !=
            memory.region_write_operation_count() ||
        report.region_bytes_written != memory.region_bytes_written() ||
        report.output_write_operation_count !=
            memory.output_write_operation_count() ||
        report.output_bytes_written != memory.output_bytes_written()) {
        return AudioTaskError::invalid_backend_report;
    }
    if (!memory.all_regions_observed()) {
        return AudioTaskError::referenced_memory_incomplete;
    }
    if (!memory.output_complete()) {
        return AudioTaskError::output_incomplete;
    }
    return AudioTaskError::none;
}

}  // namespace

AudioRspTaskAdapter::AudioRspTaskAdapter(
    AudioRspProgram* const program) noexcept
    : program_(program) {}

AudioBackendCapabilities AudioRspTaskAdapter::capabilities() const noexcept {
    return {
        program_ != nullptr ? kAudioProgramVariantCount : 0U,
        program_ != nullptr,
        program_ != nullptr,
        true,
        true,
    };
}

AudioBackendReport AudioRspTaskAdapter::execute(
    const AudioBackendTaskView& task,
    AudioMemoryAccess& memory) {
    AudioBackendReport report{};
    if (program_ == nullptr) {
        return report;
    }

    const AudioRspProgramReport program_report = program_->execute(task, memory);
    report.accepted = program_report.exit_reason == AudioRspExitReason::broke;
    report.parse_complete = program_report.parse_complete;
    report.selected_variant = program_report.selected_variant;
    report.parsed_command_count = program_report.parsed_command_count;
    report.unsupported_command_count =
        program_report.unsupported_command_count;
    report.input_read_operation_count =
        program_report.input_read_operation_count;
    report.input_bytes_read = program_report.input_bytes_read;
    report.region_write_operation_count =
        program_report.region_write_operation_count;
    report.region_bytes_written = program_report.region_bytes_written;
    report.output_write_operation_count =
        program_report.output_write_operation_count;
    report.output_bytes_written = program_report.output_bytes_written;
    return report;
}

AudioTaskResult AudioTaskBridge::submit(
    const AudioTaskView& task,
    AudioTaskBackend& backend,
    AudioOutputValidator& output_validator) const noexcept {
    const AudioTaskError task_error = validate_task(task);
    if (task_error != AudioTaskError::none) {
        return failure(task_error);
    }

    try {
        const AudioTaskError capability_error =
            validate_capabilities(backend.capabilities());
        if (capability_error != AudioTaskError::none) {
            return failure(capability_error);
        }

        BoundedAudioMemory memory(task.referenced_regions, task.output.size());
        const AudioBackendTaskView backend_task{
            task.variant,
            task.active_program,
            task.program_data,
            task.command_stream,
            task.referenced_regions.size(),
            static_cast<std::size_t>(std::count_if(
                task.referenced_regions.begin(),
                task.referenced_regions.end(),
                [](const AudioReferencedRegion& region) {
                    return !region.writable_bytes.empty();
                })),
            task.output.size(),
        };
        const AudioBackendReport report = backend.execute(backend_task, memory);
        const AudioTaskError report_error =
            validate_report(backend_task, report, memory);
        if (report_error != AudioTaskError::none) {
            return failure(report_error);
        }
        if (!output_validator.validate(memory.output())) {
            return failure(AudioTaskError::output_validation_failed);
        }

        memory.commit_regions();
        std::copy(memory.output().begin(), memory.output().end(), task.output.begin());
        AudioTaskResult result{};
        result.selected_variant = report.selected_variant;
        result.parsed_command_count = report.parsed_command_count;
        result.input_bytes_read = report.input_bytes_read;
        result.referenced_bytes_written = report.region_bytes_written;
        result.output_bytes_written = report.output_bytes_written;
        result.referenced_memory_closed = true;
        result.output_validated = true;
        result.completion_authorized = true;
        return result;
    }
    catch (...) {
        return failure(AudioTaskError::backend_exception);
    }
}

AudioScheduledTaskResult AudioTaskSchedulerGate::submit(
    const AudioTaskView& task,
    AudioTaskBackend& backend,
    AudioOutputValidator& output_validator,
    AudioTaskCompletionSink& completion_sink) const noexcept {
    AudioScheduledTaskResult scheduled{};
    scheduled.task = AudioTaskBridge{}.submit(task, backend, output_validator);
    if (!scheduled.task.ok()) {
        return scheduled;
    }
    try {
        if (!completion_sink.prepare_sp_complete(scheduled.task)) {
            return scheduled;
        }
    }
    catch (...) {
        return scheduled;
    }
    completion_sink.commit_sp_complete(scheduled.task);
    scheduled.completion_emitted = true;
    return scheduled;
}

AudioRuntimeTaskWorker::AudioRuntimeTaskWorker() noexcept
    : worker_identity_(allocate_audio_worker_identity()) {}

AudioWorkerInstallResult AudioRuntimeTaskWorker::install(
    std::unique_ptr<AudioRspProgram> program) noexcept {
    AudioWorkerInstallResult result{};
    if (program == nullptr) {
        result.error = AudioWorkerError::invalid_program;
        return result;
    }
    try {
        const std::lock_guard lock(mutex_);
        if (worker_identity_ == 0U || next_generation_ == 0U) {
            result.error = AudioWorkerError::identity_exhausted;
            return result;
        }
        if (active_program_ != nullptr) {
            result.error = AudioWorkerError::already_installed;
            return result;
        }

        const std::shared_ptr<AudioRspProgram> owned_program(
            std::move(program));
        result.installation = AudioWorkerInstallation(
            worker_identity_,
            next_generation_);
        ++next_generation_;
        active_installation_ = result.installation;
        active_program_ = owned_program;
        return result;
    }
    catch (...) {
        result.error = AudioWorkerError::internal_failure;
        result.installation = {};
        return result;
    }
}

AudioWorkerError AudioRuntimeTaskWorker::uninstall(
    const AudioWorkerInstallation installation) noexcept {
    std::shared_ptr<AudioRspProgram> released_program;
    try {
        {
            const std::lock_guard lock(mutex_);
            if (active_program_ == nullptr) {
                return AudioWorkerError::not_installed;
            }
            if (!installation.valid() ||
                installation != active_installation_) {
                return AudioWorkerError::stale_installation;
            }
            if (busy_) {
                return AudioWorkerError::busy;
            }
            released_program = std::move(active_program_);
            active_installation_ = {};
        }
        released_program.reset();
        return AudioWorkerError::none;
    }
    catch (...) {
        return AudioWorkerError::internal_failure;
    }
}

AudioWorkerDispatchResult AudioRuntimeTaskWorker::submit(
    const AudioWorkerInstallation installation,
    const AudioTaskView& task,
    AudioOutputValidator& output_validator,
    AudioTaskCompletionSink& completion_sink) noexcept {
    AudioWorkerDispatchResult result{};
    std::shared_ptr<AudioRspProgram> program;
    try {
        const std::lock_guard lock(mutex_);
        if (active_program_ == nullptr) {
            result.error = AudioWorkerError::not_installed;
            return result;
        }
        if (!installation.valid() ||
            installation != active_installation_) {
            result.error = AudioWorkerError::stale_installation;
            return result;
        }
        if (busy_) {
            result.error = AudioWorkerError::busy;
            return result;
        }
        program = active_program_;
        busy_ = true;
    }
    catch (...) {
        result.error = AudioWorkerError::internal_failure;
        return result;
    }

    AudioRspTaskAdapter adapter(program.get());
    result.scheduled = AudioTaskSchedulerGate{}.submit(
        task,
        adapter,
        output_validator,
        completion_sink);
    try {
        const std::lock_guard lock(mutex_);
        busy_ = false;
    }
    catch (...) {
        result.error = AudioWorkerError::internal_failure;
    }
    return result;
}

const char* audio_task_error_message(const AudioTaskError error) noexcept {
    switch (error) {
    case AudioTaskError::none:
        return "no error";
    case AudioTaskError::unsupported_variant:
        return "audio program variant is unsupported";
    case AudioTaskError::empty_active_program:
        return "active program is empty";
    case AudioTaskError::active_program_too_large:
        return "active program exceeds the supported bound";
    case AudioTaskError::active_program_misaligned:
        return "active program is not instruction-aligned";
    case AudioTaskError::empty_program_data:
        return "program data is empty";
    case AudioTaskError::program_data_too_large:
        return "program data exceeds the supported bound";
    case AudioTaskError::empty_command_stream:
        return "command stream is empty";
    case AudioTaskError::command_stream_too_large:
        return "command stream exceeds the supported bound";
    case AudioTaskError::command_stream_misaligned:
        return "command stream is not command-aligned";
    case AudioTaskError::empty_output:
        return "audio output is empty";
    case AudioTaskError::output_too_large:
        return "audio output exceeds the supported bound";
    case AudioTaskError::output_misaligned:
        return "audio output is not frame-aligned";
    case AudioTaskError::missing_referenced_memory:
        return "audio task has no referenced-memory regions";
    case AudioTaskError::too_many_referenced_regions:
        return "audio task has too many referenced-memory regions";
    case AudioTaskError::empty_referenced_region:
        return "audio referenced-memory region is empty";
    case AudioTaskError::referenced_region_too_large:
        return "audio referenced-memory region exceeds its bound";
    case AudioTaskError::referenced_memory_too_large:
        return "audio referenced memory exceeds the aggregate bound";
    case AudioTaskError::overlapping_memory_regions:
        return "audio referenced and output memory regions overlap";
    case AudioTaskError::incomplete_backend_capabilities:
        return "audio backend capability surface is incomplete";
    case AudioTaskError::backend_rejected:
        return "audio backend rejected the task";
    case AudioTaskError::parse_incomplete:
        return "audio command parsing did not complete";
    case AudioTaskError::unsupported_commands:
        return "audio parsing encountered unsupported commands";
    case AudioTaskError::selected_variant_mismatch:
        return "audio backend selected the wrong program variant";
    case AudioTaskError::memory_access_violation:
        return "audio referenced-memory access violated the broker contract";
    case AudioTaskError::referenced_memory_incomplete:
        return "audio referenced-memory closure is incomplete";
    case AudioTaskError::output_incomplete:
        return "audio output was not completely produced";
    case AudioTaskError::output_validation_failed:
        return "audio output failed independent validation";
    case AudioTaskError::invalid_backend_report:
        return "audio backend returned an inconsistent report";
    case AudioTaskError::backend_exception:
        return "audio bridge dependency raised an exception";
    }
    return "unknown audio task error";
}

const char* audio_worker_error_message(const AudioWorkerError error) noexcept {
    switch (error) {
    case AudioWorkerError::none:
        return "no error";
    case AudioWorkerError::invalid_program:
        return "audio worker program is invalid";
    case AudioWorkerError::already_installed:
        return "audio worker already has an installed program";
    case AudioWorkerError::not_installed:
        return "audio worker has no installed program";
    case AudioWorkerError::stale_installation:
        return "audio worker installation identity is stale";
    case AudioWorkerError::busy:
        return "audio worker is executing a task";
    case AudioWorkerError::identity_exhausted:
        return "audio worker installation identity is exhausted";
    case AudioWorkerError::internal_failure:
        return "audio worker dependency failed";
    }
    return "unknown audio worker error";
}

}  // namespace jfg
