#include "jfg/boot/guest_thread_transport.hpp"
#include <cstdint>
#include <cstdlib>
#include <memory>
#include <stdexcept>
#include <vector>

namespace {
struct Context {
  std::uint32_t value = 0, status = 0;
  std::uint32_t* self = nullptr;
};
using Transport = jfg::boot::GuestThreadTransport<Context>;
struct Event {
  unsigned kind;
  std::uint32_t from, to, pc, value, status;
  bool operator==(const Event&) const = default;
};
struct Result {
  std::vector<Event> execution, observations;
  std::uint64_t handoffs = 0;
  unsigned repairs = 0, rejected = 0;
};
void check(bool valid) { if (!valid) std::abort(); }

Result run(bool observed) {
  Result result;
  std::vector<Event> timeline;
  std::unique_ptr<Transport> transport;
  const auto record = [&](unsigned kind, std::uint32_t pc, const Context& context) {
    check(context.self == &context.value);
    Event event{kind, transport->current(), transport->current(), pc, context.value, context.status};
    result.execution.push_back(event);
    timeline.push_back(event);
  };
  const auto reject = [&](std::uint32_t next, std::uint32_t pc, Context& context) {
    const auto observations = result.observations.size();
    const auto current = transport->current();
    const auto before = context;
    bool caught = false;
    try { transport->eret(next, pc, context); }
    catch (const std::logic_error&) { caught = true; }
    check(caught && result.observations.size() == observations && transport->current() == current);
    check(context.value == before.value && context.status == before.status && context.self == before.self);
    ++result.rejected;
  };
  Transport::ObserveEret observer;
  if (observed) observer = [&](const Transport::EretBoundary& edge, const Context& context) {
    check(transport->current() == edge.from_thread);
    check(context.self == &context.value && (context.status & 6U) == 0);
    Event event{1, edge.from_thread, edge.to_thread, edge.target_pc, context.value, context.status};
    result.observations.push_back(event);
    timeline.push_back(event);
  };
  transport = std::make_unique<Transport>([&](std::uint32_t pc, Context& context) {
    if (pc == 0x400U) {
      record(0, pc, context);
      context.value = 11;
      transport->eret(1, 0x100, context);
      std::abort(); // Bootstrap is never resumed, but its boundary must exist.
    }
    if (pc == 0x100U) {
      record(0, pc, context);
      reject(0, 0x200, context);
      reject(2, 0x200, context); // No parked continuation yet.
      context.value = 12;
      transport->eret(1, 0x104, context); // No host yield for same-thread ERET.
      record(2, 0x104, context);
      transport->park_at(0x108);
      context.value = 22;
      transport->eret(2, 0x200, context);
      record(2, 0x108, context); // Returns only after thread 2's ERET to us.
      check(context.value == 111);
      transport->park_at(0x10c);
      context.value = 222;
      transport->eret(2, 0x204, context);
      std::abort();
    }
    check(pc == 0x200U);
    record(0, pc, context);
    transport->park_at(0x204);
    reject(1, 0x10c, context); // Known thread is actually parked at 0x108.
    context.value = 111;
    transport->eret(1, 0x108, context);
    record(2, 0x204, context);
    check(context.value == 222);
    transport->stop();
  }, [&](Context& context) {
    context.self = &context.value;
    ++result.repairs;
  }, observer);
  Context outside{7, 1, nullptr};
  reject(1, 0x100, outside);
  transport->run(0x400, outside, 10);
  result.handoffs = transport->handoffs();
  reject(1, 0x100, outside);
  const std::vector<Event> expected_execution{
    {0,0,0,0x400,7,1}, {0,1,1,0x100,11,1}, {2,1,1,0x104,12,1},
    {0,2,2,0x200,22,1}, {2,1,1,0x108,111,1}, {2,2,2,0x204,222,1}};
  check(result.execution == expected_execution);
  if (observed) {
    const std::vector<Event> expected{
      {0,0,0,0x400,7,1}, {1,0,1,0x100,11,1}, {0,1,1,0x100,11,1},
      {1,1,1,0x104,12,1}, {2,1,1,0x104,12,1}, {1,1,2,0x200,22,1},
      {0,2,2,0x200,22,1}, {1,2,1,0x108,111,1}, {2,1,1,0x108,111,1},
      {1,1,2,0x204,222,1}, {2,2,2,0x204,222,1}};
    check(timeline == expected && result.observations.size() == 5);
  } else check(result.observations.empty());
  return result;
}
}

int main() {
  const auto control = run(false);
  const auto observed = run(true);
  check(control.execution == observed.execution && control.handoffs == observed.handoffs);
  check(control.repairs == observed.repairs && control.rejected == observed.rejected);
  check(observed.handoffs == 5 && observed.repairs == 5 && observed.rejected == 5);
}
