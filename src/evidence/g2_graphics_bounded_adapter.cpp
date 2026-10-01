#include "jfg/evidence/g2_private_task_adapter.hpp"
#include "jfg/runtime/bounded_custom_graphics.hpp"

#include <algorithm>
#include <array>
#include <cstddef>
#include <cstdint>
#include <new>
#include <ranges>
#include <span>

namespace {

[[nodiscard]] std::uint32_t be32(
    const std::span<const std::byte> bytes,
    const std::size_t offset) noexcept {
    if (offset > bytes.size() || bytes.size() - offset < 4U) {
        return 0U;
    }
    return (std::to_integer<std::uint32_t>(bytes[offset]) << 24U) |
        (std::to_integer<std::uint32_t>(bytes[offset + 1U]) << 16U) |
        (std::to_integer<std::uint32_t>(bytes[offset + 2U]) << 8U) |
        std::to_integer<std::uint32_t>(bytes[offset + 3U]);
}

class ProjectBoundedGraphicsBackend final
    : public jfg::evidence::G2PrivateGraphicsBackend {
public:
    ProjectBoundedGraphicsBackend(
        const std::uint32_t program_address,
        const std::uint32_t command_address) noexcept
        : program_address_(program_address),
          windows_{{{
              0U, 0U, jfg::kBoundedGraphicsAddressSpaceBytes}}},
          backend_(windows_, command_address, renderer_) {
        stats_.abi_version = jfg::evidence::kG2PrivateTaskAdapterAbiVersion;
    }

    [[nodiscard]] jfg::GraphicsBackendCapabilities capabilities()
        const override {
        return backend_.capabilities();
    }

    [[nodiscard]] jfg::GraphicsBackendReport execute(
        const jfg::GraphicsTaskView& task,
        jfg::GraphicsMemoryBroker& memory) override {
        if (task.active_program.empty() ||
            program_address_ >= jfg::kBoundedGraphicsAddressSpaceBytes ||
            task.active_program.size() >
                jfg::kBoundedGraphicsAddressSpaceBytes - program_address_) {
            return {};
        }
        const std::span<const std::byte> brokered_program = memory.read(
            0U, program_address_, task.active_program.size());
        if (brokered_program.size() != task.active_program.size() ||
            !std::ranges::equal(brokered_program, task.active_program)) {
            return {};
        }
        ++stats_.program_identity_check_count;
        stats_.active_program_sha256 =
            jfg::evidence::g2_private_program_digest(task.active_program);
        ++stats_.backend_execution_count;
        return backend_.execute(task, memory);
    }

    [[nodiscard]] jfg::evidence::G2PrivateGraphicsBackendStats stats()
        const noexcept override {
        return stats_;
    }

private:
    std::uint32_t program_address_ = 0U;
    std::array<jfg::BoundedGraphicsMemoryWindow, 1U> windows_{};
    jfg::BoundedGraphicsSemanticRenderer renderer_;
    jfg::BoundedCustomGraphicsBackend backend_;
    jfg::evidence::G2PrivateGraphicsBackendStats stats_{};
};

}  // namespace

extern "C" jfg::evidence::G2PrivateGraphicsBackend*
jfg_g2_graphics_bounded_backend_v2(
    const jfg::evidence::G2PrivateGraphicsBackendInput& input) noexcept {
    if (input.task_descriptor.size() != 64U ||
        input.command_stream_address >= jfg::kBoundedGraphicsAddressSpaceBytes) {
        return nullptr;
    }
    return new (std::nothrow) ProjectBoundedGraphicsBackend(
        be32(input.task_descriptor, 16U) &
            (jfg::kBoundedGraphicsAddressSpaceBytes - 1U),
        input.command_stream_address);
}
