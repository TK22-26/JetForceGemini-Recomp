#pragma once

#include <algorithm>
#include <cstdint>
#include <span>

namespace jfg::boot {

// Minimal retained IPL3 state for the admitted US/CIC-6105 cartridge.
// The reset runner starts at the cartridge entry, after IPL3 would have run.
// These words are read by the game's original RAM checks, and osCicId is read
// during player updates. Copy the residues from the user's validated ROM;
// keep the original checks and their failure behavior intact.
// Both spans use byte-linear, big-endian storage (before native-word conversion).
[[nodiscard]] inline bool initialize_6105_handoff(
    std::span<std::uint8_t> rdram,
    std::span<const std::uint8_t> rom) noexcept {
  if (rdram.size() < 0x400000U || rom.size() < 0x1000U)
    return false;
  std::copy_n(rom.begin() + 0x838U, 4U, rdram.begin() + 0x2e8U);
  std::copy_n(rom.begin() + 0x73cU, 4U, rdram.begin() + 0x2fb1f4U);
  std::copy_n(rom.begin() + 0x750U, 4U, rdram.begin() + 0x2fe1c0U);
  constexpr std::uint32_t cic_id = 6105U;
  for (unsigned lane = 0; lane < 4U; ++lane)
    rdram[0x310U + lane] =
        static_cast<std::uint8_t>(cic_id >> (24U - lane * 8U));
  return true;
}

} // namespace jfg::boot
