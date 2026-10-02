#include "jfg/boot/gameplay_trace.hpp"
#include <fstream>
#include <iterator>
#include <string>
int main(int argc, char **argv) {
  if (argc != 2) return 1;
  jfg::boot::GameplayTrace trace;
  trace.event("disabled", {1, 2});
  if (trace || trace.open(argv[1], 64U)) return 2;
  if (!trace.open(argv[1], 256U)) return 3;
  trace.event("actor", {1, 2, 0x80100000U});
  for (unsigned i = 0; i < 100; ++i) trace.event("tick", {i, 9, 8, 7, 6, 5, 4});
  trace.flush();
  std::ifstream input(argv[1], std::ios::binary);
  const std::string text{std::istreambuf_iterator<char>(input), {}};
  if (text.size() > 256U || text.find("\tactor\t1\t2\t80100000\n") == std::string::npos) return 4;
  if (trace || text.find("limit\tbyte-limit\n") == std::string::npos) return 5;
  const auto size = text.size();
  trace.event("after-limit", {1}); trace.flush();
  if (std::filesystem::file_size(argv[1]) != size) return 6;
  return 0;
}
