#include "jfg/renderer/presentation_identity.hpp"
#include "jfg/renderer/semantic_presentation.hpp"
#include <cstdlib>
#include <limits>
static void require(bool v) {
  if (!v)
    std::abort();
}
int main() {
  const jfg::PresentationMatrix identity{1, 0, 0, 0, 0, 1, 0, 0,
                                         0, 0, 1, 0, 0, 0, 0, 1};
  jfg::SemanticPresentationSample a{
      {1, 2, 3, 4, 5, 6}, {0, 0, 0}, identity, true};
  auto b = a;
  b.world[0] = 0.1f;
  b.camera[12] = 0.02f;
  jfg::SemanticPresentationHistory history;
  require(!history.record({a, a}, 100, true, false)[0].matched);
  auto current = history.record({b, b}, 102, true, true);
  require(current[0].matched && current[1].matched &&
          current[0].world == a.world);
  history.record({}, 103, false,
                 false); // Offscreen work cannot consume the scene history.
  a = b;
  a.world[0] = 0.2f;
  require(history.record({a}, 104, true, true)[0].matched);
  auto cut = a;
  cut.camera[12] = 2.0f;
  require(!history.record({cut}, 106, true, true)[0].matched);
  auto different = a;
  different.key[3]++;
  require(!history.record({different}, 108, true, true)[0].matched);
  require(history.record({different}, 110, true, true)[0].matched);
  different.key[0]++; // Reused actor address, new lifetime.
  require(!history.record({different}, 112, true, true)[0].matched);
  require(!history.record({different}, 200, true, true)[0].matched);

  jfg::SemanticPresentationHistory coherent;
  a.world = {0, 0, 0};
  a.camera = identity;
  b = a;
  b.key[4]++; // A second joint of the same actor.
  coherent.record({a, b}, 100, true, false);
  a.world[0] = 0.1f;
  b.world[0] = 0.1f;
  b.valid = false;
  auto blocked = coherent.record({a, b}, 102, true, true);
  require(!blocked[0].matched && !blocked[1].matched);
  b.valid = true;
  require(!coherent.record({a, b}, 104, true, true)[0].matched);
  current = coherent.record({a, b}, 106, true, true);
  require(current[0].matched && current[1].matched);
  auto duplicate = a;
  duplicate.world[0] = 0.2f;
  current = coherent.record({a, b, duplicate}, 108, true, true);
  require(!current[0].matched && !current[1].matched);
  require(!coherent.record({a, b}, 110, true, true)[0].matched);
  a.world[0] = std::numeric_limits<float>::quiet_NaN();
  require(!coherent.record({a, b}, 112, true, true)[0].matched);

  // Synthetic guest layout: changing palette buffers keeps identity; frees,
  // absent actors, level changes and camera selection invalidate ownership.
  std::vector<std::uint8_t> ram(8U * 1024U * 1024U);
  const auto w32 = [&](std::uint32_t at, std::uint32_t value) {
    std::memcpy(ram.data() + (at & 0xffffffU), &value, 4);
  };
  const auto w8 = [&](std::uint32_t at, std::uint8_t value) {
    ram[(at & 0xffffffU) ^ 3U] = value;
  };
  w32(0x800FB114U, 1);
  w32(0x800F2CA4U, 0x80130000U);
  w32(0x800F2CA8U, 1);
  w32(0x80130000U, 0x80100000U);
  w32(0x80100040U, 0x80110000U);
  w32(0x8010006CU, 0x80120000U);
  w8(0x8011001FU, 1);
  w32(0x80120000U, 0x80140000U);
  w32(0x80140000U, 0x80150000U);
  w8(0x8015004EU, 1);
  w8(0x8015004FU, 2);
  w8(0x80150013U, 3);
  w32(0x80140004U, 0x80160000U);
  w32(0x80140010U, 0x80170000U);
  w32(0x80140014U, 0x80170100U);
  w32(0x80180000U, 0x80190000U);
  w32(0x800FA630U, 1);
  w32(0x800FA634U, 0);
  jfg::PresentationIdentityTracker tracker;
  tracker.camera(ram, 0x80180000U, 100);
  const auto first = tracker.capture(ram, 100);
  require(first.models.size() == 1 && first.models[0].bone_count == 2 &&
          first.models[0].vertex_count == 3);
  require(first.cameras.size() == 1 && first.cameras[0].matrix == 0x190000U);
  require(tracker.capture(ram, 102).models[0].lifetime ==
          first.models[0].lifetime);
  tracker.retire(0x80100000U);
  const auto reused = tracker.capture(ram, 104);
  require(reused.models[0].lifetime != first.models[0].lifetime);
  require(first.models[0].palettes[0] ==
          0x170000U); // Retained task metadata is immutable.
  w32(0x800F2CA8U, 0);
  tracker.capture(ram, 106);
  w32(0x800F2CA8U, 1);
  require(tracker.capture(ram, 108).models[0].lifetime !=
          reused.models[0].lifetime);
  require(tracker.capture(ram, 108)
              .cameras.empty()); // Stale camera buffer ownership expires.
  w32(0x800FB114U, 2);
  require(tracker.capture(ram, 110).models[0].lifetime !=
          reused.models[0].lifetime);
  w8(0x801000A0U, 1);
  require(tracker.capture(ram, 112).models.empty());
  w8(0x801000A0U, 0);
  w32(0x800F2CA8U, 257);
  require(tracker.capture(ram, 114).models.empty());
  // Byte-swapped access must remain bounded even for a partial final word.
  const std::array<std::uint8_t, 5> truncated{0, 1, 2, 3, 4};
  const jfg::PresentationGuestView short_ram(truncated);
  require(short_ram.u8(4) == 0 && short_ram.u8(1) == 2);
  require(short_ram.u32(4) == 0 && short_ram.u32(0x81100000U) == 0);
  w32(0x800F2CA8U, 1);
  w8(0x8015004FU, 128);
  require(
      tracker.capture(ram, 116).models.empty()); // Guest bone count is signed.
  return 0;
}
