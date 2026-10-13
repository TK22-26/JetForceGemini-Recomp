#pragma once
#include "jfg/renderer/interpolation_history.hpp"
#include <set>
#include <unordered_map>

namespace jfg {
using PresentationVertexKey = std::array<std::uint64_t, 6>;
struct SemanticPresentationSample {
  // Lifetime, actor/instance, model, camera identity, joint, logical vertex.
  PresentationVertexKey key{};
  std::array<float, 3> world{};
  PresentationMatrix camera{};
  bool valid = false;
};
struct SemanticPresentationPrevious {
  std::array<float, 3> world{};
  PresentationMatrix camera{};
  bool matched = false;
};
inline bool semantic_motion_continuous(const SemanticPresentationSample &a,
                                       const SemanticPresentationSample &b) {
  const auto project = [](const SemanticPresentationSample &s) {
    std::array<float, 4> p{};
    for (std::size_t c = 0; c < 4; ++c)
      p[c] = s.world[0] * s.camera[c] + s.world[1] * s.camera[4 + c] +
             s.world[2] * s.camera[8 + c] + s.camera[12 + c];
    return p;
  };
  for (float x : a.world)
    if (!std::isfinite(x))
      return false;
  for (float x : b.world)
    if (!std::isfinite(x))
      return false;
  for (float x : a.camera)
    if (!std::isfinite(x))
      return false;
  for (float x : b.camera)
    if (!std::isfinite(x))
      return false;
  const auto p = project(a), q = project(b);
  for (float x : p)
    if (!std::isfinite(x))
      return false;
  for (float x : q)
    if (!std::isfinite(x))
      return false;
  if (p[3] <= 0.001f && q[3] <= 0.001f)
    return true;
  if (p[3] <= 0.001f || q[3] <= 0.001f || q[3] / p[3] < 0.5f ||
      q[3] / p[3] > 2.0f)
    return false;
  return std::abs(p[0] / p[3] - q[0] / q[3]) <= 0.35f &&
         std::abs(p[1] / p[3] - q[1] / q[3]) <= 0.35f;
}
// One immutable previous scene, indexed by semantic vertices. UV clones may
// repeat the same sample; conflicting duplicates invalidate that actor.
// Every part of one actor either interpolates on the same clock or uses the
// endpoint. Interpolate world-space vertex endpoints before applying one
// shared camera sample, avoiding cracks caused by multiplying separately
// blended joint matrices and deforming local vertices.
struct PresentationVertexHash {
  std::size_t operator()(const PresentationVertexKey& key) const noexcept {
    std::size_t result=0;
    for (const auto value:key)
      result ^= std::hash<std::uint64_t>{}(value) + std::size_t{0x9e3779b9U} +
                (result<<6U) + (result>>2U);
    return result;
  }
};
class SemanticPresentationHistory {
public:
  std::vector<SemanticPresentationPrevious>
  record(const std::vector<SemanticPresentationSample> &samples,
         std::uint64_t tick, bool scene, bool cadence) {
    std::vector<SemanticPresentationPrevious> result(samples.size());
    if (!scene)
      return result;
    std::unordered_map<PresentationVertexKey, SemanticPresentationSample, PresentationVertexHash> next;
    next.reserve(samples.size());
    std::set<std::uint64_t> blocked, corrupt;
    const bool continuous = cadence && previous_tick_ != 0U &&
                            tick > previous_tick_ &&
                            tick - previous_tick_ <= 6U;
    for (std::size_t i = 0; i < samples.size(); ++i) {
      const auto &s = samples[i];
      const auto actor = s.key[0];
      if (actor == 0U)
        continue;
      if (!s.valid || !continuous)
        blocked.insert(actor);
      if (!s.valid) {
        corrupt.insert(actor);
        continue;
      }
      // The old duplicate audit also rejected a unique NaN endpoint because
      // it compares unequal to its own copy. Preserve that actor-wide poison
      // when a corrupt vertex disappears from the following scene.
      for (float value:s.world) if (std::isnan(value)) corrupt.insert(actor);
      for (float value:s.camera) if (std::isnan(value)) corrupt.insert(actor);
      // UV clones reuse one endpoint; do not allocate discarded duplicate nodes.
      const auto [it, inserted] = next.try_emplace(s.key, s);
      if (!inserted &&
          (it->second.world != s.world || it->second.camera != s.camera)) {
        blocked.insert(actor);
        corrupt.insert(actor);
      }
      const auto old = previous_.find(s.key);
      if (old == previous_.end() || !semantic_motion_continuous(old->second, s))
        blocked.insert(actor);
      else
        result[i] = {old->second.world, old->second.camera, true};
    }
    for (std::size_t i = 0; i < samples.size(); ++i)
      if (blocked.contains(samples[i].key[0]))
        result[i].matched = false;
    // A conflicting endpoint is not a valid anchor for the next scene.
    for (auto it = next.begin(); it != next.end();) {
      if (corrupt.contains(it->first[0]))
        it = next.erase(it);
      else
        ++it;
    }
    previous_ = std::move(next);
    previous_tick_ = tick;
    return result;
  }

private:
  std::unordered_map<PresentationVertexKey, SemanticPresentationSample, PresentationVertexHash> previous_;
  std::uint64_t previous_tick_ = 0;
};
} // namespace jfg
