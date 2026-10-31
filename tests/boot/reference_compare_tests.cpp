#include "jfg/boot/reference_compare.hpp"
#include <cstdlib>
int main() {
  auto check = [](bool value) { if (!value) std::abort(); };
  jfg::boot::ReferenceCompare timer;
  check(timer.write(100, 300));
  timer.advance(299); check(!timer.interrupt());
  timer.advance(300); check(timer.interrupt() && timer.read() == 300);
  timer.advance(1000); check(timer.interrupt());
  check(timer.write(1000, 1200) && !timer.interrupt());
  check(timer.write(1100, 1400));
  timer.advance(1300); check(!timer.interrupt());
  timer.advance(1400); check(timer.interrupt());
  check(timer.write(0xffffff00ULL, 0x100));
  timer.advance(0x1000000feULL); check(!timer.interrupt());
  timer.advance(0x100000100ULL); check(timer.interrupt());
  check(timer.write(0x100000200ULL, 0));
  timer.advance(0x1ffffffffULL); check(!timer.interrupt());
  timer.advance(0x200000000ULL); check(timer.interrupt());
  check(!timer.write(100, 100));
  check(!timer.write(UINT64_MAX, 0));
}
