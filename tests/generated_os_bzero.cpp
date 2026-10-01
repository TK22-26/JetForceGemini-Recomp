// Original test driver; the OS routine itself comes only from a private root.
extern "C" {
#include "recomp.h"
void fn_000_1562_recomp(uint8_t*, recomp_context*);
}
#include <array>
#include <cstdint>
#include <cstdlib>
#include <iostream>

static std::uint64_t instructions;
extern "C" void jfg_phase9_execution_probe(unsigned, unsigned, unsigned, void*) {
  ++instructions;
}
int main() {
  unsigned cases = 0;
  for (unsigned alignment = 0; alignment < 8; ++alignment) {
    for (int length : {-4, -1, 0, 1, 2, 3, 4, 11, 12, 13, 31, 32, 33, 64, 128, 1024}) {
      std::array<std::uint8_t, 4096> memory;
      memory.fill(0x5a);
      recomp_context context{};
      const unsigned begin = 256 + alignment;
      context.r4 = static_cast<gpr>(static_cast<std::int32_t>(0x80000000U + begin));
      context.r5 = static_cast<gpr>(length);
      instructions = 0;
      fn_000_1562_recomp(memory.data(), &context);
      if (instructions == 0) return 1;
      for (unsigned index = 0; index < memory.size(); ++index) {
        const auto expected = length > 0 && index >= begin &&
            index < begin + static_cast<unsigned>(length) ? 0 : 0x5a;
        if (memory[index ^ 3U] != expected) {
          std::cerr << "bzero mismatch alignment=" << alignment << " length=" << length
                    << " offset=" << index << '\n';
          return 2;
        }
      }
      std::cout << alignment << '\t' << length << '\t' << instructions << '\n';
      ++cases;
    }
  }
  std::cout << "passed\t" << cases << '\n';
}
