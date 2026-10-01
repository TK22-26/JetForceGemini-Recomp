#include "jfg/renderer/rt64_callbacks.hpp"

namespace jfg {

Rt64GraphicsBackend::Rt64GraphicsBackend(
    Rt64Shell& shell,
    const std::span<const BoundedGraphicsMemoryWindow> windows,
    const std::uint32_t rdram_region_id,
    const Rt64GraphicsTask task,
    const Rt64MemoryLayout memory_layout) noexcept
    : shell_(shell),
      rdram_region_id_(rdram_region_id),
      task_(task),
      memory_layout_(memory_layout) {
    if (windows.empty() || windows.size() > windows_.size()) {
        return;
    }
    bool has_full_rdram = false;
    for (std::size_t index = 0U; index < windows.size(); ++index) {
        windows_[index] = windows[index];
        if (windows[index].region_id == rdram_region_id_ &&
            windows[index].target_base == 0U &&
            windows[index].byte_count == kRt64RequiredRdramBytes) {
            has_full_rdram = true;
        }
    }
    window_count_ = windows.size();
    valid_ = has_full_rdram;
}

GraphicsBackendCapabilities Rt64GraphicsBackend::capabilities() const {
    return {
        GraphicsFamily::bounded_custom,
        GraphicsOutputKind::semantic_submission,
        kGraphicsBaseCustomHandlerCount,
        kGraphicsVariantOverrideCount,
        true,
        true,
    };
}

GraphicsBackendReport Rt64GraphicsBackend::execute(
    const GraphicsTaskView& task,
    GraphicsMemoryBroker& memory) {
    last_rt64_error_ = Rt64ShellError::none;
    if (!valid_) {
        return {};
    }
    BoundedCustomGraphicsBackend parser(
        std::span<const BoundedGraphicsMemoryWindow>(
            windows_.data(), window_count_),
        task_.command_address,
        semantic_renderer_);
    GraphicsBackendReport report = parser.execute(task, memory);
    if (!report.accepted || !report.parse_complete ||
        report.unsupported_command_count != 0U) {
        return report;
    }

    const std::span<const std::byte> rdram = memory.read(
        rdram_region_id_, 0U, kRt64RequiredRdramBytes);
    if (rdram.size() != kRt64RequiredRdramBytes) {
        return {};
    }
    last_rt64_error_ = shell_.replace_rdram_snapshot(rdram, memory_layout_);
    if (last_rt64_error_ != Rt64ShellError::none) {
        return {};
    }
    last_rt64_error_ = shell_.submit(task_);
    if (last_rt64_error_ != Rt64ShellError::none) {
        return {};
    }
    return report;
}

Rt64ShellError Rt64GraphicsBackend::last_rt64_error() const noexcept {
    return last_rt64_error_;
}

Rt64RendererCallbacks::Rt64RendererCallbacks(
    Rt64Shell& shell,
    Rt64GraphicsBackend& backend,
    GraphicsOutputOracle& oracle,
    GraphicsCompletionSink& completion) noexcept
    : shell_(shell),
      backend_(backend),
      oracle_(oracle),
      completion_(completion) {}

GraphicsTaskBackend& Rt64RendererCallbacks::task_backend() noexcept {
    return backend_;
}

GraphicsOutputOracle& Rt64RendererCallbacks::output_oracle() noexcept {
    return oracle_;
}

GraphicsCompletionSink& Rt64RendererCallbacks::completion_sink() noexcept {
    return completion_;
}

bool Rt64RendererCallbacks::present() {
    return shell_.present() == Rt64ShellError::none;
}

}  // namespace jfg
