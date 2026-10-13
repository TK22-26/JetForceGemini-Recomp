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
struct PresentationSceneIdentity {
  std::vector<PresentationModelIdentity> models;
  std::vector<PresentationCameraIdentity> cameras;
};
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
  void retire(std::uint32_t actor) { actors_.erase(actor); }
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
      if (!ram.valid(header, 0x20U) || model_count == 0U || model_count > 16U ||
          !ram.valid(models, model_count * 4U))
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
        if (!ram.valid(instance, 0x20U) || !ram.valid(model, 0x80U) ||
            ram.u8(model + 0x4EU) == 0U)
          continue;
        const auto bones = ram.u8(model + 0x4FU);
        const auto vertices = ram.u16(model + 0x12U);
        const auto vertex_base = ram.u32(instance + 4U);
        const auto p0 = ram.u32(instance + 0x10U),
                   p1 = ram.u32(instance + 0x14U);
        if (bones == 0U || bones > 127U || vertices == 0U || vertices > 8192U ||
            !ram.valid(p0, bones * 64U) || !ram.valid(p1, bones * 64U) ||
            !ram.valid(vertex_base, vertices * 10U))
          continue;
        result.models.push_back({serial,
                                 actor,
                                 instance,
                                 model,
                                 {PresentationGuestView::physical(p0),
                                  PresentationGuestView::physical(p1)},
                                 PresentationGuestView::physical(vertex_base),
                                 vertices,
                                 bones});
      }
    }
    actors_ = std::move(live);
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
  std::map<std::uint32_t, Lifetime> actors_;
  std::map<std::uint32_t, Camera> cameras_;
  std::uint64_t serial_ = 0;
  std::uint32_t level_ = UINT32_MAX;
  void level(std::uint32_t current) {
    if (current != level_) {
      actors_.clear();
      cameras_.clear();
      level_ = current;
    }
  }
};
} // namespace jfg
