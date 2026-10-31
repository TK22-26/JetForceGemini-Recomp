#include "jfg/boot/sp_status.hpp"
#include <array>
#include <cstdlib>
#include <iostream>

using jfg::boot::SpStatus;
static void check(bool value) { if (!value) std::abort(); }
int main() {
  SpStatus sp;
  check(!sp.command(0) && !sp.prepare_task() && !sp.complete_task());
  check(!sp.initialize(0x8000, false));
  // Every old status and every individual command bit. DMA/IO flags are
  // read-only and must survive unrelated CPU writes.
  for (unsigned old = 0; old < 0x8000; ++old) {
    for (unsigned bit = 0; bit < 25; ++bit) {
      check(sp.initialize(old, false));
      check(sp.command(1U << bit));
      unsigned expected = old;
      bool pending = false;
      if (bit == 0) expected &= ~1U;
      else if (bit == 1) expected |= 1U;
      else if (bit == 2) expected &= ~2U;
      else if (bit == 4) pending = true;
      else if (bit >= 5) {
        const auto target = bit < 9 ? (bit < 7 ? 5U : 6U) : 7U + (bit - 9U) / 2U;
        if ((bit & 1U) != 0U) expected &= ~(1U << target);
        else expected |= 1U << target;
      }
      check(sp.read() == expected && sp.interrupt() == pending);
    }
  }
  for (auto shift : std::array<unsigned, 12>{0, 3, 5, 7, 9, 11, 13, 15, 17, 19, 21, 23}) {
    check(sp.initialize(0x7fff, true));
    check(!sp.command((3U << shift) | 4U));
    check(sp.read() == 0x7fff && sp.interrupt());
  }
  check(!sp.command(0x02000000) && sp.read() == 0x7fff);
  check(sp.initialize(0x243, true));
  check(sp.prepare_task() && sp.read() == 0x43);
  check(sp.command(0x125) && sp.read() == 0x40);
  check(!sp.prepare_task());
  check(sp.complete_task() && sp.read() == 0x243 && sp.interrupt());
  check(!sp.complete_task());
  sp.acknowledge_interrupt();
  check(!sp.interrupt());
  check(sp.initialize(0, false) && sp.complete_task() && !sp.interrupt());
  check(sp.initialize(4, false) && !sp.complete_task());
  std::cout << "all SP-status tests passed\n";
}
