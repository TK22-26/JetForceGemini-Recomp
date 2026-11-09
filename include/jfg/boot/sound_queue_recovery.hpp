#pragma once
#include "jfg/boot/hle.hpp"
#include <cstdint>

namespace jfg::boot {
// This common ABI is checked against original instructions in every revision
// by qualify_sound_queue_layout before native generation is admitted.
struct SoundQueueAbi {
  static constexpr std::uint32_t player_queue=0x14U,player_event=0x2cU,
    player_callback=8U,player_period=0x4cU,queue_head=8U,
    queue_counts=0x10U,queue_free=0U,event_bytes=16U;
};
struct SoundQueueLayout {
  std::uint32_t player_global,callback,entry_word,save_word;
};

// Qualified sound-player overflow recovery, after the original next-event routine.
// A full pool can drop the periodic event. Once its remaining events drain,
// the original player spins on NONE with a zero delay. Deliver one periodic
// event at the player's own interval so its next callback restarts the clock.
// Never change queue links, ordering, accounting, or another player's events.
template <typename Context>
[[nodiscard]] bool recover_empty_sound_queue(const SoundQueueLayout& layout, hle::GuestMemory &memory,
    Context &context, std::uint32_t queue, std::uint32_t event) noexcept {
  if (static_cast<std::uint32_t>(context.r2) != 0U) return false;
  std::uint32_t player = 0, callback = 0, head = 0, free = 0, counts = 0;
  std::uint32_t period = 0, type = 0, unused = 0;
  if (!memory.read_u32(layout.player_global, player) || (player & 3U) != 0U ||
      player < 0x80000000U || player > 0x807FFFA8U ||
      queue != player + SoundQueueAbi::player_queue || event != player + SoundQueueAbi::player_event ||
      !memory.read_u32(player + SoundQueueAbi::player_callback, callback) || callback != layout.callback ||
      !memory.read_u32(callback, unused) || unused != layout.entry_word ||
      !memory.read_u32(callback + 4U, unused) || unused != layout.save_word ||
      !memory.read_u32(queue + SoundQueueAbi::queue_head, head) || head != 0U ||
      !memory.read_u32(queue + SoundQueueAbi::queue_counts, counts) ||
      (counts >> 16U) != 0U || (counts & 0xFFFFU) == 0U ||
      !memory.read_u32(queue + SoundQueueAbi::queue_free, free) || free < 0x80000000U || (free & 3U) != 0U ||
      !memory.read_u32(free, unused) ||
      !memory.read_u32(player + SoundQueueAbi::player_period, period) || period == 0U ||
      period > 1000000U ||
      !memory.read_u32(event, type) || (type >> 16U) != 0xFFFFU)
    return false;
  // Preflight the complete event before changing memory; clear unused payload
  // so a discarded sound pointer cannot become this clock event's owner.
  for (std::uint32_t offset = 4U; offset < SoundQueueAbi::event_bytes; offset += 4U)
    if (!memory.read_u32(event + offset, unused)) return false;
  if (!memory.write_u32(event, 0x00200000U) ||
      !memory.write_u32(event + 4U, 0U) ||
      !memory.write_u32(event + 8U, 0U) ||
      !memory.write_u32(event + 12U, 0U)) return false;
  context.r2 = period;
  return true;
}
} // namespace jfg::boot
