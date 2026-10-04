#pragma once
#include "jfg/boot/hle.hpp"
#include <array>
#include <cstdint>

namespace jfg::boot {
// US retail osSyncPrintf output callback. The symbol inventory omits this
// local leaf. It accepts formatted output without reading its buffer, spills
// its three arguments into the caller's ABI home area, and returns non-null.
// Qualify the exact loaded leaf before substituting it; unknown code still
// fails closed. These words describe instruction identity, not string data.
inline constexpr std::uint32_t kSyncPrintSink = 0x8009A710U;
inline constexpr std::array<std::uint32_t, 5> kSyncPrintSinkSignature{
    0xAFA40000U, 0xAFA50004U, 0xAFA60008U, 0x03E00008U, 0x24020001U};

template <typename Context>
[[nodiscard]] bool invoke_sync_print_sink(hle::GuestMemory &memory,
                                         Context &context) noexcept {
  for (std::uint32_t i = 0; i < kSyncPrintSinkSignature.size(); ++i) {
    std::uint32_t word = 0;
    if (!memory.read_u32(kSyncPrintSink + i * 4U, word) ||
        word != kSyncPrintSinkSignature[i]) return false;
  }
  const auto stack = static_cast<std::uint32_t>(context.r29);
  if ((stack & 3U) != 0U || stack > UINT32_MAX - 8U) return false;
  // Preflight the entire home area so rejection cannot partially write it.
  for (std::uint32_t offset = 0; offset < 12U; offset += 4U) {
    std::uint32_t unused = 0;
    if (!memory.read_u32(stack + offset, unused)) return false;
  }
  if (!memory.write_u32(stack, static_cast<std::uint32_t>(context.r4)) ||
      !memory.write_u32(stack + 4U, static_cast<std::uint32_t>(context.r5)) ||
      !memory.write_u32(stack + 8U, static_cast<std::uint32_t>(context.r6)))
    return false;
  context.r2 = 1U;
  return true;
}
} // namespace jfg::boot
