#include "jfg/boot/thread_scheduler.hpp"

#include <utility>

namespace jfg::boot {

int ThreadScheduler::create_thread(
    const std::uint32_t priority, ThreadEntry entry) {
    const int id = static_cast<int>(threads_.size());
    threads_.push_back(Thread{.priority = priority,
                              .state = ThreadState::kStopped,
                              .blocked_queue = 0U});
    // Spawn the body parked; it becomes schedulable only after start_thread.
    const int participant = executor_.spawn(
        [this, entry = std::move(entry)](BatonExecutor&, int self) {
            entry(*this, self);
        });
    // create_thread is called scheduler-side before run(); participant ids are
    // assigned in the same order as thread ids, so they coincide.
    (void)participant;
    return id;
}

void ThreadScheduler::start_thread(const int thread_id) {
    if (thread_id < 0 || thread_id >= static_cast<int>(threads_.size())) {
        return;
    }
    Thread& thread = threads_[static_cast<std::size_t>(thread_id)];
    if (thread.state == ThreadState::kStopped) {
        thread.state = ThreadState::kRunnable;
    }
}

bool ThreadScheduler::set_priority(const int thread_id,
                                   const std::uint32_t priority) {
    if (thread_id < 0 || thread_id >= static_cast<int>(threads_.size())) {
        return false;
    }
    threads_[static_cast<std::size_t>(thread_id)].priority = priority;
    return true;
}

std::optional<std::uint32_t>
ThreadScheduler::priority_of(const int thread_id) const {
    if (thread_id < 0 || thread_id >= static_cast<int>(threads_.size())) {
        return std::nullopt;
    }
    return threads_[static_cast<std::size_t>(thread_id)].priority;
}

void ThreadScheduler::yield_current() {
    if (current_ >= 0 && current_ < static_cast<int>(threads_.size())) {
        executor_.yield_to_scheduler();
    }
}

bool ThreadScheduler::set_baton_hook(std::function<void(int, bool)> hook) {
    if (current_ >= 0 || dispatch_count_ != 0U) return false;
    baton_hook_ = std::move(hook);
    return true;
}

void ThreadScheduler::preempt_current() {
    if (current_ >= 0 && current_ < static_cast<int>(threads_.size())) {
        preempt_requested_ = true;
        executor_.yield_to_scheduler();
    }
}

void ThreadScheduler::pause_current() {
    while (current_ >= 0 && current_ < static_cast<int>(threads_.size())) {
        Thread& thread = threads_[static_cast<std::size_t>(current_)];
        thread.state = ThreadState::kStopped;
        thread.blocked_queue = 0U;
        executor_.yield_to_scheduler();
    }
}

bool ThreadScheduler::create_queue(
    const std::uint32_t mq_ptr, const std::uint32_t msg_buf_ptr,
    const std::int32_t count) {
    return hle::os_create_mesg_queue(memory_, mq_ptr, msg_buf_ptr, count);
}

std::int32_t ThreadScheduler::recv_blocking(
    const std::uint32_t mq_ptr, const std::uint32_t mesg_out_ptr) {
    while (true) {
        const std::int32_t result =
            hle::os_recv_mesg(memory_, mq_ptr, mesg_out_ptr);
        if (result == hle::kOsSuccess) {
            notify_received(mq_ptr);
            return result;
        }
        // Empty: block the running thread and yield the baton. When a sender
        // wakes us, resume() re-enters here and we retry the receive.
        if (!block_current(mq_ptr, WaitKind::receive)) return result;
    }
}

std::int32_t ThreadScheduler::send(
    const std::uint32_t mq_ptr, const std::uint32_t message, const bool jam) {
    const std::int32_t result =
        hle::os_send_mesg(memory_, mq_ptr, message, jam);
    if (result == hle::kOsSuccess) {
        (void)wake_one(mq_ptr, WaitKind::receive);
    }
    return result;
}

std::optional<int> ThreadScheduler::wake_one(const std::uint32_t mq_ptr, WaitKind kind) {
    auto selected = waiters_.end();
    for (auto it = waiters_.begin(); it != waiters_.end(); ++it) {
        const Thread& thread = threads_[static_cast<std::size_t>(*it)];
        if (thread.state == ThreadState::kBlocked &&
            thread.blocked_queue == mq_ptr && thread.wait_kind == kind &&
            (selected == waiters_.end() || thread.priority >
             threads_[static_cast<std::size_t>(*selected)].priority)) {
            selected = it;
        }
    }
    if (selected == waiters_.end()) return std::nullopt;
    const int id = *selected;
    waiters_.erase(selected);
    auto& thread = threads_[static_cast<std::size_t>(id)];
    thread.state = ThreadState::kRunnable;
    thread.blocked_queue = 0U;
    return id;
}

bool ThreadScheduler::block_current(std::uint32_t queue, WaitKind kind) {
    if (current_ < 0 || current_ >= static_cast<int>(threads_.size())) return false;
    auto& thread = threads_[static_cast<std::size_t>(current_)];
    thread.state = ThreadState::kBlocked;
    thread.blocked_queue = queue;
    thread.wait_kind = kind;
    waiters_.push_back(current_);
    executor_.yield_to_scheduler();
    return true;
}

void ThreadScheduler::yield_to_higher_waiter(std::optional<int> awakened) {
    if (awakened && current_ >= 0 &&
        threads_[static_cast<std::size_t>(*awakened)].priority >
        threads_[static_cast<std::size_t>(current_)].priority) yield_current();
}

void ThreadScheduler::notify_received(std::uint32_t queue) {
    yield_to_higher_waiter(wake_one(queue, WaitKind::send));
}

std::int32_t ThreadScheduler::send_blocking(std::uint32_t queue,
                                          std::uint32_t message, bool jam) {
    while (true) {
        const auto result = hle::os_send_mesg(memory_, queue, message, jam);
        if (result == hle::kOsSuccess) {
            yield_to_higher_waiter(wake_one(queue, WaitKind::receive));
            return result;
        }
        if (!block_current(queue, WaitKind::send)) return result;
    }
}

std::optional<int> ThreadScheduler::pick_runnable() const {
    std::optional<int> best;
    for (std::size_t i = 0; i < threads_.size(); ++i) {
        const Thread& thread = threads_[i];
        if (thread.state != ThreadState::kRunnable) {
            continue;
        }
        if (!best.has_value()) {
            best = static_cast<int>(i);
            continue;
        }
        const Thread& current = threads_[static_cast<std::size_t>(*best)];
        // Highest priority first; lowest id breaks ties.
        if (thread.priority > current.priority) {
            best = static_cast<int>(i);
        }
    }
    return best;
}

ScheduleOutcome ThreadScheduler::run(const std::uint64_t step_limit) {
    std::uint64_t steps = 0U;
    while (true) {
        const std::optional<int> next = pick_runnable();
        if (!next.has_value()) {
            for (const Thread& thread : threads_) {
                if (thread.state != ThreadState::kFinished) {
                    return ScheduleOutcome::kQuiescent;
                }
            }
            return ScheduleOutcome::kAllFinished;
        }
        if (steps >= step_limit) {
            return ScheduleOutcome::kUnbounded;
        }
        ++steps;
        current_ = *next;
        if (baton_hook_) baton_hook_(*next, true);
        const bool finished = executor_.resume(*next);
        if (baton_hook_) baton_hook_(*next, false);
        current_ = -1;
        ++dispatch_count_;
        const bool preempted = preempt_requested_;
        preempt_requested_ = false;
        Thread& thread = threads_[static_cast<std::size_t>(*next)];
        if (finished) {
            thread.state = ThreadState::kFinished;
            thread.blocked_queue = 0U;
        } else if (thread.state == ThreadState::kRunnable) {
            // Yielded without blocking: leave runnable (cooperative yield).
        }
        if (preempted) {
            return ScheduleOutcome::kTimeslice;
        }
    }
}

ThreadState ThreadScheduler::state_of(const int thread_id) const {
    if (thread_id < 0 || thread_id >= static_cast<int>(threads_.size())) {
        return ThreadState::kFinished;
    }
    return threads_[static_cast<std::size_t>(thread_id)].state;
}

std::optional<ThreadSnapshot>
ThreadScheduler::snapshot_of(const int thread_id) const {
    if (thread_id < 0 || thread_id >= static_cast<int>(threads_.size())) {
        return std::nullopt;
    }
    const Thread& thread = threads_[static_cast<std::size_t>(thread_id)];
    return ThreadSnapshot{thread.priority, thread.state, thread.blocked_queue};
}

} // namespace jfg::boot
