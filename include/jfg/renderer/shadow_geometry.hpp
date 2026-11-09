#pragma once
#include <array>
#include <algorithm>
#include <cmath>
#include <cstdint>
#include <bit>
#include <optional>
namespace jfg {
// Native projected lights use 16-bit yaw/elevation. A downward ray advances
// (sin(yaw),cos(yaw)) horizontally as it descends; native elongation is capped
// at two world units per vertical unit. This affects presentation only.
inline std::array<float,2> shadow_light_shear(std::uint16_t yaw,std::uint16_t elevation) {
  constexpr double angle=6.283185307179586476925286766559/65536.0;
  const double c=std::cos(double(elevation)*angle),s=std::sin(double(elevation)*angle);
  const double ratio=c>1e-9 ? (std::abs(s)>1e-9 ? (std::min)(2.0,c/s) : 2.0) : 0.0;
  return {float(std::sin(double(yaw)*angle)*ratio),float(std::cos(double(yaw)*angle)*ratio)};
}
// Retain the native producer's fractional receiver point only when it
// reproduces the exact emitted signed coordinates and keeps its depth lift.
inline std::optional<std::array<float,3>> shadow_precise_position(
    const std::array<float,3>& source, float lift,
    const std::array<float,3>& packed) {
  if(!std::isfinite(lift) || lift<1.0f || lift>32.0f)return {};
  const std::array<float,3> world{source[0],source[1]+lift,source[2]};
  for(unsigned c=0;c<3U;++c)
    if(!std::isfinite(world[c]) || world[c]<-32768.0f || world[c]>=32768.0f ||
       std::trunc(world[c])!=packed[c])return {};
  return world;
}
// A native projected shadow is clipped against receiver triangles. Its DMA
// buffer/order is transient. Identify corners by the two clipping boundaries,
// so a recycled slot cannot match a different floor vertex or intersection.
struct ShadowClipGeometry {
  std::array<std::array<float,3>,3> receiver{};
  std::array<std::array<float,2>,4> projector{}; // native X,Z rectangle
  std::uint64_t receiver_key=0;
};
inline std::uint64_t shadow_receiver_key(const ShadowClipGeometry& clip,
                                         std::uint32_t plane) {
  std::uint64_t key=14695981039346656037ULL;
  const auto add=[&](std::uint32_t value) {key^=value;key*=1099511628211ULL;};
  add(plane);
  for(const auto& p:clip.receiver)for(const float v:p) {
    if(!std::isfinite(v))return 0;
    add(std::bit_cast<std::uint32_t>(v==0.0f?0.0f:v));
  }
  return key?key:1U;
}
inline unsigned shadow_corner_identity(const ShadowClipGeometry& clip,
                                       const std::array<float,3>& point) {
  for(float v:point)if(!std::isfinite(v))return 0;
  constexpr double tolerance=1.0/64.0;
  const std::array<double,2> p{point[0],point[2]};
  const auto close_enough=[&](double x,double z) {
    return std::abs(p[0]-x)<=tolerance && std::abs(p[1]-z)<=tolerance;
  };
  for(unsigned i=0;i<3;++i)
    if(close_enough(clip.receiver[i][0],clip.receiver[i][2]))return 0x100U+i;
  for(unsigned i=0;i<4;++i)
    if(close_enough(clip.projector[i][0],clip.projector[i][1]))return 0x200U+i;
  const auto edge=[&](double ax,double az,double bx,double bz) {
    const double dx=bx-ax,dz=bz-az,length=std::hypot(dx,dz);
    if(!std::isfinite(length) || length<tolerance)return false;
    const double t=((p[0]-ax)*dx+(p[1]-az)*dz)/length;
    return std::abs((p[0]-ax)*dz-(p[1]-az)*dx)<=tolerance*length &&
        t>=-tolerance && t<=length+tolerance;
  };
  unsigned result=0;
  for(unsigned r=0;r<3;++r)for(unsigned q=0;q<4;++q) {
    const auto& a=clip.receiver[r];const auto& b=clip.receiver[(r+1U)%3U];
    const auto& c=clip.projector[q];const auto& d=clip.projector[(q+1U)%4U];
    if(edge(a[0],a[2],b[0],b[2]) && edge(c[0],c[1],d[0],d[1])) {
      if(result)return 0; // Coincident/ambiguous edges do not own a history key.
      result=0x300U+r*4U+q;
    }
  }
  return result;
}
} // namespace jfg
