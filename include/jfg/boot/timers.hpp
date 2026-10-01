#pragma once

// Independently authored public libultra timer contract. Monotonic Count
// deadlines are independent of osSetTime. OS-private list links are not
// reproduced: this HLE owns the timer list in runtime side state.
#include "jfg/boot/hle.hpp"
#include <algorithm>
#include <cstdint>
#include <optional>
#include <vector>

namespace jfg::boot {
class Timers final {
  struct Entry {
    std::uint32_t address, queue, message;
    std::uint64_t deadline, interval, order;
  };
  std::vector<Entry> entries_;
  std::uint64_t order_ = 0;
  static bool put64(hle::GuestMemory &memory, std::uint32_t address,
                    std::uint64_t value) {
    return memory.write_u32(address, static_cast<std::uint32_t>(value >> 32U)) &&
           memory.write_u32(address + 4U, static_cast<std::uint32_t>(value));
  }
public:
  bool set(hle::GuestMemory &memory, std::uint64_t now,
           std::uint32_t address, std::uint64_t countdown,
           std::uint64_t interval, std::uint32_t queue, std::uint32_t message) {
    const auto delay = countdown != 0 ? countdown : interval;
    if (address > UINT32_MAX - 31U || (address & 7U) != 0U ||
        delay > UINT64_MAX - now) return false;
    std::uint32_t ignored = 0;
    for (std::uint32_t offset = 0; offset < 32U; offset += 4U)
      if (!memory.read_u32(address + offset, ignored)) return false;
    if (!memory.write_u32(address, 0) || !memory.write_u32(address + 4U, 0) ||
        !put64(memory, address + 8U, interval) ||
        !put64(memory, address + 16U, delay) ||
        !memory.write_u32(address + 24U, queue) ||
        !memory.write_u32(address + 28U, message)) return false;
    stop(address);
    entries_.push_back({address, queue, message, now + delay, interval, order_++});
    return true;
  }
  void stop(std::uint32_t address) {
    std::erase_if(entries_, [address](const Entry &e) { return e.address == address; });
  }
  std::optional<std::uint64_t> next() const {
    if (entries_.empty()) return std::nullopt;
    return std::min_element(entries_.begin(), entries_.end(),
        [](const Entry &a, const Entry &b) { return a.deadline < b.deadline; })->deadline;
  }
  // Send is nonblocking: full queues drop notifications, not periodic timers.
  template<class Send>
  bool service(hle::GuestMemory &memory, std::uint64_t now, Send send) {
    while (!entries_.empty()) {
      const auto it = std::min_element(entries_.begin(), entries_.end(),
          [](const Entry &a, const Entry &b) {
            return a.deadline < b.deadline ||
                   (a.deadline == b.deadline && a.order < b.order);
          });
      if (it->deadline > now) break;
      auto e = *it;
      entries_.erase(it);
      if (!put64(memory, e.address + 16U, e.interval)) return false;
      if (e.interval != 0) {
        if (e.interval > UINT64_MAX - e.deadline) return false;
        e.deadline += e.interval;
        e.order = order_++;
        entries_.push_back(e);
      }
      if (e.queue != 0) send(e.queue, e.message);
    }
    return true;
  }
};
} // namespace jfg::boot
