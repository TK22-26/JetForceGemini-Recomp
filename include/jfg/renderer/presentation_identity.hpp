#pragma once
#include "jfg/renderer/rigid_camera.hpp"
#include <array>
#include <algorithm>
#include <bitset>
#include <limits>
#include <bit>
#include <cstdint>
#include <cstring>
#include <map>
#include <optional>
#include <span>
#include <vector>

namespace jfg {
// Host-only identity for the supported US guest. No writes to simulation RAM.
// Addresses locate a sample; lifetime + model + bone identify what it means.
struct PresentationModelIdentity {
  std::uint64_t lifetime = 0;
  std::uint32_t actor = 0, instance = 0, model = 0;
  std::array<std::uint32_t, 2> palettes{};
  std::uint32_t vertices = 0, vertex_count = 0, bone_count = 0;
  bool deforming_bridge = false; // US hitBridgeControl (behavior 55).
  bool animated_ship = false; // US animship, used only for attached effects.
};
struct PresentationCameraIdentity {
  std::uint32_t matrix = 0;
  std::uint64_t identity = 0;
  std::uint64_t generation = 0;
  RigidPresentationPose pose;
  bool pose_valid = false;
  // Sky uses native operands for byte validation, folded model/view only for motion.
  std::optional<RigidPresentationPose> motion_pose;
};
struct PresentationSpriteIdentity {
  std::uint32_t anchor = 0, actor = 0, sprite = 0;
  std::uint64_t lifetime = 0;
  std::uint32_t sub_id = 0, control = 0;
};
inline std::array<std::uint64_t,4> presentation_sprite_key(
    const PresentationSpriteIdentity& sprite,std::uint64_t camera) {
  return {sprite.lifetime,(std::uint64_t(sprite.sub_id)<<32U)|sprite.actor,
      (std::uint64_t(sprite.control)<<32U)|sprite.sprite,camera};
}
// A rigid object's transient combined matrix is bound to its actor lifetime.
// The address locates this task's sample; it is never the history key.
struct PresentationRigidIdentity {
  std::uint32_t matrix = 0, actor = 0;
  std::uint64_t lifetime = 0, camera = 0;
  RigidPresentationPose pose;
};
// US behavior 68 / beamDraw: two eight-vertex buffers in actor control data.
// The physical buffer alternates; actor lifetime, control allocation and shape
// flags identify the same logical vertices across scenes.
struct PresentationBeamIdentity {
  std::uint64_t lifetime = 0;
  std::uint32_t actor = 0, control = 0, header = 0, vertices = 0, flags = 0;
};
// US behavior 78 / glassDraw: intact panes use a shared four-vertex quad,
// outside the actor's model vertex allocations. The control allocation and
// actor lifetime own this custom draw; the vertex address only locates it.
struct PresentationGlassIdentity {
  std::uint64_t lifetime = 0;
  std::uint32_t actor = 0, control = 0, header = 0, vertices = 0;
  std::array<float,2> texture_period{};
};
// US behavior 64 / objPrintSeveredLimb draws baked body-part vertices with
// no model instances. The live actor/control allocation owns the geometry;
// display-list DMA ranges delimit it without guessing allocation sizes.
struct PresentationLimbIdentity {
  std::uint64_t lifetime = 0;
  std::uint32_t actor = 0, control = 0, header = 0, vertices = 0;
  std::vector<std::array<std::uint32_t,2>> ranges;
};
// US animshipDrawThrusters attaches separately allocated fxDrawCone geometry
// to a model bone. Both alternating buffers represent the same logical mesh.
struct PresentationConeIdentity {
  std::uint64_t lifetime = 0;
  std::uint32_t actor = 0, instance = 0, control = 0, allocation = 0;
  std::array<std::uint32_t,2> vertices{};
  std::uint32_t vertex_count = 0, joint = 0;
};
// US objDrawTracer emits a transient four-vertex view-space quad.
// The live projectile/control allocation owns it; task bytes bind scratch reuse.
// US behavior 40 / shockwaveDraw: two alternating 20-vertex rings at
// control+0 and control+200. Radius changes in local vertices each scene.
struct PresentationShockwaveIdentity {
  std::uint64_t lifetime=0;
  std::uint32_t actor=0,control=0,header=0,vertices=0,texture=0;
};
struct PresentationTracerIdentity {
  std::uint64_t lifetime=0, camera=0;
  std::uint32_t actor=0, control=0, header=0, vertices=0, matrix=0;
  RigidPresentationPose pose{};
};
struct PresentationCameraFade { std::uint32_t actor=0; float opacity=0; };
struct PresentationSceneIdentity {
  std::vector<PresentationCameraFade> camera_fades;
  std::vector<PresentationModelIdentity> models;
  std::vector<PresentationConeIdentity> cones;
  std::vector<PresentationCameraIdentity> cameras;
  std::vector<PresentationSpriteIdentity> sprites;
  std::vector<PresentationRigidIdentity> rigids;
  std::vector<PresentationBeamIdentity> beams;
  std::vector<PresentationTracerIdentity> tracers;
  std::vector<PresentationShockwaveIdentity> shockwaves;
  std::vector<PresentationGlassIdentity> glass;
  std::vector<PresentationLimbIdentity> limbs;
};
// A reduced-detail mesh can use the main model's bone palette. Resolve
// palette ownership first, then the vertex stream within that same actor.
struct PresentationVertexIdentity {
  const PresentationModelIdentity *owner = nullptr, *geometry = nullptr;
  std::uint32_t joint = 0, vertex = 0;
  const PresentationConeIdentity* cone = nullptr;
};
inline void presentation_cone_vertex(const PresentationSceneIdentity& scene,
    std::uint32_t source, PresentationVertexIdentity& result) {
  if (!result.owner || result.geometry) return;
  for (const auto& cone:scene.cones) {
    if (cone.actor!=result.owner->actor || cone.lifetime!=result.owner->lifetime ||
        cone.instance!=result.owner->instance || cone.joint!=result.joint) continue;
    for (const auto base:cone.vertices) {
      if (!base || source<base || (source-base)%10U ||
          (source-base)/10U>=cone.vertex_count) continue;
      // An ambiguous custom allocation is never a provenance fallback.
      if (result.cone) {result.cone=nullptr;return;}
      result.cone=&cone;result.vertex=(source-base)/10U;
    }
  }
}
inline PresentationVertexIdentity
presentation_vertex_identity(const PresentationSceneIdentity &scene,
                             std::uint32_t matrix, std::uint32_t source) {
  PresentationVertexIdentity result;
  for (const auto &model : scene.models)
    for (const auto palette : model.palettes) {
      if (!palette || matrix < palette ||
          matrix - palette >= model.bone_count * 64U ||
          (matrix - palette) % 64U)
        continue;
      if (result.owner && result.owner != &model)
        // Preserve invalid semantic provenance so this mesh holds its
        // endpoint instead of falling back to an ambiguous shape match.
        return result;
      result.owner = &model;
      result.joint = (matrix - palette) / 64U;
    }
  if (!result.owner)
    return result;
  for (const auto &model : scene.models) {
    if (model.actor != result.owner->actor ||
        model.lifetime != result.owner->lifetime || source < model.vertices ||
        source - model.vertices >= model.vertex_count * 10U ||
        (source - model.vertices) % 10U)
      continue;
    if (result.geometry) {
      result.geometry = nullptr;
      return result;
    }
    result.geometry = &model;
    result.vertex = (source - model.vertices) / 10U;
  }
  presentation_cone_vertex(scene,source,result);
  return result;
}
// F3DDKR DMA supplies at most 32 consecutive ten-byte vertices with one
// palette matrix. Resolve palette ownership once, then intersect model ranges
// with the batch. Preserve first-owner/first-vertex and ambiguous provenance
// exactly as the scalar lookup; a third overlap cannot revive a rejected key.
inline void presentation_vertex_identities(const PresentationSceneIdentity& scene,
    std::uint32_t matrix, std::uint32_t source,
    std::span<PresentationVertexIdentity> result) {
  if(result.empty())return;
  if(result.size()>32U || std::uint64_t(source)+(result.size()-1U)*10U>
      (std::numeric_limits<std::uint32_t>::max)()) {
    for(std::size_t i=0;i<result.size();++i)
      result[i]=presentation_vertex_identity(scene,matrix,
          source+static_cast<std::uint32_t>(i*10U));
    return;
  }
  PresentationVertexIdentity owner;
  for(const auto& model:scene.models)for(const auto palette:model.palettes) {
    if(!palette || matrix<palette || matrix-palette>=model.bone_count*64U ||
       (matrix-palette)%64U)continue;
    if(owner.owner && owner.owner!=&model) {
      std::fill(result.begin(),result.end(),owner);return;
    }
    owner.owner=&model;owner.joint=(matrix-palette)/64U;
  }
  std::fill(result.begin(),result.end(),owner);
  if(!owner.owner)return;
  std::bitset<32> ambiguous;
  for(const auto& model:scene.models) {
    if(model.actor!=owner.owner->actor || model.lifetime!=owner.owner->lifetime)continue;
    const auto first=source<model.vertices
        ? (std::uint64_t(model.vertices)-source+9U)/10U : 0U;
    if(first>=result.size())continue;
    const auto offset=std::uint64_t(source)+first*10U-model.vertices;
    // Keep the scalar contract's uint32 multiplication, including overflow.
    const auto bytes=model.vertex_count*10U;
    if(offset>=bytes || offset%10U)continue;
    const auto end=(std::min)(std::uint64_t(result.size()),first+(bytes-offset+9U)/10U);
    for(auto i=first;i<end;++i) {
      if(ambiguous[i])continue;
      auto& vertex=result[i];
      if(vertex.geometry) {vertex.geometry=nullptr;ambiguous.set(i);continue;}
      vertex.geometry=&model;
      vertex.vertex=static_cast<std::uint32_t>(offset/10U+i-first);
    }
  }
  if (!scene.cones.empty()) for (std::size_t i=0;i<result.size();++i)
    if (!ambiguous[i]) presentation_cone_vertex(scene,
        source+static_cast<std::uint32_t>(i*10U),result[i]);
}
inline const PresentationRigidIdentity* presentation_rigid_owner(
    const PresentationSceneIdentity& scene, std::uint32_t matrix) {
  const PresentationRigidIdentity* owner=nullptr;
  for (const auto& rigid:scene.rigids) if(rigid.matrix==matrix) {
    if(owner) return nullptr;
    owner=&rigid;
  }
  return owner;
}
inline const PresentationShockwaveIdentity* presentation_shockwave_batch(
    const PresentationSceneIdentity& scene, const PresentationRigidIdentity& owner,
    std::uint32_t source,std::uint32_t count) {
  if(!owner.lifetime || !owner.camera || !count)return nullptr;
  const PresentationShockwaveIdentity* found=nullptr;
  for(const auto& wave:scene.shockwaves) {
    if(wave.actor!=owner.actor || wave.lifetime!=owner.lifetime ||
       source<wave.vertices || source-wave.vertices>=200U ||
       (source-wave.vertices)%10U || count>(200U-(source-wave.vertices))/10U)continue;
    if(found)return nullptr;
    found=&wave;
  }
  return found;
}
inline const PresentationBeamIdentity* presentation_beam_vertex(
    const PresentationSceneIdentity& scene, const PresentationRigidIdentity& owner,
    std::uint32_t source) {
  const PresentationBeamIdentity* found = nullptr;
  for (const auto& beam:scene.beams) {
    if (beam.actor!=owner.actor || beam.lifetime!=owner.lifetime ||
        source<beam.vertices || source-beam.vertices>=80U ||
        (source-beam.vertices)%10U) continue;
    if (found) return nullptr;
    found=&beam;
  }
  return found;
}
// A bridge bends by changing local vertices, independently of its rigid pose.
// Resolve a whole DMA range against one current actor/model allocation. The
// buffer address locates samples; model instance + logical index own history.
inline const PresentationModelIdentity* presentation_bridge_vertices(
    const PresentationSceneIdentity& scene, const PresentationRigidIdentity& owner,
    std::uint32_t source, std::uint32_t count) {
  if (!owner.lifetime || !owner.camera || !count) return nullptr;
  const PresentationModelIdentity* found = nullptr;
  for (const auto& model:scene.models) {
    if (model.actor!=owner.actor || model.lifetime!=owner.lifetime ||
        source<model.vertices || (source-model.vertices)%10U) continue;
    const auto first=(source-model.vertices)/10U;
    if (first>=model.vertex_count || count>model.vertex_count-first) continue;
    if (found || !model.deforming_bridge) return nullptr;
    found=&model;
  }
  return found;
}
inline std::array<std::uint64_t, 4> presentation_rigid_key(
    const PresentationSceneIdentity &scene, std::uint32_t matrix,
    std::uint32_t source, std::uint32_t count) {
  const auto* owner = presentation_rigid_owner(scene, matrix);
  if (!owner || !owner->lifetime || !owner->camera || !count) return {};
  // Identical intact glass quads cannot anchor shape-only history: every
  // pane has the same local geometry. Bind only a proven live custom range,
  // retaining exact geometry/topology in the eventual rigid history key.
  const PresentationGlassIdentity* pane = nullptr;
  for (const auto& candidate : scene.glass) {
    if (candidate.actor != owner->actor ||
        candidate.lifetime != owner->lifetime || source < candidate.vertices ||
        (source - candidate.vertices) % 10U) continue;
    const auto first = (source - candidate.vertices) / 10U;
    if (first >= 4U || count > 4U - first) continue;
    if (pane) return {};
    pane = &candidate;
  }
  if (pane)
    return {owner->lifetime,
            (std::uint64_t(owner->actor) << 32U) | pane->control,
            (std::uint64_t(pane->header) << 32U) | 0x474C4153U,
            owner->camera};
  const PresentationLimbIdentity* limb = nullptr;
  for (const auto& candidate : scene.limbs) {
    if (candidate.actor != owner->actor || candidate.lifetime != owner->lifetime)
      continue;
    const bool contains = std::any_of(candidate.ranges.begin(),candidate.ranges.end(),
        [&](const auto& range) {
          return source >= range[0] && (source-range[0])%10U == 0U &&
              (source-range[0])/10U < range[1] &&
              count <= range[1]-(source-range[0])/10U;
        });
    if (!contains) continue;
    if (limb) return {};
    limb = &candidate;
  }
  if (limb)
    return {owner->lifetime,
            (std::uint64_t(owner->actor)<<32U) | limb->control,
            (std::uint64_t(limb->header)<<32U) | limb->vertices,
            owner->camera};
  const PresentationModelIdentity *geometry = nullptr;
  for (const auto &model : scene.models) {
    if (model.actor != owner->actor || model.lifetime != owner->lifetime ||
        source < model.vertices || (source - model.vertices) % 10U) continue;
    const auto first = (source - model.vertices) / 10U;
    if (first >= model.vertex_count || count > model.vertex_count - first) continue;
    if (geometry) return {};
    geometry = &model;
  }
  if (!geometry) return {};
  return {owner->lifetime, (std::uint64_t(owner->actor) << 32U) | geometry->instance,
          geometry->model, owner->camera};
}
class PresentationGuestView {
public:
  explicit PresentationGuestView(std::span<const std::uint8_t> data)
      : data_(data) {}
  static std::uint32_t physical(std::uint32_t address) {
    return address & 0x00FFFFFFU;
  }
  bool valid(std::uint32_t address, std::size_t size) const {
    const auto p = physical(address);
    const auto segment = address & 0xFF000000U;
    return (segment == 0U || segment == 0x80000000U ||
            segment == 0xA0000000U) &&
           p != 0U && p <= data_.size() && size <= data_.size() - p;
  }
  std::uint8_t u8(std::uint32_t address) const {
    const auto offset = physical(address) ^ 3U;
    return valid(address, 1) && offset < data_.size() ? data_[offset] : 0;
  }
  std::uint16_t u16(std::uint32_t address) const {
    return static_cast<std::uint16_t>(valid(address, 2)
               ? (std::uint16_t(u8(address)) << 8U) | u8(address + 1U)
               : 0);
  }
  std::uint32_t u32(std::uint32_t address) const {
    if (!valid(address, 4) || (address & 3U))
      return 0;
    std::uint32_t word = 0;
    std::memcpy(&word, data_.data() + physical(address), 4);
    return word;
  }

private:
  std::span<const std::uint8_t> data_;
};
// modMakeLimbModel emits two linear lists with absolute vertex DMA addresses.
// Reject malformed/unterminated lists, branches, matrix/segment/offset changes,
// and vertices outside the bounded baked stream. Material counted calls (07)
// do not contain geometry. Opaque/transparent lists may name the same ranges.
inline std::vector<std::array<std::uint32_t,2>> presentation_limb_ranges(
    const PresentationGuestView& ram, std::uint32_t vertices,
    const std::array<std::uint32_t,2>& lists) {
  std::vector<std::array<std::uint32_t,2>> ranges;
  if (!ram.valid(vertices,10U)) return {};
  const auto base = PresentationGuestView::physical(vertices);
  for (const auto list : lists) {
    if ((list&7U) || !ram.valid(list,8U)) return {};
    bool ended=false;
    for (std::uint32_t i=0;i<1024U;++i) {
      if (list>UINT32_MAX-i*8U || !ram.valid(list+i*8U,8U)) return {};
      const auto word=ram.u32(list+i*8U), address=ram.u32(list+i*8U+4U);
      const auto op=word>>24U;
      if (op==0xB8U) {ended=true;break;}
      if (op==0x06U || op==0x02U || op==0xBFU || op==0xBCU) return {};
      if (op!=0x04U) continue;
      const auto count=(word>>19U)&0x1FU;
      const auto source=PresentationGuestView::physical(address);
      if (!count || !ram.valid(address,count*10U) || source<base ||
          (source-base)%10U || source-base>81920U-count*10U) return {};
      ranges.push_back({source,count});
      if (ranges.size()>512U) return {};
    }
    if (!ended) return {};
  }
  std::sort(ranges.begin(),ranges.end());
  ranges.erase(std::unique(ranges.begin(),ranges.end()),ranges.end());
  return ranges;
}
class PresentationIdentityTracker {
public:
  void retire(std::uint32_t actor) {
    actors_.erase(actor);
    if(sky_actor_==actor){sky_actor_=0;sky_lifetime_={};}
    for(auto it=tracers_.begin();it!=tracers_.end();)
      if(it->second.identity.actor==actor)it=tracers_.erase(it);else ++it;
    for (auto it = rigids_.begin(); it != rigids_.end();)
      if (it->second.actor == actor) it = rigids_.erase(it); else ++it;
    for (auto it = sprites_.begin(); it != sprites_.end();)
      if (it->second.actor == actor)
        it = sprites_.erase(it);
      else
        ++it;
  }
  // US particle slots are 0x78 bytes. Allocation/free hooks distinguish
  // immediate slot reuse even when it occurs between two captured scenes.
  void particle_retire(std::uint32_t particle) {
    particle = PresentationGuestView::physical(particle);
    particles_.erase(particle);
    for (auto it = particle_sprites_.begin(); it != particle_sprites_.end();)
      if (it->second.particle == particle)
        it = particle_sprites_.erase(it);
      else
        ++it;
  }
  void particles_clear() {
    particles_.clear();
    particle_sprites_.clear();
  }
  void particle_allocate(std::span<const std::uint8_t> data,
                         std::uint32_t particle) {
    const PresentationGuestView ram(data);
    level(ram.u32(0x800FB114U));
    particle_retire(particle);
    if (!ram.valid(particle, 0x78U) || ram.u16(particle + 0x2CU) != 2U)
      return;
    if (particles_.size() >= 4096U)
      particles_clear();
    particles_[PresentationGuestView::physical(particle)] = ++serial_;
  }
  // Only the verified partDraw billboard caller uses this layout. Particle
  // asset ownership is independent of nearby pickup actors and their assets.
  void particle_sprite(std::span<const std::uint8_t> data,
                       std::uint32_t output_pointer, std::uint32_t particle,
                       std::uint32_t asset, std::uint64_t tick) {
    const PresentationGuestView ram(data);
    level(ram.u32(0x800FB114U));
    const auto address = ram.u32(output_pointer);
    const auto physical = PresentationGuestView::physical(particle);
    const auto live = particles_.find(physical);
    if (live == particles_.end() || !ram.valid(address, 10) ||
        !ram.valid(particle, 0x78U) || ram.u16(particle + 0x2CU) != 2U ||
        !asset || ram.u32(particle + 0x4CU) != asset)
      return;
    if (particle_sprites_.size() >= 4096U)
      particle_sprites_.clear();
    particle_sprites_[PresentationGuestView::physical(address)] =
        {physical, asset, live->second, tick};
  }
  // camDoSprite emits one world-space anchor at *a2 for the actor in a3.
  // Record addresses only; capture binds them to the actor's live lifetime.
  void sprite(std::span<const std::uint8_t> data, std::uint32_t output_pointer,
              std::uint32_t actor, std::uint32_t asset, std::uint64_t tick) {
    const PresentationGuestView ram(data);
    level(ram.u32(0x800FB114U));
    const auto address = ram.u32(output_pointer);
    if (!ram.valid(address, 10) || !ram.valid(actor, 0xA1U))
      return;
    if (sprites_.size() >= 4096U)
      sprites_.clear();
    sprites_[PresentationGuestView::physical(address)] = {
        actor, asset, ram.u32(actor + 0x40U), ram.u32(actor + 0x6CU), tick};
  }
  // US regionidDraw sorts 20 persistent sparkle slots by distance, then
  // calls camDoSprite with a temporary ObjectTransform on its stack. The
  // sorted slot, not draw order or that temporary address, owns the sprite.
  void region_sprite(std::span<const std::uint8_t> data,
      std::uint32_t output_pointer, std::uint32_t actor,
      std::uint32_t control, std::uint32_t index, std::uint32_t asset,
      std::uint64_t tick) {
    const PresentationGuestView ram(data);
    level(ram.u32(0x800FB114U));
    const auto address=ram.u32(output_pointer);
    const auto physical=PresentationGuestView::physical(address);
    sprites_.erase(physical); // Scratch reuse cannot retain a prior owner.
    if(index>=20U || !ram.valid(address,10U) || !ram.valid(actor,0xA1U) ||
       ram.u16(actor+0x48U)!=136U || ram.u32(actor+0x68U)!=control ||
       (control&3U) || !ram.valid(control,0x154U) || !ram.u8(control+0xFU))return;
    const auto header=ram.u32(actor+0x40U);
    const auto assets=ram.u32(header+0xACU);
    if(!ram.valid(header,0xB0U) || !ram.valid(assets,4U) ||
       !ram.valid(asset,8U) || ram.u32(assets)!=asset)return;
    if(sprites_.size()>=4096U)sprites_.clear();
    sprites_[physical]={actor,asset,header,ram.u32(actor+0x6CU),tick,index+1U,control};
  }
  // US camPushModelMtx (0x80041CA0), and module 122 ShirukenPushMtx
  // (0x07A00F38), consume ObjectTransform* in a2 and
  // write a combined model/camera matrix at the entry value of *a1. Observe
  // after it returns. capture() accepts only an exact live actor and unchanged
  // emitted matrix bytes, so unrelated transforms/buffer reuse cannot bind.
  void rigid(std::span<const std::uint8_t> data, std::uint32_t matrix,
             std::uint32_t actor, std::uint64_t tick) {
    const PresentationGuestView ram(data);
    level(ram.u32(0x800FB114U));
    const auto physical = PresentationGuestView::physical(matrix);
    rigids_.erase(physical);
    const auto number = ram.u32(0x800FA634U), mode = ram.u32(0x800FA630U);
    if (!ram.valid(matrix, 64U) || (matrix & 3U) ||
        !ram.valid(actor, 0xA1U) || number > 3U) return;
    if (rigids_.size() >= 4096U) rigids_.clear();
    Rigid binding{actor, ram.u32(actor + 0x40U), ram.u32(actor + 0x6CU),
                  tick, (std::uint64_t(mode) << 32U) | (number + 1U), {}};
    for (unsigned i = 0; i < 16; ++i) binding.words[i] = ram.u32(matrix + i*4U);
    // US camPushModelMtx constructs model at 0x800FAAB0, concatenates it
    // with view/projection (0x800FAF78/0x800FAA70), then emits fixed MVP.
    // Capture before another object reuses these scratch globals. The matrix
    // byte/lifetime checks below and decoder product check bind the operands.
    for (unsigned i=0;i<16;++i) {
      binding.pose.world[i]=std::bit_cast<float>(ram.u32(0x800FAAB0U+i*4U));
      binding.pose.view[i]=std::bit_cast<float>(ram.u32(0x800FAF78U+i*4U));
      binding.pose.projection[i]=std::bit_cast<float>(ram.u32(0x800FAA70U+i*4U));
    }
    rigids_[physical] = binding;
  }
  // Observe only the verified objPrintCustomObject projectile callers,
  // after exactly four native vertices and their projection DMA are emitted.
  void tracer(std::span<const std::uint8_t> data, std::uint32_t actor,
              std::uint32_t vertices, std::uint32_t matrix, std::uint64_t tick) {
    const PresentationGuestView ram(data);
    level(ram.u32(0x800FB114U));
    vertices=PresentationGuestView::physical(vertices);
    matrix=PresentationGuestView::physical(matrix);
    tracers_.erase(vertices);
    const auto number=ram.u32(0x800FA634U), mode=ram.u32(0x800FA630U);
    if(!ram.valid(actor,0xA1U) || !ram.valid(vertices,40U) ||
       !ram.valid(matrix,64U) || (matrix&3U) || (vertices&1U) || number>3U)
      return;
    const auto control=ram.u32(actor+0x68U);
    if(!control || !ram.valid(control,0x20U))return;
    if(tracers_.size()>=1024U)tracers_.clear();
    Tracer record{};
    record.tick=tick;record.models=ram.u32(actor+0x6CU);
    record.identity.actor=actor;record.identity.control=control;
    record.identity.header=ram.u32(actor+0x40U);
    record.identity.vertices=vertices;record.identity.matrix=matrix;
    record.identity.camera=(std::uint64_t(mode)<<32U)|(number+1U);
    // Native corners are decoded back into world space before presentation.
    // The remaining camera pose has an identity world transform.
    record.identity.pose.world={1,0,0,0,0,1,0,0,0,0,1,0,0,0,0,1};
    for(unsigned i=0;i<40U;++i)record.vertices[i]=ram.u8(vertices+i);
    for(unsigned i=0;i<16U;++i) {
      record.matrix[i]=ram.u32(matrix+i*4U);
      record.identity.pose.view[i]=std::bit_cast<float>(ram.u32(0x800FAF78U+i*4U));
      record.identity.pose.projection[i]=std::bit_cast<float>(ram.u32(0x800FAA70U+i*4U));
    }
    tracers_[vertices]=record;
  }
  // camSetProjMtx writes one camera MVP at *a1 and emits its DMA command.
  // Observe before the guest call; bind the record to the eventual task copy.
  void camera(std::span<const std::uint8_t> data, std::uint32_t output_pointer,
              std::uint64_t tick) {
    const PresentationGuestView ram(data);
    level(ram.u32(0x800FB114U));
    const auto number = ram.u32(0x800FA634U), mode = ram.u32(0x800FA630U);
    const auto address = ram.u32(output_pointer);
    if (number > 3U || !ram.valid(address, 64))
      return;
    if (cameras_.size() >= 256U)
      cameras_.clear();
    cameras_[PresentationGuestView::physical(address)] = {
        (std::uint64_t(mode) << 32U) | (number + 1U), tick};
  }
  // Capture camera operands after camSetProjMtx emits the fixed matrix, before
  // another object reuses the guest scratch matrices. Bind to exact bytes.
  void camera_completed(std::span<const std::uint8_t> data,
                        std::uint32_t matrix, std::uint64_t tick) {
    const PresentationGuestView ram(data);
    const auto found=cameras_.find(PresentationGuestView::physical(matrix));
    if (found==cameras_.end() || !ram.valid(matrix,64U) || (matrix&3U)) return;
    auto& camera=found->second;
    camera.tick=tick;
    camera.pose.world={1,0,0,0,0,1,0,0,0,0,1,0,0,0,0,1};
    for (unsigned i=0;i<16;++i) {
      camera.words[i]=ram.u32(matrix+i*4U);
      camera.pose.view[i]=std::bit_cast<float>(ram.u32(0x800FAF78U+i*4U));
      camera.pose.projection[i]=std::bit_cast<float>(ram.u32(0x800FAA70U+i*4U));
    }
    camera.pose_valid=true;
  }
  PresentationSceneIdentity capture(std::span<const std::uint8_t> data,
                                    std::uint64_t tick) {
    return capture(data,tick,[](std::uint32_t address) { return address; });
  }
  template<class ResolveGraphicsAddress>
  PresentationSceneIdentity capture(std::span<const std::uint8_t> data,
                                    std::uint64_t tick,
                                    ResolveGraphicsAddress&& resolve_graphics_address) {
    const PresentationGuestView ram(data);
    level(ram.u32(0x800FB114U));
    PresentationSceneIdentity result;
    for (auto it = cameras_.begin(); it != cameras_.end();) {
      if (tick < it->second.tick || tick - it->second.tick > 6U)
        it = cameras_.erase(it);
      else {
        bool unchanged=it->second.pose_valid;
        for(unsigned i=0;i<16 && unchanged;++i)
          unchanged=ram.u32(it->first+i*4U)==it->second.words[i];
        result.cameras.push_back({it->first,it->second.identity,camera_generation_,
                                  it->second.pose,unchanged});
        ++it;
      }
    }
    const auto list = ram.u32(0x800F2CA4U), count = ram.u32(0x800F2CA8U);
    if (count > 256U || !ram.valid(list, count * 4U)) {
      actors_.clear();
      return result;
    }
    std::map<std::uint32_t, Lifetime> live;
    for (std::uint32_t i = 0; i < count; ++i) {
      const auto actor = ram.u32(list + i * 4U);
      if (!ram.valid(actor, 0xA1U) || ram.u8(actor + 0xA0U) != 0U ||
          live.contains(actor))
        continue;
      const auto header = ram.u32(actor + 0x40U),
                 models = ram.u32(actor + 0x6CU);
      const auto model_count = ram.u8(header + 0x1FU);
      if (!ram.valid(header, 0x20U) || model_count > 16U ||
          (model_count != 0U && !ram.valid(models, model_count * 4U)))
        continue;
      auto old = actors_.find(actor);
      const auto serial = old != actors_.end() &&
                                  old->second.header == header &&
                                  old->second.models == models
                              ? old->second.serial
                              : ++serial_;
      live[actor] = {serial, header, models};
      // Verified US objPrintCustomObject case 68 calls beamDraw. Its control
      // allocation contains 2 * 80 vertex bytes followed by state at +0xCC.
      // A malformed/disabled beam gets no procedural interpolation identity.
      const auto control=ram.u32(actor+0x68U);
      if (ram.u16(actor+0x48U)==64U && model_count==0U &&
          !(control&3U) && ram.valid(control,0x20U)) {
        const auto vertices=ram.u32(control+4U);
        auto ranges=presentation_limb_ranges(ram,vertices,
            {ram.u32(control+0x0CU),ram.u32(control+0x10U)});
        if (!ranges.empty())
          result.limbs.push_back({serial,actor,control,header,
              PresentationGuestView::physical(vertices),std::move(ranges)});
      }
      if(ram.u16(actor+0x48U)==40U && ram.valid(control,0x1DBU) &&
         !(control&3U) && ram.u8(control+0x1DAU)<=1U) {
        const auto texture=ram.u32(control+0x190U);
        if(ram.valid(texture,8U))
          result.shockwaves.push_back({serial,actor,control,header,
              PresentationGuestView::physical(control)+ram.u8(control+0x1DAU)*200U,texture});
      }
      if (ram.u16(actor+0x48U)==68U && ram.valid(control,0xD0U) &&
          (control&3U)==0U && ram.u8(control+0xCCU)!=0U &&
          ram.u8(control+0xCDU)<=1U) {
        const auto flags=ram.u16(control+0xCEU);
        if (flags && !(flags&~7U))
          result.beams.push_back({serial,actor,control,header,
              PresentationGuestView::physical(control)+ram.u8(control+0xCDU)*80U,flags});
      }
      // The US transparent-object dispatcher binds behavior 78 to glassDraw
      // (0x06500DCC). Positive +0x88 selects the intact shared quad at
      // control+0x0C; after shattering it uses a different 120-vertex stream.
      // Restrict this identity to intact glass. Do not interpolate between
      // the pane and shards or across a control/lifetime replacement.
      if (ram.u16(actor + 0x48U) == 78U && ram.valid(control, 0x60U) &&
          (control & 3U) == 0U &&
          std::bit_cast<std::int32_t>(ram.u32(actor + 0x88U)) > 0 &&
          ram.u32(actor + 0x8CU) <= 1U) {
        // Intact quad vertices are a linked overlay constant. Resolve through
        // the renderer's exact overlay materialization map before validation;
        // masking the guest pointer does not locate the copied GPU vertices.
        const auto resolve_block=[&](std::uint32_t address,std::uint32_t bytes) {
          if(address>UINT32_MAX-(bytes-1U))return std::uint32_t{0};
          const auto first=resolve_graphics_address(address);
          const auto last=resolve_graphics_address(address+bytes-1U);
          return first<=UINT32_MAX-(bytes-1U) && last==first+bytes-1U ?
              first : std::uint32_t{0};
        };
        const auto vertices = resolve_block(ram.u32(control + 0x0CU),40U);
        const auto triangles = resolve_block(
            ram.u32(control + 4U + ram.u32(actor + 0x8CU) * 4U),32U);
        if (ram.valid(vertices, 40U) && ram.valid(triangles, 32U)) {
          const auto texture=ram.u32(control);
          const std::array<float,2> period=ram.valid(texture,2U) ?
            std::array<float,2>{float(ram.u8(texture)),float(ram.u8(texture+1U))} :
            std::array<float,2>{};
          result.glass.push_back({serial, actor, control, header,
                                 PresentationGuestView::physical(vertices),period});
        }
      }
      for (std::uint32_t j = 0; j < model_count; ++j) {
        const auto instance = ram.u32(models + j * 4U),
                   model = ram.u32(instance);
        if (!ram.valid(instance, 8U) || !ram.valid(model, 0x80U))
          continue;
        const auto bones = ram.u8(model + 0x4FU);
        const auto vertices = ram.u16(model + 0x12U);
        const auto vertex_base = ram.u32(instance + 4U);
        const auto p0 = ram.u32(instance + 0x10U),
                   p1 = ram.u32(instance + 0x14U);
        if (bones > 127U || vertices == 0U || vertices > 8192U ||
            !ram.valid(vertex_base, vertices * 10U))
          continue;
        // Compact LOD instances own vertices but share another instance's
        // palette. Words at +0x10/+0x14 can already be vertex data there.
        const auto source = PresentationGuestView::physical(vertex_base);
        const auto fields = PresentationGuestView::physical(instance) + 0x10U;
        const bool inline_vertices =
            source < fields + 8U && source + vertices * 10U > fields;
        const bool palette = !inline_vertices && ram.u8(model + 0x4EU) != 0U &&
                             bones != 0U && ram.valid(p0, bones * 64U) &&
                             ram.valid(p1, bones * 64U);
        result.models.push_back(
            {serial,
             actor,
             instance,
             model,
             {palette ? PresentationGuestView::physical(p0) : 0U,
              palette ? PresentationGuestView::physical(p1) : 0U},
             PresentationGuestView::physical(vertex_base),
             vertices,
             bones,
             ram.u16(actor + 0x48U) == 55U,ram.u16(actor + 0x48U) == 95U});
        // Module 73 animshipDrawThrusters uses the selected instance's bone
        // palette for up to sixteen 12-byte engine entries. fxAllocateCone
        // owns a header, triangle stream and two contiguous vertex buffers;
        // fxDrawCone selects +8/+12 with byte +0x16. Recognize that exact
        // allocation layout, never arbitrary vertices near a model.
        if (palette && ram.u16(actor+0x48U)==95U &&
            j==ram.u8(actor+0x3AU) && !(control&3U) && ram.valid(control,192U)) {
          for (std::uint32_t engine=0;engine<16U;++engine) {
            const auto entry=control+engine*12U, cone=ram.u32(entry);
            if (!cone) break;
            const auto joint=ram.u8(entry+11U);
            if (!ram.u8(entry+4U) || joint>=bones || (cone&3U) ||
                !ram.valid(cone,0x28U)) continue;
            const auto sides=ram.u8(cone+0x15U);
            const auto cone_vertices=sides ? sides+1U : 34U;
            const auto triangle_bytes=sides ? sides*16U : 0x280U;
            const auto bytes=0x28U+triangle_bytes+cone_vertices*20U;
            if (sides>30U || ram.u8(cone+0x14U)!=sides+1U ||
                ram.u8(cone+0x16U)>1U || !ram.valid(cone,bytes)) continue;
            const auto first=cone+0x28U+triangle_bytes;
            if (ram.u32(cone+0x10U)!=cone+0x28U ||
                ram.u32(cone+8U)!=first || ram.u32(cone+12U)!=first+cone_vertices*10U)
              continue;
            result.cones.push_back({serial,actor,instance,control,cone,
                {PresentationGuestView::physical(first),
                 PresentationGuestView::physical(first+cone_vertices*10U)},cone_vertices,joint});
          }
        }
      }
    }
    actors_ = std::move(live);
    for(auto it=tracers_.begin();it!=tracers_.end();) {
      const auto& record=it->second;const auto& id=record.identity;
      const auto actor=actors_.find(id.actor);
      bool bytes_match=true;
      for(unsigned i=0;i<40U;++i)bytes_match=bytes_match && ram.u8(id.vertices+i)==record.vertices[i];
      for(unsigned i=0;i<16U;++i)bytes_match=bytes_match && ram.u32(id.matrix+i*4U)==record.matrix[i];
      if(tick<record.tick || tick-record.tick>6U || !bytes_match ||
         actor==actors_.end() || actor->second.header!=id.header ||
         actor->second.models!=record.models || ram.u32(id.actor+0x68U)!=id.control)
        it=tracers_.erase(it);
      else {
        auto retained=id;retained.lifetime=actor->second.serial;
        result.tracers.push_back(retained);++it;
      }
    }
    const auto sky=ram.u32(0x800F2F88U);
    const auto sky_header=ram.u32(sky+0x40U),sky_models=ram.u32(sky+0x6CU);
    const auto sky_count=ram.u8(sky_header+0x1FU);
    const bool sky_live=ram.valid(sky,0xA4U) && ram.valid(sky_header,0x20U) &&
        sky_count>0U && sky_count<=16U && ram.valid(sky_models,sky_count*4U);
    if(!sky_live){sky_actor_=0;sky_lifetime_={};}
    else if(sky_actor_!=sky || sky_lifetime_.header!=sky_header || sky_lifetime_.models!=sky_models) {
      sky_actor_=sky;sky_lifetime_={++serial_,sky_header,sky_models};
    }
    for (auto it = rigids_.begin(); it != rigids_.end();) {
      const auto &rigid = it->second;
      const auto actor = actors_.find(rigid.actor);
      bool bytes_match = true;
      for (unsigned i = 0; i < 16; ++i)
        bytes_match = bytes_match && ram.u32(it->first + i*4U) == rigid.words[i];
      // The sky is drawn before ordinary actors and follows a separate
      // allocation. Bind its exact emitted transform, not whichever triangle
      // happens to remain in front of the camera this frame. Folding its model
      // transform into the view lets the standard owned-camera continuity/cut
      // checks apply without weakening arbitrary near-plane geometry guards.
      if(sky_live && rigid.actor==sky_actor_ && rigid.header==sky_lifetime_.header &&
         rigid.models==sky_lifetime_.models && tick>=rigid.tick && tick-rigid.tick<=6U && bytes_match) {
        auto pose=rigid.pose;
        pose.world={1,0,0,0,0,1,0,0,0,0,1,0,0,0,0,1};
        for(unsigned row=0;row<4;++row)for(unsigned col=0;col<4;++col) {
          const auto& a=rigid.pose.world;const auto& b=rigid.pose.view;
          const volatile float t0=a[row*4]*b[col],t1=a[row*4+1]*b[4+col],
              t2=a[row*4+2]*b[8+col],t3=a[row*4+3]*b[12+col];
          const volatile float left=t1+t2,right=t0+t3;pose.view[row*4+col]=left+right;
        }
        result.cameras.push_back({it->first,0x534B590000000000ULL|rigid.camera,
                                  sky_lifetime_.serial,rigid.pose,true,pose});
        ++it;continue;
      }
      if (tick < rigid.tick || tick - rigid.tick > 6U || !bytes_match ||
          actor == actors_.end() || actor->second.header != rigid.header ||
          actor->second.models != rigid.models) it = rigids_.erase(it);
      else {
        result.rigids.push_back({it->first, rigid.actor, actor->second.serial, rigid.camera, rigid.pose});
        ++it;
      }
    }
    for (auto it = sprites_.begin(); it != sprites_.end();) {
      const auto &sprite = it->second;
      const auto actor = actors_.find(sprite.actor);
      if (tick < sprite.tick || tick - sprite.tick > 6U ||
          actor == actors_.end() || actor->second.header != sprite.header ||
          actor->second.models != sprite.models ||
          (sprite.control && (ram.u32(sprite.actor+0x68U)!=sprite.control ||
           ram.u16(sprite.actor+0x48U)!=136U || !ram.u8(sprite.control+0xFU))))
        it = sprites_.erase(it);
      else {
        result.sprites.push_back(
            {it->first, sprite.actor, sprite.asset, actor->second.serial, sprite.sub_id, sprite.control});
        ++it;
      }
    }
    for (auto it = particle_sprites_.begin(); it != particle_sprites_.end();) {
      const auto &sprite = it->second;
      const auto particle_live = particles_.find(sprite.particle);
      if (tick < sprite.tick || tick - sprite.tick > 6U ||
          particle_live == particles_.end() || particle_live->second != sprite.serial ||
          ram.u16(sprite.particle + 0x2CU) != 2U ||
          ram.u32(sprite.particle + 0x4CU) != sprite.asset)
        it = particle_sprites_.erase(it);
      else {
        result.sprites.push_back({it->first, sprite.particle | 0x80000000U,
                                  sprite.asset, sprite.serial});
        ++it;
      }
    }
    return result;
  }

private:
  struct Lifetime {
    std::uint64_t serial;
    std::uint32_t header, models;
  };
  struct Camera {
    std::uint64_t identity, tick;
    std::array<std::uint32_t,16> words{};
    RigidPresentationPose pose{};
    bool pose_valid=false;
  };
  struct Sprite {
    std::uint32_t actor, asset, header, models;
    std::uint64_t tick;
    std::uint32_t sub_id=0, control=0;
  };
  struct Rigid {
    std::uint32_t actor, header, models;
    std::uint64_t tick, camera;
    std::array<std::uint32_t, 16> words;
    RigidPresentationPose pose{};
  };
  struct Tracer {
    PresentationTracerIdentity identity{};
    std::uint32_t models=0;
    std::uint64_t tick=0;
    std::array<std::uint8_t,40> vertices{};
    std::array<std::uint32_t,16> matrix{};
  };
  std::map<std::uint32_t,Tracer> tracers_;
  std::map<std::uint32_t, Rigid> rigids_;
  struct ParticleSprite {
    std::uint32_t particle, asset;
    std::uint64_t serial, tick;
  };
  std::map<std::uint32_t, std::uint64_t> particles_;
  std::map<std::uint32_t, ParticleSprite> particle_sprites_;
  std::map<std::uint32_t, Sprite> sprites_;
  std::map<std::uint32_t, Lifetime> actors_;
  std::uint32_t sky_actor_=0;
  Lifetime sky_lifetime_{};
  std::map<std::uint32_t, Camera> cameras_;
  std::uint64_t serial_ = 0;
  std::uint32_t level_ = UINT32_MAX;
  std::uint64_t camera_generation_=0;
  void level(std::uint32_t current) {
    if (current != level_) {
      actors_.clear();
      sky_actor_=0;sky_lifetime_={};
      rigids_.clear();
      tracers_.clear();
      cameras_.clear();
      sprites_.clear();
      particles_clear();
      level_ = current;
      camera_generation_=++serial_;
    }
  }
};
} // namespace jfg
