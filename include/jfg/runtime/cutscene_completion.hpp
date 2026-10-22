#pragma once
#include "jfg/runtime/cutscene_script.hpp"
#include <optional>

namespace jfg {
enum class CutsceneCompletionActionKind { game_flag, input_disable, input_enable,
                                          front_control, change_level, conditional_end, music_fade, music_volume, music_track, ambient_track, ambient_volume, credits_end };
struct CutsceneCompletionAction {
  CutsceneCompletionActionKind kind{};
  unsigned argument=0, value=0;
};
struct CutsceneCompletionPlan {
  std::vector<CutsceneCompletionAction> actions;
  unsigned sentinel_offset=0, destination=0, group=0;
  bool conditional=false, native_credits=false;
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
    case 0x65:case 0x66:case 0x67:case 0x68:case 0x69:case 0x6A:case 0x6B:case 0x6C:
    // 6F (8007933C..80079468) changes the selected model animation's
    // flags/rate. It has no calls or persistent game-state writes.
    case 0x6D:case 0x6E:case 0x6F:case 0x79:return true;
    default:return false;
  }
}
struct CutsceneCompletionSource { unsigned asset=~0U,group=~0U; };
inline std::optional<CutsceneCompletionPlan> plan_cutscene_completion(
    const CutsceneScriptInspection& script, unsigned current_offset,
    CutsceneCompletionSource source={}) {
  // Credits own their completion in frontCredits (03B00488), not the
  // looping background animation. Only the reviewed credits asset may use
  // this native completion, and its entire script must remain visual.
  if(script.status==CutsceneScriptStatus::loop && source.asset==360U &&
     source.group==0U && !script.commands.empty()) {
    bool cursor=false;
    for(const auto& c:script.commands) {
      cursor|=c.offset==current_offset;
      if(!cutscene_visual_command(c.word>>8))return {};
    }
    if(!cursor)return {};
    CutsceneCompletionPlan credits;
    credits.native_credits=true;
    credits.actions.push_back({CutsceneCompletionActionKind::credits_end,0,0});
    return credits;
  }
  if(script.status!=CutsceneScriptStatus::finite || script.commands.empty())return {};
  CutsceneCompletionPlan plan;
  bool cursor=false,terminal=false;
  unsigned terminal_time=0,effective_time=0;
  for(const auto& c:script.commands) {
    const auto op=static_cast<unsigned>(c.word)>>8;
    cursor|=c.offset==current_offset;
    if(c.word==0x7F00) {plan.sentinel_offset=c.offset;break;}
    // A command behind a later-timed command cannot execute before it.
    // Preserve native stream order, including descending timestamp tails.
    if(c.time>effective_time)effective_time=c.time;
    // Ending asset388/group0 leaves for392 at native time1950. Its second
    // departure at native time6500 is unreachable: mainChangeLevel arms at most30
    // native update units and this script has no MIDI synchronization gate.
    // Do not replace the real first destination with that dormant tail.
    const bool unreachable_ending_tail=source.asset==388U && source.group==0U &&
      terminal && !plan.conditional && terminal_time==1950U &&
      c.time==6500U && c.word==0x7A02U && c.payload[0]==388U &&
      plan.actions.size()==1U &&
      plan.actions[0].kind==CutsceneCompletionActionKind::change_level &&
      plan.actions[0].argument==392U && plan.actions[0].value==0U &&
      script.commands.size()>=2U &&
      script.commands[script.commands.size()-2U].offset==c.offset &&
      script.commands.back().word==0x7F00U;
    if(unreachable_ending_tail)continue;
    if(op==0x77||op==0x7A) {
      // The native interpreter executes every due command before returning.
      // Consecutive unconditional departures at the same tick each run; the
      // last destination wins. Never extend this to conditional or later ends.
      if(c.offset<current_offset ||
         (terminal && (plan.conditional || op!=0x7A || effective_time!=terminal_time)))return {};
      terminal=true;terminal_time=effective_time;
      plan.conditional=op==0x77;
      if(op==0x7A) {plan.destination=c.payload[0]&0xFFF;plan.group=c.word&15;}
    }
    // Already executed commands keep their original effects; only remaining
    // commands need a completion disposition. A passed terminal still rejects.
    if(c.offset<current_offset)continue;
    if(cutscene_visual_command(op))continue;
    if(op!=0x21&&op!=0x22&&op!=0x23&&op!=0x24&&op!=0x26&&op!=0x74&&op!=0x75&&op!=0x76&&op!=0x77&&op!=0x78&&
       op!=0x7A&&op!=0x7C&&op!=0x7D)return {};
    if(terminal && effective_time>terminal_time) {
      // Gem Quarry's completion explicitly activates its generator during
      // the native departure countdown: asset357/group1 requests room267,
      // entrance1 at24.91s, then sets flag89 at25.00s. Preserve that reviewed
      // completion state after the native change-level call. This permission
      // is not shared with other scripts, flags, destinations or timings.
      const bool quarry_generator=source.asset==357U && source.group==1U &&
        !plan.conditional && terminal_time==2491U && effective_time==2500U &&
        c.time==2500U && c.word==0x7801U && c.payload[0]==89U &&
        !plan.actions.empty() &&
        plan.actions.back().kind==CutsceneCompletionActionKind::change_level &&
        plan.actions.back().argument==0x110BU && plan.actions.back().value==0U;
      if(!quarry_generator)return {};
    }
    if(c.offset<current_offset)continue;
    using K=CutsceneCompletionActionKind;
    switch(op) {
      // Complete the native music envelope at its target volume. Do not
      // wait through its duration or omit its final audio state.
      case 0x21:plan.actions.push_back({K::music_track,c.word&255U,0});break;
      case 0x22:plan.actions.push_back({K::music_fade,c.word&255U,0});break;
      case 0x23:plan.actions.push_back({K::music_volume,c.word&255U,0});break;
      case 0x24:plan.actions.push_back({K::ambient_track,c.word&255U,0});break;
      case 0x26:plan.actions.push_back({K::ambient_volume,c.word&255U,0});break;
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
// same native no-control case at 800104A8 (also types 6 and 19);
// 57 advances only its local sprite animation. Movement/event scripts remain
// independently disallowed. Other object controls still require review.
constexpr bool cutscene_actor_control_reviewed(unsigned type) noexcept {
  switch(type) {
    case 0:case 5:case 6:case 12:case 19:case 30:case 32:case 35:case 38:case 39:case 40:
    case 45:case 46:case 47:case 48:case 49:case 50:case 51:case 54:case 55:case 57:case 63:case 65:case 68:case 69:
    // The native dispatch index is type-2:50 uses the no-op animobjControl
    // (80026FD4),112 has no ordinary control, and132 uses07C00678.
    // The caller requires132's control disabled by cinematic animation;
    // event/movement callbacks remain independently rejected.
    case 70:case 71:case 72:case 95:case 112:case 132:case 152:case 162:return true;
    default:return false;
  }
}
} // namespace jfg
