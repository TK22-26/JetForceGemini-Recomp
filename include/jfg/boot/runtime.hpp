#pragma once

// Independently authored N64 boot runtime (Phase 6).
//
// AUTHORSHIP: this is original work implemented to the public libultra / N64
// SDK contract and validated against black-box behavioral oracles. No source
// from N64ModernRuntime/librecomp or any other third-party runtime was
// copied, transcribed, or adapted. See docs/planning/phase6-acceptance.md and
// src/boot/PROVENANCE.md.
//
// The runtime sits on top of the Phase 5 deterministic kernel: it uses the
// kernel World for RDRAM and state hashing, the VirtualClock for time, and the
// Journal for the boot event log. It adds the scheduler model that Phase 6
// owns — cooperative priority threads, message queues and events, virtual
// timers, PI DMA, VI retrace, and RSP task submission capture.
//
// Thread model: threads are cooperative and step-based. A thread body runs one
// bounded step and returns a directive describing what it wants next (run
// again, receive on a queue, or exit). Scheduling decisions are fully
// deterministic — priority first, FIFO within a priority — so a given boot is
// bit-identical across runs. This is the deterministic boot profile; it does
// not model host preemption.

#include <cstddef>
#include <cstdint>
#include <functional>
#include <map>
#include <optional>
#include <string>
#include <string_view>
#include <vector>

#include "jfg/testkernel/journal.hpp"
#include "jfg/testkernel/scheduler.hpp"
#include "jfg/testkernel/world.hpp"

namespace jfg::boot {

using jfg::testkernel::Journal;
using jfg::testkernel::JournalEffect;
using jfg::testkernel::StateHashSchema;
using jfg::testkernel::VirtualClock;
using jfg::testkernel::World;

using ThreadId = std::uint32_t;
using QueueId = std::uint32_t;
using TimerId = std::uint32_t;
using Message = std::uint32_t;

inline constexpr std::uint32_t kKseg0Base = 0x80000000U;
inline constexpr std::uint64_t kViRetracePeriodTicks = 1'000U;
inline constexpr std::uint64_t kPiDmaTicksPerByte = 1U;
inline constexpr std::uint64_t kPiDmaBaseTicks = 100U;
inline constexpr std::size_t kMaxThreads = 64U;
inline constexpr std::size_t kMaxQueues = 128U;
inline constexpr std::size_t kMaxQueueDepth = 256U;
inline constexpr std::size_t kMaxTimedEvents = 4096U;
inline constexpr std::size_t kMaxRspTasks = 4096U;
inline constexpr std::uint32_t kInvalidId = 0U;

// The N64 .z64 big-endian magic in the first word of the ROM header.
inline constexpr std::uint32_t kZ64Magic = 0x80371240U;

class BootRuntime;

// What a thread step asks the scheduler to do next.
enum class ThreadWait : std::uint32_t {
    kRunnable = 1U, // schedule me again
    kReceive = 2U,  // block until a message arrives on `queue`
    kExit = 3U,     // thread is finished
};

struct ThreadDirective final {
    ThreadWait wait = ThreadWait::kRunnable;
    QueueId queue = kInvalidId;
};

// A cooperative thread body. Called once per scheduled step. `received` holds
// the message delivered by the receive the previous step requested, if any.
using ThreadBody =
    std::function<ThreadDirective(BootRuntime&, std::optional<Message> received)>;

enum class BootStatus : std::uint32_t {
    kReachedStableVi = 1U, // exit gate: repeated VI activity, no divergence
    kTrapped = 2U,         // fail-closed: unsupported operation reached
    kDeadlocked = 3U,      // no runnable thread and no pending event
    kUnbounded = 4U,       // step limit hit with work remaining
    kInvalidRom = 5U,      // ROM rejected before any execution
};

struct StubLedgerEntry final {
    std::string operation;
    std::string disposition;
    std::uint64_t first_seen_tick = 0U;
    std::uint64_t count = 0U;
};

struct RspTaskRecord final {
    std::uint32_t task_type = 0U;
    std::uint32_t ucode_boot_paddr = 0U;
    std::uint32_t data_ptr = 0U;
    std::uint32_t data_size = 0U;
    std::uint64_t tick = 0U;
};

struct BootReport final {
    BootStatus status = BootStatus::kTrapped;
    std::uint64_t vi_retraces = 0U;
    std::uint64_t dispatched_events = 0U;
    std::uint64_t final_tick = 0U;
    std::uint64_t threads_created = 0U;
    std::string journal_hex;    // digest of the boot event log
    std::string state_hash_hex; // final world state hash
    std::vector<StubLedgerEntry> stub_ledger;
    std::vector<RspTaskRecord> rsp_tasks;
    std::string trap_operation; // set when status == kTrapped

    [[nodiscard]] bool reached_gate() const noexcept {
        return status == BootStatus::kReachedStableVi;
    }
};

// A cartridge image. In tests this is a synthetic image with a valid header;
// in the private lane it is the local ROM (never distributed).
class RomImage final {
public:
    [[nodiscard]] static std::optional<RomImage> create(
        std::vector<std::uint8_t> bytes);

    [[nodiscard]] std::size_t size() const noexcept { return bytes_.size(); }
    [[nodiscard]] const std::vector<std::uint8_t>& bytes() const noexcept {
        return bytes_;
    }

private:
    explicit RomImage(std::vector<std::uint8_t> bytes)
        : bytes_(std::move(bytes)) {}

    std::vector<std::uint8_t> bytes_;
};

class BootRuntime final {
public:
    BootRuntime(World& world, VirtualClock& clock, Journal& journal,
                RomImage rom, StateHashSchema schema);

    BootRuntime(const BootRuntime&) = delete;
    BootRuntime& operator=(const BootRuntime&) = delete;

    // --- libultra-contract surface the boot calls -----------------------

    // osCreateThread + osStartThread, collapsed: registers a runnable thread.
    [[nodiscard]] ThreadId create_thread(
        std::uint32_t priority, std::string label, ThreadBody body);

    // osCreateMesgQueue.
    [[nodiscard]] QueueId create_queue(std::string label, std::size_t depth);

    // osSendMesg (jam == osJamMesg, inserts at the front). Fails closed when
    // the queue is full. Wakes a blocked receiver deterministically.
    [[nodiscard]] bool send_message(QueueId queue, Message message, bool jam);

    // osSetTimer: post `message` to `queue` after `delay` virtual ticks.
    [[nodiscard]] bool set_timer(
        QueueId queue, Message message, std::uint64_t delay);

    // osPiStartDma: copy `length` bytes from cart offset to a KSEG0 RDRAM
    // address after a deterministic latency, then post `message` to `queue`.
    [[nodiscard]] bool start_pi_dma(
        QueueId queue, Message message, std::uint32_t ram_vaddr,
        std::uint32_t cart_offset, std::uint32_t length);

    // osSetEventMesg(OS_EVENT_VI-like): register the queue/message the VI
    // retrace event posts to. The boot's main loop blocks receiving on it.
    [[nodiscard]] bool register_vi_client(QueueId queue, Message message);

    // osViSwapBuffer: record the framebuffer; retrace events are automatic.
    [[nodiscard]] bool vi_swap_buffer(std::uint32_t framebuffer_vaddr);

    // osSpTaskStartGo: capture the RSP task for Phase 7. Never rendered here.
    [[nodiscard]] bool submit_rsp_task(RspTaskRecord task);

    // Direct RDRAM helpers for boot bodies (KSEG0 addressing).
    [[nodiscard]] bool write_u32(std::uint32_t vaddr, std::uint32_t value);
    [[nodiscard]] std::optional<std::uint32_t> read_u32(
        std::uint32_t vaddr) const;

    // Any unsupported operation the boot reaches: ledger it and trap.
    void trap_unsupported(std::string_view operation);

    [[nodiscard]] std::uint64_t vi_retraces() const noexcept {
        return vi_retraces_;
    }
    [[nodiscard]] std::uint64_t now() const noexcept { return clock_.now(); }

    // Drive the boot until stable VI activity, a trap, deadlock, or the step
    // limit. `target_retraces` defines "stable"; `step_limit` bounds busy
    // loops. Registers the VI retrace generator; the first thread must be
    // created by the caller before calling run().
    [[nodiscard]] BootReport run(
        std::uint64_t target_retraces, std::uint64_t step_limit);

    [[nodiscard]] bool rom_valid() const noexcept { return rom_valid_; }

private:
    struct Thread final {
        ThreadId id = kInvalidId;
        std::uint32_t priority = 0U;
        std::string label;
        ThreadBody body;
        bool runnable = false;
        bool exited = false;
        bool blocked = false;
        QueueId blocked_on = kInvalidId;
        std::optional<Message> pending_delivery;
        std::uint64_t enqueue_seq = 0U;
    };

    struct Queue final {
        QueueId id = kInvalidId;
        std::string label;
        std::size_t depth = 0U;
        std::vector<Message> messages;
    };

    struct TimedEvent final {
        std::uint64_t due = 0U;
        std::uint64_t seq = 0U;
        QueueId queue = kInvalidId;
        Message message = 0U;
        std::uint32_t dma_ram_vaddr = 0U;
        std::uint32_t dma_cart_offset = 0U;
        std::uint32_t dma_length = 0U;
        bool is_dma = false;
        bool is_vi = false;
    };

    void log(JournalEffect effect, std::string_view label,
             std::vector<std::byte> payload);
    void note_event(std::string_view name, std::uint64_t a, std::uint64_t b);
    [[nodiscard]] bool deliver_or_enqueue(
        QueueId queue, Message message, bool jam);
    [[nodiscard]] std::optional<std::size_t> pick_runnable() const;
    [[nodiscard]] std::optional<std::size_t> next_timed_event() const;
    void schedule_timed(TimedEvent event);
    [[nodiscard]] std::size_t rdram_offset(std::uint32_t vaddr) const noexcept;

    World& world_;
    VirtualClock& clock_;
    Journal& journal_;
    RomImage rom_;
    StateHashSchema schema_;
    bool rom_valid_ = false;
    bool trapped_ = false;
    std::string trap_operation_;

    std::vector<Thread> threads_;
    std::map<QueueId, Queue> queues_;
    std::vector<TimedEvent> timed_events_;
    std::vector<RspTaskRecord> rsp_tasks_;
    std::map<std::string, StubLedgerEntry> stub_ledger_;

    ThreadId next_thread_id_ = 1U;
    QueueId next_queue_id_ = 1U;
    std::uint64_t next_event_seq_ = 0U;
    std::uint64_t enqueue_seq_ = 0U;
    std::uint64_t vi_retraces_ = 0U;
    std::uint64_t dispatched_events_ = 0U;

    bool vi_registered_ = false;
    QueueId vi_queue_ = kInvalidId;
    Message vi_message_ = 0U;
    std::uint32_t vi_framebuffer_ = 0U;
};

} // namespace jfg::boot
