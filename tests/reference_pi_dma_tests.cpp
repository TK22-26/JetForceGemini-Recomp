#include "jfg/boot/reference_pi_dma.hpp"
#include <array>
#include <cstdlib>

int main() {
  using jfg::boot::ReferencePiDma;
  auto check = [](bool ok) { if (!ok) std::abort(); };
  std::array<std::uint8_t, 64> ram{}, rom{};
  for (unsigned i = 0; i < rom.size(); ++i) rom[i] = static_cast<std::uint8_t>(i);
  ReferencePiDma pi;
  check(pi.write(0, 8, 100, ram, rom));
  check(pi.write(4, 0x10000008, 100, ram, rom));
  check(pi.write(12, 47, 100, ram, rom));
  check(pi.read(0) == 8U && pi.read(4) == 0x10000008U && pi.read(12) == 47U);
  for (unsigned i = 0; i < 48; ++i) check(ram[(8 + i) ^ 3U] == rom[8 + i]);
  check(pi.read(16) == 3U && !pi.interrupt() && pi.transfers() == 1);
  check(!pi.write(12, 47, 100, ram, rom));
  pi.advance(105); check(pi.read(16) == 3U && !pi.interrupt());
  pi.advance(106); check(pi.read(16) == 0U && pi.interrupt());
  check(pi.write(16, 2, 106, ram, rom) && !pi.interrupt());
  check(!pi.write(12, 63, 106, ram, rom)); // both buffers bounded
  check(!pi.write(8, 47, 106, ram, rom));
  check(!pi.write(12, 47, UINT64_MAX, ram, rom));
  check(!pi.read(2) && !pi.read(0x34));
  check(!pi.write(16, 4, 106, ram, rom));
  check(pi.write(12, 7, 106, ram, rom));
  check(pi.write(16, 1, 106, ram, rom));
  pi.advance(200); check(!pi.interrupt() && pi.read(16) == 0U);
  check(pi.write(0, 4, 200, ram, rom) && pi.write(4, 0x10000004, 200, ram, rom));
  check(pi.write(12, 47, 200, ram, rom));
  for (unsigned i = 0; i < 48; ++i) check(ram[(4 + i) ^ 3U] == rom[4 + i]);
  pi.advance(206);
  check(pi.write(16, 2, 206, ram, rom));
  check(pi.write(12, 51, 206, ram, rom));
  pi.advance(211); check(!pi.interrupt());
  pi.advance(212); check(pi.interrupt()); // integer length/8, not ceil(length/8)
  check(pi.write(16, 2, 212, ram, rom));
  check(pi.write(12, 3, 212, ram, rom));
  pi.advance(212); check(pi.interrupt()); // independently observed zero delay
  for (unsigned length = 1; length <= 56; ++length) {
    ram.fill(0xcc);
    check(pi.write(16, 2, 1000, ram, rom));
    check(pi.write(12, length - 1, 1000, ram, rom));
    for (unsigned i = 0; i < length; ++i) check(ram[(4 + i) ^ 3U] == rom[4 + i]);
    for (unsigned i = 4 + length; i < ram.size(); ++i) check(ram[i ^ 3U] == 0xcc);
    pi.advance(1000 + length / 8U);
    check(pi.interrupt());
  }
  for (unsigned source = 0; source < 8; source += 2) {
    for (unsigned dest = 0; dest < 8; dest += 2) {
      for (unsigned length = 1; length <= 56; ++length) {
        ram.fill(0xcc);
        check(pi.write(16, 2, 2000, ram, rom));
        check(pi.write(0, dest, 2000, ram, rom));
        check(pi.write(4, 0x10000000U + source, 2000, ram, rom));
        check(pi.write(12, length - 1, 2000, ram, rom));
        for (unsigned i = 0; i < ram.size(); ++i)
          check(ram[i ^ 3U] == (i >= dest && i < dest + length ? rom[source + i - dest] : 0xcc));
        pi.advance(2000 + length / 8);
      }
    }
  }
}
