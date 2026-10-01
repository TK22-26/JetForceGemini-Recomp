#include "jfg/boot/reference_device_timing.hpp"
#include "jfg/boot/execution_clock.hpp"
#include <cstdlib>
#include <iostream>
using namespace jfg::boot;
static void check(bool value) { if (!value) std::abort(); }
int main() {
  for (const auto vertical : {261U, 262U, 525U, 526U, 624U, 625U})
    for (const auto horizontal : {3093U, 3177U})
      check(observed_vi_period(vertical, horizontal) == (vertical + 1ULL) * 1500ULL);
  for (const auto vertical : {0U, 1U, 524U, 1024U, 0xffffffffU})
    check(!observed_vi_period(vertical, 3093));
  check(!observed_vi_period(525, 0) && !observed_vi_period(525, 3094));
  check(observed_rsp_latency(ObservedRspTask::jfg_f3ddkr) == 1000);
  check(observed_rsp_latency(ObservedRspTask::jfg_audio) == 4000);
  check(!observed_rsp_latency(static_cast<ObservedRspTask>(99)));
  // Device deadlines remain independent even while CPU delivery is masked.
  // This tests the mechanism with qualified periods, not a game CPU profile.
  ExecutionClock clock;
  InterruptLatch interrupts;
  const auto vi = *observed_vi_period(525, 3093);
  check(clock.arm(8, vi, vi));
  check(clock.advance(40));
  check(clock.arm(1, clock.now() + *observed_rsp_latency(ObservedRspTask::jfg_f3ddkr)));
  check(clock.advance(999) && !clock.take_due());
  check(clock.advance(1));
  const auto completion = clock.take_due();
  check(completion && completion->source == 1 && completion->deadline == 1040);
  interrupts.raise(1);
  interrupts.mask(0x3f);
  check(!interrupts.deliverable(false, false, true));
  check(!clock.take_due() && clock.next() == vi);
  check(clock.idle_to_next());
  const auto retrace = clock.take_due();
  check(retrace && retrace->source == 8 && retrace->deadline == vi);
  interrupts.raise(8);
  check(interrupts.deliverable(true, false, true) == 9);
  interrupts.acknowledge(1);
  check(interrupts.pending() == 8 && clock.next() == vi * 2);
  std::cout << "all reference-device timing tests passed\n";
}
