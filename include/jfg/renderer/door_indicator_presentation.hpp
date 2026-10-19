#pragma once
#include "jfg/renderer/presentation_identity.hpp"

namespace jfg {
// Intentional readability improvement for US doorSwitchControl (behavior 67).
// The owner reproduced the distance blackout in EmuHawk (RENDER-014).
// This preserves the accepted clear marker, not exact native fading or a
// general renderer repair. Native fading selects a different list at alpha254.
// Keep a fully unlocked indicator opaque only while its native draw emits
// commands. Restore the simulation byte immediately afterward; never revive
// a hidden indicator or change lock state, visibility tests, or actor lifetime.
class DoorIndicatorPresentationScope {
public:
  DoorIndicatorPresentationScope(std::span<std::uint8_t> bytes,
                                 std::uint32_t actor) {
    const PresentationGuestView ram(bytes);
    if ((actor & 3U) || !ram.valid(actor, 0xA4U) ||
        ram.u16(actor + 0x48U) != 67U || ram.u8(actor + 0x93U) != 0U)
      return;
    const auto control = ram.u32(actor + 0x68U);
    if (!ram.valid(control, 9U) || ram.u8(control + 8U) != 1U ||
        ram.u32(actor + 0x28U) != 0x3F800000U)
      return;
    const auto alpha = ram.u8(actor + 0x39U);
    if (alpha == 0U || alpha == 255U)
      return;
    const auto offset = PresentationGuestView::physical(actor + 0x39U) ^ 3U;
    if (offset >= bytes.size())
      return;
    opacity_ = bytes.data() + offset;
    original_ = alpha;
    *opacity_ = 255U;
  }
  ~DoorIndicatorPresentationScope() { restore(); }
  DoorIndicatorPresentationScope(const DoorIndicatorPresentationScope&) = delete;
  DoorIndicatorPresentationScope& operator=(const DoorIndicatorPresentationScope&) = delete;
  bool applied() const { return opacity_ != nullptr; }
  std::uint8_t original() const { return original_; }
  void restore() noexcept {
    if (opacity_) { *opacity_ = original_; opacity_ = nullptr; }
  }
private:
  std::uint8_t* opacity_ = nullptr;
  std::uint8_t original_ = 0;
};
} // namespace jfg
