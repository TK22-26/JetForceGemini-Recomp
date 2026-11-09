extern "C" {
#include "recomp.h"
void effect_store(uint8_t*, recomp_context*);
void effect_branch(uint8_t*, recomp_context*);
void effect_likely(uint8_t*, recomp_context*);
void effect_caller(uint8_t*, recomp_context*);
void effect_regcaller(uint8_t*, recomp_context*);
void effect_tail(uint8_t*, recomp_context*);
void effect_condlink(uint8_t*, recomp_context*);
void effect_likelylink(uint8_t*, recomp_context*);
void effect_leaf(uint8_t*, recomp_context*);
}
#include <cstdint>
#include <cstdlib>
#include <iostream>
#include <vector>
#include "effect_addresses.h"

struct Event { unsigned phase, pc; std::uint64_t v0, ra; std::uint32_t memory; };
static std::vector<Event> events;
static std::int32_t bases[64];
extern "C" { std::int32_t* section_addresses = bases; }
extern "C" recomp_func_t* get_function(std::int32_t address) {
  if (static_cast<std::uint32_t>(address) == EFFECT_LEAF) return effect_leaf;
  std::abort();
}
extern "C" void effect_observe(unsigned phase, unsigned pc, uint8_t* ram, recomp_context* ctx) {
  if (events.size() > 1024) std::abort();
  events.push_back({phase, pc, ctx->r2, ctx->r31, *reinterpret_cast<std::uint32_t*>(ram)});
}
static void require(bool condition) { if (!condition) std::abort(); }
static Event at(unsigned phase, unsigned pc) {
  Event found{};
  unsigned count = 0;
  for (const auto& event : events) if (event.phase == phase && event.pc == pc) { found = event; ++count; }
  require(count == 1);
  return found;
}
int main() {
  struct Case { recomp_func_t* function; std::uint32_t start; int argument; unsigned result; std::vector<unsigned> path; };
  // Instruction order is specified independently from the emitted hooks.
  const std::vector<Case> cases = {
    {effect_store, EFFECT_STORE, 0, 8, {0,4,8,12,16}},
    {effect_branch, EFFECT_BRANCH, 0, 5, {0,4,12,16,20}},
    {effect_branch, EFFECT_BRANCH, 1, 7, {0,4,8,12,16,20}},
    {effect_likely, EFFECT_LIKELY, 0, 5, {0,4,12,16,20}},
    {effect_likely, EFFECT_LIKELY, 1, 6, {0,8,12,16,20}},
    {effect_caller, EFFECT_CALLER, 0, 5, {0,4,8,EFFECT_LEAF-EFFECT_CALLER,EFFECT_LEAF+4-EFFECT_CALLER,12,16,20}},
    {effect_regcaller, EFFECT_REGCALLER, 0, 4, {0,4,8,12,16,EFFECT_LEAF-EFFECT_REGCALLER,EFFECT_LEAF+4-EFFECT_REGCALLER,20,24,28}},
    {effect_tail, EFFECT_TAIL, 0, 4, {0,4,EFFECT_LEAF-EFFECT_TAIL,EFFECT_LEAF+4-EFFECT_TAIL}},
    {effect_condlink, EFFECT_CONDLINK, 0, 5, {0,4,8,EFFECT_LEAF-EFFECT_CONDLINK,EFFECT_LEAF+4-EFFECT_CONDLINK,12,16,20}},
    {effect_condlink, EFFECT_CONDLINK, -1, 1, {0,4,8,12,16,20}},
    {effect_likelylink, EFFECT_LIKELYLINK, 0, 5, {0,4,8,EFFECT_LEAF-EFFECT_LIKELYLINK,EFFECT_LEAF+4-EFFECT_LIKELYLINK,12,16,20}},
    {effect_likelylink, EFFECT_LIKELYLINK, -1, 0, {0,4,12,16,20}},
  };
  for (unsigned index = 0; index < cases.size(); ++index) {
    const auto& test = cases[index];
    alignas(8) std::uint32_t ram[16]{};
    recomp_context ctx{};
    ctx.r4 = 0xffffffff80000000ULL;
    ctx.r5 = static_cast<gpr>(test.argument);
    ctx.r6 = static_cast<gpr>(static_cast<std::int64_t>(static_cast<std::int32_t>(EFFECT_LEAF)));
    ctx.r31 = 0xffffffff80200000ULL;
    events.clear();
    test.function(reinterpret_cast<uint8_t*>(ram), &ctx);
    require(ctx.r2 == test.result && ctx.r31 == 0xffffffff80200000ULL);
    if (index == 0) require(ram[0] == 7);
#if EFFECT_HOOKS
    require(events.size() == test.path.size() * 2);
    for (unsigned n = 0; n < test.path.size(); ++n) {
      require(events[2*n].phase == 0 && events[2*n+1].phase == 1);
      require(events[2*n].pc == test.start + test.path[n]);
      require(events[2*n+1].pc == events[2*n].pc);
    }
    if (index == 0) {
      require(at(0, EFFECT_STORE).v0 == 0 && at(1, EFFECT_STORE).v0 == 7);
      require(at(0, EFFECT_STORE+4).memory == 0 && at(1, EFFECT_STORE+4).memory == 7);
    }
    if (index == 5) {
      require(at(0, EFFECT_CALLER+4).ra == 0xffffffff80200000ULL);
      require(at(1, EFFECT_CALLER+4).ra == (0xffffffff00000000ULL | (EFFECT_CALLER+12)));
    }
#else
    require(events.empty());
#endif
    std::cout << index << '\t' << ctx.r2 << '\t' << ram[0] << '\n';
  }
  std::cout << "passed\t" << cases.size() << '\n';
}
