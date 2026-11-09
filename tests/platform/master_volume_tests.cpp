#include "jfg/audio/master_volume.hpp"
#include <cstdlib>
#include <iostream>
#include <vector>
static void check(bool value) {
  if (!value)
    std::abort();
}
int main() {
  using namespace jfg::audio;
  auto settings = parse_volume("version=1\nvolume=37\nmuted=1\n");
  check(settings && settings->percent == 37U && settings->muted);
  check(parse_volume("version=1\r\nvolume=0\r\nmuted=0\r\n").has_value());
  for (auto bad :
       {"", "version=1\nvolume=101\nmuted=0\n",
        "version=1\nvolume=-1\nmuted=0\n", "version=1\nvolume=01\nmuted=0\n",
        "version=1\nvolume=50\nmuted=2\n",
        "version=1\nvolume=50\nmuted=0\nextra",
        "version=2\nvolume=50\nmuted=0\n"})
    check(!parse_volume(bad));
  std::vector<std::uint8_t> pcm;
  for (int n = -32768; n <= 32767; ++n) {
    const auto bits =
        std::bit_cast<std::uint16_t>(static_cast<std::int16_t>(n));
    for (int c = 0; c < 2; ++c) {
      pcm.push_back(static_cast<std::uint8_t>(bits));
      pcm.push_back(static_cast<std::uint8_t>(bits >> 8U));
    }
  }
  const auto original = pcm;
  MasterVolume gain;
  gain.apply(pcm);
  check(pcm == original);
  gain.configure({50, false}, 48000, true);
  gain.apply(pcm);
  for (std::size_t i = 0; i < pcm.size(); i += 2U) {
    const auto read = [&](const auto &v) {
      return std::bit_cast<std::int16_t>(static_cast<std::uint16_t>(
          v[i] | (static_cast<unsigned>(v[i + 1U]) << 8U)));
    };
    check(read(pcm) == read(original) / 2);
  }
  pcm = original;
  gain.configure({37, true}, 48000, true);
  gain.apply(pcm);
  for (auto b : pcm)
    check(b == 0U);
  gain.configure({100, false}, 48000, true);
  gain.configure({100, true}, 48000);
  pcm.assign(480U * 4U, 0x40U);
  gain.apply(pcm);
  for (std::size_t i = 240U * 4U; i < pcm.size(); ++i)
    check(pcm[i] == 0U);
  gain.configure({100, false}, 48000);
  pcm.assign(480U * 4U, 0x40U);
  gain.apply(pcm);
  for (std::size_t i = 240U * 4U; i < pcm.size(); ++i)
    check(pcm[i] == 0x40U);
  std::cout << "master volume tests passed\n";
}
