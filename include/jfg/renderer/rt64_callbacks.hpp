#pragma once

#include "jfg/renderer/rt64_shell.hpp"
#include "jfg/runtime/bounded_custom_graphics.hpp"
#include "jfg/runtime/renderer_callbacks.hpp"

#include <array>
#include <cstddef>
#include <cstdint>
#include <span>

namespace jfg {

// Runs the bounded, fail-closed family parser first, then submits the same
// brokered RDRAM snapshot to RT64. Its output remains a semantic stream; pixel
// capture and visual acceptance are deliberately separate Phase 7 gates.
class Rt64GraphicsBackend final : public GraphicsTaskBackend {
public:
    Rt64GraphicsBackend(
        Rt64Shell& shell,
        std::span<const BoundedGraphicsMemoryWindow> windows,
        std::uint32_t rdram_region_id,
        Rt64GraphicsTask task,
        Rt64MemoryLayout memory_layout) noexcept;

    [[nodiscard]] GraphicsBackendCapabilities capabilities() const override;
    [[nodiscard]] GraphicsBackendReport execute(
        const GraphicsTaskView& task,
        GraphicsMemoryBroker& memory) override;
    [[nodiscard]] Rt64ShellError last_rt64_error() const noexcept;

private:
    Rt64Shell& shell_;
    std::array<BoundedGraphicsMemoryWindow,
        kMaximumGraphicsReferencedRegionCount> windows_{};
    std::size_t window_count_ = 0U;
    std::uint32_t rdram_region_id_ = 0U;
    Rt64GraphicsTask task_{};
    Rt64MemoryLayout memory_layout_ = Rt64MemoryLayout::big_endian;
    BoundedGraphicsSemanticRenderer semantic_renderer_;
    Rt64ShellError last_rt64_error_ = Rt64ShellError::none;
    bool valid_ = false;
};

class Rt64RendererCallbacks final : public RendererCallbacks {
public:
    Rt64RendererCallbacks(
        Rt64Shell& shell,
        Rt64GraphicsBackend& backend,
        GraphicsOutputOracle& oracle,
        GraphicsCompletionSink& completion) noexcept;

    [[nodiscard]] GraphicsTaskBackend& task_backend() noexcept override;
    [[nodiscard]] GraphicsOutputOracle& output_oracle() noexcept override;
    [[nodiscard]] GraphicsCompletionSink& completion_sink() noexcept override;
    [[nodiscard]] bool present() override;

private:
    Rt64Shell& shell_;
    Rt64GraphicsBackend& backend_;
    GraphicsOutputOracle& oracle_;
    GraphicsCompletionSink& completion_;
};

}  // namespace jfg
