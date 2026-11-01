#pragma once
#include "jfg/game/resident_memory.hpp"
#include <cstdint>

namespace jfg {
struct CutsceneSoundCall {
  bool chain=false;
  std::uint64_t qualified_scene=0;
  std::uint32_t destination=0,group=0,target=0,return_address=0,handle=0,actor=0;
};
struct CutsceneSoundBindings {
  game::DataRef level,header,group,script_start,handles;
  game::CodeRef plain,positioned;
  game::InstructionRef fire_and_forget_call,handle_call,positioned_call;
};
// The producer verifies these common field/stride semantics in the original
// interpreter and cleanup bodies of every supported revision. Call/array
// coordinates remain typed regional references, never US address defaults.
template<class Memory>
bool omit_skipped_cutscene_sound(const Memory& ram,const CutsceneSoundCall& call,
    const game::Descriptor& descriptor,const CutsceneSoundBindings& bindings) {
  if(!call.chain || !call.qualified_scene)return false;
  const auto plain=game::resident_address(descriptor,bindings.plain);
  const auto positioned=game::resident_address(descriptor,bindings.positioned);
  const auto fire_call=game::resident_address(descriptor,bindings.fire_and_forget_call);
  const auto handle_call=game::resident_address(descriptor,bindings.handle_call);
  const auto position_call=game::resident_address(descriptor,bindings.positioned_call);
  const auto handles=game::resident_address(descriptor,bindings.handles);
  if(!plain || !positioned || !fire_call || !handle_call || !position_call || !handles ||
      bindings.handles.size!=16U*4U)return false;
  try {
    game::ResidentMemory view(descriptor,ram);
    const auto level=view.u32(bindings.level),header=view.u32(bindings.header);
    const auto group=view.u32(bindings.group),start=view.u32(bindings.script_start);
    if(level!=call.destination || group!=call.group || group>255U ||
       !ram.valid(header,0x6DU) || !ram.valid(start,4U) ||
       (ram.u8(header+0x6CU)!=1U && ram.u8(header+0x6CU)!=2U) ||
       call.qualified_scene!=((std::uint64_t{level}<<48U)|(std::uint64_t{group}<<32U)|start))return false;
    const bool direct=call.target==*plain &&
        (call.return_address==*fire_call+8U || call.return_address==*handle_call+8U);
    const bool spatial=call.target==*positioned && call.return_address==*position_call+8U;
    if(!direct && !spatial)return false;
    const auto caller=call.return_address-8U;
    if(!ram.valid(caller,4U) || ram.u32(caller)!=(0x0C000000U|((call.target>>2U)&0x03FFFFFFU)))return false;
    // Original opcode20 has no handle; opcode27 uses sixteen word handles.
    if(call.return_address==*fire_call+8U)return call.handle==0;
    if(direct) {
      if(call.handle<*handles || (call.handle&3U) || call.handle-*handles>=bindings.handles.size)return false;
      return view.u32(bindings.handles,call.handle-*handles)==0;
    }
    // Original opcode29 passes actor+0x88 as the positional-sound handle.
    return !(call.actor&3U) && ram.valid(call.actor,0x8CU) &&
        call.handle==call.actor+0x88U && ram.u32(call.handle)==0;
  } catch(const std::runtime_error&) {return false;}
}
} // namespace jfg
