#pragma once

// Independently authored bounded corrected-Mupen SI/PIF profile. The phased
// probe qualifies immediate 64-byte copies, status=0 while awaiting completion,
// status=0x1000 on completion, and a 2304-Count interrupt delay. Controller
// status and pad-read packets only; unsupported protocols fail atomically.
#include <array>
#include <cstdint>
#include <optional>
#include <span>
#include "jfg/runtime/cic_nus_6105.hpp"

namespace jfg::boot {
class ReferenceSiDma final {
public:
  void sample(std::uint16_t buttons, std::int8_t x, std::int8_t y, bool connected) {
    buttons_ = buttons; x_ = x; y_ = y; connected_ = connected;
  }
  [[nodiscard]] std::optional<std::uint32_t> read(std::uint32_t offset) const {
    switch (offset) {
    case 0: return dram_;
    case 4: return read_address_;
    case 16: return write_address_;
    case 24: return interrupt_ ? 0x1000U : 0U;
    default: return std::nullopt;
    }
  }
  bool boot_command(std::uint64_t count) {
    if (deadline_ || count > UINT64_MAX - 2304U) return false;
    deadline_ = count + 2304U;
    return true;
  }
  bool write(std::uint32_t offset, std::uint32_t value, std::uint64_t count,
             std::span<std::uint8_t> rdram) {
    if (offset == 0) { dram_ = value; return true; }
    if (offset == 24) { interrupt_ = false; return true; }
    if ((offset != 4 && offset != 16) || value != 0x1fc007c0U ||
        (dram_ & 3U) != 0U || dram_ > rdram.size() || 64U > rdram.size() - dram_ ||
        count > UINT64_MAX - 2304U) return false;
    auto ram = pif_;
    auto controller = controller_;
    if (offset == 16) {
      for (unsigned i = 0; i < 64; ++i) ram[i] = rdram[(dram_ + i) ^ 3U];
      if (ram[63] > 2U) return false;
      controller = ram[63] == 1U;
      if (controller && !packets(ram, false)) return false;
      if (ram[63] == 2U && !jfg::process_cic_nus_6105_challenge(ram)) return false;
      ram[63] = 0;
    } else {
      if (controller && !packets(ram, true)) return false;
      for (unsigned i = 0; i < 64; ++i) rdram[(dram_ + i) ^ 3U] = ram[i];
    }
    pif_ = ram;
    controller_ = controller;
    if (offset == 4) read_address_ = value; else write_address_ = value;
    // Back-to-back DMAs still perform each copy/PIF operation immediately.
    // The reference coalesces their completion into the first pending SI
    // event (all four read/write pairs qualified independently).
    if (!deadline_) deadline_ = count + 2304U;
    ++transfers_;
    return true;
  }
  void advance(std::uint64_t count) {
    if (deadline_ && count >= *deadline_) { deadline_.reset(); interrupt_ = true; }
  }
  [[nodiscard]] bool interrupt() const { return interrupt_; }
  [[nodiscard]] std::optional<std::uint64_t> deadline() const { return deadline_; }
  [[nodiscard]] std::uint64_t transfers() const { return transfers_; }
  [[nodiscard]] const std::array<std::uint8_t, 64>& pif() const { return pif_; }
private:
  bool packets(std::array<std::uint8_t, 64>& ram, bool reply) const {
    unsigned cursor = 0, channel = 0, commands = 0;
    while (cursor < 63) {
      const auto tx = ram[cursor];
      if (tx == 0xfe) return commands != 0U;
      if (tx == 0xff) { ++cursor; continue; }
      if (tx == 0) { ++cursor; ++channel; continue; }
      if (channel >= 4 || tx != 1 || cursor + 3 > 63) return false;
      const auto rx = ram[cursor + 1] & 0x3fU;
      const auto command = ram[cursor + 2];
      if (cursor + 3 + rx > 63 ||
          !((rx == 3 && (command == 0 || command == 0xff)) || (rx == 4 && command == 1))) return false;
      const bool connected = channel == 0 && connected_;
      ram[cursor + 1] = static_cast<std::uint8_t>(rx | (connected ? 0U : 0x80U));
      if (connected && reply) {
        if (rx == 3) {
          ram[cursor + 3] = 5; ram[cursor + 4] = 0; ram[cursor + 5] = 0;
        } else {
          ram[cursor + 3] = static_cast<std::uint8_t>(buttons_ >> 8);
          ram[cursor + 4] = static_cast<std::uint8_t>(buttons_);
          ram[cursor + 5] = static_cast<std::uint8_t>(x_);
          ram[cursor + 6] = static_cast<std::uint8_t>(y_);
        }
      }
      cursor += 3 + rx; ++channel; ++commands;
    }
    return false;
  }
  std::array<std::uint8_t, 64> pif_{};
  std::optional<std::uint64_t> deadline_;
  std::uint32_t dram_ = 0, read_address_ = 0, write_address_ = 0;
  std::uint64_t transfers_ = 0;
  std::uint16_t buttons_ = 0;
  std::int8_t x_ = 0, y_ = 0;
  bool controller_ = false, interrupt_ = false, connected_ = true;
};
} // namespace jfg::boot
