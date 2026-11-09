#pragma once
#include "jfg/game/descriptor.hpp"

namespace jfg::game {
// IDs belong to the original runlink module table. Generated section ordinals
// are private compiler output and can change with entry layout or empty slots.
enum class OriginalModule : std::uint32_t {
  collision=3, shadows=4, starfield=5, instruments=6, hint_text=7,
  vela_control=15, juno_control=16, lupus_control=17,
  pause_root=18, pause_manager=19, floyd_missions=22, day_night=23,
  vela_magic=29, racing=31, mr_hints=32, settings=37, mantis_lighting=39,
  save_keyboard=42, credits=59, title=63, region_id=117, reflections=137
};

[[nodiscard]] constexpr std::optional<std::uint32_t> original_module_section(
    const Descriptor& descriptor, OriginalModule module) noexcept {
  std::optional<std::uint32_t> result;
  const auto slot=static_cast<std::uint32_t>(module);
  if(slot==0)return {};
  for(std::uint32_t index=0;index<descriptor.sections.size();++index) {
    const auto& section=descriptor.sections[index];
    if(section.kind==SectionKind::overlay && section.overlay_slot==slot) {
      if(result)return {}; // An ambiguous owner must never select one image.
      result=index;
    }
  }
  return result;
}
} // namespace jfg::game
