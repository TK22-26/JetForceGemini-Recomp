#pragma once

#include <array>
#include <cstddef>
#include <cstdint>

namespace jfg {

// Status/reset packets only. Commit atomically so unsupported input/read/Pak
// commands continue through their existing path without partially changed RAM.
inline bool process_controller_status_query(
    std::array<std::uint8_t, 64> &ram, std::uint8_t connected_mask = 1) {
  if (ram[63] != 1) return false;
  auto reply = ram;
  std::size_t cursor = 0, channel = 0, commands = 0;
  while (cursor < 63) {
    const auto tx = ram[cursor];
    if (tx == 0xfe) {
      if (commands == 0) return false;
      reply[63] = 0;
      ram = reply;
      return true;
    }
    if (tx == 0xff) { ++cursor; continue; }
    if (tx == 0) { ++cursor; ++channel; continue; }
    if (channel >= 4 || cursor + 6 > 63 || tx != 1 ||
        ram[cursor + 1] != 3 ||
        (ram[cursor + 2] != 0 && ram[cursor + 2] != 0xff)) return false;
    if ((connected_mask & (1U << channel)) != 0) {
      reply[cursor + 3] = 5;
      reply[cursor + 4] = 0;
      reply[cursor + 5] = 0; // Same no-accessory status as existing osContInit.
    } else {
      reply[cursor + 1] |= 0x80;
    }
    cursor += 6;
    ++channel;
    ++commands;
  }
  return false;
}

} // namespace jfg
