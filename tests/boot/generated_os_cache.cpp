// Original test driver; original OS bodies are supplied only by a private root.
extern "C" {
#include "recomp.h"
void fn_000_1558_recomp(uint8_t*, recomp_context*);
void fn_000_1559_recomp(uint8_t*, recomp_context*);
void fn_000_1561_recomp(uint8_t*, recomp_context*);
void fn_000_1566_recomp(uint8_t*, recomp_context*);
}
#include "jfg/boot/reference_cache.hpp"
#include <array>
#include <cstdint>
#include <cstdlib>
#include <iostream>

static std::uint64_t instructions, cache_calls;
extern "C" void jfg_phase9_execution_probe(unsigned, unsigned, unsigned, void*) {
  ++instructions;
}
extern "C" void cache_op(uint8_t*, recomp_context*, uint32_t operation, gpr address) {
  if (!jfg::boot::reference_coherent_cache_operation(operation, address, 0x400000))
    std::abort();
  ++cache_calls;
}
int main() {
  constexpr std::array functions{fn_000_1558_recomp, fn_000_1559_recomp,
                                  fn_000_1561_recomp, fn_000_1566_recomp};
  unsigned cases = 0;
  auto run = [&](unsigned function, unsigned alignment, int length) {
    std::array<std::uint8_t, 4096> memory;
    memory.fill(0x5a);
    recomp_context context{};
    context.r4 = static_cast<gpr>(static_cast<std::int32_t>(0x80200000U + alignment));
    context.r5 = static_cast<gpr>(length);
    instructions = cache_calls = 0;
    functions[function](memory.data(), &context);
    if (instructions == 0 || (function < 3 && length <= 0 && cache_calls != 0)) std::abort();
    for (const auto byte : memory) if (byte != 0x5a) std::abort();
    std::cout << function << '\t' << alignment << '\t' << length << '\t'
              << instructions << '\t' << cache_calls << '\n';
    ++cases;
  };
  std::cout << "function\talignment\tlength\tinstructions\tcache_operations\n";
  for (unsigned function = 0; function < 3; ++function)
    for (unsigned alignment : {0U, 1U, 15U, 31U})
      for (int length : {-4, -1, 0, 1, 2, 15, 16, 17, 31, 32, 33,
                         8191, 8192, 8193, 16383, 16384})
        run(function, alignment, length);
  run(3, 0, 0);
  std::cout << "passed\t" << cases << '\n';
}
