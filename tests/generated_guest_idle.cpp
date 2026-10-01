// Actual generated self-loops, including delay-slot side effects. The hook
// ends only the bounded test; no exception or device timing is inferred here.
extern "C" {
#include "recomp.h"
void idle_branch(uint8_t*, recomp_context*);
void idle_jump(uint8_t*, recomp_context*);
}
#include <cstdlib>
#include <iostream>
static unsigned entry, slots, limit;
struct Complete {};
extern "C" void idle_probe(unsigned pc, recomp_context* context) {
  if (pc == entry) {
    if (context->r2 != slots) std::abort();
    if (slots == limit) throw Complete{};
  } else if (pc == entry + 4) ++slots;
  else std::abort();
}
extern "C" void pause_self(uint8_t*) { std::abort(); }
int main() {
  unsigned cases = 0;
  for (auto function : {idle_branch, idle_jump}) {
    entry = function == idle_branch ? 0x80000400U : 0x80000408U;
    for (auto iterations : {1U, 2U, 7U, 1000U}) {
      slots = 0; limit = iterations;
      recomp_context context{};
      uint8_t memory[4]{};
      try { function(memory, &context); std::abort(); }
      catch (const Complete&) { if (context.r2 != iterations || slots != iterations) std::abort(); }
      ++cases;
    }
  }
  std::cout << "generated idle-loop delay slots: " << cases << " cases passed\n";
}
