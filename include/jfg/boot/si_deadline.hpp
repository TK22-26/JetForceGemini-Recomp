#pragma once
#include <cstdint>
#include <optional>

namespace jfg::boot {
// One serial transfer in flight. Latency is supplied by a named timing
// profile, not inferred from a video frame or the state of the receive queue.
class SiDeadline final {
public:
  struct Completion { std::uint32_t queue, message; };
  bool start(std::uint64_t now, std::uint64_t latency,
             std::uint32_t queue, std::uint32_t message) {
    if (deadline_ || latency == 0 || latency > UINT64_MAX - now) return false;
    deadline_ = now + latency;
    completion_ = {queue, message};
    return true;
  }
  std::optional<std::uint64_t> next() const { return deadline_; }
  std::optional<Completion> take(std::uint64_t now) {
    if (!deadline_ || now < *deadline_) return std::nullopt;
    deadline_.reset();
    return completion_;
  }
private:
  std::optional<std::uint64_t> deadline_;
  Completion completion_{};
};
} // namespace jfg::boot
