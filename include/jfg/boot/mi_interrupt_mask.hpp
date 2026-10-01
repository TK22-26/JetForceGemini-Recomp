#pragma once
#include <cstdint>

namespace jfg::boot {
// Public RCP register contract: MI_INTR_MASK_REG reads six mask bits but
// writes six clear/set command pairs. This is not ordinary read/write RAM.
// Independent implementation; no emulator register implementation copied.
class MiInterruptMask final {
public:
  bool initialize(std::uint32_t mask) {
    if (mask > 0x3fU) return false;
    mask_ = mask;
    initialized_ = true;
    return true;
  }
  [[nodiscard]] bool initialized() const { return initialized_; }
  [[nodiscard]] std::uint32_t read() const { return mask_; }
  bool command(std::uint32_t value) {
    if (!initialized_ || (value & ~0xfffU) != 0U) return false;
    std::uint32_t next = mask_;
    for (unsigned source = 0; source < 6; ++source) {
      const auto pair = (value >> (2U * source)) & 3U;
      if (pair == 3U) return false; // Conflicting commands not qualified.
      if (pair == 1U) next &= ~(1U << source);
      if (pair == 2U) next |= 1U << source;
    }
    mask_ = next;
    return true;
  }
private:
  std::uint32_t mask_ = 0;
  bool initialized_ = false;
};
} // namespace jfg::boot
