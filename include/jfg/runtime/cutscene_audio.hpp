#pragma once
#include <cstdint>

namespace jfg {
// Suppress only presentation-only sound starts issued by the original cinematic
// command interpreter during an already confirmed, qualified skip chain.
// Music, ambient-channel state, cleanup and all other callers remain native.
struct CutsceneSoundCall {
  bool chain=false;
  std::uint64_t qualified_scene=0;
  std::uint32_t destination=0,group=0,target=0,return_address=0,handle=0,actor=0;
};
template<class Memory>
bool omit_skipped_cutscene_sound(const Memory& ram,const CutsceneSoundCall& call) {
  if(!call.chain || !call.qualified_scene ||
     !ram.valid(0x800FB114U,8U) || !ram.valid(0x800A74C0U,12U))return false;
  const auto level=ram.u32(0x800FB114U),header=ram.u32(0x800FB118U);
  const auto group=ram.u32(0x800A74C0U),start=ram.u32(0x800A74C8U);
  if(level!=call.destination || group!=call.group || group>255U ||
     !ram.valid(header,0x6DU) || !ram.valid(start,4U) ||
     (ram.u8(header+0x6CU)!=1U && ram.u8(header+0x6CU)!=2U) ||
     call.qualified_scene!=((std::uint64_t{level}<<48U)|(std::uint64_t{group}<<32U)|start))
    return false;
  const bool direct=call.target==0x80001248U &&
      (call.return_address==0x80077EFCU || call.return_address==0x80078054U);
  const bool positioned=call.target==0x80003410U && call.return_address==0x80078108U;
  if(!direct&&!positioned)return false;
  if(!ram.valid(call.target,4U) || !ram.valid(call.return_address-8U,4U) ||
     ram.u32(call.target)!=(direct?0x3C0F800FU:0x27BDFFC0U) ||
     ram.u32(call.return_address-8U)!=(0x0C000000U|((call.target>>2U)&0x03FFFFFFU)))
    return false;
  // Opcode20 has no handle. Opcode27 uses the 16 sequence sound slots.
  if(call.return_address==0x80077EFCU)return call.handle==0;
  if(direct && (call.handle<0x801045C8U || call.handle>=0x80104608U ||
                 (call.handle&3U)!=0))return false;
  // Opcode29 passes actor+0x88 as its positional-sound handle.
  if(positioned && ((call.actor&3U)!=0 || !ram.valid(call.actor,0x8CU) ||
                     call.handle!=call.actor+0x88U))return false;
  // The original interpreter has already stopped/cleared the previous handle.
  // Leave that null handle exactly as it is; both native APIs return void.
  return ram.valid(call.handle,4U) && ram.u32(call.handle)==0;
}
} // namespace jfg
