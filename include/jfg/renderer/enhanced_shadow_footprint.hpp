#pragma once
#include "jfg/renderer/presentation_identity.hpp"
#include <cfenv>
namespace jfg {
struct EnhancedShadowFootprint {
  std::array<std::array<float,2>,4> points{};
  unsigned vertices=0;
  bool expanded=false;
};
// Size the render-only receiver query from both posed vertex banks. The legacy
// scale describes a 64x64 mask, not the extent of the Enhanced mesh silhouette.
inline std::optional<EnhancedShadowFootprint> enhanced_shadow_footprint(
    const RendererGameLayout& layout,    const PresentationGuestView& ram, std::uint32_t actor,
    const std::array<std::array<float,2>,4>& original,
    const std::array<float,2>& shear, const std::array<float,2>& floor) {
  for(const auto& p:original)for(float x:p)
    if(!std::isfinite(x)||std::abs(x)>32760)return {};
  for(float x:shear)if(!std::isfinite(x)||std::abs(x)>2.001f)return {};
  for(float x:floor)if(!std::isfinite(x)||std::abs(x)>32768)return {};
  if(!ram.valid(actor,0x70U))return {};
  const auto header=ram.u32(actor+layout.actor_header),table=ram.u32(actor+layout.actor_models);
  if(!ram.valid(header,0x70U)||ram.u8(header+0x1EU)==1U)return {};
  const auto index=ram.u8(actor+layout.actor_variant),models=ram.u8(header+0x1FU);
  if(!models||models>16U||index>=models||!ram.valid(table,models*4U))return {};
  const auto instance=ram.u32(table+index*4U);
  if(!ram.valid(instance,0x18U))return {};
  const auto model=ram.u32(instance);
  if(!ram.valid(model,0x64U)||!ram.u8(model+0x4EU))return {};
  const auto bones=ram.u8(model+0x4FU);
  const auto nv=ram.u16(model+0x12U),nf=ram.u16(model+0x14U),nb=ram.u16(model+0x16U);
  const auto vertices=ram.u32(instance+4U),batches=ram.u32(model+0x24U),faces=ram.u32(model+0x20U);
  if(!bones||bones>128U||!nv||nv>8192U||!nf||nf>8192U||!nb||nb>1024U||
     !ram.valid(vertices,nv*10U)||!ram.valid(faces,nf*16U)||!ram.valid(batches,(nb+1U)*16U))return {};
  std::array<std::vector<std::array<float,16>>,2> matrices;
  for(unsigned bank=0;bank<2;++bank) {
    const auto palette=ram.u32(instance+0x10U+bank*4U);
    if(!ram.valid(palette,bones*64U))return {};
    // camConvertMatrixList QUEUES float 4x3 matrices for camTick. Padding
    // words are not initialized and cannot identify the representation.
    // Use the native pending-conversion list, never value-based inference.
    const auto queued=ram.valid(layout.matrix_queue_count,4U)?ram.u32(layout.matrix_queue_count):0U;
    if(queued>1024U || (queued&&!ram.valid(layout.matrix_queue,queued*8U)))return {};
    bool floating=false;
    for(unsigned q=0;q<queued;++q) {
      const auto entry=layout.matrix_queue+q*8U;
      if(PresentationGuestView::physical(ram.u32(entry))!=PresentationGuestView::physical(palette))continue;
      if(ram.u16(entry+4U)!=bones)return {};
      floating=true;
    }
    matrices[bank].resize(bones);
    for(unsigned j=0;j<bones;++j) {
      auto& m=matrices[bank][j];
      for(unsigned k=0;k<16;++k) {
        m[k]=floating ? ((k&3U)==3U ? (k==15U?1.0f:0.0f) :
            std::bit_cast<float>(ram.u32(palette+j*64U+k*4U))) :
            float(std::int16_t(ram.u16(palette+j*64U+k*2U)))+
            float(ram.u16(palette+j*64U+32U+k*2U))/65536.0f;
        if(!std::isfinite(m[k]))return {};
      }
      if(m[3]!=0||m[7]!=0||m[11]!=0||m[15]!=1)return {};
    }
  }
  std::array<float,2> lo{1e9f,1e9f},hi{-1e9f,-1e9f};
  EnhancedShadowFootprint result;result.points=original;
  for(unsigned b=0;b<nb;++b) {
    const auto at=batches+b*16U;
    const auto first=ram.u16(at+8U),last=ram.u16(at+24U);
    if(first>last||last>nf)return {};
    if(first==last)continue;
    const auto start=ram.u16(at+6U),end=ram.u16(at+22U);
    if(start>end||end>nv)return {};
    std::vector<std::uint8_t> used(end-start);
    bool surface=false;
    for(unsigned f=first;f<last;++f) {
      const std::array<unsigned,3> triangle{ram.u8(faces+f*16U+1U),
          ram.u8(faces+f*16U+2U),ram.u8(faces+f*16U+3U)};
      // Attachment/helper entries are degenerate faces with metadata in the
      // joint bytes. Include actual triangle references, not those metadata.
      if(triangle[0]==triangle[1]||triangle[1]==triangle[2]||triangle[2]==triangle[0])continue;
      for(unsigned i:triangle){if(i>=used.size())return {};used[i]=1;}
      surface=true;
    }
    if(!surface)continue;
    const std::array<unsigned,4> offsets{0,ram.u8(at+4U),ram.u8(at+5U),unsigned(end-start)};
    if(offsets[1]>offsets[2]||offsets[2]>offsets[3])return {};
    for(unsigned group=0;group<3;++group) {
      if(offsets[group]==offsets[group+1])continue;
      const auto joint=ram.u8(at+1U+group);
      if(joint>=bones)return {};
      for(unsigned i=start+offsets[group];i<start+offsets[group+1];++i) {
        if(!used[i-start])continue;
        std::array<float,3> local{};
        for(unsigned c=0;c<3;++c)local[c]=float(std::int16_t(ram.u16(vertices+i*10U+c*2U)));
        for(unsigned bank=0;bank<2;++bank) {
          const auto& m=matrices[bank][joint];std::array<float,3> p{};
          for(unsigned c=0;c<3;++c) {
            p[c]=local[0]*m[c]+local[1]*m[4+c]+local[2]*m[8+c]+m[12+c];
            if(!std::isfinite(p[c])||std::abs(p[c])>32760)return {};
          }
          for(float y:floor)for(unsigned c=0;c<2;++c) {
            const float v=p[c*2]+(p[1]-y)*shear[c];
            lo[c]=(std::min)(lo[c],v);hi[c]=(std::max)(hi[c],v);
          }
        }
        ++result.vertices;
      }
    }
  }
  if(!result.vertices)return {};
  // Same map extent as the renderer, plus the maximum eight-texel PCF radius
  // and one unit for native packed receiver coordinates.
  float size=128;
  while(size<(std::max)(hi[0]-lo[0],hi[1]-lo[1])+16)size*=2;
  const float margin=size*(8.0f/512.0f)+1.0f;
  for(unsigned c=0;c<2;++c){lo[c]=std::floor(lo[c]-margin);hi[c]=std::ceil(hi[c]+margin);}
  if(lo[0]<-32760||lo[1]<-32760||hi[0]>32760||hi[1]>32760)return {};
  const std::array<std::array<float,2>,4> needed{{{hi[0],hi[1]},{lo[0],hi[1]},{lo[0],lo[1]},{hi[0],lo[1]}}};
  // Preserve an already sufficient original polygon byte-for-byte, including
  // its rotation. Otherwise union its bounds with the complete new footprint.
  const auto inside=[&](const std::array<float,2>& p) {
    bool positive=false,negative=false;
    for(unsigned i=0;i<4;++i) {
      const auto& a=original[i];const auto& b=original[(i+1)%4];
      const double cross=double(b[0]-a[0])*(p[1]-a[1])-double(b[1]-a[1])*(p[0]-a[0]);
      positive|=cross>0.001;negative|=cross<-.001;
    }
    return !(positive&&negative);
  };
  if(std::all_of(needed.begin(),needed.end(),inside))return result;
  for(const auto& p:original)for(unsigned c=0;c<2;++c){
    lo[c]=(std::min)(lo[c],p[c]);hi[c]=(std::max)(hi[c],p[c]);
  }
  result.points={{{hi[0],hi[1]},{lo[0],hi[1]},{lo[0],lo[1]},{hi[0],lo[1]}}};
  result.expanded=true;return result;
}
// Pinned to shadowProject's rectangle-bounds call, before both broadphase
// receiver lookup and triangle clipping. Only its temporary stack polygon changes.
inline std::optional<EnhancedShadowFootprint> enhanced_shadow_receiver_query(
    const RendererGameLayout& layout,    std::span<std::uint8_t> bytes,std::uint32_t target,std::uint32_t caller,
    std::uint32_t stack,std::uint32_t count,std::uint32_t points,bool enabled) {
  if(!enabled||target!=layout.shadow_bounds||caller!=layout.shadow_bounds_return||count!=4U||
     points!=stack+0x54U||(stack&3U))return {};
  const PresentationGuestView ram(bytes);
  if(!ram.valid(stack,0x174U))return {};
  std::fenv_t saved;
  if(std::feholdexcept(&saved)!=0)return {};
  const bool rounded=std::fesetround(FE_TONEAREST)==0;
  std::optional<EnhancedShadowFootprint> result;
  if(rounded) {
    std::array<std::array<float,2>,4> polygon{};
    for(unsigned i=0;i<4;++i)for(unsigned c=0;c<2;++c)
      polygon[i][c]=std::bit_cast<float>(ram.u32(points+i*8U+c*4U));
    const auto light=ram.u32(stack+0x16CU);
    if(!light||ram.valid(light,4U)) {
      const auto shear=light?shadow_light_shear(ram.u16(light),ram.u16(light+2U)):std::array<float,2>{};
      const std::array<float,2> floor{float(std::int16_t(ram.u16(stack+0x80U))),
          float(std::int16_t(ram.u16(stack+0x82U)))};
      result=enhanced_shadow_footprint(layout,ram,ram.u32(stack+0x74U),polygon,shear,floor);
    }
  }
  const bool restored=std::fesetenv(&saved)==0;
  if(!restored)return {};
  if(result&&result->expanded)for(unsigned i=0;i<4;++i)for(unsigned c=0;c<2;++c){
    const auto word=std::bit_cast<std::uint32_t>(result->points[i][c]);
    std::memcpy(bytes.data()+PresentationGuestView::physical(points+i*8U+c*4U),&word,4);
  }
  return result;
}
} // namespace jfg
