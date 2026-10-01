#pragma once

// Count/Compare equality, modulo 32 bits. Independently probed pending/ack and
// wrap behavior in the corrected-Mupen profile; advance at CPU event commits.
#include <cstdint>
#include <optional>

namespace jfg::boot {
class ReferenceCompare final {
public:
  bool write(std::uint64_t count, std::uint32_t value) {
    const auto distance = static_cast<std::uint32_t>(value - static_cast<std::uint32_t>(count));
    // Equality on the writing instruction needs a separate boundary probe.
    if (distance == 0U || count > UINT64_MAX - distance) return false;
    value_ = value;
    deadline_ = count + distance;
    interrupt_ = false;
    return true;
  }
  void advance(std::uint64_t count) {
    if (deadline_ && count >= *deadline_) {
      interrupt_ = true;
      deadline_.reset();
    }
  }
  [[nodiscard]] bool interrupt() const { return interrupt_; }
  [[nodiscard]] std::optional<std::uint64_t> deadline() const { return deadline_; }
  [[nodiscard]] std::uint32_t read() const { return value_; }
private:
  std::optional<std::uint64_t> deadline_;
  std::uint32_t value_ = 0;
  bool interrupt_ = false;
};
} // namespace jfg::boot
