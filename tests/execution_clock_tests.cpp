#include "jfg/boot/execution_clock.hpp"
#include "jfg/boot/thread_scheduler.hpp"
#include <cstdlib>
#include <iostream>
#include <vector>

using namespace jfg::boot;
static void check(bool value, const char* message) {
  if (!value) { std::cerr << message << '\n'; std::exit(1); }
}

static void deadlines() {
  ExecutionClock clock;
  check(!clock.idle_to_next(), "no event means no idle clock advance");
  check(clock.arm(2, 10, 10) && clock.arm(1, 10), "arm events");
  check(!clock.arm(2, 11), "duplicate source rejected");
  check(clock.advance(9) && !clock.take_due(), "no early events");
  check(clock.advance(1), "reach deadline");
  check(!clock.advance(1), "must process boundary before more work");
  check(clock.take_due()->source == 1, "stable simultaneous order");
  check(clock.take_due()->source == 2, "second simultaneous source");
  check(!clock.take_due(), "no duplicate notification");
  check(clock.next() == 20, "period is anchored");
  check(clock.advance(25), "finite work can cross multiple periods");
  check(clock.take_due()->deadline == 20, "first expired period");
  check(clock.take_due()->deadline == 30, "second expired period");
  check(clock.next() == 40 && !clock.take_due(), "no phase drift");
  check(!clock.arm(3, 34), "cannot arm in past");
  check(clock.arm(3, 35) && clock.take_due()->source == 3, "arm at current time");
  check(clock.cancel(2) && !clock.cancel(2), "cancel exactly once");
  check(clock.arm(4, 100) && clock.idle_to_next() && clock.now() == 100,
        "idle advances directly to nearest event");
  check(clock.take_due()->source == 4, "idle completion");
  check(clock.advance(UINT64_MAX - 100), "maximum time");
  check(!clock.advance(1), "clock overflow rejected");
  check(clock.arm(5, UINT64_MAX, 1), "last representable event");
  check(clock.take_due()->source == 5 && clock.exhausted() && !clock.next(),
        "period overflow signaled without wrapping");
}

static void masks() {
  InterruptLatch latch;
  latch.raise(3);
  check(latch.pending() == 3 && latch.deliverable(true, false, true) == 0,
        "masked interrupt remains pending");
  latch.mask(1);
  check(latch.deliverable(true, false, true) == 1, "unmask pending source");
  check(!latch.deliverable(false, false, true), "global disable");
  check(!latch.deliverable(true, true, true), "exception level");
  check(!latch.deliverable(true, false, false), "unsafe delay boundary");
  latch.acknowledge(1);
  check(latch.pending() == 2 && !latch.deliverable(true, false, true),
        "acknowledge only selected source");
  latch.mask(2);
  check(latch.deliverable(true, false, true) == 2, "other source preserved");
}

static void running_guest() {
  // Synthetic workload only; the separate generated-code fixture verifies
  // the hook placement in actual N64Recomp output.
  std::vector<std::uint8_t> memory(0x1000);
  ThreadScheduler scheduler{hle::GuestMemory(memory)};
  ExecutionClock clock;
  InterruptLatch interrupts;
  interrupts.mask(1);
  check(clock.arm(1, 7, 7), "arm VI");
  unsigned executed = 0, notifications = 0;
  const int thread = scheduler.create_thread(1, [&](ThreadScheduler& running, int) {
    for (; executed < 20; ++executed) {
      check(clock.advance(1), "instruction charge");
      while (const auto event = clock.take_due()) interrupts.raise(event->source);
      if (interrupts.deliverable(true, false, true)) running.preempt_current();
    }
  });
  scheduler.start_thread(thread);
  while (scheduler.run(100) == ScheduleOutcome::kTimeslice) {
    check(clock.now() == (notifications + 1U) * 7U, "interrupt during runnable loop");
    check(executed < 20, "not deferred until function return");
    ++notifications;
    interrupts.acknowledge(1);
  }
  check(notifications == 2 && executed == 20 && clock.now() == 20,
        "guest resumes without repeated or skipped work");
}
static void retirement() {
  ExecutionClock clock;
  InstructionRetirement retirement;
  check(!retirement.enter(clock, 0), "zero cost rejected");
  check(retirement.enter(clock, 3) && clock.now() == 0, "not charged before execution");
  check(retirement.enter(clock, 2) && clock.now() == 3, "previous operation retires");
  check(retirement.finish(clock) && clock.now() == 5, "last operation retires");
  check(retirement.finish(clock) && clock.now() == 5, "finish is idempotent");
  check(!retirement.in_flight(), "no pending operation");
  check(clock.arm(1, 5), "event at boundary");
  check(retirement.enter(clock, 1), "enter next operation");
  check(!retirement.finish(clock) && retirement.in_flight(), "pending event blocks execution charge");
  check(clock.take_due().has_value() && retirement.finish(clock), "retry does not lose charge");
}
int main() { deadlines(); masks(); running_guest(); retirement(); }
