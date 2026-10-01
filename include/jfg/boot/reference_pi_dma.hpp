#pragma once

// Independently authored corrected-Mupen PI ROM-read profile. The phased
// black-box probe observes immediate data visibility, retained address/length
// registers, busy=3 until completion, and length/8 Count timing as observed at
// CPU branch boundaries. This is not a hardware bus timing implementation.
#include <array>
#include <cstdint>
#include <optional>
#include <span>

namespace jfg::boot {
class ReferencePiDma final {
public:
  using CartridgeTransfer = bool (*)(void*, bool, std::uint32_t, std::uint32_t,
                                     std::uint32_t, std::span<std::uint8_t>);
  [[nodiscard]] std::optional<std::uint32_t> read(std::uint32_t offset) const {
    if ((offset & 3U) != 0U || offset > 0x30U) return std::nullopt;
    if (offset == 0x10U) return deadline_ ? busy_status_ : 0U;
    return registers_[offset / 4U];
  }
  bool write(std::uint32_t offset, std::uint32_t value, std::uint64_t count,
             std::span<std::uint8_t> rdram, std::span<const std::uint8_t> rom,
             CartridgeTransfer flash = nullptr, void* device = nullptr) {
    if ((offset & 3U) != 0U || offset > 0x30U) return false;
    if (offset == 0x10U) {
      if ((value & ~3U) != 0U) return false;
      if ((value & 1U) != 0U) deadline_.reset();
      if ((value & 2U) != 0U) interrupt_ = false;
      return true;
    }
    if (offset != 8U && offset != 12U) { registers_[offset / 4U] = value; return true; }
    const auto length = std::uint64_t(value) + 1U;
    const auto dram = registers_[0];
    const auto cart = registers_[1];
    if (cart >= 0x08000000U && cart < 0x08010000U) {
      if (!flash || deadline_ || length > UINT32_MAX || count > UINT64_MAX - 4096U ||
          !flash(device, offset == 12U, cart, dram, static_cast<std::uint32_t>(length), rdram)) return false;
      registers_[offset / 4U] = value;
      deadline_ = count + 4096U;
      busy_status_ = 1U;
      ++transfers_;
      return true;
    }
    if (offset == 8U) return false; // only qualified flash writes
    if (deadline_ || (dram & 1U) != 0U || (cart & 1U) != 0U ||
        (rdram.size() & 3U) != 0U || cart < 0x10000000U ||
        dram > rdram.size() || length > rdram.size() - dram ||
        cart - 0x10000000U > rom.size() ||
        length > rom.size() - (cart - 0x10000000U) ||
        count > UINT64_MAX - length / 8U) return false;
    for (std::uint64_t index = 0; index < length; ++index)
      rdram[(dram + index) ^ 3U] = rom[cart - 0x10000000U + index];
    registers_[3] = value;
    deadline_ = count + length / 8U;
    busy_status_ = 3U;
    ++transfers_;
    return true;
  }
  // Called when the qualified CPU commits device events, not once per host
  // callback or wall-clock tick. Acknowledgement remains a register command.
  void advance(std::uint64_t count) {
    if (deadline_ && count >= *deadline_) {
      deadline_.reset();
      interrupt_ = true;
    }
  }
  [[nodiscard]] bool interrupt() const { return interrupt_; }
  [[nodiscard]] std::optional<std::uint64_t> deadline() const { return deadline_; }
  [[nodiscard]] std::uint64_t transfers() const { return transfers_; }
private:
  std::array<std::uint32_t, 13> registers_{};
  std::optional<std::uint64_t> deadline_;
  std::uint64_t transfers_ = 0;
  std::uint32_t busy_status_ = 0;
  bool interrupt_ = false;
};
} // namespace jfg::boot
