#include "jfg/testkernel/scheduler.hpp"

#include <utility>

namespace jfg::testkernel {

bool DeterministicScheduler::schedule_at(
    const std::uint64_t due, std::string label, Action action) {
    if (due < clock_.now() || !action) {
        return false;
    }
    pending_.push_back(PendingEvent{
        .due = due,
        .sequence = next_sequence_++,
        .label = std::move(label),
        .action = std::move(action),
    });
    return true;
}

bool DeterministicScheduler::schedule_after(
    const std::uint64_t delay, std::string label, Action action) {
    const std::uint64_t due = clock_.now() + delay;
    if (due < clock_.now()) {
        return false; // overflow fails closed
    }
    return schedule_at(due, std::move(label), std::move(action));
}

bool DeterministicScheduler::schedule_every(
    const std::uint64_t period, const std::uint64_t repetitions,
    std::string label, Action action) {
    if (period == 0U || repetitions == 0U || !action) {
        return false;
    }
    // Each firing reschedules the next from its own due time.
    struct Repeater final {
        std::uint64_t period;
        std::uint64_t remaining;
        std::string label;
        Action action;

        void fire(DeterministicScheduler& scheduler) {
            action(scheduler);
            if (remaining > 1U) {
                Repeater next{period, remaining - 1U, label, action};
                const std::uint64_t due = scheduler.clock_.now() + period;
                if (due < scheduler.clock_.now()) {
                    return; // overflow fails closed: stop repeating
                }
                std::string next_label = next.label;
                (void)scheduler.schedule_at(
                    due, std::move(next_label),
                    [repeater = std::move(next)](
                        DeterministicScheduler& inner) mutable {
                        repeater.fire(inner);
                    });
            }
        }
    };
    Repeater repeater{period, repetitions, std::move(label), std::move(action)};
    const std::uint64_t due = clock_.now() + period;
    if (due < clock_.now()) {
        return false;
    }
    std::string first_label = repeater.label;
    return schedule_at(
        due, std::move(first_label),
        [repeater = std::move(repeater)](
            DeterministicScheduler& inner) mutable {
            repeater.fire(inner);
        });
}

std::optional<std::size_t> DeterministicScheduler::pop_next_index()
    const noexcept {
    if (pending_.empty()) {
        return std::nullopt;
    }
    std::size_t best = 0U;
    for (std::size_t i = 1U; i < pending_.size(); ++i) {
        const PendingEvent& candidate = pending_[i];
        const PendingEvent& current = pending_[best];
        if (candidate.due < current.due ||
            (candidate.due == current.due &&
             candidate.sequence < current.sequence)) {
            best = i;
        }
    }
    return best;
}

std::optional<std::uint64_t> DeterministicScheduler::run(
    const std::uint64_t step_limit) {
    std::uint64_t dispatched = 0U;
    while (!pending_.empty()) {
        if (dispatched >= step_limit) {
            return std::nullopt;
        }
        const std::optional<std::size_t> index = pop_next_index();
        if (!index.has_value()) {
            break;
        }
        PendingEvent event = std::move(pending_[*index]);
        pending_.erase(
            pending_.begin() + static_cast<std::ptrdiff_t>(*index));
        clock_.advance_to(event.due);
        dispatch_log_.push_back(DispatchedEvent{
            .due = event.due,
            .sequence = event.sequence,
            .label = event.label,
        });
        event.action(*this);
        ++dispatched;
    }
    return dispatched;
}

} // namespace jfg::testkernel
