#pragma once
#include <cstdint>
namespace jfg {
// Recorded preference, not a held action. Focus suspension must retain it.
inline constexpr std::uint8_t kModernFreeMovementFlag=0x20;
class ModernMovementLatch {
  bool initialized_=false,held_=false,free_=false,default_=false;
  int device_=-99;
public:
  void reset(){*this={};}
  bool sample(bool down,bool default_free,bool can_toggle,int device) {
    if(!initialized_ || device!=device_ || default_free!=default_) {
      initialized_=true;free_=default_=default_free;device_=device;held_=down;
    } else {
      if(can_toggle && down && !held_)free_=!free_;
      held_=down;
    }
    return free_;
  }
};
} // namespace jfg
