#define SDL_MAIN_HANDLED
#include "rt64_interpolation_adapter.hpp"
#include "rt64_cpu_overlay.hpp"
#include <cmath>
#include <cstdlib>
static void require(bool value) {
  if (!value)
    std::abort();
}
int main() {
  // A cutscene presents 0x15AF40 as color; the character room later uses
  // the same allocation for depth. Historical address/size compatibility
  // must not redirect a valid VI to those depth pixels.
  {
    RT64::VI current{};
    current.status.word = 0x13016U;
    current.width = 320U;
    current.origin = 0x10FF00U + 640U;
    current.hRegion.word = 0x006C02ECU;
    current.vRegion.word = 0x00330195U;
    current.xTransform.word = 0x200U;
    current.yTransform.word = 0x555U;
    RT64::VIHistory::Present oldColor{current, 320U};
    oldColor.vi.origin = 0x15AF40U + 640U;
    RT64::Framebuffer reused;
    reused.addressStart = oldColor.vi.fbAddress();
    reused.width = 320U;
    reused.siz = G_IM_SIZ_16b;
    reused.lastWriteType = RT64::Framebuffer::Type::Color;
    require(jfg::early_present_history_match(reused, oldColor, current));
    reused.lastWriteType = RT64::Framebuffer::Type::Depth;
    require(!jfg::early_present_history_match(reused, oldColor, current));
    // A later genuine color write makes the address eligible again.
    reused.lastWriteType = RT64::Framebuffer::Type::Color;
    require(jfg::early_present_history_match(reused, oldColor, current));
    reused.width = 640U;
    require(!jfg::early_present_history_match(reused, oldColor, current));
    reused.width = 320U;
    reused.siz = G_IM_SIZ_32b;
    require(!jfg::early_present_history_match(reused, oldColor, current));
    reused.siz = G_IM_SIZ_16b;
    reused.addressStart += 640U;
    require(!jfg::early_present_history_match(reused, oldColor, current));

    RT64::FramebufferPair pair;
    pair.reset();
    pair.colorImage.width = 320U;
    pair.colorImage.siz = G_IM_SIZ_16b;
    pair.fastPaths.clearDepthOnly = true;
    require(!jfg::early_present_pair_candidate(pair, true));
    require(!jfg::early_present_pair_candidate(pair, false));
    pair.fastPaths.clearDepthOnly = false;
    // A real flat color clear (fade/background) remains eligible.
    pair.fillRectOnly = true;
    require(jfg::early_present_pair_candidate(pair, true));
    pair.fillRectOnly = false;
    require(jfg::early_present_pair_candidate(pair, true));
  }
  {
    // Owner capture: clear depth, draw scene, bind depth as color for
    // readback, restore scene color without a draw. Both addresses retain
    // old presentation history; reverse scanning used to select readback.
    std::array<RT64::FramebufferPair, 4> pairs;
    for (auto& p : pairs) {
      p.reset(); p.colorImage.width = 320U; p.colorImage.siz = G_IM_SIZ_16b;
      p.depthImage.address = 0x15AF40U;
    }
    pairs[0].colorImage.address = 0x15AF40U;
    pairs[0].fastPaths.clearDepthOnly = true;
    pairs[1].colorImage.address = 0x135700U;
    pairs[1].depthRead = pairs[1].depthWrite = true;
    pairs[2].colorImage.address = 0x15AF40U;
    pairs[3].colorImage.address = 0x135700U;
    // The single-pass check alone accepts this depth-as-color readback.
    require(jfg::early_present_pair_candidate(pairs[2], true));
    require(!jfg::early_present_workload_candidate(pairs[0], true, pairs.data(), pairs.size()));
    require(jfg::early_present_workload_candidate(pairs[1], true, pairs.data(), pairs.size()));
    require(!jfg::early_present_workload_candidate(pairs[2], true, pairs.data(), pairs.size()));
    require(!jfg::early_present_workload_candidate(pairs[2], false, pairs.data(), pairs.size()));
    // Normal color-only tasks and subsequent legitimate cinematic color
    // reuse remain valid. The rule has no permanent address blacklist.
    std::array<RT64::FramebufferPair, 1> colorOnly;
    colorOnly[0].reset(); colorOnly[0].colorImage = pairs[2].colorImage;
    require(jfg::early_present_workload_candidate(colorOnly[0], true, colorOnly.data(), colorOnly.size()));
    pairs[0].fastPaths.clearDepthOnly = false;
    pairs[1].depthRead = pairs[1].depthWrite = false;
    require(jfg::early_present_workload_candidate(pairs[2], true, pairs.data(), pairs.size()));
  }
  {
    RT64::Framebuffer framebuffer;
    framebuffer.addressStart=0x135700U;framebuffer.width=320U;
    framebuffer.siz=G_IM_SIZ_16b;framebuffer.lastWriteType=RT64::Framebuffer::Type::Color;
    std::array<RT64::FramebufferPair,2> pairs;
    for(auto& pair:pairs)pair.reset();
    auto& color=pairs[0];color.colorImage.address=framebuffer.addressStart;
    color.colorImage.width=320U;color.colorImage.fmt=G_IM_FMT_RGBA;color.colorImage.siz=G_IM_SIZ_16b;
    const auto ready=[&](bool scene=true,bool paused=false,unsigned rate=30U,bool history=true) {
      return jfg::bootstrap_interpolation_target(&framebuffer,color,pairs.data(),pairs.size(),scene,paused,rate,history);
    };
    // Captured first continuous flight frame: alternating target has no
    // manager entry yet; drawing this workload will create it.
    const auto unseen=[&](unsigned rate=30U,bool history=true) {
      return jfg::bootstrap_interpolation_target(nullptr,color,pairs.data(),pairs.size(),true,false,rate,history);
    };
    require(unseen());require(!unseen(0));require(!unseen(30,false));
    pairs[1].depthImage.address=color.colorImage.address;pairs[1].depthWrite=true;
    require(!unseen());pairs[1].depthWrite=false;
    color.fastPaths.clearDepthOnly=true;require(!unseen());color.fastPaths.clearDepthOnly=false;
    require(ready());require(!ready(false));require(!ready(true,true));
    require(!ready(true,false,0));require(!ready(true,false,30,false));
    framebuffer.lastWriteType=RT64::Framebuffer::Type::Depth;require(!ready());
    framebuffer.lastWriteType=RT64::Framebuffer::Type::Color;
    pairs[1].depthImage.address=framebuffer.addressStart;pairs[1].depthRead=true;require(!ready());
    pairs[1].depthRead=false;pairs[1].fastPaths.clearDepthOnly=true;
    pairs[1].colorImage.address=framebuffer.addressStart;require(!ready());
    pairs[1].fastPaths.clearDepthOnly=false;require(ready());
    color.colorImage.fmt=G_IM_FMT_I;require(!ready());color.colorImage.fmt=G_IM_FMT_RGBA;
    framebuffer.width=640;require(!ready());framebuffer.width=320;
    framebuffer.addressStart++;require(!ready());framebuffer.addressStart--;
    color.colorImage.siz=G_IM_SIZ_32b;require(!ready());
  }
  {
    // A multi-target task must keep a known display ahead of an inferred one,
    // even when reverse draw scanning encounters the inferred target first.
    for(bool confirmed_first:{false,true}) {
      int selected=-1;bool provisional=false;
      for(unsigned i=0;i<2U;++i) {
        const bool confirmed=(i==0U)==confirmed_first;
        if(jfg::select_interpolation_target(selected!=-1,provisional,confirmed,!confirmed)) {
          selected=confirmed?1:0;provisional=!confirmed;
        }
      }
      require(selected==1 && !provisional);
    }
    require(!jfg::select_interpolation_target(true,true,false,true));
    require(!jfg::select_interpolation_target(false,false,false,false));
    require(!jfg::select_interpolation_target(true,false,true,true));
  }
  // CPU-written rain and reticles select retained masks by the actual output
  // timestamp. This is production state even when no diagnostic trace is open.
#if defined(_WIN32)
  _putenv_s("JFG_RT64_INTERPOLATION_TRACE", "");
#else
  unsetenv("JFG_RT64_INTERPOLATION_TRACE");
#endif
  require(!jfg::interpolation_trace_enabled());
  int output_owner = 0, other_output_owner = 0;
  jfg::record_presentation_output(&output_owner, UINT32_MAX, {120, 30, 0, 4, 0.0f});
  jfg::record_presentation_output(&output_owner, 3, {120, 30, 3, 4, 1.0f});
  const auto output = jfg::presentation_output_sample(&output_owner, 3);
  require(output.tick == 120 && output.source == 30 && output.frame == 3 &&
          output.count == 4 && output.alpha == 1.0f);
  require(jfg::presentation_output_sample(&output_owner, UINT32_MAX).alpha == 0.0f);
  require(jfg::presentation_output_sample(&other_output_owner, 3).tick == 0);
  require(jfg::presentation_output_sample(&output_owner, 2).tick == 0);
  jfg::record_presentation_output(&output_owner, 3, {122, 30, 1, 2, 1.0f});
  require(jfg::presentation_output_sample(&output_owner, 3).tick == 122);
  // A normal-play output must select its CPU mask; retain the existing
  // framebuffer and two-VI lifetime checks rather than bypassing them.
  {
    auto retained_mask = std::make_shared<jfg::CpuOverlayFrame>();
    retained_mask->valid = true;
    retained_mask->address = 0x110000U;
    retained_mask->tick = 120;
    {
      auto& overlays = jfg::cpu_overlay_storage();
      const std::scoped_lock lock(overlays.mutex);
      overlays.frames[0] = retained_mask;
    }
    require(jfg::cpu_overlay_for(0x110000U,
        jfg::presentation_output_sample(&output_owner, 3).tick) == retained_mask);
    require(!jfg::cpu_overlay_for(0x135700U, 122));
    require(!jfg::cpu_overlay_for(0x110000U, 119));
    require(!jfg::cpu_overlay_for(0x110000U, 123));
    jfg::release_cpu_overlays();
    require(!jfg::cpu_overlay_for(0x110000U, 122));
  }
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
