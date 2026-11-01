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
  if(!ram.valid(0x8004455CU,0x18U) || ram.u32(0x8004455CU)!=0x27BDFFE8U ||
     ram.u32(0x80044570U)!=0x91CF0072U || !ram.valid(0x800FB114U,8U) ||
     !ram.valid(0x800A74C0U,4U))return false;
  const auto header=ram.u32(0x800FB118U);
  if(!ram.valid(header,0xEAU) || ram.u8(header+0x6CU)!=1U)return false;
  for(const auto& scene:flight_music_scenes) {
    if(ram.u32(0x800FB114U)==scene.level && ram.u32(0x800A74C0U)==scene.group &&
       ram.u16(header+0xE8U)==scene.asset && ram.u8(header+0x72U)==scene.track) {
      ram.put16(header+0x72U,static_cast<std::uint16_t>(0x0700U|ram.u8(header+0x73U)));
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
  if(return_address!=0x80046FC8U || !ram.valid(0x80046FC0U,4U) ||
     ram.u32(0x80046FC0U)!=0x0C010EEEU || !ram.valid(0x80043BE0U,4U) ||
     ram.u32(0x80043BE0U)!=0x93220004U || !ram.valid(0x800468ACU,4U) ||
     ram.u32(0x800468ACU)!=0xA4243254U || !ram.valid(0x800A3250U,6U) ||
     ram.u16(0x800A3250U)!=level || !ram.valid(0x800FB124U,12U) ||
     ram.u32(0x800FB124U)!=412U)return {};
  const auto table=ram.u32(0x800FB12CU);
  if(!ram.valid(table,412U*5U))return {};
  for(const auto& scene:flight_music_scenes) {
    if(level==scene.level && ram.u16(0x800A3254U)==scene.group &&
       ram.u32(table+level*5U)==scene.metadata && ram.u8(table+level*5U+4U)==scene.track)
      return 7U;
  }
  return {};
}
} // namespace jfg
