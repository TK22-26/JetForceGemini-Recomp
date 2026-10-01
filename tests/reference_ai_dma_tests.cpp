#include "jfg/boot/reference_ai_dma.hpp"
#include <cstdio>
#include <cstdlib>
#include <fstream>
#include <source_location>
#include <sstream>
#include <string>
#include <vector>

int main(int argc, char** argv) {
  auto check = [](bool ok, std::source_location at = std::source_location::current()) {
    if (!ok) { std::fprintf(stderr, "AI check at %u\n", at.line()); std::abort(); }
  };
  check(argc == 1 || argc == 2);
  if (argc == 2) {
    std::ifstream input(argv[1]);
    std::string line; check(bool(std::getline(input, line)));
    if (!line.empty() && line.back() == '\r') line.pop_back();
    const bool fifo = line.ends_with("second_status");
    unsigned row = 0;
    while (std::getline(input, line) && !line.starts_with("result")) {
      std::istringstream fields(line); std::vector<std::uint64_t> v;
      for (std::uint64_t item; fields >> item;) v.push_back(item);
      check(v.size() == (fifo ? 16U : 10U));
      constexpr std::uint32_t rates[]{1103,2209,4419}, lengths[]{32,128,4096};
      check(row < 72 && v[0] == rates[row / 24] && v[1] == lengths[row / 8 % 3] && v[2] == row % 8);
      jfg::boot::ReferenceAiDma ai;
      const auto store = v[3] + 4;
      auto write = [&](unsigned offset, std::uint32_t value, std::uint64_t count) {
        check(ai.write(offset, value, count, 4U * 1024U * 1024U, 789000));
      };
      write(8, 1, 0); write(20, 15, 0); write(16, static_cast<std::uint32_t>(v[0]), 0);
      write(4, static_cast<std::uint32_t>(v[1]), store);
      check(ai.read(4, store + 2) == v[4]);
      if (fifo) write(4, static_cast<std::uint32_t>(v[1] / 2), store + 6);
      check(ai.read(12, store + 8) == v[5]);
      const auto first = *ai.deadline();
      check(v[6] < first && first <= v[7]);
      if (fifo) check(ai.read(4, v[10] + 4) == v[11]);
      ai.advance(first - 1); check(!ai.interrupt());
      ai.advance(v[7]); check(ai.interrupt());
      check(ai.read(12, v[7] + 12) == v[9]);
      check(ai.read(4, v[7] + 12) == v[8]);
      constexpr std::uint32_t acknowledgements[]{0,1,2,4,8,0x40000000U,0x80000000U,0xffffffffU};
      write(12, acknowledgements[row % 8], v[7] + 20); check(!ai.interrupt());
      if (fifo) {
        check(v[12] < *ai.deadline() && *ai.deadline() <= v[13]);
        ai.advance(v[13]); check(ai.interrupt());
        check(ai.read(4, v[13] + 12) == v[14] && ai.read(12, v[13] + 12) == v[15]);
      }
      ++row;
    }
    check(row == 72 && (line == "result\ttrue\t72" || line == "result\ttrue\t72\r"));
    check(!std::getline(input, line));
  }
  jfg::boot::ReferenceAiDma ai;
  check(!ai.write(4, 128, 0, 4096, 789000));
  check(ai.write(8, 1, 0, 4096, 789000));
  check(ai.write(16, 2209, 0, 4096, 789000));
  check(ai.write(20, 15, 0, 4096, 789000));
  check(!ai.write(4, 127, 0, 4096, 789000));
  check(ai.write(4, 128, 0, 4096, 789000));
  check(ai.write(4, 128, 1, 4096, 789000));
  check(!ai.write(4, 128, 2, 4096, 789000));
  check(!ai.write(16, 4419, 2, 4096, 789000));
}
