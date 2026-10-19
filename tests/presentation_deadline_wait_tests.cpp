#include "jfg/renderer/presentation_deadline_wait.hpp"
#include <atomic>
#include <cstdio>
#include <thread>
using Clock=std::chrono::steady_clock;
using namespace std::chrono_literals;
int main() {
#if defined(_WIN32)
  std::atomic<unsigned> failures{0};
  const auto exercise=[&] {
    for(unsigned lifetime=0;lifetime<4;++lifetime) {
      jfg::PresentationDeadlineWait waiter;
      if(!waiter.until(Clock::now()-1s))++failures;
      // Exercise repeated timer wakes on the same object, including
      // changing output rates, rather than only a fresh timer each time.
      for(unsigned repeat=0;repeat<24;++repeat)
      for(auto delay:{10us,100us,500us,2778us,8333us}) {
        const auto due=Clock::now()+delay;
        if(!waiter.until(due) || Clock::now()<due)++failures;
      }
    }
  };
  // Independent objects on independent threads must not share/reset a timer.
  std::thread a(exercise), b(exercise);a.join();b.join();
  const auto count=failures.load();
  std::printf("Concurrent presentation deadlines: %u failures\n",count);
  return count?1:0;
#else
  jfg::PresentationDeadlineWait waiter;
  return waiter.until(Clock::now())?1:0;
#endif
}
