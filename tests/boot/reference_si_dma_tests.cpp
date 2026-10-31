#include "jfg/boot/reference_si_dma.hpp"
#include <array>
#include <cstdlib>
#include <fstream>
#include <sstream>
#include <string>
#include <source_location>
#include <cstdio>

int main(int argc, char** argv) {
  auto check = [](bool value, std::source_location at = std::source_location::current()) {
    if (!value) { std::fprintf(stderr, "SI check failed at line %u\n", at.line()); std::abort(); }
  };
  std::array<std::uint8_t, 128> ram{};
  auto put = [&](unsigned at, std::uint8_t value) { ram[at ^ 3U] = value; };
  auto get = [&](unsigned at) { return ram[at ^ 3U]; };
  jfg::boot::ReferenceSiDma si;
  check(si.boot_command(100));
  si.advance(2403); check(!si.interrupt() && si.read(24) == 0U);
  si.advance(2404); check(si.interrupt() && si.read(24) == 0x1000U);
  check(si.write(24, 0, 2404, ram));
  for (unsigned p = 0; p < 4; ++p) { put(p * 6, 1); put(p * 6 + 1, 3); }
  put(24, 0xfe); put(63, 1);
  check(si.write(16, 0x1fc007c0, 3000, ram));
  check(si.pif()[3] == 0 && si.pif()[7] == 0x83 && si.pif()[63] == 0);
  check(si.write(4, 0x1fc007c0, 3002, ram));
  check(get(3) == 5 && si.deadline() == 5304U);
  si.advance(5304); check(si.interrupt());
  check(si.write(24, 0, 5304, ram));
  check(si.write(4, 0x1fc007c0, 5400, ram));
  check(get(3) == 5 && get(7) == 0x83 && get(63) == 0);
  si.advance(7704);
  check(si.write(24, 0, 7704, ram));
  ram.fill(0);
  for (unsigned p = 0; p < 4; ++p) { put(p * 7, 1); put(p * 7 + 1, 4); put(p * 7 + 2, 1); }
  put(28, 0xfe); put(63, 1);
  check(si.write(16, 0x1fc007c0, 8000, ram));
  si.advance(10304); check(si.write(24, 0, 10304, ram));
  si.sample(0x8102, -40, 70, true);
  check(si.write(4, 0x1fc007c0, 11000, ram));
  check(get(3) == 0x81 && get(4) == 2 && get(5) == 216 && get(6) == 70 && get(8) == 0x84);
  si.advance(13304); check(si.write(24, 0, 13304, ram));
  si.sample(0x1234, 0, 0, false);
  check(si.write(4, 0x1fc007c0, 14000, ram) && get(1) == 0x84);
  si.advance(16304); check(si.write(24, 0, 16304, ram));
  const auto previous = si.pif();
  put(2, 2); put(63, 1);
  check(!si.write(16, 0x1fc007c0, 17000, ram) && si.pif() == previous);
  check(si.write(0, 100, 17000, ram));
  check(!si.write(4, 0x1fc007c0, 17000, ram));
  check(!si.write(8, 0, 17000, ram) && !si.read(8));
  for (unsigned pair = 0; pair < 4; ++pair) {
    for (unsigned gap = 0; gap < 8; ++gap) {
      jfg::boot::ReferenceSiDma overlap;
      ram.fill(0);
      check(overlap.write(pair & 2 ? 4 : 16, 0x1fc007c0, 1000, ram));
      check(overlap.write(pair & 1 ? 16 : 4, 0x1fc007c0, 1034 + gap * 96, ram));
      check(overlap.deadline() == 3304 && overlap.transfers() == 2);
      overlap.advance(3303); check(!overlap.interrupt());
      overlap.advance(3304); check(overlap.interrupt());
      check(overlap.write(24, 0, 3304, ram));
      overlap.advance(10000); check(!overlap.interrupt() && !overlap.deadline());
    }
  }
  if (argc == 1) return 0;
  check(argc == 3);
  std::ifstream initial(argv[1]), final(argv[2]);
  check(initial.good() && final.good());
  std::string header;
  std::getline(initial, header);
  if (!header.empty() && header.back() == '\r') header.pop_back();
  check(header == "kind\tlength\tphase\tstatus\tpayload");
  std::getline(final, header);
  if (!header.empty() && header.back() == '\r') header.pop_back();
  check(header == "kind\tlength\tphase\tstatus\tpif");
  const auto hex = [](auto&& bytes) {
    std::string result;
    constexpr char digits[] = "0123456789abcdef";
    for (auto byte : bytes) { result += digits[byte >> 4]; result += digits[byte & 15]; }
    return result;
  };
  jfg::boot::ReferenceSiDma oracle;
  std::uint64_t count = 0;
  unsigned row = 0;
  for (; initial.peek() != std::char_traits<char>::eof(); ++row) {
    unsigned kind, length, phase, status, kind2, length2, phase2, status2;
    std::string data, pif;
    check(bool(initial >> kind >> length >> phase >> status >> data));
    check(bool(final >> kind2 >> length2 >> phase2 >> status2 >> pif));
    check(kind == row / 32 + 1 && phase == row % 8 && kind == kind2 &&
        length == length2 && phase == phase2);
    ram.fill(0);
    if (kind >= 8) {
      for (unsigned i = 0; i < 15; ++i) put(48 + i, static_cast<std::uint8_t>(phase + 17 * i));
      put(63, 2);
    } else if (kind >= 4) {
      const unsigned width = kind < 6 ? 6U : 7U;
      for (unsigned p = 0; p < 4; ++p) {
        put(p * width, 1); put(p * width + 1, static_cast<std::uint8_t>(width - 3));
        put(p * width + 2, kind < 6 ? 0 : 1);
      }
      put(4 * width, 0xfe); put(63, 1);
    }
    check(oracle.write(0, 0, count, ram));
    check(oracle.write(24, 0, count, ram));
    if (kind == 3) check(oracle.boot_command(count));
    else check(oracle.write(kind == 1 || kind == 4 || kind == 6 || kind == 8 ? 16 : 4, 0x1fc007c0, count, ram));
    std::array<std::uint8_t, 64> guest{};
    for (unsigned i = 0; i < 64; ++i) guest[i] = get(i);
    if (hex(guest) != data || oracle.read(24) != status)
      std::fprintf(stderr, "initial SI row %u: %s != %s\n", row, hex(guest).c_str(), data.c_str());
    check(hex(guest) == data && oracle.read(24) == status);
    oracle.advance(count + 2304);
    if (hex(oracle.pif()) != pif || oracle.read(24) != status2)
      std::fprintf(stderr, "final SI row %u: %s != %s\n", row, hex(oracle.pif()).c_str(), pif.c_str());
    check(hex(oracle.pif()) == pif && oracle.read(24) == status2);
    count += 3000;
    initial >> std::ws;
  }
  check(row == 224 || row == 288);
  std::string extra;
  check(!(initial >> extra) && !(final >> extra));
}
