#pragma once
#include "jfg/renderer/presentation_identity.hpp"
#include "jfg/renderer/semantic_presentation.hpp"
namespace jfg {
// A caster belongs to the live model, not a visible camera or mirror pass.
// Call with the original palette matrix, before the reflection adjustment.
inline SemanticPresentationSample enhanced_shadow_caster(
    const PresentationVertexIdentity& identity, const PresentationMatrix& matrix,
    const std::array<float,3>& local) {
  SemanticPresentationSample result;
  if(!identity.owner || !identity.geometry || identity.cone)return result;
  const auto& owner=*identity.owner;
  const auto& geometry=*identity.geometry;
  if(owner.actor!=geometry.actor || owner.lifetime!=geometry.lifetime)return result;
  result.key={owner.lifetime,(std::uint64_t(owner.actor)<<32U)|geometry.instance,
      geometry.model,1U,identity.joint,identity.vertex};
  result.camera={1,0,0,0,0,1,0,0,0,0,1,0,0,0,0,1};
  result.valid=owner.lifetime!=0 && identity.joint<owner.bone_count;
  for(const auto value:matrix)result.valid=result.valid&&std::isfinite(value);
  for(unsigned c=0;c<3;++c) {
    result.world[c]=local[0]*matrix[c]+local[1]*matrix[4+c]+
        local[2]*matrix[8+c]+matrix[12+c];
    result.valid=result.valid&&std::isfinite(result.world[c])&&std::abs(result.world[c])<1000000.0f;
  }
  const float w=local[0]*matrix[3]+local[1]*matrix[7]+local[2]*matrix[11]+matrix[15];
  result.valid=result.valid&&std::isfinite(w)&&std::abs(w-1.0f)<0.001f;
  return result;
}
// Rigid models use an emitted model/view/projection matrix rather than a bone
// palette. Match the exact live model allocation and verified native operands.
inline SemanticPresentationSample enhanced_shadow_rigid_caster(
    const PresentationSceneIdentity& scene,const PresentationRigidIdentity& rigid,
    std::uint32_t source,const PresentationMatrix& emitted,
    const std::array<float,3>& local) {
  SemanticPresentationSample result;
  if(!rigid.lifetime || !rigid_pose_matches_matrix(rigid.pose,emitted))return result;
  const PresentationModelIdentity* found=nullptr;
  for(const auto& model:scene.models) {
    if(model.actor!=rigid.actor || model.lifetime!=rigid.lifetime ||
       source<model.vertices || (source-model.vertices)%10U ||
       (source-model.vertices)/10U>=model.vertex_count)continue;
    if(found)return result;
    found=&model;
  }
  // Detached parts have no ModelInstance. Reuse the bounded baked vertex
  // allocation already proven for normal rigid interpolation.
  const PresentationLimbIdentity* limb=nullptr;
  for(const auto& candidate:scene.limbs) {
    if(candidate.actor!=rigid.actor || candidate.lifetime!=rigid.lifetime)continue;
    const bool contains=std::any_of(candidate.ranges.begin(),candidate.ranges.end(),
        [&](const auto& range) {
          return source>=range[0] && (source-range[0])%10U==0U &&
              (source-range[0])/10U<range[1];
        });
    if(!contains)continue;
    if(found||limb)return result;
    limb=&candidate;
  }
  if(!found&&!limb)return result;
  if(limb)result.key={rigid.lifetime,(std::uint64_t(rigid.actor)<<32U)|limb->control,
      (std::uint64_t(limb->header)<<32U)|limb->vertices,1U,1022U,source};
  else result.key={rigid.lifetime,(std::uint64_t(rigid.actor)<<32U)|found->instance,
      found->model,1U,1023U,(source-found->vertices)/10U};
  result.camera={1,0,0,0,0,1,0,0,0,0,1,0,0,0,0,1};
  result.valid=true;
  const auto& m=rigid.pose.world;
  for(const auto v:m)result.valid=result.valid&&std::isfinite(v);
  for(unsigned c=0;c<3;++c) {
    result.world[c]=local[0]*m[c]+local[1]*m[c+4]+local[2]*m[c+8]+m[c+12];
    result.valid=result.valid&&std::isfinite(result.world[c])&&std::abs(result.world[c])<1000000.0f;
  }
  const float w=local[0]*m[3]+local[1]*m[7]+local[2]*m[11]+m[15];
  result.valid=result.valid&&std::isfinite(w)&&std::abs(w-1.0f)<0.001f;
  return result;
}
inline SemanticCameraFrames enhanced_shadow_world_frame() {
  SemanticCameraFrame frame;
  frame.generation=1;
  frame.matrix={1,0,0,0,0,1,0,0,0,0,1,0,0,0,0,1};
  frame.pose.world=frame.pose.view=frame.pose.projection=frame.matrix;
  return {{1U,frame}};
}
}
