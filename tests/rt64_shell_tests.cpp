#include "jfg/renderer/rt64_shell.hpp"
#include "jfg/renderer/rt64_f3ddkr_address.hpp"

#include <algorithm>
#include <array>
#include <cstddef>
#include <cstdlib>
#include <vector>

namespace {

void require(const bool condition) {
    if (!condition) {
        std::abort();
    }
}

}  // namespace

int main() {
    static_assert(jfg::kRt64RequiredRdramBytes == 8U * 1024U * 1024U);
    require(jfg::kPinnedRt64Revision[0] == '5');
    require(jfg::detail::resolve_f3ddkr_dma_base(
        0x0012'3457U, 0x0000'0100U) == 0x0012'3550U);
    require(jfg::detail::resolve_f3ddkr_dma_base(
        0x0047'5BC6U, 0x0010'0000U) == 0x0047'5BC0U);
    require(jfg::detail::resolve_f3ddkr_direct_dma_source(
        0x00E0'12A0U) == 0x0060'12A0U);
    require(jfg::detail::resolve_f3ddkr_direct_dma_source(
        0x00A5'C4B0U) == 0x0025'C4B0U);
    require(jfg::detail::resolve_f3ddkr_byte_source(
        0x00E0'12A7U) == 0x0060'12A7U);
    require(jfg::detail::resolve_f3ddkr_vertex_dma_source(
        0x0018'0CDEU, 0x0011'3000U, 0x0426'0050U) == 0x0029'3CDEU);
    require(jfg::detail::resolve_f3ddkr_vertex_dma_source(
        0x0047'5BC6U, 0x0010'0000U, 0x0426'0050U) == 0x0047'5BC6U);
    // Resolutions that would previously have been masked onto valid-looking
    // snapshot bytes now report the invalid sentinel so callers fail closed.
    require(jfg::detail::resolve_f3ddkr_direct_dma_source(
        0x0100'0000U) == jfg::detail::kF3ddkrInvalidAddress);
    // Segment bases are stored as KSEG0 pointers; KSEG0/KSEG1 strip cleanly
    // while other MIPS segments are rejected.
    require(jfg::detail::resolve_f3ddkr_direct_dma_source(
        0x800A'3658U) == 0x000A'3658U);
    require(jfg::detail::resolve_f3ddkr_direct_dma_source(
        0xA00A'3658U) == 0x000A'3658U);
    require(jfg::detail::resolve_f3ddkr_direct_dma_source(
        0xC00A'3658U) == jfg::detail::kF3ddkrInvalidAddress);
    require(jfg::detail::resolve_f3ddkr_dma_base(
        0x800A'3658U, 0x100U) == 0x000A'3758U);
    require(jfg::detail::resolve_f3ddkr_direct_dma_source(
        0x00FF'FFF8U) == 0x007F'FFF8U);
    require(jfg::detail::resolve_f3ddkr_dma_base(
        0x0100'0100U, 0U) == jfg::detail::kF3ddkrInvalidAddress);
    require(jfg::detail::resolve_f3ddkr_dma_base(
        0x003F'FF00U, 0x00C0'0000U) == jfg::detail::kF3ddkrInvalidAddress);
    require(jfg::detail::resolve_f3ddkr_dma_base(
        0x003F'FF00U, 0x0040'0000U) == 0x007F'FF00U);
    require(jfg::detail::resolve_f3ddkr_vertex_dma_source(
        0x003F'FF00U, 0x00C0'0000U, 0x0426'0050U) ==
        jfg::detail::kF3ddkrInvalidAddress);
    const auto common_matrix =
        jfg::detail::decode_f3ddkr_matrix_command(0x01C0'0040U);
    require(common_matrix.index == 3U);
    require(!common_matrix.multiply);
    const auto alternate_matrix =
        jfg::detail::decode_f3ddkr_matrix_command(0x0182'0040U);
    require(alternate_matrix.index == 2U);
    require(alternate_matrix.multiply);

    std::array<std::byte, jfg::kRt64RequiredHeaderBytes> header{};
    std::vector<std::byte> rdram(jfg::kRt64RequiredRdramBytes);
    jfg::Rt64ViRegisters vi;
    jfg::Rt64ShellConfiguration configuration{
        reinterpret_cast<void*>(1U),
        0U,
        header,
        rdram,
        &vi,
        false,
        jfg::Rt64MemoryLayout::big_endian,
    };

    require(jfg::validate_rt64_shell_configuration(configuration) ==
        jfg::Rt64ShellError::none);
    configuration.native_window = nullptr;
    require(jfg::validate_rt64_shell_configuration(configuration) ==
        jfg::Rt64ShellError::invalid_window);
    configuration.native_window = reinterpret_cast<void*>(1U);
    configuration.rdram = std::span<const std::byte>(
        rdram.data(), rdram.size() - 1U);
    require(jfg::validate_rt64_shell_configuration(configuration) ==
        jfg::Rt64ShellError::invalid_memory);
    configuration.rdram = rdram;
    rdram[0U] = std::byte{0x01};
    rdram[1U] = std::byte{0x02};
    rdram[2U] = std::byte{0x03};
    rdram[3U] = std::byte{0x04};
    std::vector<std::byte> converted(jfg::kRt64RequiredRdramBytes);
    require(jfg::copy_rt64_rdram_snapshot(
        rdram, converted, jfg::Rt64MemoryLayout::big_endian) ==
        jfg::Rt64ShellError::none);
    require(converted[0U] == std::byte{0x04});
    require(converted[1U] == std::byte{0x03});
    require(converted[2U] == std::byte{0x02});
    require(converted[3U] == std::byte{0x01});
    require(jfg::copy_rt64_rdram_snapshot(
        rdram, converted, jfg::Rt64MemoryLayout::host_word_swapped) ==
        jfg::Rt64ShellError::none);
    require(converted[0U] == std::byte{0x01});
    require(converted[3U] == std::byte{0x04});
    std::vector<std::byte> previous = converted;
    converted[4U] = std::byte{0xA5};
    converted[5U] = std::byte{0xA5};
    rdram[0U] = std::byte{0x01};
    rdram[4U] = std::byte{0x77};
    require(jfg::merge_rt64_rdram_snapshot(
        rdram, converted, previous,
        jfg::Rt64MemoryLayout::host_word_swapped) ==
        jfg::Rt64ShellError::none);
    require(converted[0U] == std::byte{0x01});
    require(converted[4U] == std::byte{0x77});
    require(previous[4U] == std::byte{0x77});
    require(converted[5U] == std::byte{0xA5});
    require(previous[5U] == std::byte{0x00});
    // Completed GPU ownership includes same-value writes; a CPU change in
    // any owned byte rejects the entire commit, never a partial snapshot.
    std::vector<std::byte> submitted(jfg::kRt64RequiredRdramBytes);
    std::vector<std::byte> rendered = submitted;
    std::vector<std::byte> live = submitted;
    const std::array<jfg::Rt64RdramRange, 2U> ranges = {{{2U, 5U}, {8U, 12U}}};
    rendered[2U ^ 3U] = std::byte{0xFA};
    rendered[4U ^ 3U] = std::byte{0xFB};
    rendered[8U ^ 3U] = std::byte{0xFC};
    rendered[20U] = std::byte{0xFF}; // Not a device-owned image byte.
    live[30U] = std::byte{0x77}; // New CPU state outside GPU ownership.
    live[9U ^ 3U] = std::byte{0x42}; // GPU wrote the SAME old value here.
    const auto unchanged = live;
    require(jfg::commit_rt64_rdram_ranges(submitted, rendered, live, ranges) ==
        jfg::Rt64ShellError::conflicting_cpu_write);
    require(live == unchanged);
    live[9U ^ 3U] = std::byte{0};
    require(jfg::commit_rt64_rdram_ranges(submitted, rendered, live, ranges) ==
        jfg::Rt64ShellError::none);
    require(live[2U ^ 3U] == std::byte{0xFA});
    require(live[4U ^ 3U] == std::byte{0xFB});
    require(live[8U ^ 3U] == std::byte{0xFC});
    require(live[20U] == std::byte{0});
    require(live[30U] == std::byte{0x77});
    // Base-RAM N64 runtime has 4 MiB; RT64's private allocation is 8 MiB.
    std::fill(live.begin(), live.end(), std::byte{0});
    require(jfg::commit_rt64_rdram_ranges(submitted, rendered,
        std::span(live).first(4U * 1024U * 1024U), ranges) == jfg::Rt64ShellError::none);
    const std::array<jfg::Rt64RdramRange, 1U> invalid = {{{0U, live.size() + 1U}}};
    require(jfg::commit_rt64_rdram_ranges(submitted, rendered, live, invalid) ==
        jfg::Rt64ShellError::invalid_memory);
    jfg::Rt64ViRegisters framebuffer_vi;
    framebuffer_vi.status = 0x0000'320EU;
    framebuffer_vi.origin = 0x0010'0000U;
    framebuffer_vi.width = 320U;
    framebuffer_vi.horizontal_start = 0x006C'02ECU;
    framebuffer_vi.vertical_start = 0x0025'01FFU;
    framebuffer_vi.x_scale = 0x0000'0200U;
    framebuffer_vi.y_scale = 0x0000'0400U;
    jfg::Rt64FramebufferInfo framebuffer;
    require(jfg::inspect_rt64_framebuffer(
        framebuffer_vi, rdram.size(), framebuffer) ==
        jfg::Rt64ShellError::none);
    require(framebuffer.address == 0x000F'FD80U);
    require(framebuffer.width == 320U);
    require(framebuffer.height == 240U);
    require(framebuffer.bytes_per_pixel == 2U);
    require(framebuffer.byte_count() == 320U * 240U * 2U);
    framebuffer_vi.origin = 0x007F'FF00U;
    require(jfg::inspect_rt64_framebuffer(
        framebuffer_vi, rdram.size(), framebuffer) ==
        jfg::Rt64ShellError::invalid_framebuffer);
    framebuffer_vi.origin = 0x0010'0000U;
    framebuffer_vi.y_scale = 0U;
    require(jfg::inspect_rt64_framebuffer(
        framebuffer_vi, rdram.size(), framebuffer) ==
        jfg::Rt64ShellError::invalid_framebuffer);
    std::array<std::byte, 16U> pixels{};
    require(jfg::Rt64FrameView{1U, 1U, 4U,
        std::span<const std::byte>(pixels.data(), 4U)}.valid());
    require(!jfg::Rt64FrameView{SIZE_MAX, 1U, SIZE_MAX,
        pixels}.valid());
    require(jfg::rt64_shell_error_message(
        jfg::Rt64ShellError::unsupported_microcode) != nullptr);
    return 0;
}
