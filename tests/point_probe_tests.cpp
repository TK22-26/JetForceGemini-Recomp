#include "jfg/boot/point_probe.hpp"
#include <cstdlib>
#include <string>

int main() {
  using jfg::boot::point_probe_addresses;
  const auto check = [](bool ok) { if (!ok) std::abort(); };
  check(point_probe_addresses("")->empty());
  const auto good = point_probe_addresses("0x80000000,0x803ffffc");
  check(good && good->size() == 2 && (*good)[1] == 0x803ffffcU);
  for (const auto bad : {"0x8000000", "0x80000001", "0x80400000", "0xa0000000", "0x80000000,",
                        ",0x80000000", "0x80000000,,0x80000004", "0x80000000,0x80000000", "0x8000000g"})
    check(!point_probe_addresses(bad));
  std::string text;
  for (unsigned i = 0; i < 17; ++i) {
    if (i) text += ',';
    const char hex[] = "0123456789abcdef";
    text += "0x800000";
    text += hex[(i * 4) >> 4]; text += hex[(i * 4) & 15];
    check(static_cast<bool>(point_probe_addresses(text)) == (i < 16));
  }
}
