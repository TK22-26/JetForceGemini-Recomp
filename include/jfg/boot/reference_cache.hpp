#pragma once
#include <cstdint>

namespace jfg::boot {
// Explicit reference profile, NOT a VR4300 hardware cache. The caller owns
// already coherent CPU memory and publishes validated generated overlay code.
// No dirty CPU lines exist in this model, so these maintenance instructions
// have no additional RAM transfer. It does not provide tag registers, cache
// misses/bus timing, or arbitrary self-modifying generated code. GPU writeback
// remains a separate ownership/commit operation; this does not replace it.
// Selector encodings: NEC VR4300 manual, chapter 17, CACHE instruction.
constexpr bool reference_coherent_cache_operation(std::uint32_t operation,
                                                  std::uint64_t address,
                                                  std::uint32_t rdram_size) {
  const auto low = static_cast<std::uint32_t>(address);
  const auto extended = static_cast<std::uint64_t>(static_cast<std::int64_t>(
      static_cast<std::int32_t>(low)));
  // Only the cached direct-mapped addresses qualified by the private probe.
  if (address != extended || (low & 0xe0000000U) != 0x80000000U ||
      (low & 0x1fffffffU) >= rdram_size) return false;
  switch (operation) {
  case 0:  // Index invalidate instruction.
  case 1:  // Index writeback/invalidate data.
  case 16: // Hit invalidate instruction.
  case 17: // Hit invalidate data.
  case 21: // Hit writeback/invalidate data.
  case 25: // Hit writeback data.
    return true;
  default:
    return false;
  }
}
} // namespace jfg::boot
