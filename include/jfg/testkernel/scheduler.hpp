#pragma once

// Virtual time and deterministic queues/timers/scheduling for the test
// kernel (Phase 5, kernel v0).  Nothing here reads host time: the clock
// advances only when the scheduler dispatches, and ties are broken by a
// monotonically assigned sequence number, so a given set of scheduled events
// always dispatches in exactly one order.

#include <cstdint>
#include <functional>
#include <optional>
#include <string>
#include <vector>

namespace jfg::testkernel {

class VirtualClock final {
public:
    [[nodiscard]] std::uint64_t now() const noexcept { return now_; }

    // Time never moves backwards; a stale target is a no-op.
    void advance_to(const std::uint64_t target) noexcept {
        if (target > now_) {
            now_ = target;
        }
    }

private:
    std::uint64_t now_ = 0U;
};

struct DispatchedEvent final {
    std::uint64_t due = 0U;
    std::uint64_t sequence = 0U;
    std::string label;

    [[nodiscard]] bool operator==(const DispatchedEvent&) const = default;
};

class DeterministicScheduler final {
public:
    using Action = std::function<void(DeterministicScheduler&)>;

    [[nodiscard]] const VirtualClock& clock() const noexcept { return clock_; }

    // Schedules an event at an absolute virtual due time.  Returns false and
    // schedules nothing when the due time is already in the past.
    [[nodiscard]] bool schedule_at(
        std::uint64_t due, std::string label, Action action);

    // A timer is an event at now + delay; a periodic timer reschedules
    // itself from its own due time, so drift cannot accumulate.
    [[nodiscard]] bool schedule_after(
        std::uint64_t delay, std::string label, Action action);
    [[nodiscard]] bool schedule_every(
        std::uint64_t period, std::uint64_t repetitions,
        std::string label, Action action);

    // Dispatches events in (due, sequence) order until the queue is empty or
    // the step limit is reached.  Returns the number of dispatched events;
    // std::nullopt when the limit was hit with work remaining, which callers
    // must treat as a failed (potentially unbounded) run.
    [[nodiscard]] std::optional<std::uint64_t> run(std::uint64_t step_limit);

    // The replay-comparable record of everything dispatched, in order.
    [[nodiscard]] const std::vector<DispatchedEvent>& dispatch_log()
        const noexcept {
        return dispatch_log_;
    }

private:
    struct PendingEvent final {
        std::uint64_t due = 0U;
        std::uint64_t sequence = 0U;
        std::string label;
        Action action;
    };

    [[nodiscard]] std::optional<std::size_t> pop_next_index() const noexcept;

    VirtualClock clock_{};
    std::vector<PendingEvent> pending_;
    std::vector<DispatchedEvent> dispatch_log_;
    std::uint64_t next_sequence_ = 0U;
};

} // namespace jfg::testkernel
