#include "jfg/boot/timers.hpp"
#include "jfg/boot/si_deadline.hpp"
#include "jfg/boot/thread_scheduler.hpp"
#include <cstdlib>
#include <iostream>
#include <vector>

using namespace jfg::boot;
static void check(bool value) {
  if (!value) { std::cerr << "timer test failed\n"; std::exit(1); }
}
int main() {
  SiDeadline si;
  check(!si.start(0, 0, 1, 2));
  check(!si.start(UINT64_MAX, 1, 1, 2));
  check(si.start(100, 2568, 1, 2));
  check(!si.start(101, 2568, 3, 4));
  check(!si.take(2667));
  const auto completion = si.take(2668);
  check(completion && completion->queue == 1 && completion->message == 2);
  check(!si.take(2668) && !si.next());
  check(si.start(2668, 2568, 3, 4));
  check(si.take(10000)->queue == 3);
  for (auto layout : {hle::GuestMemory::Layout::byte_linear_big_endian,
                      hle::GuestMemory::Layout::native_word_big_endian}) {
    std::vector<std::uint8_t> bytes(4096);
    hle::GuestMemory memory(bytes, layout);
    ThreadScheduler scheduler(memory);
    Timers timers;
    constexpr std::uint32_t timer = 0x80000100, queue = 0x80000200;
    check(scheduler.create_queue(queue, queue + 32, 1));
    bool received = false;
    const int consumer = scheduler.create_thread(10, [&](ThreadScheduler &s, int) {
      check(s.recv_blocking(queue, queue + 64) == 0);
      received = true;
    });
    scheduler.start_thread(consumer);
    check(scheduler.run(100) == ScheduleOutcome::kQuiescent);
    auto send = [&](std::uint32_t q, std::uint32_t m) {
      (void)scheduler.send(q, m, false);
    };
    check(timers.set(memory, 100, timer, 20, 0, queue, 123));
    check(timers.next() == 120);
    check(timers.service(memory, 119, send));
    check(scheduler.run(100) == ScheduleOutcome::kQuiescent && !received);
    check(timers.service(memory, 120, send));
    check(scheduler.run(100) == ScheduleOutcome::kAllFinished && received);
    std::uint32_t value = 0;
    check(memory.read_u32(queue + 64, value) && value == 123);
    check(!timers.next());

    // Interval fallback, catch-up and full-queue loss; periodic work survives.
    check(timers.set(memory, 120, timer, 0, 10, queue, 77));
    check(timers.next() == 130);
    check(timers.service(memory, 155, send));
    check(timers.next() == 160);
    check(hle::os_recv_mesg(memory, queue, queue + 64) == 0);
    check(hle::os_recv_mesg(memory, queue, queue + 64) == -1);
    check(timers.service(memory, 160, send));
    check(hle::os_recv_mesg(memory, queue, queue + 64) == 0);
    timers.stop(timer);
    timers.stop(timer);
    check(!timers.next());

    // Rearm replaces prior registration, 64-bit delays do not truncate.
    check(timers.set(memory, 0, timer, 1, 0, queue, 1));
    check(timers.set(memory, 0, timer, 0x100000001ULL, 0, queue, 2));
    check(timers.next() == 0x100000001ULL);
    check(timers.service(memory, 0x100000000ULL, send));
    check(hle::os_recv_mesg(memory, queue, 0) == -1);
    timers.stop(timer);
    check(!timers.set(memory, UINT64_MAX, timer, 1, 0, queue, 0));
    check(!timers.set(memory, 0, 0x80000ff8, 1, 0, queue, 0));
    check(!timers.next());

    std::vector<std::uint32_t> messages;
    auto collect = [&](std::uint32_t, std::uint32_t m) { messages.push_back(m); };
    check(timers.set(memory, 0, timer, 5, 0, queue, 1));
    check(timers.set(memory, 0, timer + 32, 5, 0, queue, 2));
    check(timers.service(memory, 5, collect));
    check(messages == std::vector<std::uint32_t>({1, 2}));
    check(timers.set(memory, 5, timer, 0, 0, 0, 3));
    check(timers.service(memory, 5, collect));
    check(!timers.next() && messages.size() == 2);
  }
  std::cout << "timer tests passed (both guest memory layouts)\n";
}
