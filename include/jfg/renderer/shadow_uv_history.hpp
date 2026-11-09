#pragma once
#include "jfg/renderer/semantic_presentation.hpp"
namespace jfg {
struct ShadowUvSample {
  PresentationVertexKey key{};
  std::array<float,2> uv{};
  bool geometry_matched=false;
  std::array<float,2> position{};
  bool position_valid=false, camera_only=false;
};
// Native shadow UVs are affine in the unquantized receiver X/Z coordinates.
// A new clipped corner has no old position, but its current floor position can
// still be evaluated in the previous projector without borrowing another corner.
class ShadowUvHistory {
  using Group=std::array<std::uint64_t,5>;
  struct Entry { std::array<float,2> uv{};bool conflict=false; };
  struct Projector {
    std::array<double,2> origin{}, uv{};
    std::array<double,2> dx{}, dz{};
    std::array<double,4> inverse_basis{};
    bool bounded(const std::array<float,2>& p) const {
      const double x=p[0]-origin[0],z=p[1]-origin[1];
      const double b=inverse_basis[0]*x+inverse_basis[1]*z;
      const double c=inverse_basis[2]*x+inverse_basis[3]*z;
      // Bound extrapolation of native 1/32-texel rounding. A thin old clip
      // cannot amplify that quantization into a large new texture jump.
      return std::isfinite(b) && std::isfinite(c) &&
          std::abs(1.0-b-c)+std::abs(b)+std::abs(c)<=4.0;
    }
    std::array<double,2> at(const std::array<float,2>& p) const {
      return {uv[0]+dx[0]*(p[0]-origin[0])+dz[0]*(p[1]-origin[1]),
              uv[1]+dx[1]*(p[0]-origin[0])+dz[1]*(p[1]-origin[1])};
    }
  };
  static Group group(const ShadowUvSample& s) {
    return {s.key[0],s.key[1],s.key[2],s.key[3],s.key[4]};
  }
  static std::optional<Projector> fit(const std::vector<const ShadowUvSample*>& points) {
    if(points.size()<3U)return {};
    const auto& a=*points.front();const ShadowUvSample* b=nullptr;double distance=0;
    for(const auto* p:points) {
      const double x=double(p->position[0])-a.position[0],z=double(p->position[1])-a.position[1];
      if(x*x+z*z>distance) {distance=x*x+z*z;b=p;}
    }
    if(!b || distance<1.0)return {};
    const double bx=double(b->position[0])-a.position[0],bz=double(b->position[1])-a.position[1];
    const ShadowUvSample* c=nullptr;double determinant=0;
    for(const auto* p:points) {
      const double d=bx*(double(p->position[1])-a.position[1])-bz*(double(p->position[0])-a.position[0]);
      if(std::abs(d)>std::abs(determinant)) {determinant=d;c=p;}
    }
    if(!c || std::abs(determinant)<1.0)return {};
    const double cx=double(c->position[0])-a.position[0],cz=double(c->position[1])-a.position[1];
    Projector result;result.origin={a.position[0],a.position[1]};result.uv={a.uv[0],a.uv[1]};
    result.inverse_basis={cz/determinant,-cx/determinant,-bz/determinant,bx/determinant};
    for(unsigned i=0;i<2U;++i) {
      const double u=double(b->uv[i])-a.uv[i],v=double(c->uv[i])-a.uv[i];
      result.dx[i]=(u*cz-v*bz)/determinant;result.dz[i]=(v*bx-u*cx)/determinant;
      if(!std::isfinite(result.dx[i]) || !std::isfinite(result.dz[i]))return {};
    }
    // Native UVs are truncated to 1/32 texel. Reject non-affine data, seams,
    // conflicting duplicates and poorly conditioned clipped slivers.
    for(const auto* p:points) {
      const auto uv=result.at(p->position);
      for(unsigned i=0;i<2U;++i)if(!std::isfinite(uv[i]) || std::abs(uv[i]-p->uv[i])>0.0625)return {};
    }
    return result;
  }
  std::map<PresentationVertexKey,Entry> previous_;
  std::map<Group,Projector> previous_projectors_;
  std::uint64_t tick_=0;bool have_tick_=false;
public:
  std::vector<std::array<float,2>> record(std::span<const ShadowUvSample> samples,
                                        std::uint64_t tick,bool continuous) {
    std::vector<std::array<float,2>> result(samples.size());
    if(have_tick_ && tick==tick_)return result;
    const bool adjacent=have_tick_ && continuous && tick>tick_ && tick-tick_<=6U;
    std::map<PresentationVertexKey,Entry> current;
    std::map<Group,std::vector<const ShadowUvSample*>> points;
    for(const auto& s:samples)if(s.key[0] && s.key[3] && s.key[4]==0x53484144U &&
        std::isfinite(s.uv[0]) && std::isfinite(s.uv[1])) {
      const auto [it,inserted]=current.emplace(s.key,Entry{s.uv});
      if(!inserted && it->second.uv!=s.uv)it->second.conflict=true;
      if(s.position_valid && std::isfinite(s.position[0]) && std::isfinite(s.position[1]))
        points[group(s)].push_back(&s);
    }
    std::map<Group,Projector> projectors;
    for(const auto& [key,p]:points)if(const auto projection=fit(p))projectors.emplace(key,*projection);
    for(std::size_t i=0;i<samples.size() && adjacent;++i) {
      const auto& s=samples[i];const auto now=current.find(s.key),old=previous_.find(s.key);
      if(now==current.end() || now->second.conflict)continue;
      if(s.geometry_matched && old!=previous_.end() && !old->second.conflict) {
        const std::array<float,2> delta{s.uv[0]-old->second.uv[0],s.uv[1]-old->second.uv[1]};
        if(std::isfinite(delta[0]) && std::isfinite(delta[1]))result[i]=delta;
      } else if(s.camera_only && s.position_valid && projectors.contains(group(s))) {
        const auto prior=previous_projectors_.find(group(s));
        if(prior==previous_projectors_.end() || !prior->second.bounded(s.position))continue;
        const auto uv=prior->second.at(s.position);
        const std::array<float,2> delta{float(s.uv[0]-uv[0]),float(s.uv[1]-uv[1])};
        // Camera-only motion is already guarded against cuts. Also reject a
        // projector jump larger than one quarter of the native 64-pixel mask.
        if(std::isfinite(delta[0]) && std::isfinite(delta[1]) &&
           std::abs(delta[0])<=16.0f && std::abs(delta[1])<=16.0f)result[i]=delta;
      }
    }
    previous_=std::move(current);previous_projectors_=std::move(projectors);
    tick_=tick;have_tick_=true;return result;
  }
};
} // namespace jfg
