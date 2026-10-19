#include "jfg/boot/executor.hpp"

#include "jfg/runtime/execution_local.hpp"
#include <exception>
#include <system_error>
#if defined(_WIN32)
#ifndef NOMINMAX
#define NOMINMAX
#endif
#include <windows.h>
#endif

#include <utility>
#include <algorithm>
#include <stdexcept>
#if defined(_M_X64) || defined(__SSE2__)
#include <immintrin.h>
#endif

namespace jfg::boot {

namespace {

// Thrown into a parked participant during shutdown to unwind its body so the
// transport can release its stack cleanly. Never escapes the participant entry.
struct ExecutorShutdown final {};

// The running participant's own id, so yield_to_scheduler() needs no argument.
thread_local int t_self = kSchedulerParticipant;

} // namespace

struct BatonExecutor::FiberState {
#if defined(_WIN32)
    struct Entry {
        BatonExecutor* owner = nullptr;
        int id = -1;
        Body body;
        void* fiber = nullptr;
        std::exception_ptr error;
        std::uint64_t cycle_start=0,cycle_total=0;bool cycle_valid=true;
        jfg::runtime::ExecutionLocalContext local;
    };
    BatonExecutor& owner;
    DWORD thread_id = GetCurrentThreadId();
    void* root = nullptr;
    std::vector<std::unique_ptr<Entry>> entries;

    explicit FiberState(BatonExecutor& executor) : owner(executor) {
        if (IsThreadAFiber() || jfg::runtime::execution_local_context)
            throw std::logic_error("nested or externally owned fiber transport");
        root = ConvertThreadToFiberEx(nullptr, FIBER_FLAG_FLOAT_SWITCH);
        if (!root) throw std::system_error(static_cast<int>(GetLastError()),std::system_category(),"ConvertThreadToFiberEx");
        jfg::runtime::select_execution_local_context(nullptr);
    }
    void require_root() const {
        if (thread_id != GetCurrentThreadId() || !IsThreadAFiber() || GetCurrentFiber()!=root)
            throw std::logic_error("fiber scheduler must stay on its owning stack and thread");
    }
    void begin_cycles(Entry& entry) noexcept {
        if (!owner.timing_enabled_) return;
        const auto sample=BatonExecutor::host_cycles();
        entry.cycle_start=sample.cycles;entry.cycle_valid=entry.cycle_valid && sample.valid;
    }
    void end_cycles(Entry& entry) noexcept {
        if (!owner.timing_enabled_) return;
        const auto sample=BatonExecutor::host_cycles();
        entry.cycle_valid=entry.cycle_valid && sample.valid && sample.cycles>=entry.cycle_start;
        if (entry.cycle_valid) entry.cycle_total+=sample.cycles-entry.cycle_start;
    }
    CycleSample execution_cycles() const noexcept {
        if (thread_id!=GetCurrentThreadId()) return {};
        if (t_self==kSchedulerParticipant) return BatonExecutor::host_cycles();
        if (t_self<0 || static_cast<std::size_t>(t_self)>=entries.size()) return {};
        const auto& entry=*entries[static_cast<std::size_t>(t_self)];
        const auto sample=BatonExecutor::host_cycles();
        const bool valid=owner.timing_enabled_ && entry.cycle_valid && sample.valid && sample.cycles>=entry.cycle_start;
        return {valid?entry.cycle_total+sample.cycles-entry.cycle_start:0U,
            0x80000000U|static_cast<std::uint32_t>(t_self),valid};
    }
    static void WINAPI enter(void* opaque) {
        auto& entry=*static_cast<Entry*>(opaque);
        auto& ex=*entry.owner;
        ex.receive_timing();
        try {
            if (ex.shutting_down_) throw ExecutorShutdown{};
            entry.body(ex,entry.id);
        } catch (const ExecutorShutdown&) {
        } catch (...) { entry.error=std::current_exception(); }
        ex.fibers_->end_cycles(entry);
        ex.participants_[static_cast<std::size_t>(entry.id)].finished=true;
        // Returning a Windows fiber callback terminates the host thread.
        // Park the completed stack permanently; only the scheduler deletes it.
        ex.publish_timing();
        ex.holder_=kSchedulerParticipant;
        t_self=kSchedulerParticipant;
        jfg::runtime::select_execution_local_context(nullptr);
        SwitchToFiber(ex.fibers_->root);
        std::terminate();
    }
    int spawn(Body body) {
        require_root();
        if (owner.shutting_down_) throw std::logic_error("spawn after executor shutdown");
        auto entry=std::make_unique<Entry>();
        entry->owner=&owner;entry->id=static_cast<int>(owner.participants_.size());entry->body=std::move(body);
        owner.participants_.emplace_back();
        try { entries.push_back(std::move(entry)); }
        catch (...) { owner.participants_.pop_back();throw; }
        auto& added=*entries.back();
        // Zero sizes retain the executable's existing stack commit/reserve.
        added.fiber=CreateFiberEx(0,0,FIBER_FLAG_FLOAT_SWITCH,&enter,&added);
        if (!added.fiber) {
            const auto error=GetLastError();entries.pop_back();owner.participants_.pop_back();
            throw std::system_error(static_cast<int>(error),std::system_category(),"CreateFiberEx");
        }
        owner.participants_.back().started=true;
        return added.id;
    }
    bool resume(int id) {
        require_root();
        if (id<0 || static_cast<std::size_t>(id)>=entries.size()) throw std::out_of_range("fiber participant");
        auto& entry=*entries[static_cast<std::size_t>(id)];
        if (!owner.participants_[static_cast<std::size_t>(id)].finished) {
            owner.publish_timing();owner.holder_=id;t_self=id;
            jfg::runtime::select_execution_local_context(&entry.local);
            begin_cycles(entry);
            SwitchToFiber(entry.fiber);
            owner.receive_timing();
        }
        if (entry.error) std::rethrow_exception(std::exchange(entry.error,{}));
        return owner.participants_[static_cast<std::size_t>(id)].finished;
    }
    void yield() {
        const int id=t_self;
        if (thread_id!=GetCurrentThreadId() || id<0 || static_cast<std::size_t>(id)>=entries.size() ||
            GetCurrentFiber()!=entries[static_cast<std::size_t>(id)]->fiber)
            throw std::logic_error("fiber yield outside guest stack");
        end_cycles(*entries[static_cast<std::size_t>(id)]);
        owner.publish_timing();owner.holder_=kSchedulerParticipant;t_self=kSchedulerParticipant;
        jfg::runtime::select_execution_local_context(nullptr);
        SwitchToFiber(root);
        owner.receive_timing();
        if (owner.shutting_down_) throw ExecutorShutdown{};
    }
    void shutdown() {
        require_root();owner.shutting_down_=true;
        for (std::size_t i=0;i<entries.size();++i) {
            if (!owner.participants_[i].finished) {
                try { (void)resume(static_cast<int>(i)); }
                catch (...) { /* body exception has been captured; its stack is unwound */ }
                if (!owner.participants_[i].finished) std::terminate();
            }
            DeleteFiber(entries[i]->fiber);
        }
        entries.clear();
        jfg::runtime::select_execution_local_context(nullptr);
        if (!ConvertFiberToThread()) std::terminate();
        root=nullptr;
    }
#else
    explicit FiberState(BatonExecutor&) { throw std::logic_error("Windows fibers unavailable"); }
    int spawn(Body) { throw std::logic_error("Windows fibers unavailable"); }
    bool resume(int) { throw std::logic_error("Windows fibers unavailable"); }
    void yield() { throw std::logic_error("Windows fibers unavailable"); }
    void shutdown() {}
    CycleSample execution_cycles() const noexcept { return {}; }
#endif
};

BatonExecutor::BatonExecutor() = default;
BatonExecutor::CycleSample BatonExecutor::host_cycles() noexcept {
#if defined(_WIN32)
    ULONG64 cycles=0;
    const bool valid=QueryThreadCycleTime(GetCurrentThread(),&cycles)!=0;
    return {cycles,GetCurrentThreadId(),valid};
#else
    return {};
#endif
}
BatonExecutor::CycleSample BatonExecutor::execution_cycles() const noexcept {
    return fibers_?fibers_->execution_cycles():host_cycles();
}
bool BatonExecutor::fibers_supported() noexcept {
#if defined(_WIN32) && !defined(JFG_ADDRESS_SANITIZER) && !defined(__SANITIZE_ADDRESS__)
    return true;
#else
    return false;
#endif
}
void BatonExecutor::set_fiber_mode(bool enabled) {
    if (!participants_.empty() || shutting_down_) throw std::logic_error("fiber mode must be configured before spawn");
    if (enabled) {
        if (!fibers_supported()) throw std::logic_error("fiber mode unavailable for this build");
        if (!fibers_) fibers_=std::make_unique<FiberState>(*this);
    } else if (fibers_) { fibers_->shutdown();fibers_.reset();shutting_down_=false; }
}

void BatonExecutor::set_spin_budget(unsigned microseconds) {
    std::lock_guard<std::mutex> lock(mutex_);
    if (!participants_.empty()) throw std::logic_error("spin budget must be configured before spawn");
    if (microseconds > 100U) throw std::invalid_argument("spin budget exceeds 100 microseconds");
    spin_microseconds_ = microseconds;
}

void BatonExecutor::enable_timing(bool enabled) {
    std::lock_guard<std::mutex> lock(mutex_);
    if (!participants_.empty()) throw std::logic_error("timing must be configured before spawn");
    timing_enabled_ = enabled;
}
BatonExecutor::Timing BatonExecutor::timing() {
    std::lock_guard<std::mutex> lock(mutex_);
    return timing_;
}
void BatonExecutor::publish_timing() {
    if (timing_enabled_) handoff_started_ = std::chrono::steady_clock::now();
}
void BatonExecutor::receive_timing() {
    if (!timing_enabled_) return;
    const auto elapsed = static_cast<std::uint64_t>(std::chrono::duration_cast<std::chrono::nanoseconds>(
        std::chrono::steady_clock::now() - handoff_started_).count());
    ++timing_.wakes;
    timing_.wake_ns += elapsed;
    timing_.max_wake_ns = (std::max)(timing_.max_wake_ns, elapsed);
}

BatonExecutor::~BatonExecutor() {
    shutdown();
}

int BatonExecutor::spawn(Body body) {
    if (fibers_) return fibers_->spawn(std::move(body));
    std::unique_lock<std::mutex> lock(mutex_);
    const int id = static_cast<int>(participants_.size());
    participants_.emplace_back();
    participants_[static_cast<std::size_t>(id)].started = true;
    // The new thread immediately parks on the baton (holder_ != id), so it
    // touches nothing until the scheduler resumes it.
    participants_[static_cast<std::size_t>(id)].thread =
        std::thread([this, id, body = std::move(body)]() {
            participant_main(id, body);
        });
    return id;
}

void BatonExecutor::participant_main(const int id, Body body) {
    t_self = id;
    wait_until_holder(id);
    try {
        if (shutting_down_) {
            throw ExecutorShutdown{};
        }
        body(*this, id);
    } catch (const ExecutorShutdown&) {
        // Cooperative cancellation during shutdown; fall through to hand back.
    }
    {
        std::unique_lock<std::mutex> lock(mutex_);
        participants_[static_cast<std::size_t>(id)].finished = true;
        publish_timing();
        holder_ = kSchedulerParticipant;
    }
    cv_.notify_one();
}

bool BatonExecutor::resume(const int id) {
    if (fibers_) return fibers_->resume(id);
    hand_off(id);
    wait_until_holder(kSchedulerParticipant);
    std::unique_lock<std::mutex> lock(mutex_);
    return participants_[static_cast<std::size_t>(id)].finished;
}

void BatonExecutor::yield_to_scheduler() {
    if (fibers_) { fibers_->yield(); return; }
    const int self = t_self;
    hand_off(kSchedulerParticipant);
    wait_until_holder(self);
    if (shutting_down_) {
        throw ExecutorShutdown{};
    }
}

void BatonExecutor::hand_off(const int to) {
    std::condition_variable *ready = nullptr;
    {
        std::unique_lock<std::mutex> lock(mutex_);
        publish_timing();
        holder_ = to;
        ready = to == kSchedulerParticipant ? &cv_
            : participants_[static_cast<std::size_t>(to)].ready.get();
    }
    // Only the selected baton recipient can run. Waking the other parked
    // guest threads just makes them contend for this mutex and sleep again.
    ready->notify_one();
}

void BatonExecutor::wait_until_holder(const int self) {
    // Poll only the published recipient. Shared scheduler/guest data is still
    // acquired through the original mutex and predicate below. No participant
    // executes a guest instruction before receiving the existing baton.
    if (spin_microseconds_ != 0U && holder_.load(std::memory_order_acquire) != self) {
        const auto deadline = std::chrono::steady_clock::now() +
            std::chrono::microseconds(spin_microseconds_);
        while (holder_.load(std::memory_order_acquire) != self) {
            for (unsigned n = 0; n < 32U; ++n) {
#if defined(_M_X64) || defined(__SSE2__)
                _mm_pause();
#else
                std::atomic_signal_fence(std::memory_order_seq_cst);
#endif
                if (holder_.load(std::memory_order_acquire) == self) break;
            }
            if (std::chrono::steady_clock::now() >= deadline) break;
        }
    }
    std::unique_lock<std::mutex> lock(mutex_);
    auto &ready = self == kSchedulerParticipant ? cv_
        : *participants_[static_cast<std::size_t>(self)].ready;
    ready.wait(lock, [&]() { return holder_ == self; });
    receive_timing();
}

void BatonExecutor::shutdown() {
    if (fibers_) { fibers_->shutdown(); fibers_.reset(); return; }
    // Unwind each unfinished participant one at a time, in id order. Only the
    // baton holder ever runs, so this stays deterministic and race-free.
    for (std::size_t index = 0; index < participants_.size(); ++index) {
        bool finished = false;
        {
            std::unique_lock<std::mutex> lock(mutex_);
            finished = participants_[index].finished;
            if (!finished) {
                shutting_down_ = true;
            }
        }
        if (!finished) {
            (void)resume(static_cast<int>(index));
        }
    }
    for (Participant& participant : participants_) {
        if (participant.thread.joinable()) {
            participant.thread.join();
        }
    }
}

} // namespace jfg::boot
