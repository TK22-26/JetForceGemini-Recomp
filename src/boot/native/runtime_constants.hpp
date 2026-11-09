#pragma once
#include <array>
#include <cstddef>
#include <cstdint>

namespace jfg::boot::native::detail {
inline constexpr std::size_t kRomSize = 32U * 1024U * 1024U;
inline constexpr std::size_t kRdramSize = 4U * 1024U * 1024U;
inline constexpr std::size_t kKseg1AliasOffset = 0x20000000U;
inline constexpr std::size_t kCartCachedAliasOffset = 0x10000000U;
inline constexpr std::size_t kCartUncachedAliasOffset = 0x30000000U;
inline constexpr std::size_t kGuestAddressSpan = 0x8A000000U;
inline constexpr std::size_t kMmioPageSize = 0x1000U;
inline constexpr std::size_t kWindowsAllocationGranularity = 0x10000U;
inline constexpr std::array<std::size_t, 12U> kMmioHostOffsets = {
    0x24040000U, 0x24100000U, 0x24300000U, 0x24400000U,
    0x24500000U, 0x24600000U, 0x24700000U, 0x24800000U,
    0x24080000U, 0x3fc00000U, 0x28000000U, 0x28010000U,
};
inline constexpr std::array<std::uint32_t, 12U> kMmioGuestBases = {
    0xA4040000U, 0xA4100000U, 0xA4300000U, 0xA4400000U,
    0xA4500000U, 0xA4600000U, 0xA4700000U, 0xA4800000U,
    0xA4080000U, 0xbfc00000U, 0xa8000000U, 0xa8010000U,
};
inline constexpr std::array<std::uint32_t, 12U> kMmioLastRegister = {
    0x1CU, 0x1CU, 0x0CU, 0x34U, 0x14U, 0x30U, 0x1CU, 0x1CU, 0U, 0x7fcU, 0U, 0U,
};

} // namespace jfg::boot::native::detail
