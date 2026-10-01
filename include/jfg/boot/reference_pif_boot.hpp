#pragma once
#include <cstdint>

namespace jfg::boot {
// Restricted, black-box-qualified PIF boot acknowledgement. This is not the
// controller command/DMA engine. Unsupported control commands fail closed.
class ReferencePifBoot final {
public:
  [[nodiscard]] std::uint32_t read() const { return 0; }
  bool write(std::uint32_t value) {
    if (value != 8U) return false;
    acknowledged_ = true;
    return true;
  }
  [[nodiscard]] bool acknowledged() const { return acknowledged_; }
private:
  bool acknowledged_ = false;
};
} // namespace jfg::boot
