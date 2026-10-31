// Phase 6 thread-scheduler HLE tests. ROM-free: synthetic producer/consumer
// thread bodies exercise osCreateThread/osStartThread + blocking osRecvMesg /
// waking osSendMesg through guest OSMesgQueue structures on a local RDRAM.

#include "jfg/boot/thread_scheduler.hpp"

#include <cstdint>
#include <iostream>
#include <memory>
#include <span>
#include <string_view>
#include <vector>

namespace {

using namespace jfg::boot;

int failures = 0;

void check(const bool condition, const std::string_view message) {
    if (!condition) {
        ++failures;
        std::cerr << "FAIL: " << message << '\n';
    }
}

constexpr std::uint32_t kQueue = 0x80001000U;
constexpr std::uint32_t kMsgBuf = 0x80001100U;
constexpr std::uint32_t kOutSlot = 0x80002000U;

void test_producer_consumer_blocks_and_wakes() {
    std::vector<std::uint8_t> rdram(0x10000U, 0U);
    ThreadScheduler scheduler(
        hle::GuestMemory(std::span<std::uint8_t>(rdram.data(), rdram.size())));
    check(scheduler.create_queue(kQueue, kMsgBuf, 4), "queue created");

    std::vector<std::uint32_t> consumed;

    // Consumer (higher priority): blocks on the queue, records 3 messages.
    const int consumer = scheduler.create_thread(
        10U, [&consumed](ThreadScheduler& sched, int) {
            for (int i = 0; i < 3; ++i) {
                (void)sched.recv_blocking(kQueue, kOutSlot);
                std::uint32_t got = 0U;
                (void)sched.memory().read_u32(kOutSlot, got);
                consumed.push_back(got);
            }
        });
    // Producer (lower priority): sends 3 messages then exits.
    const int producer = scheduler.create_thread(
        5U, [](ThreadScheduler& sched, int) {
            for (std::uint32_t i = 0; i < 3U; ++i) {
                (void)sched.send(kQueue, 0x1000U + i, false);
            }
        });

    scheduler.start_thread(consumer);
    scheduler.start_thread(producer);

    const ScheduleOutcome outcome = scheduler.run(1000U);
    check(outcome == ScheduleOutcome::kAllFinished,
          "all threads finished");
    check(scheduler.state_of(consumer) == ThreadState::kFinished,
          "consumer finished");
    check(scheduler.state_of(producer) == ThreadState::kFinished,
          "producer finished");
    const std::vector<std::uint32_t> expected = {0x1000U, 0x1001U, 0x1002U};
    check(consumed == expected,
          "consumer received all messages in FIFO order across blocks/wakes");
}

void test_consumer_blocks_when_no_producer() {
    std::vector<std::uint8_t> rdram(0x10000U, 0U);
    ThreadScheduler scheduler(
        hle::GuestMemory(std::span<std::uint8_t>(rdram.data(), rdram.size())));
    check(scheduler.create_queue(kQueue, kMsgBuf, 4), "queue created");
    const int consumer = scheduler.create_thread(
        10U, [](ThreadScheduler& sched, int) {
            (void)sched.recv_blocking(kQueue, kOutSlot); // never satisfied
        });
    scheduler.start_thread(consumer);
    const ScheduleOutcome outcome = scheduler.run(1000U);
    check(outcome == ScheduleOutcome::kQuiescent,
          "a lone blocked receiver leaves the scheduler quiescent, not spinning");
    check(scheduler.state_of(consumer) == ThreadState::kBlocked,
          "consumer remains blocked");
    // Executor destructor must unwind the still-blocked thread cleanly.
}

void test_priority_order_and_determinism() {
    const auto run_once = []() {
        std::vector<std::uint8_t> rdram(0x10000U, 0U);
        auto log = std::make_shared<std::vector<int>>();
        ThreadScheduler scheduler(hle::GuestMemory(
            std::span<std::uint8_t>(rdram.data(), rdram.size())));
        // Three threads that just record their id and exit; higher priority
        // must run first.
        const int low = scheduler.create_thread(
            1U, [log](ThreadScheduler&, int id) { log->push_back(id); });
        const int high = scheduler.create_thread(
            9U, [log](ThreadScheduler&, int id) { log->push_back(id); });
        const int mid = scheduler.create_thread(
            5U, [log](ThreadScheduler&, int id) { log->push_back(id); });
        scheduler.start_thread(low);
        scheduler.start_thread(high);
        scheduler.start_thread(mid);
        (void)scheduler.run(1000U);
        return *log;
    };
    const std::vector<int> first = run_once();
    const std::vector<int> second = run_once();
    // high(id1), mid(id2), low(id0) by priority.
    const std::vector<int> expected = {1, 2, 0};
    check(first == expected, "threads run in priority order");
    check(first == second, "schedule is deterministic across runs");
}

void test_deterministic_interrupt_preemption() {
    std::vector<std::uint8_t> rdram(0x10000U, 0U);
    ThreadScheduler scheduler(
        hle::GuestMemory(std::span<std::uint8_t>(rdram.data(), rdram.size())));
    std::vector<int> checkpoints;
    const int thread = scheduler.create_thread(
        10U, [&checkpoints](ThreadScheduler& sched, int) {
            checkpoints.push_back(1);
            sched.preempt_current();
            checkpoints.push_back(2);
        });
    scheduler.start_thread(thread);

    check(scheduler.run(1000U) == ScheduleOutcome::kTimeslice,
          "interrupt preemption returns control to the scheduler caller");
    check(checkpoints == std::vector<int>{1},
          "preempted guest stack remains suspended");
    check(scheduler.state_of(thread) == ThreadState::kRunnable,
          "preempted thread remains runnable");
    check(scheduler.run(1000U) == ScheduleOutcome::kAllFinished,
          "a second schedule resumes the preempted stack");
    check(checkpoints == std::vector<int>({1, 2}),
          "preempted guest stack resumes at the exact yield point");
}

void test_one_waiter_fifo() {
    std::vector<std::uint8_t> rdram(0x10000U, 0U);
    ThreadScheduler scheduler{hle::GuestMemory(rdram)};
    check(scheduler.create_queue(kQueue, kMsgBuf, 1), "create one-slot queue");
    const auto receive = [](ThreadScheduler& sched, int) {
        (void)sched.recv_blocking(kQueue, 0U);
    };
    const int earlier_id = scheduler.create_thread(5U, receive);
    const int first_waiter = scheduler.create_thread(5U, receive);
    scheduler.start_thread(first_waiter);
    check(scheduler.run(100) == ScheduleOutcome::kQuiescent, "first waiter blocks");
    scheduler.start_thread(earlier_id);
    check(scheduler.run(100) == ScheduleOutcome::kQuiescent, "second waiter blocks");
    check(scheduler.send(kQueue, 1U, false) == 0, "send one message");
    check(scheduler.state_of(first_waiter) == ThreadState::kRunnable,
          "first equal-priority waiter wakes regardless of creation id");
    check(scheduler.state_of(earlier_id) == ThreadState::kBlocked,
          "one message wakes exactly one receiver");
}

void test_blocking_send_and_jam() {
    for (const bool jam : {false, true}) {
        std::vector<std::uint8_t> rdram(0x10000U, 0U);
        ThreadScheduler scheduler{hle::GuestMemory(rdram)};
        check(scheduler.create_queue(kQueue, kMsgBuf, 2), "create full queue");
        check(scheduler.send(kQueue, 11U, false) == 0 &&
              scheduler.send(kQueue, 22U, false) == 0, "fill queue");
        check(scheduler.send(kQueue, 99U, jam) == hle::kOsFull,
              "nonblocking full send does not enqueue");
        std::vector<int> order;
        std::vector<std::uint32_t> messages;
        const int sender = scheduler.create_thread(10U, [&](ThreadScheduler& sched, int) {
            check(sched.send_blocking(kQueue, 33U, jam) == 0, "blocked send succeeds");
            order.push_back(2);
        });
        scheduler.start_thread(sender);
        check(scheduler.run(100) == ScheduleOutcome::kQuiescent,
              "full send parks without spinning");
        check(scheduler.state_of(sender) == ThreadState::kBlocked && order.empty(),
              "sender has not returned before space is available");
        const int receiver = scheduler.create_thread(5U, [&](ThreadScheduler& sched, int) {
            order.push_back(1);
            for (unsigned index = 0; index < 3; ++index) {
                check(sched.recv_blocking(kQueue, kOutSlot) == 0, "receive queued message");
                std::uint32_t value = 0;
                check(sched.memory().read_u32(kOutSlot, value), "read received message");
                messages.push_back(value);
                if (index == 0) order.push_back(3);
            }
        });
        scheduler.start_thread(receiver);
        check(scheduler.run(100) == ScheduleOutcome::kAllFinished, "send and receive finish");
        check(order == std::vector<int>({1, 2, 3}), "higher-priority sender runs before receive returns");
        check(messages == (jam ? std::vector<std::uint32_t>{11, 33, 22} :
                                  std::vector<std::uint32_t>{11, 22, 33}),
              "blocked payload retained exactly once with correct send/jam order");
    }
}

void test_sender_priority_and_fifo() {
    std::vector<std::uint8_t> rdram(0x10000U, 0U);
    ThreadScheduler scheduler{hle::GuestMemory(rdram)};
    check(scheduler.create_queue(kQueue, kMsgBuf, 1), "create priority queue");
    check(scheduler.send(kQueue, 0, false) == 0, "fill priority queue");
    const auto send = [](ThreadScheduler& sched, int id) {
        (void)sched.send_blocking(kQueue, static_cast<std::uint32_t>(id), false);
    };
    const int last_equal = scheduler.create_thread(5, send);
    const int first_equal = scheduler.create_thread(5, send);
    const int highest = scheduler.create_thread(9, send);
    for (int id : {first_equal, highest, last_equal}) {
        scheduler.start_thread(id);
        check(scheduler.run(100) == ScheduleOutcome::kQuiescent, "sender blocks");
    }
    for (int expected : {highest, first_equal, last_equal}) {
        check(hle::os_recv_mesg(scheduler.memory(), kQueue, 0) == 0, "free one slot");
        scheduler.notify_received(kQueue);
        check(scheduler.state_of(expected) == ThreadState::kRunnable, "priority/FIFO sender selected");
        for (int id : {last_equal, first_equal, highest}) {
            if (id != expected && scheduler.state_of(id) != ThreadState::kFinished)
                check(scheduler.state_of(id) == ThreadState::kBlocked, "other senders stay asleep");
        }
        (void)scheduler.run(100);
        check(scheduler.state_of(expected) == ThreadState::kFinished, "selected sender completes");
    }
}

// Mirrors phase9_cpu_queue_threads_micro.S's ROM-owned OS experiment.
// Yield explicitly where the native OS bridge reschedules; send() itself
// is also used by host devices and deliberately does not perform a yield.
void test_original_os_handoff_scenario() {
    std::vector<std::uint8_t> rdram(0x10000U, 0U);
    ThreadScheduler scheduler{hle::GuestMemory(rdram)};
    check(scheduler.create_queue(kQueue, kMsgBuf, 1), "oracle one-slot queue");
    std::vector<std::uint32_t> payloads;
    int worker = -1;
    const auto receive = [&](ThreadScheduler& sched) {
        check(sched.recv_blocking(kQueue, kOutSlot) == 0, "oracle receive succeeds");
        std::uint32_t value = 0;
        check(sched.memory().read_u32(kOutSlot, value), "oracle payload readable");
        payloads.push_back(value);
    };
    const int main_thread = scheduler.create_thread(30, [&](ThreadScheduler& sched, int id) {
        sched.start_thread(worker);
        sched.yield_current();
        check(sched.state_of(worker) == ThreadState::kBlocked, "worker waits for first message");
        check(sched.set_priority(id, 50), "raise main priority");
        check(sched.send(kQueue, 1111, false) == 0, "wake lower-priority worker");
        sched.yield_current();
        check(payloads.empty() && sched.state_of(worker) == ThreadState::kRunnable,
              "lower-priority waiter wakes but cannot preempt sender");
        check(sched.set_priority(id, 30), "lower main priority");
        sched.yield_current();
        check(payloads == std::vector<std::uint32_t>{1111} &&
              sched.state_of(worker) == ThreadState::kBlocked, "worker waits for second message");
        check(sched.send(kQueue, 2222, false) == 0, "wake higher-priority worker");
        sched.yield_current();
        check(payloads == std::vector<std::uint32_t>({1111, 2222}) &&
              sched.state_of(worker) == ThreadState::kBlocked, "worker blocks sending to full queue");
        receive(sched);
        check(sched.state_of(worker) == ThreadState::kFinished,
              "space waiter resumed before main receive returned");
        receive(sched);
    });
    worker = scheduler.create_thread(40, [&](ThreadScheduler& sched, int) {
        receive(sched);
        receive(sched);
        check(sched.send(kQueue, 3333, false) == 0, "worker fills queue");
        check(sched.send_blocking(kQueue, 4444, false) == 0, "worker completes blocked send");
    });
    scheduler.start_thread(main_thread);
    check(scheduler.run(100) == ScheduleOutcome::kAllFinished, "oracle scenario completes");
    check(payloads == std::vector<std::uint32_t>({1111, 2222, 3333, 4444}),
          "native payloads match original-OS black-box result");
}

void test_context_baton_hook() {
    std::vector<std::uint8_t> rdram(0x10000U, 0U);
    ThreadScheduler scheduler{hle::GuestMemory(rdram)};
    check(scheduler.create_queue(kQueue, kMsgBuf, 1), "context hook queue");
    std::vector<unsigned> saved{63, 63};
    unsigned live = 0;
    std::vector<std::pair<int, bool>> events;
    check(scheduler.set_baton_hook([&](int id, bool entering) {
        check(scheduler.current_thread_id() == id, "hook identifies baton owner");
        check(!scheduler.set_baton_hook({}), "hook cannot replace itself during handoff");
        events.emplace_back(id, entering);
        if (entering) live = saved[static_cast<std::size_t>(id)];
        else saved[static_cast<std::size_t>(id)] = live;
    }), "install context hook before running");
    int worker = -1;
    const int main_thread = scheduler.create_thread(1, [&](ThreadScheduler& sched, int) {
        check(live == 63, "initial main context");
        live = 62;
        sched.start_thread(worker);
        sched.yield_current();
        check(live == 62, "main restored after worker blocks");
        check(sched.send(kQueue, 41, false) == 0, "wake context worker");
        sched.preempt_current();
        check(live == 62, "main restored after preemption and worker completion");
    });
    worker = scheduler.create_thread(2, [&](ThreadScheduler& sched, int) {
        check(live == 63, "initial worker context independent of main");
        live = 61;
        check(sched.recv_blocking(kQueue, 0) == 0, "worker receives after blocking");
        check(live == 61, "worker context restored");
    });
    scheduler.start_thread(main_thread);
    check(scheduler.run(100) == ScheduleOutcome::kTimeslice, "context hook preemption");
    check(scheduler.run(100) == ScheduleOutcome::kAllFinished, "context hook completion");
    check(events == std::vector<std::pair<int, bool>>({{0, true}, {0, false}, {1, true},
        {1, false}, {0, true}, {0, false}, {1, true}, {1, false}, {0, true}, {0, false}}),
        "paired hooks across yield, block, preempt and completion");
    check(saved == std::vector<unsigned>({62, 61}) && !scheduler.set_baton_hook({}),
          "completed contexts retained; late hook replacement rejected");
}

} // namespace

int main() {
    test_producer_consumer_blocks_and_wakes();
    test_consumer_blocks_when_no_producer();
    test_priority_order_and_determinism();
    test_deterministic_interrupt_preemption();
    test_one_waiter_fifo();
    test_blocking_send_and_jam();
    test_sender_priority_and_fifo();
    test_original_os_handoff_scenario();
    test_context_baton_hook();
    if (failures != 0) {
        std::cerr << failures << " failure(s)\n";
        return 1;
    }
    std::cout << "all thread-scheduler tests passed\n";
    return 0;
}
