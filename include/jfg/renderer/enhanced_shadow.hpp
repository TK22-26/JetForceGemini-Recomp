#pragma once
#include <array>
#include <cstdint>
#include <memory>
#include <optional>
#include <vector>
namespace jfg {
// Immutable, host-only geometry for one scene. Vertex indices address this
// workload's RSP output, never an older ring-buffer slot.
// Exact producer-owned world geometry. Camera history may be unavailable at
// a cut or a newly exposed clipping edge; ownership does not depend on it.
// Sprite objects have no polygonal body. Their authored shadow footprint and
// native origin define an explicit spherical caster in Enhanced.
// This is a native object class, never a fallback for a missing mesh.
struct EnhancedShadowProxy {
  std::uint32_t actor=0;
  std::uint64_t lifetime=0,projection=0;
  std::array<float,4> current{},previous{}; // center XYZ, horizontal radius
  float vertical=0,previous_vertical=0;
  bool valid=false;
};
struct EnhancedShadowReceiver {
    std::uint32_t actor=0;
    std::array<float,3> world{};
    float lift=0;
    bool valid=false;
    std::uint64_t projection=0;
    std::array<float,2> light{};
    float opacity=1;
};
struct EnhancedShadowVertex {
  std::array<float,3> current{};
  std::uint32_t source=0;
  std::array<float,3> previous{};
  float opacity=1;
  float previous_opacity=1;
  std::array<float,3> padding{};
};
static_assert(sizeof(EnhancedShadowVertex)==48);
struct EnhancedShadowActor {
  std::uint32_t actor=0, caster_start=0, caster_count=0;
  std::uint32_t receiver_start=0,receiver_count=0;
  std::uint64_t lifetime=0,camera=0,projection=0;
  std::optional<EnhancedShadowProxy> proxy;
    std::array<float,4> light{}; // current X/Z, previous X/Z.
  // Light-space X/Z origin and width. Fixed power-of-two widths and a
  // world-aligned texel grid prevent a swaying pose resizing its shadow map.
  std::array<float,4> bounds{};
};
struct EnhancedShadowDraw {
  std::uint32_t first_index=0, index_count=0, receiver_start=0, actor_index=0;
};
struct EnhancedShadowFrame {
  unsigned unresolved_draws=0;
  std::vector<EnhancedShadowVertex> vertices;
  std::vector<EnhancedShadowActor> actors;
  std::vector<EnhancedShadowDraw> draws;
};
}
