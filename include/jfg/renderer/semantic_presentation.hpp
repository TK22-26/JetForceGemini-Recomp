#pragma once
#include <span>
#include "jfg/renderer/interpolation_history.hpp"
#include <set>
#include <map>
#include <functional>
#include <algorithm>
#include <limits>
#include <stdexcept>

namespace jfg {
using PresentationVertexKey = std::array<std::uint64_t, 6>;
struct SemanticPresentationSample {
  // Lifetime, actor/instance, model, camera identity, joint, logical vertex.
  PresentationVertexKey key{};

  std::array<float, 3> world{};
  PresentationMatrix camera{};
  bool valid = false;
  // Decoder proved the affine bone matrix collapses every local vertex to
  // one finite world point. Topology must still prove it is non-rendering.
  bool point_collapsed = false;
};

// Native death animations hide bones by scaling them exactly to zero.
// Do not treat an almost-zero, non-affine or nonfinite matrix as hidden.
inline bool semantic_point_collapse(const PresentationMatrix& matrix) {
  for (std::size_t i=0;i<12U;++i)
    if (matrix[i]!=0.0F) return false;
  return matrix[15]==1.0F && std::isfinite(matrix[12]) &&
      std::isfinite(matrix[13]) && std::isfinite(matrix[14]);
}

// Exclude only collapsed vertices whose incident triangles all collapse to
// the same owned world point. They have no rasterized area. A connection to
// visible geometry keeps the original invalid-actor safeguard. GPU geometry
// is untouched, and the caller must hold excluded matrices at the endpoint.
inline std::size_t exclude_collapsed_semantic_samples(
    std::span<SemanticPresentationSample> samples,
    std::span<const std::uint32_t> indices) {
  if (indices.size()%3U || std::none_of(samples.begin(),samples.end(),
      [](const auto& s){return s.point_collapsed && s.key[0] && !s.valid;}))
    return 0U;
  std::vector<std::uint8_t> excluded(samples.size());
  for(std::size_t i=0;i<samples.size();++i) {
    const auto& s=samples[i];
    excluded[i]=s.point_collapsed && s.key[0] && !s.valid &&
        std::all_of(s.world.begin(),s.world.end(),[](float v){return std::isfinite(v);});
  }
  for(const auto index:indices) if(index>=samples.size())return 0U;
  for(std::size_t t=0;t<indices.size();t+=3U) {
    const auto a=indices[t],b=indices[t+1U],c=indices[t+2U];
    const auto& x=samples[a];const auto& y=samples[b];const auto& z=samples[c];
    const auto same_owner=[](const auto& p,const auto& q) {
      return std::equal(p.key.begin(),p.key.begin()+4,q.key.begin());
    };
    // Eligibility is not propagated between triangles: any visible use
    // permanently vetoes exclusion for that vertex.
    if(!x.point_collapsed || !y.point_collapsed || !z.point_collapsed ||
       x.world!=y.world || x.world!=z.world ||
       !same_owner(x,y) || !same_owner(x,z))
      excluded[a]=excluded[b]=excluded[c]=0U;
  }
  std::size_t count=0;
  for(std::size_t i=0;i<samples.size();++i) if(excluded[i]) {
    samples[i].key={}; // No inverse or history entry for a hidden point.
    ++count;
  }
  return count;
}
struct SemanticPresentationPrevious {
  std::array<float, 3> world{};
  PresentationMatrix camera{};
  bool matched = false;
  // New visibility/topology has no old vertex pose, but a verified continuous
  // camera can still present its current pose in phase with the scenery.
  bool camera_only = false;
};
using SemanticBirthEndpoints=std::map<PresentationVertexKey,SemanticPresentationPrevious>;
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
// Optional per-lifetime reasons: invalid sample, cadence break, conflicting
// duplicate, missing old endpoint, projected-motion cut, matched vertex,
// owned-camera exception, attached effect birth. Births still obey every
// whole-actor poison/cut/camera guard and need a verified previous attachment.
using SemanticPresentationDiagnostics=std::map<std::uint64_t,std::array<std::uint64_t,8>>;
using SemanticRigidPoses=std::map<std::uint64_t,RigidPresentationPose>;
// Captured camera operands must have matched the actual emitted fixed matrix.
// Generation separates rooms; the key identifies the camera mode/player.
struct SemanticCameraFrame {
  std::uint64_t generation = 0;
  RigidPresentationPose pose{};
  PresentationMatrix matrix{};
};
using SemanticCameraFrames=std::map<std::uint64_t,SemanticCameraFrame>;
inline bool semantic_world_motion_continuous(const SemanticPresentationSample& old,
                                             const SemanticPresentationSample& current) {
  double distance2=0;
  for(unsigned c=0;c<3;++c) {
    if(!std::isfinite(old.world[c]) || !std::isfinite(current.world[c]))return false;
    const auto delta=double(current.world[c])-old.world[c];distance2+=delta*delta;
  }
  // Same guest-world bound as the owned bridge path. Real relocations must
  // not trail across a source interval, even if their projected size is small.
  return distance2<=128.0*128.0;
}
class SemanticPresentationHistory {
  struct Endpoint {
    SemanticPresentationSample sample;
    std::size_t first = 0;
  };
  // Two retained, contiguous endpoint tables avoid one heap allocation per
  // logical vertex per scene. Hash collisions always compare the entire key;
  // indices are local to each table and are rebuilt before reusing storage.
  struct Endpoints {
    static constexpr auto empty = (std::numeric_limits<std::size_t>::max)();
    std::vector<Endpoint> entries;
    std::vector<std::size_t> slots;
    void clear(std::size_t maximum) {
      if (maximum > empty / 4U) throw std::length_error("semantic history capacity");
      std::size_t capacity=16U;
      while (capacity < maximum*2U) capacity*=2U;
      if (capacity > slots.size()) slots.resize(capacity);
      std::fill(slots.begin(),slots.end(),empty);
      entries.clear();entries.reserve(maximum);
    }
    std::pair<Endpoint*,bool> insert(const SemanticPresentationSample& sample,std::size_t first) {
      auto slot=PresentationVertexHash{}(sample.key)&(slots.size()-1U);
      while (slots[slot]!=empty) {
        auto& entry=entries[slots[slot]];
        if (entry.sample.key==sample.key) return {&entry,false};
        slot=(slot+1U)&(slots.size()-1U);
      }
      slots[slot]=entries.size();entries.push_back({sample,first});
      return {&entries.back(),true};
    }
    const Endpoint* find(const PresentationVertexKey& key) const {
      if (slots.empty()) return nullptr;
      auto slot=PresentationVertexHash{}(key)&(slots.size()-1U);
      while (slots[slot]!=empty) {
        const auto& entry=entries[slots[slot]];
        if (entry.sample.key==key) return entry.sample.valid ? &entry : nullptr;
        slot=(slot+1U)&(slots.size()-1U);
      }
      return nullptr;
    }
  };
public:
  std::vector<SemanticPresentationPrevious>
  record(const std::vector<SemanticPresentationSample> &samples,
         std::uint64_t tick, bool scene, bool cadence,
         SemanticPresentationDiagnostics* diagnostics=nullptr,
         const SemanticRigidPoses* rigid_poses=nullptr,
         const SemanticCameraFrames* camera_frames=nullptr,
         const SemanticBirthEndpoints* births=nullptr) {
    std::vector<SemanticPresentationPrevious> result;
    record_into(samples, tick, scene, cadence, result, diagnostics, rigid_poses, camera_frames, births);
    return result;
  }
  // The caller owns this scratch output, which is consumed before its next
  // use. Reset every element even when size is unchanged: a held/offscreen
  // scene must never retain the preceding scene's matched endpoints.
  void record_into(const std::vector<SemanticPresentationSample>& samples,
      std::uint64_t tick, bool scene, bool cadence,
      std::vector<SemanticPresentationPrevious>& result,
      SemanticPresentationDiagnostics* diagnostics=nullptr,
      const SemanticRigidPoses* rigid_poses=nullptr,
         const SemanticCameraFrames* camera_frames=nullptr,
         const SemanticBirthEndpoints* births=nullptr) {
    result.assign(samples.size(), SemanticPresentationPrevious{});
    if (!scene) return;
    next_.clear(samples.size());
    std::set<std::uint64_t> blocked, corrupt, missing_actors, camera_ineligible;
    const bool continuous = cadence && previous_tick_ != 0U &&
                            tick > previous_tick_ &&
                            tick - previous_tick_ <= 6U;
    std::set<std::uint64_t> continuous_rigids;
    if(rigid_poses)for(const auto& [lifetime,pose]:*rigid_poses) {
      const auto old=previous_rigid_poses_.find(lifetime);
      if(old!=previous_rigid_poses_.end() && continuous_owned_camera_motion(old->second,pose))
        continuous_rigids.insert(lifetime);
    }
    std::set<std::uint64_t> continuous_cameras;
    if(camera_frames)for(const auto& [identity,camera]:*camera_frames) {
      const auto old=previous_camera_frames_.find(identity);
      if(old!=previous_camera_frames_.end() && camera.generation!=0U &&
         old->second.generation==camera.generation &&
         continuous_owned_camera_motion(old->second.pose,camera.pose))
        continuous_cameras.insert(identity);
    }
    const auto owned_camera_motion=[&](const auto& old,const auto& current)
        -> std::optional<bool> {
      if(!camera_frames)return std::nullopt;
      const auto camera=camera_frames->find(current.key[3]);
      const auto prior=previous_camera_frames_.find(old.key[3]);
      if(camera==camera_frames->end() || prior==previous_camera_frames_.end() ||
         camera->second.matrix!=current.camera || prior->second.matrix!=old.camera)
        return std::nullopt;
      return continuous_cameras.contains(current.key[3]) &&
             semantic_world_motion_continuous(old,current);
    };
    const auto procedural_continuous=[&](const auto& old,const auto& current) {
      if((current.key[4]!=0x42524944U && current.key[4]!=0x4245414dU && current.key[4]!=0x53484f43U && current.key[4]!=0x54524143U) ||
         !continuous_rigids.contains(current.key[0]))
        return false;
      for(float value:old.camera)if(!std::isfinite(value))return false;
      for(float value:current.camera)if(!std::isfinite(value))return false;
      double distance2=0;
      for(unsigned c=0;c<3;++c) {
        if(!std::isfinite(old.world[c]) || !std::isfinite(current.world[c]))return false;
        const auto delta=double(current.world[c])-old.world[c];distance2+=delta*delta;
      }
      // Retain a world-space bound on bridge/beam deformation. Camera/zoom/model
      // cuts have already been checked using the immutable owned operands.
      return distance2<=128.0*128.0;
    };
    for (std::size_t i = 0; i < samples.size(); ++i) {
      const auto &s = samples[i];
      const auto actor = s.key[0];
      if (actor == 0U)
        continue;
      if(diagnostics) {
        (*diagnostics)[actor][0]+=!s.valid;
        (*diagnostics)[actor][1]+=!continuous;
      }
      if (!s.valid || !continuous) {
        blocked.insert(actor);camera_ineligible.insert(actor);
      }
      if (!s.valid) {
        corrupt.insert(actor);
        continue;
      }
      // Identical UV clones share one continuity decision. Keep the full key
      // and endpoint comparison: conflicting clones still poison the actor.
      const auto [it, inserted] = next_.insert(s,i);
      if (inserted) {
        (*it) = {s, i};
      } else if ((*it).sample.world == s.world &&
                 (*it).sample.camera == s.camera) {
        result[i] = result[(*it).first];
        continue;
      } else {
        blocked.insert(actor);
        corrupt.insert(actor);camera_ineligible.insert(actor);
        if(diagnostics)++(*diagnostics)[actor][2];
      }
      // A unique NaN endpoint was rejected by the original duplicate audit.
      // Preserve its poison even when that vertex is culled next scene.
      for (float value:s.world) if (std::isnan(value)) corrupt.insert(actor);
      for (float value:s.camera) if (std::isnan(value)) corrupt.insert(actor);
      const Endpoint* old = previous_.find(s.key);
      Endpoint attached;
      bool birth=false;
      if(!old && births && continuous && s.valid) {
        const auto found=births->find(s.key);
        if(found!=births->end() && found->second.matched) {
          attached.sample=s;attached.sample.world=found->second.world;
          attached.sample.camera=found->second.camera;old=&attached;birth=true;
        }
      }
      if (old == nullptr) {
        blocked.insert(actor);missing_actors.insert(actor);
        if(diagnostics)++(*diagnostics)[actor][3];
      } else {
        // Screen-space speed combines the camera and actor. A close/offscreen
        // vertex can exceed that threshold during a valid camera sweep and
        // otherwise freeze every visible joint at a different camera phase.
        const bool projected=semantic_motion_continuous(old->sample,s);
        const auto owned=owned_camera_motion(old->sample,s);
        const bool motion=birth?owned.value_or(false):owned.has_value()?*owned:
            (projected || procedural_continuous(old->sample,s));
        if(!motion) {
          blocked.insert(actor);camera_ineligible.insert(actor);
          if(diagnostics)++(*diagnostics)[actor][4];
        } else {
          result[i] = {old->sample.world, old->sample.camera, true};
          if(diagnostics) {
            ++(*diagnostics)[actor][5];
            (*diagnostics)[actor][7]+=birth;
            (*diagnostics)[actor][6]+=!projected && owned.value_or(false);
          }
        }
      }
    }
    // Missing geometry history must not advance the camera to the native
    // endpoint while the room uses an intermediate camera. Keep all vertices
    // of that actor at the current world pose, with zero deformation velocity.
    // Only a fully validated camera shared by every part can be borrowed.
    auto camera_only=missing_actors;
    for(const auto actor:camera_ineligible)camera_only.erase(actor);
    for(const auto& sample:samples) {
      const auto actor=sample.key[0];
      if(!camera_only.contains(actor))continue;
      if(!camera_frames || !continuous_cameras.contains(sample.key[3])) {
        camera_only.erase(actor);continue;
      }
      const auto current=camera_frames->find(sample.key[3]);
      const auto old=previous_camera_frames_.find(sample.key[3]);
      if(current==camera_frames->end() || old==previous_camera_frames_.end() ||
         current->second.matrix!=sample.camera ||
         !std::all_of(old->second.matrix.begin(),old->second.matrix.end(),
             [](float value){return std::isfinite(value);}))
        camera_only.erase(actor);
    }
    for (std::size_t i = 0; i < samples.size(); ++i)
      if (blocked.contains(samples[i].key[0])) {
        result[i].matched = false;
        if(camera_only.contains(samples[i].key[0]))
          result[i]={samples[i].world,
              previous_camera_frames_.at(samples[i].key[3]).matrix,false,true};
      }
    // A conflicting endpoint is not a valid anchor for the next scene.
    for (auto& entry : next_.entries)
      if (corrupt.contains(entry.sample.key[0])) entry.sample.valid=false;
    std::swap(previous_,next_);
    previous_tick_ = tick;
    previous_rigid_poses_=rigid_poses?*rigid_poses:SemanticRigidPoses{};
    previous_camera_frames_=camera_frames?*camera_frames:SemanticCameraFrames{};
  }

private:
  Endpoints previous_, next_;
  SemanticRigidPoses previous_rigid_poses_;
  SemanticCameraFrames previous_camera_frames_;
  std::uint64_t previous_tick_ = 0;
};
} // namespace jfg
