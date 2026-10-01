#pragma once

#include "jfg/runtime/graphics_task_bridge.hpp"

#include <array>
#include <cstddef>
#include <cstdint>
#include <span>
#include <vector>

namespace jfg {

inline constexpr std::uint32_t kBoundedGraphicsAddressSpaceBytes =
    8U * 1024U * 1024U;
inline constexpr std::size_t kBoundedGraphicsDisplayListStackDepth = 10U;
inline constexpr std::size_t kBoundedGraphicsVertexCapacity = 80U;
inline constexpr std::size_t kBoundedGraphicsMatrixCapacity = 32U;
inline constexpr std::size_t kBoundedGraphicsSemanticRecordBytes = 32U;

struct BoundedGraphicsMemoryWindow {
    std::uint32_t region_id = 0U;
    std::uint32_t target_base = 0U;
    std::size_t byte_count = 0U;
};

struct BoundedGraphicsCommand {
    std::uint32_t word0 = 0U;
    std::uint32_t word1 = 0U;
};

enum class BoundedGraphicsEventKind : std::uint8_t {
    base_command = 1U,
    display_list = 2U,
    end_display_list = 3U,
    dma_matrix = 4U,
    dma_texture_offset = 5U,
    dma_vertex = 6U,
    dma_triangles = 7U,
    dma_display_list = 8U,
    dma_offsets = 9U,
    billboard = 10U,
    model_matrix_select = 11U,
};

struct BoundedGraphicsRendererEvent {
    BoundedGraphicsEventKind kind = BoundedGraphicsEventKind::base_command;
    std::array<BoundedGraphicsCommand, 4U> commands{};
    std::size_t command_count = 0U;
    std::uint32_t argument0 = 0U;
    std::uint32_t argument1 = 0U;
    std::uint32_t argument2 = 0U;
};

class BoundedGraphicsMemoryReader final {
public:
    BoundedGraphicsMemoryReader(const BoundedGraphicsMemoryReader&) = delete;
    BoundedGraphicsMemoryReader& operator=(
        const BoundedGraphicsMemoryReader&) = delete;
    BoundedGraphicsMemoryReader(BoundedGraphicsMemoryReader&&) = delete;
    BoundedGraphicsMemoryReader& operator=(
        BoundedGraphicsMemoryReader&&) = delete;

    [[nodiscard]] std::span<const std::byte> read(
        std::uint32_t target_address,
        std::size_t length) noexcept;
    [[nodiscard]] bool failed() const noexcept;

private:
    friend class BoundedCustomGraphicsBackend;

    BoundedGraphicsMemoryReader(
        GraphicsMemoryBroker& broker,
        std::span<const BoundedGraphicsMemoryWindow> windows) noexcept;

    void poison_broker() noexcept;

    GraphicsMemoryBroker& broker_;
    std::span<const BoundedGraphicsMemoryWindow> windows_;
    bool failed_ = false;
};

class BoundedCustomGraphicsRenderer {
public:
    virtual ~BoundedCustomGraphicsRenderer() = default;

    [[nodiscard]] virtual bool begin() = 0;
    [[nodiscard]] virtual bool submit(
        const BoundedGraphicsRendererEvent& event,
        std::span<const std::byte> payload,
        BoundedGraphicsMemoryReader& memory) = 0;
    [[nodiscard]] virtual GraphicsOutputView finish(
        std::size_t parsed_command_count) = 0;
    virtual void abort() noexcept = 0;
};

// A deterministic renderer-owned semantic submission stream. It is useful for
// exact private oracle comparison and adapter testing, but it is not a pixel or
// visual-correctness oracle.
class BoundedGraphicsSemanticRenderer final
    : public BoundedCustomGraphicsRenderer {
public:
    [[nodiscard]] bool begin() override;
    [[nodiscard]] bool submit(
        const BoundedGraphicsRendererEvent& event,
        std::span<const std::byte> payload,
        BoundedGraphicsMemoryReader& memory) override;
    [[nodiscard]] GraphicsOutputView finish(
        std::size_t parsed_command_count) override;
    void abort() noexcept override;

private:
    std::vector<std::byte> output_;
    std::size_t submitted_command_count_ = 0U;
    bool active_ = false;
    bool failed_ = false;
};

// Project-owned bounded parser for the reviewed custom family. The parser
// implements its seven custom handlers and one vertex-count variant, delegates
// only a fixed allowlist of shared base-family commands, and rejects malformed
// state, address, stack, count, renderer, and unknown-command cases.
class BoundedCustomGraphicsBackend final : public GraphicsTaskBackend {
public:
    BoundedCustomGraphicsBackend(
        std::span<const BoundedGraphicsMemoryWindow> windows,
        std::uint32_t command_stream_target_address,
        BoundedCustomGraphicsRenderer& renderer) noexcept;

    [[nodiscard]] GraphicsBackendCapabilities capabilities() const override;
    [[nodiscard]] GraphicsBackendReport execute(
        const GraphicsTaskView& task,
        GraphicsMemoryBroker& memory) override;

private:
    std::array<BoundedGraphicsMemoryWindow,
        kMaximumGraphicsReferencedRegionCount> windows_{};
    std::size_t window_count_ = 0U;
    std::uint32_t command_stream_target_address_ = 0U;
    BoundedCustomGraphicsRenderer& renderer_;
    bool windows_valid_ = false;
};

}  // namespace jfg
