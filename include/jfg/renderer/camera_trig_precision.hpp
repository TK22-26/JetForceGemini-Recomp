#pragma once
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
inline bool camera_precision_call(bool interpolated, std::uint32_t target,std::uint32_t caller,
    std::uint32_t transform,std::uint32_t destination) {
  if(!interpolated || transform!=0x800FA638U)return false;
  if(destination==0x800FAF78U) {
    if(target==0x80049C34U)return caller==0x8004A1B4U || caller==0x8004A1C8U || caller==0x8004A1DCU;
    if(target==0x80049C30U)return caller==0x8004A1BCU || caller==0x8004A1D0U || caller==0x8004A1E4U;
  }
  if(destination==0x800F2A08U) {
    if(target==0x80049C34U)return caller==0x80049F1CU || caller==0x80049F30U || caller==0x80049F44U;
    if(target==0x80049C30U)return caller==0x80049F24U || caller==0x80049F38U || caller==0x80049F4CU;
  }
  return false;
}
} // namespace jfg
