#pragma once
#include "jfg/renderer/presentation_identity.hpp"
#include "jfg/renderer/semantic_presentation.hpp"

namespace jfg {
struct ShadowPresentationVertex {
  SemanticPresentationSample sample;
  const PresentationCameraIdentity* camera = nullptr;
};

inline std::optional<ShadowPresentationVertex> shadow_presentation_vertex(
    const PresentationSceneIdentity& scene, std::uint32_t source,
    const PresentationMatrix& emitted_camera, const std::array<float, 3>& position) {
  const auto* shadow = presentation_shadow_vertex(scene, source);
  if (!shadow || !shadow->history_valid) return {};
  const auto* camera = presentation_shadow_camera(scene, emitted_camera);
  if (!camera) return {};
  for (const float value : position) if (!std::isfinite(value)) return {};
  ShadowPresentationVertex result;
  result.camera = camera;
  result.sample.key = {shadow->lifetime,
      (std::uint64_t(shadow->actor) << 32U) | shadow->texture,
      shadow->receiver, camera->identity, 0x53484144U,
      shadow->corners[(source - shadow->vertices) / 10U]};
  result.sample.world = position;
  const auto corner=(source-shadow->vertices)/10U;
  if(corner<shadow->precise_positions.size()) {
    const auto& precise=shadow->precise_positions[corner];
    bool consistent=true;
    for(unsigned c=0;c<3U;++c)
      consistent=consistent && std::isfinite(precise[c]) && std::trunc(precise[c])==position[c];
    if(consistent)result.sample.world=precise;
  }
  // Coplanar decals must share the receiver's emitted camera product. The
  // float operands validate ownership/cuts; recomputing their product here
  // changes clip-space depth relative to the fixed-point floor and flickers.
  result.sample.camera = emitted_camera;
  result.sample.shadow_lift = shadow->receiver_lift;
  result.sample.shadow_light = shadow->light_shear;
  result.sample.shadow_opacity = shadow->opacity;
  result.sample.valid = true;
  return result;
}
} // namespace jfg
