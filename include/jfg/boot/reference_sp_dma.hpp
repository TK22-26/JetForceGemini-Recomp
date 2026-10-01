#pragma once

// Independently authored, synchronous SP task-load DMA profile. The SDK defines
// register fields and transfer direction. The pinned Mupen black-box probe
// qualifies immediate aligned single-block reads, retained address/length/PC
// register values, and zero busy/full on return. This is not hardware timing,
// a general RSP engine, multi-block DMA, or yielded-task support.
#include <array>
#include <cstdint>
#include <cstring>
#include <optional>
#include <span>

namespace jfg::boot {
class ReferenceSpDma final {
public:
  [[nodiscard]] std::optional<std::uint32_t> read(std::uint32_t offset) const {
    switch (offset) {
    case 0: return memory_address_;
    case 4: return dram_address_;
    case 8: return read_length_;
    case 0x14: case 0x18: return 0; // synchronous reference profile
    default: return std::nullopt;
    }
  }
  // Both byte arrays use the generated CPU's 32-bit word-swapped storage.
  bool write(std::uint32_t offset, std::uint32_t value,
             std::span<const std::uint8_t> rdram) {
    if (offset == 0) { memory_address_ = value; return true; }
    if (offset == 4) { dram_address_ = value; return true; }
    if (offset != 8 || (value & ~0xfffU) != 0U) return false;
    const auto length = value + 1U;
    const auto local = memory_address_ & 0x1fffU;
    const auto dram = dram_address_ & 0xffffffU;
    if ((local & 7U) != 0U || (dram & 7U) != 0U || (length & 7U) != 0U ||
        (local & 0xfffU) + length > 0x1000U ||
        dram > rdram.size() || length > rdram.size() - dram) return false;
    std::memcpy(memory_.data() + local, rdram.data() + dram, length);
    read_length_ = value;
    ++transfers_;
    return true;
  }
  bool write_pc(std::uint32_t value) {
    if ((value & 3U) != 0U) return false;
    pc_ = value;
    return true;
  }
  [[nodiscard]] std::uint32_t pc() const { return pc_; }
  [[nodiscard]] std::uint64_t transfers() const { return transfers_; }
  [[nodiscard]] std::span<const std::uint8_t> memory() const { return memory_; }
private:
  std::array<std::uint8_t, 8192> memory_{};
  std::uint32_t memory_address_ = 0, dram_address_ = 0, read_length_ = 0, pc_ = 0;
  std::uint64_t transfers_ = 0;
};
} // namespace jfg::boot
