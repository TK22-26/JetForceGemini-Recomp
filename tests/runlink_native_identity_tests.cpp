#include "jfg/boot/runlink_native_identity.hpp"
#include <cstdlib>
#include <random>
#include <vector>
using Index = jfg::boot::NativeRunlinkIdentityIndex;
using Identity = Index::Identity;
unsigned legacy(std::span<const std::uint8_t> records, const Identity &wanted) {
  if (records.size() != Index::kRecordBytes)
    return 0;
  unsigned matched = 0;
  for (unsigned i = 0; i < Index::kSlotCount; ++i) {
    Identity value;
    std::memcpy(value.data(), records.data() + i * 32 + 4, 16);
    if (value[0] != wanted[0] || value[1] != wanted[1] ||
        value[2] != wanted[2] || value[3] != wanted[3])
      continue;
    if (matched)
      return 0;
    matched = i + 1;
  }
  return matched;
}
void require(bool v) {
  if (!v)
    std::abort();
}
void put(std::vector<std::uint8_t> &data, unsigned i, const Identity &key) {
  std::memcpy(data.data() + i * 32 + 4, key.data(), 16);
}
int main() {
  std::mt19937 random(79131);
  std::vector<std::uint8_t> data(Index::kRecordBytes);
  std::array<Identity, 157> identities{};
  for (unsigned i = 0; i < identities.size(); ++i) {
    identities[i] = {random(), random(), random(), random()};
    put(data, i, identities[i]);
  }
  Index test;
  for (unsigned round = 0; round < 6000; ++round) {
    const unsigned slot = random() % 157U;
    if (round % 3 == 0) {
      identities[slot] = {random(), random(), random(), random()};
      put(data, slot, identities[slot]);
    }
    if (round % 7 == 0)
      put(data, random() % 157U, identities[slot]);
    if (round % 11 == 0)
      data[random() % data.size()] ^= static_cast<std::uint8_t>(random());
    Identity key = round % 5 == 0
                       ? Identity{random(), random(), random(), random()}
                       : identities[slot];
    require(test.find(data, key) == legacy(data, key));
    require(test.find(data, key) == legacy(data, key));
    auto moved = data;
    require(test.find(moved, key) == legacy(moved, key));
  }
  require(test.find(std::span<const std::uint8_t>(data.data(), data.size() - 1),
                    identities[0]) == 0);
  for (unsigned i = 0; i < 157; ++i) {
    identities[i] = {i * 64 + 1, i + 4, i + 5, i + 6};
    put(data, i, identities[i]);
  }
  put(data, 156, identities[0]);
  require(test.find(data, identities[0]) == 0);
  put(data, 156, identities[156]);
  require(test.find(data, identities[0]) == 1);
  identities[156] = {99999, 2, 3, 4};
  put(data, 156, identities[156]);
  require(test.find(data, identities[156]) == 157);
  return 0;
}
