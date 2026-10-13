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
  // Goldwood drones: compact LOD geometry shares the full model's palette.
  // A second identical enemy must not acquire the first one's vertices.
  jfg::PresentationSceneIdentity scene;
  scene.models.push_back(
      {1, 0x1000, 0x2000, 0x3000, {0x4000, 0x5000}, 0x6000, 20, 2});
  scene.models.push_back({1, 0x1000, 0x2100, 0x3100, {}, 0x7000, 8, 2});
  scene.models.push_back(
      {2, 0x1100, 0x2200, 0x3000, {0x8000, 0x9000}, 0xa000, 20, 2});
  scene.models.push_back({2, 0x1100, 0x2300, 0x3100, {}, 0xb000, 8, 2});
  auto vertex = jfg::presentation_vertex_identity(scene, 0x4040, 0x701e);
  require(vertex.owner && vertex.geometry && vertex.geometry->model == 0x3100 &&
          vertex.geometry->instance == 0x2100 && vertex.joint == 1 &&
          vertex.vertex == 3);
  vertex = jfg::presentation_vertex_identity(scene, 0x5040, 0x701e);
  require(vertex.geometry &&
          vertex.geometry->instance == 0x2100); // palette swap
  require(!jfg::presentation_vertex_identity(scene, 0x4040, 0xb01e).geometry);
  require(!jfg::presentation_vertex_identity(scene, 0x4040, 0x701f).geometry);
  require(!jfg::presentation_vertex_identity(scene, 0x4041, 0x701e).owner);
  scene.models.push_back(scene.models[0]);
  const auto ambiguous_palette = jfg::presentation_vertex_identity(scene, 0x4040, 0x701e);
  require(ambiguous_palette.owner && !ambiguous_palette.geometry);

  // Compact instances still appear in the task identity snapshot. Their
  // inline vertex bytes are not treated as pointers to a private palette.
  w8(0x8015004FU, 2);
  w8(0x8011001FU, 2);
  w32(0x80120004U, 0x80140100U);
  w32(0x80140100U, 0x80150100U);
  w32(0x80140104U, 0x80160100U);
  w8(0x8015014EU, 1);
  w8(0x8015014FU, 2);
  w8(0x80150113U, 3);
  w32(0x80140110U, 0xffff0001U);
  w32(0x80140114U, 0x00140020U);
  const auto lod = tracker.capture(ram, 118);
  require(lod.models.size() == 2 && lod.models[1].palettes[0] == 0 &&
          lod.models[1].vertices == 0x160100U);
  vertex = jfg::presentation_vertex_identity(lod, 0x170040U, 0x16010aU);
  require(vertex.geometry && vertex.geometry->instance == 0x80140100U &&
          vertex.vertex == 1);

  // Inline compact vertices can accidentally look like in-range pointers.
  // Their overlap with the palette fields must still prevent ownership.
  w32(0x80140104U, 0x80140110U);
  w32(0x80140110U, 0x80171000U);
  w32(0x80140114U, 0x80171100U);
  const auto inline_lod = tracker.capture(ram, 118);
  require(inline_lod.models.size() == 2 &&
          inline_lod.models[1].palettes[0] == 0);

  // Identical billboard assets retain distinct actor lifetimes. Address
  // reuse, object frees, expiry and level changes cannot reuse old ownership.
  w32(0x80180000U, 0x80190000U);
  tracker.sprite(ram, 0x80180000U, 0x80100000U, 0x801a0000U, 118);
  auto sprites = tracker.capture(ram, 118);
  require(sprites.sprites.size() == 1 &&
          sprites.sprites[0].anchor == 0x190000U &&
          sprites.sprites[0].lifetime == sprites.models[0].lifetime);
  const auto old_sprite = sprites.sprites[0].lifetime;
  tracker.retire(0x80100000U);
  require(tracker.capture(ram, 120).sprites.empty());
  tracker.sprite(ram, 0x80180000U, 0x80100000U, 0x801a0000U, 120);
  sprites = tracker.capture(ram, 120);
  require(sprites.sprites.size() == 1 &&
          sprites.sprites[0].lifetime != old_sprite);
  require(tracker.capture(ram, 127).sprites.empty());
  tracker.sprite(ram, 0x80180000U, 0x80100000U, 0x801a0000U, 128);
  w32(0x800FB114U, 3);
  require(tracker.capture(ram, 128).sprites.empty());
  // Multiple pickups with the same asset are separate owners, including
  // a sprite-only actor with no model array. Freeing one preserves the other.
  w32(0x800F2CA8U, 2);
  w32(0x80130004U, 0x80100200U);
  w32(0x80100240U, 0x80110200U);
  w32(0x8010026CU, 0);
  w8(0x8011021FU, 0);
  w32(0x80180004U, 0x80190010U);
  tracker.sprite(ram, 0x80180000U, 0x80100000U, 0x801a0000U, 130);
  tracker.sprite(ram, 0x80180004U, 0x80100200U, 0x801a0000U, 130);
  sprites = tracker.capture(ram, 130);
  require(sprites.sprites.size() == 2 &&
          sprites.sprites[0].sprite == sprites.sprites[1].sprite &&
          sprites.sprites[0].actor != sprites.sprites[1].actor &&
          sprites.sprites[0].lifetime != sprites.sprites[1].lifetime);
  tracker.retire(0x80100000U);
  sprites = tracker.capture(ram, 132);
  require(sprites.sprites.size() == 1 && sprites.sprites[0].actor == 0x80100200U);
  scene.models.resize(3);
  scene.models.push_back(scene.models[1]);
  scene.models.back().instance++;
  require(!jfg::presentation_vertex_identity(scene, 0x4040, 0x701e).geometry);
  return 0;
}
