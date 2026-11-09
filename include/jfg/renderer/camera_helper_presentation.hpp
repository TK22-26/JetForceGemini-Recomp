#pragma once
#include "jfg/renderer/presentation_identity.hpp"

namespace jfg {
// AnimCamera (US object 30, behavior 47) is a cinematic view controller with
// an editor camera mesh. animseqStartPath clears its hidden flag just as it
// does for ordinary actors; switching shots does not necessarily stop it.
// Keep the controller and all script state intact, but make its helper mesh
// non-rendering at objPrintObject. Restore immediately after that call.
// This intentionally repairs an original-game artifact, not an RSP decoder
// discrepancy. Behavior 47 is shared with visible animated props: neither
// that behavior alone nor the actor's position/color identifies a camera.
class CameraHelperPresentationScope {
public:
  CameraHelperPresentationScope(const RendererGameLayout& layout,std::span<std::uint8_t> bytes,
                                std::uint32_t target, std::uint32_t actor) {
    if (target != layout.draw_object) return;
    const PresentationGuestView ram(bytes);
    // Check the revision-bound draw gate before using its a3 actor/hidden-bit ABI.
    if (!layout.camera_entry.matches(ram) || !layout.camera_flags.matches(ram) ||
        !layout.camera_mask.matches(ram) ||
        (actor & 3U) || !ram.valid(actor, 0xA4U) ||
        ram.u32(actor + layout.actor_type) != 0x002F001EU ||
        (ram.u16(actor + layout.actor_flags) & 0x0C00U)) return;
    const auto header = ram.u32(actor + layout.actor_header);
    constexpr char name[] = "AnimCamera";
    if ((header & 3U) || !ram.valid(header, 4U + sizeof(name))) return;
    for (unsigned i = 0; i < sizeof(name); ++i)
      if (ram.u8(header + 4U + i) != static_cast<std::uint8_t>(name[i])) return;
    hidden_ = bytes.data() + (PresentationGuestView::physical(actor + layout.actor_flags) ^ 3U);
    original_ = *hidden_;
    *hidden_ |= 4U; // Big-endian flags halfword: 0x0400.
  }
  ~CameraHelperPresentationScope() { restore(); }
  CameraHelperPresentationScope(const CameraHelperPresentationScope&) = delete;
  CameraHelperPresentationScope& operator=(const CameraHelperPresentationScope&) = delete;
  bool applied() const noexcept { return hidden_ != nullptr; }
  void restore() noexcept {
    if (hidden_) { *hidden_ = original_; hidden_ = nullptr; }
  }
private:
  std::uint8_t* hidden_ = nullptr;
  std::uint8_t original_ = 0;
};
} // namespace jfg
