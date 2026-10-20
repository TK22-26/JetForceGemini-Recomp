#pragma once
#include "jfg/runtime/cutscene_script.hpp"
#include <optional>

namespace jfg {
enum class CutsceneCompletionActionKind { game_flag, input_disable, input_enable,
                                          front_control, change_level, conditional_end, music_fade, music_volume, music_track };
struct CutsceneCompletionAction {
  CutsceneCompletionActionKind kind{};
  unsigned argument=0, value=0;
};
struct CutsceneCompletionPlan {
  std::vector<CutsceneCompletionAction> actions;
  unsigned sentinel_offset=0, destination=0, group=0;
  bool conditional=false;
};
// Only command families inspected in the original US cinematic interpreter.
// This is not a fast-forward clock: audiovisual path commands are omitted;
// persistent effects and the original transition arguments are retained.
constexpr bool cutscene_visual_command(unsigned op) noexcept {
  switch(op) {
    case 0x00:case 0x01:case 0x02:case 0x03:case 0x04:case 0x05:case 0x06:
    case 0x20:case 0x27:case 0x28:case 0x29:case 0x2A:
    case 0x40:case 0x41:case 0x43:case 0x45:case 0x46:case 0x47:case 0x48:case 0x49:
    case 0x4B:case 0x4C:case 0x60:case 0x62:case 0x63:case 0x64:
    case 0x65:case 0x66:case 0x67:case 0x68:case 0x69:case 0x6A:case 0x6C:
    case 0x6D:case 0x6E:case 0x79:return true;
    default:return false;
  }
}
inline std::optional<CutsceneCompletionPlan> plan_cutscene_completion(
    const CutsceneScriptInspection& script, unsigned current_offset) {
  if(script.status!=CutsceneScriptStatus::finite || script.commands.empty())return {};
  CutsceneCompletionPlan plan;
  bool cursor=false,terminal=false;
  unsigned terminal_time=0;
  for(const auto& c:script.commands) {
    const auto op=c.word>>8;
    cursor|=c.offset==current_offset;
    if(c.word==0x7F00) {plan.sentinel_offset=c.offset;break;}
    if(op==0x77||op==0x7A) {
      if(terminal || c.offset<current_offset)return {};
      terminal=true;terminal_time=c.time;
      plan.conditional=op==0x77;
      if(op==0x7A) {plan.destination=c.payload[0]&0xFFF;plan.group=c.word&15;}
    }
    // Already executed commands keep their original effects; only remaining
    // commands need a completion disposition. A passed terminal still rejects.
    if(c.offset<current_offset)continue;
    if(cutscene_visual_command(op))continue;
    if(op!=0x21&&op!=0x22&&op!=0x23&&op!=0x74&&op!=0x75&&op!=0x76&&op!=0x77&&op!=0x78&&
       op!=0x7A&&op!=0x7C&&op!=0x7D)return {};
    // Do not guess whether an effect scheduled after departure ever executes.
    if(terminal && c.time>terminal_time)return {};
    if(c.offset<current_offset)continue;
    using K=CutsceneCompletionActionKind;
    switch(op) {
      // Complete the native music envelope at its target volume. Do not
      // wait through its duration or omit its final audio state.
      case 0x21:plan.actions.push_back({K::music_track,c.word&255U,0});break;
      case 0x22:plan.actions.push_back({K::music_fade,c.word&255U,0});break;
      case 0x23:plan.actions.push_back({K::music_volume,c.word&255U,0});break;
      case 0x74:case 0x75:plan.actions.push_back({K::front_control,op==0x74?1U:0U,0});break;
      // This synchronizes departure to an unplayed MIDI cue. A skip
      // cancels that presentation wait; it is not a persistent game effect.
      case 0x76:break;
      case 0x77:plan.actions.push_back({K::conditional_end,0,0});break;
      case 0x78:plan.actions.push_back({K::game_flag,c.payload[0],c.word&255U});break;
      case 0x7A:plan.actions.push_back({K::change_level,c.payload[0],c.word&255U});break;
      case 0x7C:plan.actions.push_back({K::input_disable,c.word&3U,0});break;
      case 0x7D:plan.actions.push_back({K::input_enable,c.word&3U,0});break;
    }
  }
  if(!cursor||!terminal)return {};
  return plan;
}
struct CutsceneDestination { unsigned level,character,entrance,mode,group; };
constexpr CutsceneDestination cutscene_destination(unsigned payload,unsigned word,
    unsigned next_character,unsigned remembered_character,unsigned resume_level,unsigned mode) noexcept {
  unsigned level=payload&4095,selector=(word>>4)&15;
  if(level==4095)level=resume_level;
  unsigned character=next_character;
  if(selector) {
    character=selector-1;
    if((next_character&3)==3 && (character&3)!=3)character=remembered_character;
  }
  return {level,character,payload>>12,level==360?23U:mode,word&15};
}
// Actual cinematic actor controls reviewed in the captured travel, story and
// rescue rooms. Types 30/45/54 (lights/audio/huts) have no ordinary control;
// 48 (forest introduction pad) and 65 (flashback glowing light) share the
// same native no-control case at 800104A8 (also Tawfret type 19);
// 57 advances only its local sprite animation. Movement/event scripts remain
// independently disallowed. Other object controls still require review.
constexpr bool cutscene_actor_control_reviewed(unsigned type) noexcept {
  switch(type) {
    case 0:case 5:case 12:case 19:case 30:case 32:case 35:case 38:case 39:case 40:
    case 45:case 46:case 47:case 48:case 49:case 51:case 54:case 55:case 57:case 63:case 65:case 68:case 69:
    case 70:case 71:case 72:case 95:case 152:case 162:return true;
    default:return false;
  }
}
} // namespace jfg
