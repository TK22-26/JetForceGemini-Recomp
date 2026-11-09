// Driver for actual N64Recomp output of the original assembly fixture.
// One tick per instruction is a TEST profile, not an N64 timing assertion.
#include "jfg/boot/execution_clock.hpp"
#include "jfg/boot/thread_scheduler.hpp"
extern "C" {
#include "recomp.h"
void clock_loop(uint8_t*, recomp_context*);
void clock_caller(uint8_t*, recomp_context*);
}
#include <cstdlib>
#include <iostream>
#include <vector>

using namespace jfg::boot;
static void check(bool condition, const char* reason) {
  if (!condition) { std::cerr << reason << '\n'; std::exit(1); }
}
struct Run {
  ExecutionClock clock;
  InterruptLatch interrupts;
  ThreadScheduler* scheduler;
  InstructionRetirement retirement;
  bool masked = false;
  unsigned instruction_entries = 0;
  unsigned delivered = 0;
  unsigned delayed = 0;
};
static Run* active;

// Each entry retires the previously executed instruction. Charging at
// entry without this distinction would interrupt BEFORE the charged work.
extern "C" void jfg_clock_before(unsigned, unsigned delay_slot) {
  auto& run = *active;
  check(run.retirement.finish(run.clock), "retire previous instruction");
  while (const auto event = run.clock.take_due()) run.interrupts.raise(event->source);
  ++run.instruction_entries;
  if (run.masked && run.instruction_entries == 12) run.interrupts.mask(1);
  if (delay_slot && run.interrupts.pending()) ++run.delayed;
  if (run.interrupts.deliverable(true, false, !delay_slot)) run.scheduler->preempt_current();
  check(run.retirement.enter(run.clock, 1), "begin instruction after resumption");
}

static void run_case(unsigned iterations, bool nested, bool masked) {
  std::vector<uint8_t> memory(4096);
  ThreadScheduler scheduler{hle::GuestMemory(memory)};
  Run run{.scheduler = &scheduler, .masked = masked};
  active = &run;
  run.interrupts.mask(masked ? 0 : 1);
  // Deadline six lands between a branch and its delay slot in the leaf.
  check(run.clock.arm(1, 6, 6), "arm periodic interrupt");
  recomp_context context{};
  context.r4 = iterations;
  bool finished = false;
  const auto thread = scheduler.create_thread(1, [&](ThreadScheduler&, int) {
    (nested ? clock_caller : clock_loop)(memory.data(), &context);
    check(run.retirement.finish(run.clock), "retire final return delay slot");
    while (const auto event = run.clock.take_due()) run.interrupts.raise(event->source);
    finished = true;
  });
  scheduler.start_thread(thread);
  ScheduleOutcome outcome;
  while ((outcome = scheduler.run(100)) == ScheduleOutcome::kTimeslice) {
    check(!finished && run.interrupts.pending() == 1, "preemption inside generated code");
    if (masked) check(run.instruction_entries >= 12, "mask defers delivery");
    ++run.delivered;
    run.interrupts.acknowledge(1);
  }
  check(outcome == ScheduleOutcome::kAllFinished, "generated program finishes");
  const unsigned expected = (iterations ? 4 * iterations + 6 : 11) + (nested ? 6 : 0);
  check(run.instruction_entries == expected && run.clock.now() == expected,
        "exact dynamic instruction count, including annulled and duplicated slots");
  check(context.r2 == (iterations ? iterations : 101) &&
        context.r3 == (iterations ? iterations : 1), "guest arithmetic unchanged");
  check(run.delivered > 0, "interrupt delivered without an OS call");
  if (!nested && iterations > 1 && !masked) check(run.delayed > 0, "delay slot safe boundary exercised");
}
int main() {
  for (unsigned repeat = 0; repeat < 10; ++repeat) {
    for (unsigned count : {0U, 1U, 4U, 20U}) {
      run_case(count, false, false);
      run_case(count, true, false);
    }
    run_case(20, false, true);
  }
  std::cout << "90 generated execution-clock cases passed\n";
}
