#include "jfg/boot/mi_interrupt_mask.hpp"
#include <cstdlib>
#include <iostream>

static void check(bool condition) { if (!condition) std::abort(); }
int main() {
  using jfg::boot::MiInterruptMask;
  MiInterruptMask unknown;
  check(!unknown.initialized() && !unknown.command(0) && !unknown.initialize(64));
  unsigned cases = 0;
  for (unsigned old = 0; old < 64; ++old) {
    for (unsigned command = 0; command < 4096; ++command) {
      MiInterruptMask mask;
      check(mask.initialize(old));
      auto expected = old;
      bool conflict = false;
      for (unsigned bit = 0; bit < 6; ++bit) {
        const bool clear = (command & (1U << (bit * 2))) != 0;
        const bool set = (command & (2U << (bit * 2))) != 0;
        conflict |= clear && set;
        if (clear) expected &= ~(1U << bit);
        if (set) expected |= 1U << bit;
      }
      check(mask.command(command) == !conflict);
      check(mask.read() == (conflict ? old : expected));
      const auto before = mask.read();
      check(!mask.command(0x1000) && !mask.initialize(64) && mask.read() == before);
      ++cases;
    }
  }
  std::cout << cases << " MI mask command cases passed\n";
}
