#include "jfg/boot/reference_sp_dma.hpp"
#include <array>
#include <cstdlib>
#include <cstring>

static void check(bool condition) { if (!condition) std::abort(); }
int main() {
  using jfg::boot::ReferenceSpDma;
  std::array<std::uint8_t, 8192> ram{};
  for (unsigned i = 0; i < ram.size(); ++i) ram[i] = static_cast<std::uint8_t>(i * 13);
  for (unsigned local : {0U, 0xfc0U, 0x1000U, 0x1fc0U}) {
    ReferenceSpDma dma;
    check(dma.write(0, 0x04000000 + local, ram) && dma.write(4, 0x80000100, ram));
    check(dma.write(8, 63, ram) && dma.transfers() == 1);
    check(std::memcmp(dma.memory().data() + local, ram.data() + 0x100, 64) == 0);
    check(dma.read(0) == 0x04000000U + local && dma.read(4) == 0x80000100U && dma.read(8) == 63U);
    check(dma.read(0x14) == 0U && dma.read(0x18) == 0U && !dma.read(12));
    const auto before = dma.memory();
    std::array<std::uint8_t, 8192> saved{};
    std::memcpy(saved.data(), before.data(), saved.size());
    for (unsigned length : {0U, 62U, 0x1000U, 0x10003fU})
      check(!dma.write(8, length, ram));
    check(!dma.write(12, 63, ram) && !dma.write(0x14, 0, ram));
    check(dma.transfers() == 1 && dma.read(8) == 63U &&
          std::memcmp(saved.data(), dma.memory().data(), saved.size()) == 0);
    check(dma.write_pc(0x04001000) && dma.pc() == 0x04001000);
    check(!dma.write_pc(0x1001) && dma.pc() == 0x04001000);
  }
  ReferenceSpDma dma;
  check(dma.write(0, 0x1ff8, ram) && dma.write(4, 0x100, ram));
  check(!dma.write(8, 15, ram)); // unqualified bank wrap
  check(dma.write(0, 0x1000, ram) && dma.write(4, 0x1ff8, ram));
  check(!dma.write(8, 15, ram)); // out of RDRAM
  check(dma.write(4, 0x101, ram) && !dma.write(8, 63, ram));
  check(dma.transfers() == 0);
}
