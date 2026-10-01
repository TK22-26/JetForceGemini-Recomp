extern "C" {
#include "recomp.h"
void continuation_effect(uint8_t*, recomp_context*);
}
#include <array>
#include <cstdint>
#include <cstdlib>
#include <iostream>
#include <vector>

struct Event { unsigned phase, pc; std::uint64_t v0, scratch; };
static std::vector<Event> events;
extern "C" recomp_func_t* get_function(std::int32_t) { std::abort(); }
extern "C" void continuation_observe(unsigned phase, unsigned pc, recomp_context* ctx) {
  if (events.size() > 32) std::abort();
  events.push_back({phase, pc, ctx->r2, ctx->r0});
}
int main() {
  unsigned failures = 0;
  for (unsigned first = 0; first < 4; ++first) {
    recomp_context ctx{};
    ctx.r31 = 0xffffffff80200000ULL;
    ctx.r0 = first ? 0x100U + first * 4U : 0;
    alignas(8) std::array<std::uint8_t, 16> ram{};
    events.clear();
    continuation_effect(ram.data(), &ctx);
    bool ok = ctx.r0 == 0 && ctx.r2 == (first == 0 ? 7U : first == 1 ? 6U : first == 2 ? 4U : 0U);
    ok = ok && events.size() == (5U-first)*2U;
    unsigned value = 0;
    for (unsigned i = 0; i < events.size(); ++i) {
      const auto& event = events[i];
      const unsigned offset = first + i/2;
      if ((i & 1U) && offset < 3U) value += 1U << offset;
      if (event.phase != (i & 1U) || event.pc != 0x80001000U + offset*4U ||
          event.scratch != 0 || event.v0 != value) ok = false;
    }
    if (!ok) ++failures;
    std::cout << first << '\t' << (ok ? "pass" : "fail") << '\t' << ctx.r2 << '\t' << events.size() << '\n';
  }
  std::cout << "failures\t" << failures << '\n';
  return failures ? 1 : 0;
}
