#pragma once

// Independent CPU-visible SP status register, from the public SDK register
// contract. Task completion is an explicit external event, never a CPU write
// or a VI side effect. No RSP execution, DMA or latency model is implied.
#include <array>
#include <cstdint>

namespace jfg::boot {
class SpStatus final {
public:
  bool initialize(std::uint32_t status, bool interrupt) {
    if ((status & ~0x7fffU) != 0U) return false;
    status_ = status;
    interrupt_ = interrupt;
    initialized_ = true;
    return true;
  }
  [[nodiscard]] bool initialized() const { return initialized_; }
  [[nodiscard]] std::uint32_t read() const { return status_; }
  [[nodiscard]] bool interrupt() const { return interrupt_; }
  void acknowledge_interrupt() { interrupt_ = false; }

  bool command(std::uint32_t value) {
    if (!initialized_ || (value & ~0x01ffffffU) != 0U) return false;
    // Conflicting set/clear pairs are unqualified, not silently prioritized.
    constexpr std::array<unsigned, 12> shifts{0, 3, 5, 7, 9, 11, 13, 15, 17, 19, 21, 23};
    for (const auto shift : shifts)
      if (((value >> shift) & 3U) == 3U) return false;
    auto status = status_;
    auto interrupt = interrupt_;
    const auto apply = [value](unsigned shift, unsigned bit, std::uint32_t& bits) {
      if ((value & (1U << shift)) != 0U) bits &= ~(1U << bit);
      if ((value & (2U << shift)) != 0U) bits |= 1U << bit;
    };
    apply(0, 0, status); // halt
    if ((value & 4U) != 0U) status &= ~2U; // broke is clear-only from CPU
    if ((value & 8U) != 0U) interrupt = false;
    if ((value & 16U) != 0U) interrupt = true;
    apply(5, 5, status); // single-step
    apply(7, 6, status); // interrupt on break
    for (unsigned i = 0; i != 8; ++i) apply(9 + 2 * i, 7 + i, status);
    status_ = status;
    interrupt_ = interrupt;
    return true;
  }

  // HLE task preparation's SDK-visible signal clearing, not OS CPU work.
  bool prepare_task() {
    if (!initialized_ || (status_ & 0x1dU) != 1U) return false;
    status_ &= ~0x380U; // yield, yielded, task-done
    return true;
  }
  // Completion of an SDK task that reaches BREAK and signals TASKDONE.
  // Yielded and arbitrary RSP programs need their own qualified transitions.
  bool complete_task() {
    if (!initialized_ || (status_ & 0x1dU) != 0U) return false;
    status_ |= 0x203U;
    if ((status_ & 0x40U) != 0U) interrupt_ = true;
    return true;
  }
private:
  std::uint32_t status_ = 0;
  bool interrupt_ = false;
  bool initialized_ = false;
};
} // namespace jfg::boot
