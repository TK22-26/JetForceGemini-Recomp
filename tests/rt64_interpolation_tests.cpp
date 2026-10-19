#define SDL_MAIN_HANDLED
#include "rt64_interpolation_adapter.hpp"
#include <cmath>
#include <cstdlib>
static void require(bool value) {
  if (!value)
    std::abort();
}
int main() {
  // A real N64 scene starts by binding its depth image as a color target
  // for a fill, then draws the scene into a different RGBA16 target.
  // The clear must not make the source ambiguous; two drawn scenes must.
  {
    RT64::Workload scene;
    scene.fbPairs.resize(4);
    scene.fbPairCount = 2;
    auto setup = [](RT64::FramebufferPair& pair, std::uint32_t address) {
      pair.reset();
      pair.colorImage.address = address;
      pair.colorImage.width = 320U;
      pair.colorImage.siz = G_IM_SIZ_16b;
      pair.colorImage.fmt = G_IM_FMT_RGBA;
      pair.drawColorRect = RT64::FixedRect(0, 0, 320 * 4, 240 * 4);
      pair.fillRectOnly = false;
    };
    setup(scene.fbPairs[0], 0x180000U);
    scene.fbPairs[0].fillRectOnly = true;
    scene.fbPairs[0].fastPaths.clearDepthOnly = true;
    setup(scene.fbPairs[1], 0x110000U);
    require(jfg::blur_world_source(scene) == 0x110000U);
    scene.fbPairs[0].fastPaths.clearDepthOnly = false;
    require(jfg::blur_world_source(scene) == 0x110000U);
    scene.fbPairs[0].fillRectOnly = false;
    require(jfg::blur_world_source(scene) == 0U);
    scene.fbPairs[0].fillRectOnly = true;
    scene.fbPairs[1].fillRectOnly = true;
    require(jfg::blur_world_source(scene) == 0U);
    scene.fbPairs[1].fillRectOnly = false;
    scene.fbPairCount = 3;
    setup(scene.fbPairs[2], 0x110000U); // More draws to the same scene are valid.
    require(jfg::blur_world_source(scene) == 0x110000U);
    scene.fbPairs[2].colorImage.address = 0x200000U;
    scene.fbPairs[2].colorImage.width = 64U; // Offscreen masks do not compete.
    require(jfg::blur_world_source(scene) == 0x110000U);
    scene.fbPairs[1].drawColorRect.reset();
    require(jfg::blur_world_source(scene) == 0U);
  }
  RT64::Workload workload;
  const hlslpp::float4x4 endpoint(1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 2, 0, 0,
                                  1);
  workload.drawData.worldTransforms.push_back(endpoint);
  require(!jfg::apply_presentation_interpolation(workload, 0, 1));
  auto frame = std::make_shared<jfg::PresentationHistoryFrame>();
  frame->scene = true;
  frame->transforms.push_back(
      {{1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1}, true});
  jfg::publish_presentation_snapshot(&workload, frame);
  require(jfg::apply_presentation_interpolation(workload, 0, 0.25f));
  float row[4];
  for (unsigned c = 0; c < 4; ++c)
    row[c] = workload.drawData.lerpWorldTransforms[0].m[3][c];
  require(std::abs(row[0] - 0.5f) < 0.00001f && row[3] == 1.0f);
  for (unsigned c = 0; c < 4; ++c)
    row[c] = workload.drawData.worldTransforms[0].m[3][c];
  require(row[0] == 2.0f); // Authored endpoint is untouched.
  require(jfg::apply_presentation_interpolation(workload, 0.5f, 1));
  for (unsigned c = 0; c < 4; ++c)
    row[c] = workload.drawData.lerpWorldTransforms[0].m[3][c];
  require(row[0] == 2.0f);
  for (unsigned c = 0; c < 4; ++c)
    row[c] = workload.drawData.prevWorldTransforms[0].m[3][c];
  require(row[0] == 1.0f);
  const auto retained = jfg::presentation_snapshot(&workload);
  jfg::publish_presentation_snapshot(&workload, nullptr);
  require(!jfg::presentation_snapshot(&workload));
  require(
      retained->transforms[0].matched); // An in-flight reader owns its data.
  frame = std::make_shared<jfg::PresentationHistoryFrame>();
  frame->transforms.push_back({});
  jfg::publish_presentation_snapshot(&workload, frame);
  require(jfg::apply_presentation_interpolation(workload, 0, 0.5f));
  for (unsigned c = 0; c < 4; ++c)
    row[c] = workload.drawData.lerpWorldTransforms[0].m[3][c];
  require(row[0] == 2.0f); // Unmatched geometry uses the current endpoint.
  jfg::publish_presentation_snapshot(&workload, nullptr);
  // World endpoint motion and the camera use the same interpolation phase.
  frame = std::make_shared<jfg::PresentationHistoryFrame>();
  jfg::PresentationTransform semantic;
  semantic.matched = true;
  semantic.semantic_vertices = true;
  semantic.current_world = {1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 10, 0, 0, 1};
  semantic.previous_camera = {1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1};
  semantic.current_camera = semantic.previous_camera;
  semantic.current_camera[12] = 2;
  frame->transforms.push_back(semantic);
  jfg::publish_presentation_snapshot(&workload, frame);
  for (float alpha : {0.0f, 0.25f, 0.5f, 0.75f, 1.0f}) {
    require(jfg::apply_presentation_interpolation(workload, alpha, alpha));
    // Current local vertex 1, previous world vertex 9 -> previous local -1.
    const auto point =
        hlslpp::mul(hlslpp::float4(1.0f - 2.0f * (1.0f - alpha), 0, 0, 1),
                    workload.drawData.lerpWorldTransforms[0]);
    require(std::abs(float(point.x) - (9.0f + 4.0f * alpha)) < 0.00001f);
  }
  jfg::publish_presentation_snapshot(&workload, nullptr);
  // Coincident vertices belonging to differently rotated joints must stay
  // coincident at every subframe while the camera also moves.
  const hlslpp::float4x4 joints[]{
      hlslpp::float4x4(0, 1, 0, 0, -1, 0, 0, 0, 0, 0, 1, 0, 5, 2, 0, 1),
      hlslpp::float4x4(0, -1, 0, 0, 1, 0, 0, 0, 0, 0, 1, 0, -3, 4, 0, 1)};
  const hlslpp::float4 old_world(1, 2, 0, 1), new_world(2, 3, 0, 1);
  workload.drawData.worldTransforms.resize(2);
  frame = std::make_shared<jfg::PresentationHistoryFrame>();
  for (unsigned joint = 0; joint < 2; ++joint) {
    auto pose = semantic;
    for (unsigned r = 0; r < 4; ++r)
      for (unsigned c = 0; c < 4; ++c)
        pose.current_world[r * 4 + c] = joints[joint][r][c];
    frame->transforms.push_back(pose);
  }
  jfg::publish_presentation_snapshot(&workload, frame);
  for (float alpha : {0.0f, 0.25f, 0.5f, 0.75f, 1.0f}) {
    require(jfg::apply_presentation_interpolation(workload, alpha, alpha));
    for (unsigned joint = 0; joint < 2; ++joint) {
      const auto inverse = hlslpp::inverse(joints[joint]);
      const auto previous_local = hlslpp::mul(old_world, inverse);
      const auto current_local = hlslpp::mul(new_world, inverse);
      const auto point =
          hlslpp::mul(previous_local * (1 - alpha) + current_local * alpha,
                      workload.drawData.lerpWorldTransforms[joint]);
      require(std::abs(float(point.x) - (1 + 3 * alpha)) < 0.00001f);
      require(std::abs(float(point.y) - (2 + alpha)) < 0.00001f);
    }
  }
  jfg::publish_presentation_snapshot(&workload, nullptr);
  // New scene timing, rather than the previous long interval, releases a
  // finite output sequence. This must work without interpolation logging.
  int owner1 = 0, owner2 = 0, shadow = 0, counters = 0;
  auto publish = [](const void* owner, std::uint64_t tick, bool scene) {
    auto value = std::make_shared<jfg::PresentationHistoryFrame>();
    value->tick = tick; value->scene = scene;
    jfg::publish_presentation_snapshot(owner, value);
  };
  publish(&owner1, 100, true);
  publish(&shadow, 101, false);
  jfg::record_presentation_sequence(&counters, 100);
  require(jfg::presentation_sequence_tick(&counters) == 100);
  require(!jfg::presentation_next_scene_due(100, 12, 120));
  publish(&owner2, 103, true);
  require(!jfg::presentation_next_scene_due(100, 5, 120));
  require(jfg::presentation_next_scene_due(100, 6, 120) == 103);
  require(!jfg::presentation_next_scene_due(100, 17, 360));
  require(jfg::presentation_next_scene_due(100, 18, 360) == 103);
  require(!jfg::presentation_next_scene_due(100, 0, 120));
  require(!jfg::presentation_next_scene_due(0, 12, 120));
  require(!jfg::presentation_next_scene_due(100, 12, 0));
  require(!jfg::presentation_next_scene_due(100, 12, jfg::kUnlimitedPresentation));
  publish(&owner2, 102, true);
  require(!jfg::presentation_next_scene_due(100, 3, 120));
  require(jfg::presentation_next_scene_due(100, 4, 120) == 102);
  publish(&owner2, 100, true);
  require(!jfg::presentation_next_scene_due(100, 12, 120));
  publish(&owner2, 90, true);
  require(!jfg::presentation_next_scene_due(100, 12, 120));
  jfg::publish_presentation_snapshot(&owner1, nullptr);
  jfg::publish_presentation_snapshot(&owner2, nullptr);
  jfg::publish_presentation_snapshot(&shadow, nullptr);
  require(!jfg::presentation_sequence_tick(&counters));
  return 0;
}
