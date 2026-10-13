#pragma once
#include <array>
#include <cstdint>
#include <cstring>
#include <map>
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
};
struct PresentationCameraIdentity {
  std::uint32_t matrix = 0;
  std::uint64_t identity = 0;
};
struct PresentationSpriteIdentity {
  std::uint32_t anchor = 0, actor = 0, sprite = 0;
  std::uint64_t lifetime = 0;
};
struct PresentationSceneIdentity {
  std::vector<PresentationModelIdentity> models;
  std::vector<PresentationCameraIdentity> cameras;
  std::vector<PresentationSpriteIdentity> sprites;
};
// A reduced-detail mesh can use the main model's bone palette. Resolve
// palette ownership first, then the vertex stream within that same actor.
struct PresentationVertexIdentity {
  const PresentationModelIdentity *owner = nullptr, *geometry = nullptr;
  std::uint32_t joint = 0, vertex = 0;
};
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
  return result;
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
    return valid(address, 2)
               ? (std::uint16_t(u8(address)) << 8U) | u8(address + 1U)
               : 0;
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
class PresentationIdentityTracker {
public:
  void retire(std::uint32_t actor) {
    actors_.erase(actor);
    for (auto it = sprites_.begin(); it != sprites_.end();)
      if (it->second.actor == actor)
        it = sprites_.erase(it);
      else
        ++it;
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
  PresentationSceneIdentity capture(std::span<const std::uint8_t> data,
                                    std::uint64_t tick) {
    const PresentationGuestView ram(data);
    level(ram.u32(0x800FB114U));
    PresentationSceneIdentity result;
    for (auto it = cameras_.begin(); it != cameras_.end();) {
      if (tick < it->second.tick || tick - it->second.tick > 6U)
        it = cameras_.erase(it);
      else {
        result.cameras.push_back({it->first, it->second.identity});
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
             bones});
      }
    }
    actors_ = std::move(live);
    for (auto it = sprites_.begin(); it != sprites_.end();) {
      const auto &sprite = it->second;
      const auto actor = actors_.find(sprite.actor);
      if (tick < sprite.tick || tick - sprite.tick > 6U ||
          actor == actors_.end() || actor->second.header != sprite.header ||
          actor->second.models != sprite.models)
        it = sprites_.erase(it);
      else {
        result.sprites.push_back(
            {it->first, sprite.actor, sprite.asset, actor->second.serial});
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
  };
  struct Sprite {
    std::uint32_t actor, asset, header, models;
    std::uint64_t tick;
  };
  std::map<std::uint32_t, Sprite> sprites_;
  std::map<std::uint32_t, Lifetime> actors_;
  std::map<std::uint32_t, Camera> cameras_;
  std::uint64_t serial_ = 0;
  std::uint32_t level_ = UINT32_MAX;
  void level(std::uint32_t current) {
    if (current != level_) {
      actors_.clear();
      cameras_.clear();
      sprites_.clear();
      level_ = current;
    }
  }
};
} // namespace jfg
