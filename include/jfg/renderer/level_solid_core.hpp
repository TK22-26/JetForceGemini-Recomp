#pragma once
#include "jfg/renderer/presentation_identity.hpp"
namespace jfg {
// A blended level texture can contain solid pixels as well as soft edges.
// Keep its native colour pass, then let only alpha==1 contribute depth.
// These ranges prove level-material ownership; actors, HUD and effects cannot
// acquire this policy merely by sharing a render mode or a texture address.
struct LevelSolidCoreRange {
  std::uint32_t first=0,end=0;
};
inline std::vector<LevelSolidCoreRange> level_solid_core_ranges(
    const RendererGameLayout& layout,    const PresentationGuestView& ram) {
  std::vector<LevelSolidCoreRange> result;
  if(!ram.valid(layout.track,4U))return result;
  const auto track=ram.u32(layout.track);
  if(!ram.valid(track,0x30U))return result;
  const auto textures=ram.u32(track),blocks=ram.u32(track+4U);
  const auto nt=ram.u16(track+0x18U),nb=ram.u16(track+0x1AU);
  if(!nt||nt>256U||!nb||nb>512U||!ram.valid(textures,nt*8U)||
     !ram.valid(blocks,nb*0x48U))return result;
  std::vector<bool> solid(nt);
  for(unsigned i=0;i<nt;++i) {
    const auto texture=ram.u32(textures+i*8U);
    if(!ram.valid(texture,32U)||(ram.u8(texture+2U)&15U)!=0U||
       !(ram.u16(texture+6U)&4U))continue;
    const auto pixels=unsigned(ram.u8(texture))*ram.u8(texture+1U);
    if(!pixels||pixels>16384U||!ram.valid(texture+32U,pixels*4U))continue;
    // Pixel order/interlace does not change the alpha histogram.
    for(unsigned p=0;p<pixels;++p)
      if(ram.u8(texture+35U+p*4U)==255U){solid[i]=true;break;}
  }
  for(unsigned i=0;i<nb;++i) {
    const auto block=blocks+i*0x48U;
    const auto faces=ram.u32(block+4U),batches=ram.u32(block+12U);
    const auto nf=ram.u16(block+0x26U),count=ram.u16(block+0x28U);
    if(!nf||nf>32768U||!count||count>4096U||
       !ram.valid(faces,nf*16U)||!ram.valid(batches,(count+1U)*16U))continue;
    for(unsigned j=0;j<count;++j) {
      const auto at=batches+j*16U;
      const auto index=ram.u8(at);
      if(index>=nt||!solid[index]||!(ram.u32(at+12U)&8U))continue;
      const auto first=ram.u16(at+8U),end=ram.u16(at+24U);
      if(first>=end||end>nf)continue;
      result.push_back({(faces&0x1FFFFFFFU)+first*16U,
                        (faces&0x1FFFFFFFU)+end*16U});
    }
  }
  std::sort(result.begin(),result.end(),[](const auto& a,const auto& b){return a.first<b.first;});
  return result;
}
inline bool level_solid_core_batch(const std::vector<LevelSolidCoreRange>& ranges,
                                  std::uint32_t source,std::uint32_t count) {
  if(!count||count>16U)return false;
  const auto it=std::upper_bound(ranges.begin(),ranges.end(),source,
      [](auto at,const auto& range){return at<range.first;});
  if(it==ranges.begin())return false;
  const auto& range=*std::prev(it);
  return source>=range.first && (source-range.first)%16U==0U &&
         source<range.end && count<=(range.end-source)/16U;
}
} // namespace jfg
