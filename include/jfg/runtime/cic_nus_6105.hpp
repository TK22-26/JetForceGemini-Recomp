#pragma once

#include <cstddef>
#include <cstdint>
#include <span>

namespace jfg {

inline constexpr std::size_t kPifRamBytes = 64U;

// Applies the CIC-NUS-6105 challenge response used when PIF RAM byte 63 is
// 0x02. Returns false without modifying the buffer for any other PIF command.
[[nodiscard]] bool process_cic_nus_6105_challenge(
    std::span<std::uint8_t, kPifRamBytes> pif_ram) noexcept;

} // namespace jfg
