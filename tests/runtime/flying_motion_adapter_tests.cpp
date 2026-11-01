#include "regional_game_fixture.hpp"
// ROM-free integration tests drive the same call scopes as the native runtime.
#include "jfg/runtime/flying_motion.hpp"
#include "jfg/runtime/execution_local.hpp"
#include "jfg/mod/navigation_mod.hpp"
#include <array>
#include <bit>
#include <cfenv>
#include <cstring>
#include <initializer_list>
#include <iostream>
#include <unordered_set>
#include <vector>
#include "jfg/game/original_modules.hpp"
using jfg::game::OriginalModule;
// Deliberately unrelated synthetic section ordinals, code tokens and field
// offsets: the adapter must consume bindings rather than former US constants.
consteval unsigned game_module(OriginalModule m) {
  if(m!=OriginalModule::collision)throw "Unknown fixture module";return 5;
}
consteval unsigned game_overlay_extent(OriginalModule) {return 0x1B000;}
consteval unsigned game_code(std::string_view n) {
  if(n=="game.objMoveXYZ")return 0x80001020;throw "Unknown fixture resident operation";
}
consteval unsigned game_overlay_token(std::string_view n) {
  if(n=="overlay.collision.update_animation")return 0x70000000;
  if(n=="overlay.collision.prepare_squaddie")return 0x70000004;
  if(n=="overlay.collision.smooth_acceleration")return 0x70000008;
  if(n=="overlay.collision.turn")return 0x7000000c;
  if(n=="overlay.collision.accelerate")return 0x70000010;
  if(n=="overlay.collision.drag")return 0x70000014;
  if(n=="overlay.collision.move")return 0x70000018;
  if(n=="overlay.collision.death_move")return 0x7000001c;
  if(n=="overlay.collision.collision_move")return 0x70000020;
  if(n=="overlay.collision.squaddie_control")return 0x70000024;
  throw "Unknown fixture overlay operation";
}
consteval unsigned game_overlay_data(std::string_view n,OriginalModule m) {
  if(m!=OriginalModule::collision)throw "Wrong fixture module";
  if(n=="flight.actor")return 0x18000;
  if(n=="flight.control")return 0x18004;
  if(n=="flight.descriptor")return 0x18008;
  if(n=="flight.record")return 0x1800c;
  if(n=="flight.death_retention")return 0x18010;
  if(n=="flight.collision_retention")return 0x18014;
  if(n=="flight.turn_target")return 0x18018;
  if(n=="flight.speed")return 0x1801c;
  if(n=="flight.drag_retention")return 0x18020;
  throw "Unknown fixture field";
}
constexpr std::size_t kRdramSize=0x400000,kGuestAddressSpan=0x8A000000;
constexpr std::uint32_t kKseg0=0x80000000;
struct JfgGeneratedSectionMetadata {
  unsigned linked_vram=0x80100000,is_overlay=1,text_size=0x19000,data_size=0x1000,bss_size=0x1000;
};
bool jfg_generated_section_metadata(unsigned section,JfgGeneratedSectionMetadata* m) {
  *m={};return section==game_module(OriginalModule::collision);
}
std::uint32_t addresses[6]{0,0,0,0,0,0x80100000};
auto* section_addresses=addresses;
struct recomp_context {
  std::uint64_t r4{},r5{},r6{},r7{};
  struct {float fl{};} f0;
};
struct Trace {
  void event(const char*,std::initializer_list<std::uint64_t>){}
};
struct State {
  std::uint8_t* rdram{};
  bool diagnostic_host_clock=true;
  bool flying_motion_adapter_enabled=true;
  std::unordered_set<unsigned> active_overlay_sections{game_module(OriginalModule::collision)};
  unsigned vi_retraces{};
  Trace gameplay_trace{};
};
using NativeGameMemory = jfg::test::GameMemory;
#include "../../src/boot/flying_motion.inl"

static void require(bool value,const char* message) {
  if(!value){std::cerr<<message<<'\n';std::abort();}
}
static bool near(float a,float b){return std::abs(a-b)<0.0001f;}
struct Fixture {
  std::vector<std::uint8_t> storage=std::vector<std::uint8_t>(kRdramSize);
  State state{storage.data()};
  recomp_context context;
  jfg::test::GameMemory ram{{storage.data(),storage.size()}};
  static constexpr unsigned actor=0x80001000,control=0x80002000,desc=0x80003000,record=0x80004000,base=0x80100000;
  void word(unsigned address,unsigned value){std::memcpy(storage.data()+(address&0x1fffffff),&value,4);}
  void number(unsigned address,float value){word(address,std::bit_cast<unsigned>(value));}
  void byte(unsigned address,unsigned value){storage[(address&0x1fffffff)^3]=static_cast<std::uint8_t>(value);}
  Fixture() {
    ram.put16(actor+0x48,24);word(actor+0x68,control);
    word(base+game_overlay_data("flight.actor",OriginalModule::collision),actor);word(base+game_overlay_data("flight.control",OriginalModule::collision),control);
    word(base+game_overlay_data("flight.descriptor",OriginalModule::collision),desc);word(base+game_overlay_data("flight.record",OriginalModule::collision),record);
    byte(record+0x2a,1);byte(record+0x2b,5);
    byte(desc+0x24,30);byte(desc+0x25,0);
    number(base+game_overlay_data("flight.death_retention",OriginalModule::collision),.99f);number(base+game_overlay_data("flight.drag_retention",OriginalModule::collision),.98f);number(base+game_overlay_data("flight.collision_retention",OriginalModule::collision),.97f);
    number(base+game_overlay_data("flight.speed",OriginalModule::collision),100);ram.put16(control+0xa6,100);
    context.r4=actor;context.r5=2;
  }
  void prepare(){FlyingMotionScope scope(state,game_overlay_token("overlay.collision.prepare_squaddie"),context);}
  float argument(std::uint64_t v){return std::bit_cast<float>(static_cast<unsigned>(v));}
  void velocity(float x,float y,float z) {
    number(actor+0x1c,x);number(actor+0x20,y);number(actor+0x24,z);
  }
  void arguments(float x,float y,float z) {
    context.r4=actor;context.r5=std::bit_cast<unsigned>(x);
    context.r6=std::bit_cast<unsigned>(y);context.r7=std::bit_cast<unsigned>(z);
  }
};
int main(){
  {
    Fixture f;
    FlyingMotionScope controller(f.state,game_overlay_token("overlay.collision.squaddie_control"),f.context);f.prepare();
    {
      FlyingMotionScope force(f.state,game_overlay_token("overlay.collision.drag"),f.context);
      {FlyingMotionScope solver(f.state,game_overlay_token("overlay.collision.smooth_acceleration"),f.context);f.context.f0.fl=3;}
      require(near(f.context.f0.fl,2),"flight force did not use elapsed VI");
    }
    // Unrelated callers of the same solver retain their return value.
    {FlyingMotionScope solver(f.state,game_overlay_token("overlay.collision.smooth_acceleration"),f.context);f.context.f0.fl=3;}
    require(f.context.f0.fl==3,"unrelated solver modified");
    f.velocity(6,3,-9);
    {FlyingMotionScope move(f.state,game_overlay_token("overlay.collision.collision_move"),f.context);
     f.arguments(6,3,-9);FlyingMotionScope integration(f.state,game_code("game.objMoveXYZ"),f.context);
     require(near(f.argument(f.context.r5),4)&&near(f.argument(f.context.r6),2)&&
             near(f.argument(f.context.r7),-6),"live displacement units");
     require(f.ram.f32(Fixture::actor+0x1c)==6,"canonical velocity was rescaled");}
    // A native contact response must override the pre-contact movement.
    {FlyingMotionScope move(f.state,game_overlay_token("overlay.collision.collision_move"),f.context);
     f.arguments(-6,0,9);FlyingMotionScope integration(f.state,game_code("game.objMoveXYZ"),f.context);
     require(near(f.argument(f.context.r5),-4)&&near(f.argument(f.context.r6),0)&&
             near(f.argument(f.context.r7),6),"collision response discarded");}
    f.velocity(6,0,0);
    {FlyingMotionScope move(f.state,game_overlay_token("overlay.collision.collision_move"),f.context);
     FlyingMotionScope collision(f.state,game_overlay_token("overlay.collision.death_move"),f.context);
     f.velocity(6*.97f,0,0);f.arguments(6*.97f,0,0);
     FlyingMotionScope integration(f.state,game_code("game.objMoveXYZ"),f.context);
     require(near(f.argument(f.context.r5),4*std::pow(.97f,2.f/3)),
             "contact retention remains per-update");
     require(f.argument(f.context.r6)==0,"stopped contact retained falling displacement");}
    f.number(Fixture::control+0x20,10);f.velocity(10,3,0);
    {FlyingMotionScope drag(f.state,game_overlay_token("overlay.collision.move"),f.context);
     f.number(Fixture::control+0x20,9.8f);f.velocity(9.8f,3,0);}
    require(near(f.ram.f32(Fixture::actor+0x1c),10*std::pow(.98f,2.f/3)),"drag time scale");
    f.ram.put16(Fixture::base+game_overlay_data("flight.turn_target",OriginalModule::collision),10000);
    {FlyingMotionScope turn(f.state,game_overlay_token("overlay.collision.turn"),f.context);f.ram.put16(Fixture::actor,1000);}
    require(f.ram.u16(Fixture::actor)==667,"turn time scale");
  }
  require(flying_motion_detail::execution().current==nullptr,"scope leaked after controller");
  for(unsigned bypass:{0U,1U,2U}) {
    Fixture f;
    if(bypass==1U)f.state.diagnostic_host_clock=false;
    else if(bypass==2U)f.state.flying_motion_adapter_enabled=false;
    else f.byte(Fixture::record+0x2b,1);
    FlyingMotionScope controller(f.state,game_overlay_token("overlay.collision.squaddie_control"),f.context);f.prepare();
    f.velocity(6,3,-9);
    {FlyingMotionScope force(f.state,game_overlay_token("overlay.collision.drag"),f.context);
     {FlyingMotionScope solver(f.state,game_overlay_token("overlay.collision.smooth_acceleration"),f.context);f.context.f0.fl=3;}
     require(f.context.f0.fl==3,"ground/oracle force changed");}
    FlyingMotionScope move(f.state,game_overlay_token("overlay.collision.collision_move"),f.context);
    f.arguments(6,3,-9);FlyingMotionScope integration(f.state,game_code("game.objMoveXYZ"),f.context);
    require(f.argument(f.context.r5)==6,"ground/oracle displacement changed");
  }
  {
    Fixture f;FlyingMotionScope controller(f.state,game_overlay_token("overlay.collision.squaddie_control"),f.context);f.prepare();
    f.ram.put16(Fixture::control+0xa6,0);f.velocity(12,8,-3);
    for(unsigned i=0;i<3;++i)f.ram.put16(Fixture::control+0x44+i*2,300);
    f.context.r4=12;
    {FlyingMotionScope animation(f.state,game_overlay_token("overlay.collision.update_animation"),f.context);}
    // Emulate native per-update gravity/drag/spin after the impulse.
    f.velocity(12*.99f,7,-3*.99f);
    for(unsigned i=0;i<3;++i)f.ram.put16(Fixture::actor+i*2,300);
    FlyingMotionScope move(f.state,game_overlay_token("overlay.collision.collision_move"),f.context);
    require(near(f.ram.f32(Fixture::actor+0x20),8-2.f/3),"death acceleration");
    require(f.ram.u16(Fixture::actor)==200,"death angular velocity");
    f.arguments(f.ram.f32(Fixture::actor+0x1c),f.ram.f32(Fixture::actor+0x20),
                f.ram.f32(Fixture::actor+0x24));
    FlyingMotionScope integration(f.state,game_code("game.objMoveXYZ"),f.context);
    require(near(f.argument(f.context.r6),8*(2.f/3)-(2.f/3)*(2.f/3+1)/2),
            "death trajectory integration");
  }
  require(flying_motion_detail::execution().current==nullptr,"death scope leaked");
  {
    Fixture f;f.context.r5=16;
    FlyingMotionScope controller(f.state,game_overlay_token("overlay.collision.squaddie_control"),f.context);f.prepare();
    f.velocity(3,0,0);
    {FlyingMotionScope move(f.state,game_overlay_token("overlay.collision.collision_move"),f.context);
     f.arguments(3,0,0);FlyingMotionScope integration(f.state,game_code("game.objMoveXYZ"),f.context);
     require(near(f.argument(f.context.r5),16),"long elapsed update reverted to legacy speed");}
    auto* outer=flying_motion_detail::execution().current;
    {FlyingMotionScope nested(f.state,game_overlay_token("overlay.collision.squaddie_control"),f.context);
     require(flying_motion_detail::execution().current!=outer,"nested frame reused outer state");}
    require(flying_motion_detail::execution().current==outer,"nested frame did not restore context");
    f.word(Fixture::base+game_overlay_data("flight.actor",OriginalModule::collision),Fixture::actor+0x100);
    {FlyingMotionScope force(f.state,game_overlay_token("overlay.collision.drag"),f.context);
     {FlyingMotionScope solver(f.state,game_overlay_token("overlay.collision.smooth_acceleration"),f.context);f.context.f0.fl=3;}
     require(f.context.f0.fl==3,"mismatched current actor modified");}
    f.prepare();
    require(!outer->active,"failed actor resolution retained prior activation");
  }
  require(flying_motion_detail::execution().current==nullptr,"nested scope leaked");
  std::cout<<"Flight adapter, collision, death and isolation checks passed\n";
}
