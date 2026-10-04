#pragma once
#include "jfg/boot/hle.hpp"
#include <cstdint>

namespace jfg::boot {
inline constexpr std::uint32_t kSoundNextEvent = 0x8008B55CU;
inline constexpr std::uint32_t kSoundPlayerGlobal = 0x800A95ACU;

// US sound-player overflow recovery, after the original next-event routine.
// A full pool can drop the periodic event. Once its remaining events drain,
// the original player spins on NONE with a zero delay. Deliver one periodic
// event at the player's own interval so its next callback restarts the clock.
// Never change queue links, ordering, accounting, or another player's events.
template <typename Context>
[[nodiscard]] bool recover_empty_sound_queue(hle::GuestMemory &memory,
    Context &context, std::uint32_t queue, std::uint32_t event) noexcept {
  if (static_cast<std::uint32_t>(context.r2) != 0U) return false;
  std::uint32_t player = 0, callback = 0, head = 0, free = 0, counts = 0;
  std::uint32_t period = 0, type = 0, unused = 0;
  if (!memory.read_u32(kSoundPlayerGlobal, player) || (player & 3U) != 0U ||
      player < 0x80000000U || player > 0x807FFFA8U ||
      queue != player + 0x14U || event != player + 0x2CU ||
      !memory.read_u32(player + 8U, callback) || callback != 0x80084468U ||
      !memory.read_u32(callback, unused) || unused != 0x27BDFFD0U ||
      !memory.read_u32(callback + 4U, unused) || unused != 0xAFBF0014U ||
      !memory.read_u32(queue + 8U, head) || head != 0U ||
      !memory.read_u32(queue + 0x10U, counts) ||
      (counts >> 16U) != 0U || (counts & 0xFFFFU) == 0U ||
      !memory.read_u32(queue, free) || free < 0x80000000U || (free & 3U) != 0U ||
      !memory.read_u32(free, unused) ||
      !memory.read_u32(player + 0x4CU, period) || period == 0U ||
      period > 1000000U ||
      !memory.read_u32(event, type) || (type >> 16U) != 0xFFFFU)
    return false;
  // Preflight the complete event before changing memory; clear unused payload
  // so a discarded sound pointer cannot become this clock event's owner.
  for (std::uint32_t offset = 4U; offset < 16U; offset += 4U)
    if (!memory.read_u32(event + offset, unused)) return false;
  if (!memory.write_u32(event, 0x00200000U) ||
      !memory.write_u32(event + 4U, 0U) ||
      !memory.write_u32(event + 8U, 0U) ||
      !memory.write_u32(event + 12U, 0U)) return false;
  context.r2 = period;
  return true;
}
} // namespace jfg::boot
