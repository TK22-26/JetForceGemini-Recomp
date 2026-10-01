#pragma once

// Independently authored virtual-time mechanism. Costs and device periods
// are supplied by a separately qualified profile; this is not a CPU model.
#include <algorithm>
#include <cstdint>
#include <optional>
#include <vector>

namespace jfg::boot {
class ExecutionClock final {
public:
  struct Event {
    std::uint32_t source;
    std::uint64_t deadline;
    std::uint64_t period;
  };
  [[nodiscard]] std::uint64_t now() const { return now_; }
  [[nodiscard]] std::optional<std::uint64_t> next() const {
    if (events_.empty()) return std::nullopt;
    return earliest()->deadline;
  }
  // One outstanding event per source. Replacement must be explicit.
  bool arm(std::uint32_t source, std::uint64_t deadline,
           std::uint64_t period = 0) {
    if (deadline < now_ || std::any_of(events_.begin(), events_.end(),
        [source](const Event& event) { return event.source == source; })) return false;
    events_.push_back({source, deadline, period});
    return true;
  }
  bool cancel(std::uint32_t source) {
    const auto size = events_.size();
    std::erase_if(events_, [source](const Event& event) { return event.source == source; });
    return size != events_.size();
  }
  // Charge actual executed work, including while interrupts are masked.
  // A caller must drain due events before charging further work.
  bool advance(std::uint64_t ticks) {
    if (ticks > UINT64_MAX - now_ || (next() && *next() <= now_)) return false;
    now_ += ticks;
    return true;
  }
  // Only use when no guest thread can run. No gratuitous video-frame step.
  bool idle_to_next() {
    const auto deadline = next();
    if (!deadline) return false;
    now_ = (std::max)(now_, *deadline);
    return true;
  }
  // Periodic events remain phase-locked to their previous deadline.
  // Equal deadlines use source id order, independent of arm order.
  [[nodiscard]] std::optional<Event> take_due() {
    if (events_.empty()) return std::nullopt;
    const auto it = earliest();
    if (it->deadline > now_) return std::nullopt;
    const Event event = *it;
    if (event.period == 0 || event.period > UINT64_MAX - event.deadline) {
      events_.erase(it);
      if (event.period != 0) exhausted_ = true;
    } else {
      it->deadline += event.period;
    }
    return event;
  }
  [[nodiscard]] bool exhausted() const { return exhausted_; }
private:
  std::vector<Event>::const_iterator earliest() const {
    return std::min_element(events_.begin(), events_.end(), before);
  }
  std::vector<Event>::iterator earliest() {
    return std::min_element(events_.begin(), events_.end(), before);
  }
  static bool before(const Event& a, const Event& b) {
    return a.deadline < b.deadline ||
           (a.deadline == b.deadline && a.source < b.source);
  }
  std::uint64_t now_ = 0;
  std::vector<Event> events_;
  bool exhausted_ = false;
};

// Device assertion and CPU interrupt delivery are distinct. Masks do not
// stop time or discard pending interrupts. Acknowledgement clears a source.
class InterruptLatch final {
public:
  void raise(std::uint32_t bits) { pending_ |= bits; }
  void acknowledge(std::uint32_t bits) { pending_ &= ~bits; }
  void mask(std::uint32_t bits) { enabled_ = bits; }
  [[nodiscard]] std::uint32_t pending() const { return pending_; }
  [[nodiscard]] std::uint32_t deliverable(bool global_enabled,
                                         bool exception_level,
                                         bool safe_boundary) const {
    return global_enabled && !exception_level && safe_boundary
        ? pending_ & enabled_ : 0U;
  }
private:
  std::uint32_t pending_ = 0, enabled_ = 0;
};

// Generated before-instruction hooks must retire the PREVIOUS operation,
// not charge an operation whose register/memory effects have not run yet.
// At a preemptible boundary: finish(), drain events, yield if needed, then
// enter() AFTER resumption. Keep one retirement record per guest context,
// not one shared pending operation across multiple guest threads. The caller
// supplies a qualified cost and determines whether the boundary is safe.
class InstructionRetirement final {
public:
  bool enter(ExecutionClock& clock, std::uint64_t next_cost) {
    if (next_cost == 0 || !finish(clock)) return false;
    pending_cost_ = next_cost;
    return true;
  }
  bool finish(ExecutionClock& clock) {
    if (!pending_cost_) return true;
    if (!clock.advance(*pending_cost_)) return false;
    pending_cost_.reset();
    return true;
  }
  [[nodiscard]] bool in_flight() const { return pending_cost_.has_value(); }
private:
  std::optional<std::uint64_t> pending_cost_;
};
} // namespace jfg::boot
