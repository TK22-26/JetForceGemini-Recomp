#pragma once
#include "jfg/renderer/presentation_identity.hpp"
#include "jfg/renderer/actor_lod_settings.hpp"
#include <cstring>
namespace jfg {
// US objPrintModelObject keeps actor+0x3A as the authored state/variant.
// A distance threshold in header+0xCC and the global detail offset choose
// a compact instance AFTER that base. Disable only that offset during draw;
// restore both operands before returning to simulation or another actor.
class ActorLodPresentationScope {
public:
  ActorLodPresentationScope(std::span<std::uint8_t> bytes,
      std::uint32_t target,std::uint32_t actor,bool high) {
    if(!high || target!=0x8000CC64U)return;
    const PresentationGuestView ram(bytes);
    if(ram.u32(target)!=0x27BDFEE0U ||
       ram.u32(0x8000D3B8U)!=0x90420A20U ||
       ram.u32(0x8000D3D8U)!=0xC5F000CCU ||
       ram.u32(0x8000D434U)!=0x00827021U ||
       (actor&3U) || !ram.valid(actor,0xA4U))return;
    const auto header=ram.u32(actor+0x40U),models=ram.u32(actor+0x6CU);
    if((header&3U)||(models&3U)||!ram.valid(header,0xD0U))return;
    const auto count=ram.u8(header+0x1FU),base=ram.u8(actor+0x3AU);
    if(count==0 || count>64 || base>=count || !ram.valid(models,count*4U))return;
    const auto instance=ram.u32(models+base*4U);
    if((instance&3U)||!ram.valid(instance,0x10U)||!ram.valid(ram.u32(instance),0x80U))return;
    if(!ram.valid(0x800A0A20U,1U))return;
    threshold_=bytes.data()+PresentationGuestView::physical(header+0xCCU);
    detail_=bytes.data()+(PresentationGuestView::physical(0x800A0A20U)^3U);
    std::memcpy(&saved_threshold_,threshold_,4U);saved_detail_=*detail_;
    const std::uint32_t zero=0;std::memcpy(threshold_,&zero,4U);*detail_=0;
  }
  ~ActorLodPresentationScope(){restore();}
  ActorLodPresentationScope(const ActorLodPresentationScope&)=delete;
  ActorLodPresentationScope& operator=(const ActorLodPresentationScope&)=delete;
  bool applied() const noexcept{return threshold_!=nullptr;}
  void restore() noexcept {
    if(threshold_){std::memcpy(threshold_,&saved_threshold_,4U);*detail_=saved_detail_;threshold_=nullptr;detail_=nullptr;}
  }
private:
  std::uint8_t* threshold_=nullptr;std::uint8_t* detail_=nullptr;
  std::uint32_t saved_threshold_=0;std::uint8_t saved_detail_=0;
};
}
