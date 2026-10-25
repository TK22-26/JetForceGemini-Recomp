#pragma once
#include "jfg/renderer/semantic_presentation.hpp"
namespace jfg {
// A newly visible effect can inherit an already observed attachment pose.
// This never invents an old pose for a new actor, bone, model or camera.
using EffectAttachmentKey = std::array<std::uint64_t,5>; // lifetime, actor/instance, model, bone, camera
struct EffectAttachmentPose {
  PresentationMatrix world{}, camera{};
  bool operator==(const EffectAttachmentPose&) const = default;
};
using EffectAttachmentFrames = std::map<EffectAttachmentKey,std::optional<EffectAttachmentPose>>;
inline bool valid_effect_attachment(const EffectAttachmentPose& pose) {
  for(float x:pose.world)if(!std::isfinite(x))return false;
  for(float x:pose.camera)if(!std::isfinite(x))return false;
  const auto& m=pose.world;
  if(m[3]!=0 || m[7]!=0 || m[11]!=0 || m[15]!=1)return false;
  const double d=double(m[0])*(double(m[5])*m[10]-double(m[6])*m[9])-
      double(m[1])*(double(m[4])*m[10]-double(m[6])*m[8])+
      double(m[2])*(double(m[4])*m[9]-double(m[5])*m[8]);
  return std::isfinite(d) && std::abs(d)>1e-9;
}
inline void observe_effect_attachment(EffectAttachmentFrames& frames,
    const EffectAttachmentKey& key,const EffectAttachmentPose& pose) {
  auto [it,fresh]=frames.emplace(key,std::nullopt);
  if(fresh) {if(valid_effect_attachment(pose))it->second=pose;}
  else if(!it->second || *it->second!=pose || !valid_effect_attachment(pose))it->second.reset();
}
struct AttachedEffectVertex {
  SemanticPresentationSample sample;
  EffectAttachmentKey attachment{};
  std::array<float,3> local{};
};
class AttachedEffectHistory {
public:
  SemanticBirthEndpoints record(const EffectAttachmentFrames& frames,
      const std::vector<AttachedEffectVertex>& vertices,std::uint64_t tick,bool scene,bool cadence) {
    SemanticBirthEndpoints result;
    if(!scene)return result;
    const bool continuous=cadence && previous_tick_ && tick>previous_tick_ && tick-previous_tick_<=6U;
    if(continuous) for(const auto& vertex:vertices) {
      if(!vertex.sample.valid)continue;
      const auto current=frames.find(vertex.attachment);
      const auto old=previous_.find(vertex.attachment);
      if(current==frames.end() || old==previous_.end() || !current->second || !old->second ||
         current->second->camera!=vertex.sample.camera)continue;
      std::array<float,3> before{},now{};bool valid=true;
      for(unsigned c=0;c<3;++c) {
        const auto transform=[&](const PresentationMatrix& m) {
          return vertex.local[0]*m[c]+vertex.local[1]*m[4+c]+vertex.local[2]*m[8+c]+m[12+c];
        };
        before[c]=transform(old->second->world);now[c]=transform(current->second->world);
        valid=valid && std::isfinite(before[c]) && std::isfinite(now[c]) &&
            std::abs(now[c]-vertex.sample.world[c])<=0.03125f;
      }
      if(!valid)continue;
      const SemanticPresentationPrevious endpoint{before,old->second->camera,true};
      const auto [it,fresh]=result.emplace(vertex.sample.key,endpoint);
      if(!fresh && (it->second.world!=endpoint.world || it->second.camera!=endpoint.camera))
        it->second.matched=false; // Conflicting UV clones cannot revive a birth.
    }
    previous_=frames;previous_tick_=tick;
    return result;
  }
private:
  EffectAttachmentFrames previous_;
  std::uint64_t previous_tick_=0;
};
} // namespace jfg
