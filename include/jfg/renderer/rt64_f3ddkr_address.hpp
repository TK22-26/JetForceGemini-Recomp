#pragma once

#include <cstddef>
#include <cstdint>

namespace jfg::detail {

struct F3ddkrMatrixCommand final {
    std::uint8_t index = 0U;
    bool multiply = false;
};

[[nodiscard]] constexpr F3ddkrMatrixCommand decode_f3ddkr_matrix_command(
    const std::uint32_t word0) noexcept {
    const auto low_index = static_cast<std::uint8_t>((word0 >> 16U) & 0x0FU);
    if (low_index == 0U) {
        return {
            static_cast<std::uint8_t>((word0 >> 22U) & 0x03U),
            false,
        };
    }
    return {
        low_index,
        (word0 & 0x0080'0000U) != 0U,
    };
}

inline constexpr std::uint32_t kF3ddkrGuestRdramBytes =
    4U * 1024U * 1024U;
inline constexpr std::uint32_t kF3ddkrRt64SnapshotBytes =
    8U * 1024U * 1024U;
inline constexpr std::uint32_t kF3ddkrRt64ByteAddressMask = 0x007F'FFFFU;
inline constexpr std::uint32_t kF3ddkrRt64RdramMask = 0x007F'FFF8U;
// RT64's segmented translation retains 24 physical bits and can exceed them
// when a segment base and offset sum past 16 MiB. Any resolution outside the
// physical range the masks below are documented for is reported with this
// sentinel so that every caller's range check fails closed instead of the
// mask silently aliasing the address into valid-looking snapshot bytes.
inline constexpr std::uint32_t kF3ddkrInvalidAddress = 0xFFFF'FFFFU;
inline constexpr std::uint32_t kF3ddkrMaximumResolvedAddress = 0x00FF'FFFFU;

// RT64 stores G_MW_SEGMENT bases unmasked, so a resolved address is a MIPS
// virtual address: JFG programs segment bases with KSEG0 pointers. Accept the
// direct, KSEG0, and KSEG1 windows and report every other segment or any
// physical offset past the 24-bit RSP DMA range as invalid.
[[nodiscard]] constexpr std::uint32_t f3ddkr_physical_from_resolved(
    const std::uint32_t resolved_address) noexcept {
    const std::uint32_t segment = resolved_address & 0xE000'0000U;
    if (segment != 0U && segment != 0x8000'0000U && segment != 0xA000'0000U)
        return kF3ddkrInvalidAddress;
    const std::uint32_t physical = resolved_address & 0x1FFF'FFFFU;
    if (physical > kF3ddkrMaximumResolvedAddress)
        return kF3ddkrInvalidAddress;
    return physical;
}

// JFG's DMA texture-offset tables hold 40 u16 shifts (0x50 bytes). The game
// keeps them double-buffered back to back, 0x50 bytes apart. A texture image
// after the 40th entry must not read past the table: that slot is the other
// buffer's first shift, which loads the next texture from the wrong address.
inline constexpr std::size_t kF3ddkrTextureOffsetEntries = 40U;

[[nodiscard]] constexpr bool f3ddkr_texture_offset_entry_available(
    const std::size_t texture_count) noexcept {
    return texture_count < kF3ddkrTextureOffsetEntries;
}

[[nodiscard]] constexpr std::uint32_t resolve_f3ddkr_byte_source(
    const std::uint32_t resolved_address) noexcept {
    return resolved_address & kF3ddkrRt64ByteAddressMask;
}

// Rare's DMA commands apply the RSP's physical-address mask after segmented
// translation. RT64's stock helper retains 24 physical bits, while the Phase
// 8 task snapshot is an 8 MiB aperture. Keeping the wider result rejects valid
// upper-half overlay payloads such as 0x00E012A0 instead of selecting their
// materialized 0x006012A0 source.
[[nodiscard]] constexpr std::uint32_t resolve_f3ddkr_direct_dma_source(
    const std::uint32_t resolved_address) noexcept {
    const std::uint32_t physical =
        f3ddkr_physical_from_resolved(resolved_address);
    if (physical == kF3ddkrInvalidAddress)
        return kF3ddkrInvalidAddress;
    return physical & kF3ddkrRt64RdramMask;
}

// Phase 8 places immutable overlay payloads in the upper half of RT64's
// private 8 MiB snapshot because JFG itself uses 4 MiB RDRAM. Those shadow
// addresses are already absolute. F3DDKR's task DMA offset applies only to
// original guest addresses; adding it again silently points vertex/matrix
// reads at unrelated snapshot bytes.
[[nodiscard]] constexpr std::uint32_t resolve_f3ddkr_dma_base(
    const std::uint32_t resolved_address,
    const std::uint32_t dma_offset) noexcept {
    const std::uint32_t physical =
        f3ddkr_physical_from_resolved(resolved_address);
    if (physical == kF3ddkrInvalidAddress)
        return kF3ddkrInvalidAddress;
    if (physical >= kF3ddkrGuestRdramBytes)
        return resolve_f3ddkr_direct_dma_source(physical);
    // The task offset is a 24-bit field; its sum with a 4 MiB guest address
    // can exceed the 8 MiB snapshot, where the physical mask would wrap it
    // onto unrelated bytes. Report that as invalid instead.
    const std::uint32_t sum = dma_offset + physical;
    if (sum < physical || sum >= kF3ddkrRt64SnapshotBytes)
        return kF3ddkrInvalidAddress;
    return resolve_f3ddkr_direct_dma_source(sum);
}

[[nodiscard]] constexpr std::uint32_t resolve_f3ddkr_vertex_dma_source(
    const std::uint32_t resolved_address,
    const std::uint32_t dma_offset,
    const std::uint32_t command_word0) noexcept {
    // F3DDKR preserves the even byte offset discarded by the RSP's eight-byte
    // DMA alignment in bits 17-18 of the command parameter.
    const std::uint32_t base =
        resolve_f3ddkr_dma_base(resolved_address, dma_offset);
    if (base == kF3ddkrInvalidAddress)
        return kF3ddkrInvalidAddress;
    return base + ((command_word0 >> 16U) & 0x06U);
}

}  // namespace jfg::detail
