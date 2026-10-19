#pragma once
#include "jfg/boot/host_deadline_wait.hpp"
#include <algorithm>
namespace jfg {
// Keep the renderer's original target timestamp. Sleep through the bulk of
// the interval using the existing high-resolution host timer, then poll over
// a bounded wake margin. Observed timer overshoot adjusts that margin without
// moving the presentation deadline. Failure retains the original fallback.
class PresentationDeadlineWait {
public:
  template<class Clock, class Duration>
  bool until(std::chrono::time_point<Clock, Duration> target) noexcept {
#if defined(_WIN32)
    const auto now=Clock::now();
    if(now>=target)return true;
    const auto sleep_target=target-guard_;
    if(now<sleep_target) {
      const auto remaining=sleep_target-now;
      if(!timer_.until(std::chrono::steady_clock::now()+
          std::chrono::duration_cast<std::chrono::steady_clock::duration>(remaining)))
        return false;
      // The scheduler may wake later than the requested timer deadline.
      // A fixed 100 us margin lost output cadence in native tests. Track
      // that overshoot, increase immediately and decay slowly (1 us/wake).
      // Bounds prevent one long stall from turning all future waits into
      // full-frame polling. The original frame deadline remains unchanged.
      using namespace std::chrono;
      const auto overshoot=duration_cast<nanoseconds>(Clock::now()-sleep_target);
      guard_=(std::clamp)((std::max)(guard_-nanoseconds(1000),
          overshoot+nanoseconds(150000)),nanoseconds(500000),nanoseconds(2000000));
    }
    while(Clock::now()<target) YieldProcessor();
    return true;
#else
    (void)target; return false;
#endif
  }
private:
  boot::HostDeadlineWait timer_;
  std::chrono::nanoseconds guard_{750000};
};
inline bool presentation_timer_candidate_enabled() noexcept {
  static const bool enabled=[] {
#if defined(_WIN32)
    char value[2]{};
    return GetEnvironmentVariableA("JFG_DIAGNOSTIC_PRESENT_TIMER",value,2U)==1U &&
        value[0]=='1';
#else
    return false;
#endif
  }();
  return enabled;
}
template<class Clock, class Duration>
inline bool wait_presentation_deadline(std::chrono::time_point<Clock,Duration> target) noexcept {
  if(!presentation_timer_candidate_enabled())return false;
  thread_local PresentationDeadlineWait waiter;
  return waiter.until(target);
}
} // namespace jfg
