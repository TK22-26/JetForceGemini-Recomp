#pragma once

// Deterministic stackful guest-thread executor.
//
// Recompiled game code can block in libultra calls deep within a C stack.
// Each guest participant owns a stack; exactly one participant runs at a time.
// The scheduler selects every handoff, independently of host thread timing.
//
// OS threads remain the default and sanitizer-compatible backend. The opt-in
// Windows fiber backend preserves the same handoffs on one host thread, with
// per-stack state and floating-point preservation. Neither backend runs guest
// participants concurrently.

#include <atomic>
#include <condition_variable>
#include <chrono>
#include <cstdint>
#include <functional>
#include <mutex>
#include <memory>
#include <thread>
#include <vector>

namespace jfg::boot {

// Sentinel participant id for the scheduler (baton holder when no guest runs).
inline constexpr int kSchedulerParticipant = -1;

class BatonExecutor final {
public:
    // A guest body receives the executor and its own participant id. It runs
    // only while it holds the baton; it calls yield_to_scheduler() to block
    // and returns when the thread is finished.
    using Body = std::function<void(BatonExecutor&, int)>;

    struct Timing {
        std::uint64_t wakes = 0, wake_ns = 0, max_wake_ns = 0;
    };
    // Diagnostic only; configured before participants exist. Measures baton
    // publication-to-receipt latency, never time executing a guest slice.
    void enable_timing(bool enabled);
    // Optional bounded polling before the existing parked wait; configure before spawn.
    void set_spin_budget(unsigned microseconds);
    [[nodiscard]] Timing timing();
    struct CycleSample { std::uint64_t cycles=0;std::uint32_t participant=0;bool valid=false; };
    [[nodiscard]] static CycleSample host_cycles() noexcept;
    // When diagnostic timing is enabled, exclude cycles spent on other fibers.
    [[nodiscard]] CycleSample execution_cycles() const noexcept;

    // Optional same-thread Windows stacks. Guest scheduling remains unchanged.
    // Unavailable under ASan until sanitizer stack-switch support is qualified.
    void set_fiber_mode(bool enabled);
    [[nodiscard]] static bool fibers_supported() noexcept;
    BatonExecutor();
    ~BatonExecutor();

    BatonExecutor(const BatonExecutor&) = delete;
    BatonExecutor& operator=(const BatonExecutor&) = delete;

    // Registers a participant with its own parked stack. Returns its id.
    // Must be called from the scheduler side only.
    [[nodiscard]] int spawn(Body body);

    // Scheduler hands the baton to participant `id`, blocks until the baton
    // returns (the participant yielded or finished), and returns whether that
    // participant has finished. Scheduler-side only.
    bool resume(int id);

    // Participant hands the baton back to the scheduler and blocks until it is
    // resumed again. Participant-side only.
    void yield_to_scheduler();

    // Unwinds parked participants, then joins threads or deletes fiber stacks.
    // Scheduler-side only; repeated shutdown calls are harmless.
    void shutdown();

    [[nodiscard]] std::size_t participant_count() const noexcept {
        return participants_.size();
    }

private:
    struct FiberState;
    std::unique_ptr<FiberState> fibers_;
    struct Participant final {
        std::thread thread;
        std::unique_ptr<std::condition_variable> ready = std::make_unique<std::condition_variable>();
        bool finished = false;
        bool started = false;
    };

    void participant_main(int id, Body body);
    void hand_off(int to);            // set holder and wake the waiter
    void wait_until_holder(int self); // block until `self` holds the baton

    void publish_timing();
    void receive_timing();
    bool timing_enabled_ = false;
    Timing timing_{};
    std::chrono::steady_clock::time_point handoff_started_{};
    std::mutex mutex_;
    std::condition_variable cv_;
    std::atomic<int> holder_{kSchedulerParticipant};
    unsigned spin_microseconds_ = 0;
    bool shutting_down_ = false;
    std::vector<Participant> participants_;
};

} // namespace jfg::boot
