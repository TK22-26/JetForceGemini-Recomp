#pragma once
#include "jfg/renderer/game_layout.hpp"
#include <cmath>
#include <cstdint>
#include <optional>
namespace jfg {
// Preserve native table samples while interpolating the low four angle bits.
// Higher-refresh camera presentation needs finer angles than the original
// lookup; Original presentation retains the exact native result.
// Reflect the interpolated sample within each quadrant.
// The caller preserves guest fenv and limits this to camera matrix builders.
template<class Read>
std::optional<float> camera_precision_sine(std::uint32_t angle, Read&& read) {
  const auto phase=(angle&0x4000U)?0x4000U-(angle&0x3FFFU):(angle&0x3FFFU);
  const auto index=phase>>4U, fraction=phase&15U;
  const float lower=read(index);
  if(!std::isfinite(lower))return std::nullopt;
  float result=lower;
  if(fraction) {
    const float upper=read(index+1U);
    if(!std::isfinite(upper))return std::nullopt;
    result=lower+(upper-lower)*(static_cast<float>(fraction)/16.0f);
  }
  return (angle&0x8000U)?-result:result;
}
inline bool camera_precision_call(const RendererGameLayout& layout,bool interpolated, std::uint32_t target,std::uint32_t caller,
    std::uint32_t transform,std::uint32_t destination) {
  if(!interpolated || transform!=layout.camera_transform)return false;
  const auto contains=[caller](const auto& sites){for(auto site:sites)if(site==caller)return true;return false;};
  if(destination==layout.view_matrix) {
    if(target==layout.sine)return contains(layout.ypr_sine);
    if(target==layout.cosine)return contains(layout.ypr_cosine);
  }
  if(destination==layout.inverse_matrix) {
    if(target==layout.sine)return contains(layout.rpy_sine);
    if(target==layout.cosine)return contains(layout.rpy_cosine);
  }
  return false;
}
} // namespace jfg
