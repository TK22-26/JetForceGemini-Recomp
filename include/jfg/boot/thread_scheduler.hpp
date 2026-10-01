#pragma once

// libultra thread-scheduler HLE (Phase 6 native boot).
//
// Binds the deterministic stackful executor (BatonExecutor) to the guest
// message-queue HLE so the libultra thread primitives actually schedule real
// thread bodies that block and wake:
//
//   osCreateThread -> create_thread (spawns a parked executor participant)
//   osStartThread  -> start_thread  (marks it runnable)
//   osRecvMesg     -> recv_blocking (blocks the running thread when empty)
//   osSendMesg     -> send / send_blocking (wait for space, wake one receiver)
//
// Scheduling is deterministic: highest priority first, lowest thread id to
// break ties, one thread running at a time via the baton. This is the
// deterministic boot profile — cooperative at libultra block points — not
// host-preemptive.
//
// AUTHORSHIP: original work to the public libultra thread/queue contract; no
// decomp source copied (see src/boot/PROVENANCE.md).

#include <cstdint>
#include <functional>
#include <optional>
#include <vector>

#include "jfg/boot/executor.hpp"
#include "jfg/boot/hle.hpp"

namespace jfg::boot {

class ThreadScheduler;

// A guest thread body (synthetic in tests; a recompiled entry once real code
// is linked). Receives the scheduler and its own thread id.
using ThreadEntry = std::function<void(ThreadScheduler&, int)>;

enum class ThreadState : std::uint32_t {
    kStopped = 0U,  // created, not yet started
    kRunnable = 1U,
    kBlocked = 2U,  // waiting for a message or space on blocked_queue
    kFinished = 3U,
};

enum class ScheduleOutcome : std::uint32_t {
    kQuiescent = 1U, // no runnable thread remains (all blocked or finished)
    kAllFinished = 2U,
    kUnbounded = 3U, // step limit hit
    kTimeslice = 4U, // running thread yielded for a deterministic interrupt
};

struct ThreadSnapshot final {
    std::uint32_t priority = 0U;
    ThreadState state = ThreadState::kStopped;
    std::uint32_t blocked_queue = 0U;
};

class ThreadScheduler final {
public:
    ThreadScheduler(hle::GuestMemory memory) noexcept : memory_(memory) {}

    // osCreateThread + osStartThread split. create_thread spawns the body
    // parked; start_thread makes it schedulable.
    [[nodiscard]] int create_thread(std::uint32_t priority, ThreadEntry entry);
    void start_thread(int thread_id);
    [[nodiscard]] bool set_priority(int thread_id, std::uint32_t priority);
    [[nodiscard]] std::optional<std::uint32_t> priority_of(int thread_id) const;
    [[nodiscard]] int current_thread_id() const noexcept { return current_; }
    // Host-owned per-context state (e.g. RCP masks) is saved/restored at
    // every baton boundary, including blocking, preemption and completion.
    // Install before the first run; never replace it while guest work runs.
    [[nodiscard]] bool set_baton_hook(std::function<void(int, bool)> hook);
    void yield_current();
    void preempt_current();
    // Models a guest branch-to-self idle loop. The current thread is parked
    // permanently and returns the baton; it can only be resumed for executor
    // shutdown, which unwinds it cooperatively.
    void pause_current();

    // osRecvMesg with OS_MESG_BLOCK semantics: returns 0 once a message is
    // available (written to mesg_out_ptr), blocking the running thread until
    // then. Called from within a running thread body only.
    std::int32_t recv_blocking(std::uint32_t mq_ptr, std::uint32_t mesg_out_ptr);

    // Nonblocking enqueue and wake one highest-priority receiver (FIFO ties).
    // The guest-call bridge performs any priority reschedule after send;
    // host/device callers may also use this method outside a running thread.
    // Returns hle::kOsSuccess or hle::kOsFull.
    std::int32_t send(std::uint32_t mq_ptr, std::uint32_t message, bool jam);
    // Blocking full-queue send/jam; payload stays on the suspended guest
    // caller's host stack. Only valid from a running guest thread.
    std::int32_t send_blocking(std::uint32_t mq_ptr, std::uint32_t message, bool jam);
    // For callers which already performed a successful queue pop through
    // the validated HLE dispatcher. Wake one space waiter, not receivers.
    void notify_received(std::uint32_t mq_ptr);

    // osCreateMesgQueue passthrough on guest memory.
    [[nodiscard]] bool create_queue(
        std::uint32_t mq_ptr, std::uint32_t msg_buf_ptr, std::int32_t count);

    // Runs the scheduler until quiescent, all finished, or the step limit.
    [[nodiscard]] ScheduleOutcome run(std::uint64_t step_limit);

    [[nodiscard]] hle::GuestMemory& memory() noexcept { return memory_; }
    [[nodiscard]] ThreadState state_of(int thread_id) const;
    [[nodiscard]] std::optional<ThreadSnapshot> snapshot_of(int thread_id) const;
    [[nodiscard]] std::size_t thread_count() const noexcept {
        return threads_.size();
    }
    [[nodiscard]] std::uint64_t dispatch_count() const noexcept {
        return dispatch_count_;
    }

private:
    enum class WaitKind { receive, send };
    struct Thread final {
        std::uint32_t priority = 0U;
        ThreadState state = ThreadState::kStopped;
        std::uint32_t blocked_queue = 0U;
        WaitKind wait_kind = WaitKind::receive;
    };

    [[nodiscard]] std::optional<int> pick_runnable() const;
    std::optional<int> wake_one(std::uint32_t mq_ptr, WaitKind kind);
    bool block_current(std::uint32_t mq_ptr, WaitKind kind);
    void yield_to_higher_waiter(std::optional<int> awakened);

    hle::GuestMemory memory_;
    BatonExecutor executor_;
    std::vector<Thread> threads_;
    // Insertion order implements FIFO ties among blocked waiters, which
    // is distinct from the boot profile's runnable-thread id tie-break.
    std::vector<int> waiters_;
    int current_ = -1; // thread id currently holding the baton, or -1
    std::uint64_t dispatch_count_ = 0U;
    bool preempt_requested_ = false;
    std::function<void(int, bool)> baton_hook_;
};

} // namespace jfg::boot
