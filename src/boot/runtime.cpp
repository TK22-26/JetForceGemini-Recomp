#include "jfg/boot/runtime.hpp"

#include <algorithm>
#include <cstring>

#include "jfg/testkernel/sha256.hpp"

namespace jfg::boot {

namespace {

void put_u32(std::vector<std::byte>& out, const std::uint32_t value) {
    for (std::size_t i = 0; i < 4U; ++i) {
        out.push_back(static_cast<std::byte>(value >> (8U * i)));
    }
}

void put_u64(std::vector<std::byte>& out, const std::uint64_t value) {
    for (std::size_t i = 0; i < 8U; ++i) {
        out.push_back(static_cast<std::byte>(value >> (8U * i)));
    }
}

} // namespace

std::optional<RomImage> RomImage::create(std::vector<std::uint8_t> bytes) {
    // A valid image needs at least a header word and must present the
    // big-endian .z64 magic. Byte-swapped (.n64/.v64) images are rejected
    // rather than silently reinterpreted.
    if (bytes.size() < 4U) {
        return std::nullopt;
    }
    const std::uint32_t magic = (std::uint32_t{bytes[0]} << 24U) |
        (std::uint32_t{bytes[1]} << 16U) | (std::uint32_t{bytes[2]} << 8U) |
        std::uint32_t{bytes[3]};
    if (magic != kZ64Magic) {
        return std::nullopt;
    }
    return RomImage(std::move(bytes));
}

BootRuntime::BootRuntime(World& world, VirtualClock& clock, Journal& journal,
                         RomImage rom, StateHashSchema schema)
    : world_(world),
      clock_(clock),
      journal_(journal),
      rom_(std::move(rom)),
      schema_(std::move(schema)) {
    rom_valid_ = rom_.size() >= 4U;
    // A thread body may create further threads while it is executing; the
    // storage backing the running body must not reallocate underneath it, so
    // reserve the whole capacity up front. create_thread caps at kMaxThreads.
    threads_.reserve(kMaxThreads);
}

void BootRuntime::log(const JournalEffect effect, const std::string_view label,
                      std::vector<std::byte> payload) {
    (void)journal_.append(
        effect, label, std::span<const std::byte>(payload.data(), payload.size()));
}

void BootRuntime::note_event(const std::string_view name,
                             const std::uint64_t a, const std::uint64_t b) {
    std::vector<std::byte> payload;
    put_u64(payload, clock_.now());
    put_u64(payload, a);
    put_u64(payload, b);
    log(JournalEffect::kCheckpoint, name, std::move(payload));
    ++dispatched_events_;
}

std::size_t BootRuntime::rdram_offset(const std::uint32_t vaddr) const noexcept {
    return static_cast<std::size_t>(vaddr - kKseg0Base);
}

ThreadId BootRuntime::create_thread(
    const std::uint32_t priority, std::string label, ThreadBody body) {
    if (threads_.size() >= kMaxThreads || !body) {
        trap_unsupported("create_thread:capacity");
        return kInvalidId;
    }
    Thread thread;
    thread.id = next_thread_id_++;
    thread.priority = priority;
    thread.label = std::move(label);
    thread.body = std::move(body);
    thread.runnable = true;
    thread.enqueue_seq = enqueue_seq_++;
    const ThreadId id = thread.id;
    threads_.push_back(std::move(thread));
    note_event("thread.create", id, priority);
    return id;
}

QueueId BootRuntime::create_queue(std::string label, const std::size_t depth) {
    if (queues_.size() >= kMaxQueues || depth == 0U ||
        depth > kMaxQueueDepth) {
        trap_unsupported("create_queue:capacity");
        return kInvalidId;
    }
    const QueueId id = next_queue_id_++;
    Queue queue;
    queue.id = id;
    queue.label = std::move(label);
    queue.depth = depth;
    queues_.emplace(id, std::move(queue));
    note_event("queue.create", id, depth);
    return id;
}

bool BootRuntime::deliver_or_enqueue(
    const QueueId queue, const Message message, const bool jam) {
    // A blocked receiver takes the message directly and wakes; ties break by
    // the order threads blocked (deterministic).
    std::optional<std::size_t> receiver;
    for (std::size_t i = 0; i < threads_.size(); ++i) {
        const Thread& thread = threads_[i];
        if (thread.blocked && thread.blocked_on == queue) {
            if (!receiver.has_value() ||
                threads_[*receiver].enqueue_seq > thread.enqueue_seq) {
                receiver = i;
            }
        }
    }
    if (receiver.has_value()) {
        Thread& thread = threads_[*receiver];
        thread.blocked = false;
        thread.blocked_on = kInvalidId;
        thread.runnable = true;
        thread.pending_delivery = message;
        return true;
    }
    const auto found = queues_.find(queue);
    if (found == queues_.end() || found->second.messages.size() >=
                                      found->second.depth) {
        return false;
    }
    if (jam) {
        found->second.messages.insert(found->second.messages.begin(), message);
    } else {
        found->second.messages.push_back(message);
    }
    return true;
}

bool BootRuntime::send_message(
    const QueueId queue, const Message message, const bool jam) {
    if (queues_.find(queue) == queues_.end()) {
        trap_unsupported("send_message:unknown-queue");
        return false;
    }
    const bool ok = deliver_or_enqueue(queue, message, jam);
    if (!ok) {
        return false; // full queue is a caller-visible condition, not a trap
    }
    note_event(jam ? "queue.jam" : "queue.send", queue, message);
    return true;
}

bool BootRuntime::set_timer(
    const QueueId queue, const Message message, const std::uint64_t delay) {
    if (queues_.find(queue) == queues_.end() ||
        timed_events_.size() >= kMaxTimedEvents || delay == 0U) {
        trap_unsupported("set_timer:invalid");
        return false;
    }
    TimedEvent event;
    event.due = clock_.now() + delay;
    event.seq = next_event_seq_++;
    event.queue = queue;
    event.message = message;
    schedule_timed(std::move(event));
    note_event("timer.set", queue, delay);
    return true;
}

bool BootRuntime::start_pi_dma(
    const QueueId queue, const Message message, const std::uint32_t ram_vaddr,
    const std::uint32_t cart_offset, const std::uint32_t length) {
    if (queues_.find(queue) == queues_.end() ||
        timed_events_.size() >= kMaxTimedEvents) {
        trap_unsupported("pi_dma:invalid-queue");
        return false;
    }
    if (ram_vaddr < kKseg0Base) {
        trap_unsupported("pi_dma:non-kseg0");
        return false;
    }
    const std::size_t ram = rdram_offset(ram_vaddr);
    if (length == 0U || ram + length < ram ||
        ram + length > world_.rdram().size() ||
        static_cast<std::size_t>(cart_offset) + length < cart_offset ||
        static_cast<std::size_t>(cart_offset) + length > rom_.size()) {
        trap_unsupported("pi_dma:out-of-range");
        return false;
    }
    TimedEvent event;
    event.due = clock_.now() + kPiDmaBaseTicks + length * kPiDmaTicksPerByte;
    event.seq = next_event_seq_++;
    event.queue = queue;
    event.message = message;
    event.dma_ram_vaddr = ram_vaddr;
    event.dma_cart_offset = cart_offset;
    event.dma_length = length;
    event.is_dma = true;
    schedule_timed(std::move(event));
    note_event("pi_dma.start", ram_vaddr, length);
    return true;
}

bool BootRuntime::register_vi_client(
    const QueueId queue, const Message message) {
    if (queues_.find(queue) == queues_.end()) {
        trap_unsupported("vi_client:unknown-queue");
        return false;
    }
    vi_registered_ = true;
    vi_queue_ = queue;
    vi_message_ = message;
    note_event("vi.register", queue, message);
    return true;
}

bool BootRuntime::vi_swap_buffer(const std::uint32_t framebuffer_vaddr) {
    if (framebuffer_vaddr < kKseg0Base ||
        rdram_offset(framebuffer_vaddr) >= world_.rdram().size()) {
        trap_unsupported("vi_swap:bad-framebuffer");
        return false;
    }
    vi_framebuffer_ = framebuffer_vaddr;
    note_event("vi.swap", framebuffer_vaddr, 0U);
    return true;
}

bool BootRuntime::submit_rsp_task(RspTaskRecord task) {
    if (rsp_tasks_.size() >= kMaxRspTasks) {
        trap_unsupported("rsp_task:capacity");
        return false;
    }
    task.tick = clock_.now();
    // Captured for Phase 7; the renderer/audio path is disabled here, so this
    // records the submission without changing simulation state.
    std::vector<std::byte> payload;
    put_u32(payload, task.task_type);
    put_u32(payload, task.ucode_boot_paddr);
    put_u32(payload, task.data_ptr);
    put_u32(payload, task.data_size);
    log(JournalEffect::kRendererSubmit, "rsp.task",
        std::move(payload));
    rsp_tasks_.push_back(task);
    ++dispatched_events_;
    return true;
}

bool BootRuntime::write_u32(
    const std::uint32_t vaddr, const std::uint32_t value) {
    if (vaddr < kKseg0Base || (vaddr & 3U) != 0U) {
        trap_unsupported("write_u32:misaligned-or-low");
        return false;
    }
    const std::size_t offset = rdram_offset(vaddr);
    if (offset + 4U > world_.rdram().size()) {
        trap_unsupported("write_u32:out-of-range");
        return false;
    }
    auto memory = world_.rdram();
    for (std::size_t i = 0; i < 4U; ++i) {
        memory[offset + i] = static_cast<std::uint8_t>(value >> (24U - 8U * i));
    }
    return true;
}

std::optional<std::uint32_t> BootRuntime::read_u32(
    const std::uint32_t vaddr) const {
    if (vaddr < kKseg0Base || (vaddr & 3U) != 0U) {
        return std::nullopt;
    }
    const std::size_t offset = rdram_offset(vaddr);
    if (offset + 4U > world_.rdram().size()) {
        return std::nullopt;
    }
    const auto memory = world_.rdram();
    std::uint32_t value = 0U;
    for (std::size_t i = 0; i < 4U; ++i) {
        value |= std::uint32_t{memory[offset + i]} << (24U - 8U * i);
    }
    return value;
}

void BootRuntime::trap_unsupported(const std::string_view operation) {
    const std::string key(operation);
    auto found = stub_ledger_.find(key);
    if (found == stub_ledger_.end()) {
        StubLedgerEntry entry;
        entry.operation = key;
        entry.disposition = "fail-closed-trap";
        entry.first_seen_tick = clock_.now();
        entry.count = 1U;
        stub_ledger_.emplace(key, std::move(entry));
    } else {
        ++found->second.count;
    }
    if (!trapped_) {
        trapped_ = true;
        trap_operation_ = key;
    }
    std::vector<std::byte> payload;
    put_u64(payload, clock_.now());
    log(JournalEffect::kHostCallRejected, operation, std::move(payload));
}

std::optional<std::size_t> BootRuntime::pick_runnable() const {
    std::optional<std::size_t> best;
    for (std::size_t i = 0; i < threads_.size(); ++i) {
        const Thread& thread = threads_[i];
        if (!thread.runnable || thread.exited || thread.blocked) {
            continue;
        }
        if (!best.has_value()) {
            best = i;
            continue;
        }
        const Thread& current = threads_[*best];
        // Highest priority first; ties break by thread id (creation order).
        if (thread.priority > current.priority ||
            (thread.priority == current.priority && thread.id < current.id)) {
            best = i;
        }
    }
    return best;
}

void BootRuntime::schedule_timed(TimedEvent event) {
    timed_events_.push_back(std::move(event));
}

std::optional<std::size_t> BootRuntime::next_timed_event() const {
    std::optional<std::size_t> best;
    for (std::size_t i = 0; i < timed_events_.size(); ++i) {
        if (!best.has_value()) {
            best = i;
            continue;
        }
        const TimedEvent& candidate = timed_events_[i];
        const TimedEvent& current = timed_events_[*best];
        if (candidate.due < current.due ||
            (candidate.due == current.due && candidate.seq < current.seq)) {
            best = i;
        }
    }
    return best;
}

BootReport BootRuntime::run(
    const std::uint64_t target_retraces, const std::uint64_t step_limit) {
    BootReport report;
    if (!rom_valid_) {
        report.status = BootStatus::kInvalidRom;
        report.journal_hex = jfg::testkernel::hex_digest(journal_.digest());
        const auto hash = world_.hash(schema_);
        report.state_hash_hex =
            hash.has_value() ? jfg::testkernel::hex_digest(*hash) : "";
        return report;
    }

    // Seed the first VI retrace; it reschedules itself each period.
    {
        TimedEvent vi;
        vi.due = clock_.now() + kViRetracePeriodTicks;
        vi.seq = next_event_seq_++;
        vi.is_vi = true;
        schedule_timed(std::move(vi));
    }

    std::uint64_t steps = 0U;
    BootStatus status = BootStatus::kDeadlocked;
    while (true) {
        if (trapped_) {
            status = BootStatus::kTrapped;
            break;
        }
        if (vi_retraces_ >= target_retraces) {
            status = BootStatus::kReachedStableVi;
            break;
        }
        const std::optional<std::size_t> runnable = pick_runnable();
        if (runnable.has_value()) {
            if (steps >= step_limit) {
                status = BootStatus::kUnbounded;
                break;
            }
            ++steps;
            Thread& thread = threads_[*runnable];
            const std::optional<Message> received = thread.pending_delivery;
            thread.pending_delivery.reset();
            const ThreadDirective directive = thread.body(*this, received);
            // The body may have trapped via a runtime call; re-check next loop.
            if (directive.wait == ThreadWait::kExit) {
                thread.exited = true;
                thread.runnable = false;
                note_event("thread.exit", thread.id, 0U);
            } else if (directive.wait == ThreadWait::kReceive) {
                const auto found = queues_.find(directive.queue);
                if (found == queues_.end()) {
                    trap_unsupported("receive:unknown-queue");
                } else if (!found->second.messages.empty()) {
                    const Message message = found->second.messages.front();
                    found->second.messages.erase(
                        found->second.messages.begin());
                    thread.pending_delivery = message;
                    thread.runnable = true;
                } else {
                    thread.runnable = false;
                    thread.blocked = true;
                    thread.blocked_on = directive.queue;
                    thread.enqueue_seq = enqueue_seq_++;
                }
            } else {
                thread.runnable = true;
            }
            continue;
        }

        // No runnable thread: advance virtual time to the next event.
        const std::optional<std::size_t> event_index = next_timed_event();
        if (!event_index.has_value()) {
            status = BootStatus::kDeadlocked;
            break;
        }
        TimedEvent event = timed_events_[*event_index];
        timed_events_.erase(
            timed_events_.begin() +
            static_cast<std::ptrdiff_t>(*event_index));
        clock_.advance_to(event.due);

        if (event.is_vi) {
            ++vi_retraces_;
            note_event("vi.retrace", vi_retraces_, 0U);
            if (vi_registered_) {
                (void)deliver_or_enqueue(vi_queue_, vi_message_, false);
            }
            TimedEvent next;
            next.due = clock_.now() + kViRetracePeriodTicks;
            next.seq = next_event_seq_++;
            next.is_vi = true;
            schedule_timed(std::move(next));
        } else if (event.is_dma) {
            const std::size_t ram = rdram_offset(event.dma_ram_vaddr);
            auto memory = world_.rdram();
            std::memcpy(memory.data() + ram,
                        rom_.bytes().data() + event.dma_cart_offset,
                        event.dma_length);
            note_event("pi_dma.done", event.dma_ram_vaddr, event.dma_length);
            (void)deliver_or_enqueue(event.queue, event.message, false);
        } else {
            note_event("timer.fire", event.queue, event.message);
            (void)deliver_or_enqueue(event.queue, event.message, false);
        }
    }

    report.status = status;
    report.vi_retraces = vi_retraces_;
    report.dispatched_events = dispatched_events_;
    report.final_tick = clock_.now();
    report.threads_created = next_thread_id_ - 1U;
    report.journal_hex = jfg::testkernel::hex_digest(journal_.digest());
    const auto hash = world_.hash(schema_);
    report.state_hash_hex =
        hash.has_value() ? jfg::testkernel::hex_digest(*hash) : "";
    report.rsp_tasks = rsp_tasks_;
    report.trap_operation = trap_operation_;
    for (const auto& [key, entry] : stub_ledger_) {
        report.stub_ledger.push_back(entry);
    }
    return report;
}

} // namespace jfg::boot
