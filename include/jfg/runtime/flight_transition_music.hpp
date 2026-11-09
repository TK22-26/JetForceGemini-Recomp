#pragma once
#include <array>
#include <cstdint>
#include <optional>

namespace jfg {
struct FlightMusicScene {
  std::uint32_t level,group,asset,track,metadata;
};
// Remaining Vela departure candidates; their original-region expectations still
// need individual review. Walkway is deliberately excluded: NTSC hardware omits
// its departure music. Metadata is the exact level summary (tune excluded).
inline constexpr std::array<FlightMusicScene,2> flight_music_scenes{{
  {88,0,91,21,0x01060001U},
  {20,0,20,23,0x010A0001U}
}};
// Correct only the loaded header copy, before levelTunePlay compares it with
// the playing tune. The original engine then owns start/keep, fades and volume.
// ROM bytes, explicit script commands and all other scene variants stay intact.
template<class Memory>
bool apply_flight_transition_music_header(Memory& ram) {
  // These two optional corrections have only US evidence. PAL/JP retain their
  // original music; regional candidate support does not broaden correction policy.
  if(ram.context().descriptor().revision!="jfg-us-r0")return false;
  if(!ram.instruction_matches("guard.flight.tune_entry") ||
     !ram.instruction_matches("guard.flight.tune_field") || !ram.global_valid("globals.currentLevel") || !ram.global_valid("globals.levelHeader") ||
     !ram.global_valid("globals.cutsceneGroup"))return false;
  const auto header=ram.global_u32("globals.levelHeader");
  if(!ram.valid(header,0xEAU) || ram.u8(header+ram.member_offset("layout.levelHeader.kind"))!=1U)return false;
  for(const auto& scene:flight_music_scenes) {
    if(ram.global_u32("globals.currentLevel")==scene.level && ram.global_u32("globals.cutsceneGroup")==scene.group &&
       ram.u16(header+ram.member_offset("layout.levelHeader.sceneAsset"))==scene.asset && ram.u8(header+ram.member_offset("layout.levelHeader.music"))==scene.track) {
      ram.put8(header+ram.member_offset("layout.levelHeader.music"),7U);
      return true;
    }
  }
  return false;
}
// The transition checks levelGetTune *before* loading the next header. Give
// that comparison the same answer, so an existing flight theme is not stopped
// and restarted between shots. Restrict this to the pinned transition caller,
// pending destination/group and original US level summary; do not edit it.
template<class Memory>
std::optional<std::uint32_t> flight_transition_next_music(
    const Memory& ram,std::uint32_t level,std::uint32_t return_address) {
  if(ram.context().descriptor().revision!="jfg-us-r0")return {};
  if(return_address!=ram.instruction_address("guard.flight.transition_call")+8U || !ram.instruction_matches("guard.flight.transition_call") || !ram.instruction_matches("guard.flight.summary_field") || !ram.instruction_matches("guard.flight.pending_group") || !ram.global_valid("globals.pendingLevel") || !ram.global_valid("globals.pendingCutsceneGroup") ||
     ram.global_u16("globals.pendingLevel")!=level || !ram.global_valid("globals.levelCount") || !ram.global_valid("globals.levelSummaryTable") ||
     ram.global_u32("globals.levelCount")!=412U)return {};
  const auto table=ram.global_u32("globals.levelSummaryTable");
  if(!ram.valid(table,412U*5U))return {};
  for(const auto& scene:flight_music_scenes) {
    if(level==scene.level && ram.global_u16("globals.pendingCutsceneGroup")==scene.group &&
       ram.u32(table+level*5U)==scene.metadata && ram.u8(table+level*5U+4U)==scene.track)
      return 7U;
  }
  return {};
}
} // namespace jfg
