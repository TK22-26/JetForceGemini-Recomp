#include "jfg/boot/guest_thread_transport.hpp"
#include <cstdlib>
#include <memory>
#include <stdexcept>

namespace {
struct Context { unsigned value = 0; unsigned* self = nullptr; };
void check(bool valid) { if (!valid) std::abort(); }
}
int main() {
  using Transport = jfg::boot::GuestThreadTransport<Context>;
  std::unique_ptr<Transport> transport;
  unsigned visits = 0, repairs = 0;
  transport = std::make_unique<Transport>([&](std::uint32_t pc, Context& context) {
    check(context.self == &context.value);
    if (pc == 0x400U) {
      check(transport->current() == 0 && context.value == 7);
      context.value = 11;
      transport->eret(1, 0x100, context);
      std::abort(); // boot continuation was never selected
    } else if (pc == 0x100U) {
      check(transport->current() == 1 && context.value == 11);
      ++visits;
      transport->park_at(0x104);
      context.value = 22; // an already restored next-thread context
      transport->eret(2, 0x200, context);
      check(transport->current() == 1 && context.value == 111 && context.self == &context.value);
      ++visits;
      transport->park_at(0x108);
      context.value = 222;
      transport->eret(2, 0x204, context);
      std::abort();
    } else {
      check(pc == 0x200 && transport->current() == 2 && context.value == 22);
      ++visits;
      transport->park_at(0x204);
      context.value = 111;
      transport->eret(1, 0x104, context);
      check(transport->current() == 2 && context.value == 222 && context.self == &context.value);
      ++visits;
      transport->stop();
    }
  }, [&](Context& context) { context.self = &context.value; ++repairs; });
  bool rejected = false;
  try { transport->park_at(0x100); } catch (const std::logic_error&) { rejected = true; }
  check(rejected);
  transport->run(0x400, Context{7, nullptr}, 10);
  check(visits == 4 && repairs == 5 && transport->handoffs() == 5);
  rejected = false;
  try { transport->run(0x400, Context{}, 10); } catch (const std::logic_error&) { rejected = true; }
  check(rejected);
  return 0;
}
