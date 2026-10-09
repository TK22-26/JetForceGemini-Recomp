#include "jfg/runtime/pc_input.hpp"
#include <cstdlib>
#include <iostream>
#include <string>
namespace {
int checks=0;
void check(bool result,const char* what){++checks;if(!result){std::cerr<<what<<'\n';std::exit(1);}}
}
int main() {
  jfg::PcInputConfig config,roundtrip;
  check(!jfg::pc_experiments_enabled(""),"missing switch stays disabled");
  check(!jfg::pc_experiments_enabled("version=1\nexperimental=2\n"),"invalid opt-in stays disabled");
  check(!jfg::pc_experiments_enabled("version=1\nexperimental=1\nunknown=1\n"),"unknown opt-in rejected");
  check(jfg::pc_experiments_enabled(jfg::serialize_pc_experiments(true)),"explicit opt-in");
  check(!jfg::pc_experiments_enabled(jfg::serialize_pc_experiments(false)),"explicit opt-out");
  check(jfg::pc_experiments_enabled("version=1\r\nexperimental=1\r\n"),"CRLF opt-in");
  auto stored=jfg::pc_keyboard_preset();stored.dual_stick=1;
  auto gated=jfg::effective_pc_input(false,stored);
  check(gated.keys==config.keys && !gated.mouse_aim && !gated.dual_stick,"opt-out restores original keyboard and aim");
  check(jfg::effective_pc_input(true,stored).keys==stored.keys && stored.mouse_aim,"opt-in restores saved bindings");
  const auto text=jfg::serialize_pc_input(config);
  check(jfg::parse_pc_input(text,roundtrip)&&roundtrip.keys==config.keys,"default roundtrip");
  auto invalid=[&](std::string s){const auto before=jfg::serialize_pc_input(roundtrip);check(!jfg::parse_pc_input(s,roundtrip)&&jfg::serialize_pc_input(roundtrip)==before,"invalid config changed active settings");};
  invalid(text+"mouse_aim=1\n");invalid(text.substr(text.find('\n')+1));invalid(text+"unknown=2\n");
  auto replace=[&](std::string a,std::string b){auto t=text;t.replace(t.find(a),a.size(),b);invalid(t);};
  replace("key0=32","key0=258");replace("key0=32","key0=-1");replace("mouse_sensitivity=100","mouse_sensitivity=0");
  replace("aim_deadzone=7849","aim_deadzone=32767");replace("dual_stick=0","dual_stick=2");replace("key0=32","key0=32junk");
  replace("version=2","version=3");invalid(std::string(4097,'x'));
  std::array<bool,258> keys{};
  const auto sample=[&](){return jfg::map_pc_keyboard(config,[&](int k){return keys[static_cast<std::size_t>(k)];});};
  keys['W']=keys['D']=true;auto move=sample();check(move.x==80&&move.y==80,"movement directions");
  keys['S']=keys['A']=true;check(sample().x==0&&sample().y==0,"opposite movement cancellation");
  keys={};keys[32]=true;check(sample().buttons==0x8000,"Space compatibility");
  keys={};keys['Z']=true;check(sample().buttons==0x8000,"alternate A compatibility");
  config=jfg::pc_keyboard_preset();keys={};keys[1]=keys[2]=true;check((sample().buttons&0x2010)==0x2010,"mouse fire and aim together");
  keys={};keys[32]=true;check(sample().buttons==8,"Normal jump preset");
  config=jfg::pc_keyboard_preset(true);check(sample().buttons==0x8000,"Expert jump preset");
  config.keys[0]=0;keys={};keys[0]=true;check(sample().buttons==0,"unbound key");
  jfg::PcWheelPulses wheel;wheel.add(60);check(wheel.sample()==0,"partial wheel notch");wheel.add(300);
  check(wheel.sample()==256&&wheel.sample()==0&&wheel.sample()==256&&wheel.sample()==0&&wheel.sample()==256&&wheel.sample()==0&&wheel.sample()==0,"wheel pulses retain releases");
  wheel.add(-240);check(wheel.sample()==257,"wheel down");wheel.clear();check(wheel.sample()==0,"wheel cleared on capture loss");
  jfg::PcMouseMotion mouse;config={};mouse.add(12,-9);auto aim=mouse.take(config);
  check(aim.x==12&&aim.y==9,"relative mouse axes");check(mouse.take(config)==jfg::N64StickSample{},"mouse delta consumed once");
  config.mouse_invert_y=1;config.mouse_sensitivity=200;mouse.add(10,10);aim=mouse.take(config);check(aim.x==20&&aim.y==20,"mouse sensitivity and inversion");
  mouse.add(2147483647,-2147483647);aim=mouse.take(config);check(aim.x==127&&aim.y==-127,"bounded mouse spikes");
  mouse.add(20,20);mouse.clear();check(mouse.take(config)==jfg::N64StickSample{},"stale mouse cleared");
  config={};config.mouse_sensitivity=10;int slow_total=0;
  for(int i=0;i<20;++i){mouse.add(1,0);slow_total+=mouse.take(config).x;}
  check(slow_total==2,"slow mouse displacement retained across updates");
  mouse.add(4096,0);(void)mouse.take(config);
  check(mouse.take(config)==jfg::N64StickSample{},"clipped mouse does not drift afterward");
  mouse.add(1,0);(void)mouse.take(config);mouse.clear();
  check(mouse.take(config)==jfg::N64StickSample{},"fractional motion cleared on disable");
  config.mouse_sensitivity=50;mouse.add(1,-1);bool idle_stable=true;
  for(int i=0;i<10;++i)idle_stable &= mouse.take(config)==jfg::N64StickSample{};
  check(idle_stable,"half-pixel residual must not oscillate while idle");
  mouse.add(1,-1);check(mouse.take(config)==jfg::N64StickSample{1,1},"half-pixel residual accumulates on new motion");
  jfg::StandardControllerSample pad;pad.axes={32767,0,0,-32768,0,0};config={};
  aim=jfg::pc_aim_stick(config,pad,0);check(aim.x==0&&aim.y==80,"right aim independent of left movement");
  aim=jfg::pc_aim_stick(config,pad,1);check(aim.x==80&&aim.y==0,"swapped sticks remain independent");
  pad.axes={0,0,2000,-2000,0,0};check(jfg::pc_aim_stick(config,pad,0)==jfg::N64StickSample{},"aim stick drift deadzone");
  pad.axes={0,0,0,-32768,0,0};config.aim_invert_y=1;check(jfg::pc_aim_stick(config,pad,0).y==-80,"aim stick Y inversion");
  jfg::ControllerInputGate gate;std::array<jfg::ControllerPortSample,4> raw{};
  check(gate.blocked(true,raw),"settings capture");raw[0].buttons=1;check(gate.blocked(false,raw),"aim deflection prevents premature release");raw[0].buttons=0;check(!gate.blocked(false,raw),"neutral release");
  config=jfg::pc_keyboard_preset();check(config.modern==1,"modern keyboard preset");
  auto old=jfg::serialize_pc_input(config);old.replace(old.find("version=2"),9,"version=1");
  old.erase(old.find("modern=1\n"),9);
  check(jfg::parse_pc_input(old,roundtrip) && !roundtrip.modern,"v1 profile retains legacy aim");
  config={};mouse.add(10,-5);auto angular=mouse.take_angles(config);
  check(angular==jfg::PcLookDelta{180,90},"mouse displacement maps directly to angles");
  check(mouse.take_angles(config)==jfg::PcLookDelta{},"direct mouse motion consumed once");
  auto direct=jfg::pc_direct_aim(-32760,0,{100,200},-100,100);
  check(direct.x==32676 && direct.y==-100,"direct aim wraps yaw and clamps pitch");
  check(jfg::pc_direct_aim(20,30,{},-100,100)==jfg::PcLookDelta{20,30},"stationary direct aim remains still");
  const auto diagonal=jfg::pc_aim_movement(80,80);
  check(std::abs(diagonal.side/2.5F*diagonal.side/2.5F+diagonal.forward/3.0F*diagonal.forward/3.0F-1.0F)<0.001F,"aim diagonal stays normalized");
  check(jfg::pc_aim_movement(0,0).side==0 && jfg::pc_aim_movement(0,0).forward==0,"neutral aim movement");
  const auto clear=jfg::pc_camera_clearance({0,0,0},{0,0,100},{0,0,50});
  check(clear.x==0 && clear.y==0 && clear.z==38,"wall hit retreats toward focus for camera clearance");
  check(jfg::pc_camera_clearance({0,0,0},{0,0,100},{0,0,100}).z==100,"unblocked camera is unchanged");
  check(jfg::pc_camera_clearance({0,0,0},{0,0,100},{0,0,20}).z==16,"camera clearance keeps minimum focus distance");
  const auto floor_clear=jfg::pc_camera_clearance({0,0,0},{0,0,100},{0,16,100});
  check(floor_clear.y==16 && floor_clear.z==100,"floor correction is not pulled back into terrain");
  const auto orbit=jfg::pc_orbit_point(16384,0,200);
  check(std::abs(orbit.x-200)<0.001F && std::abs(orbit.y)<0.001F && std::abs(orbit.z)<0.001F,"quarter orbit preserves radius");
  check(jfg::pc_camera_delta(3,{15,20},5)==jfg::PcLookDelta{15,20},"mouse orbit is displacement independent of guest ticks");
  check(jfg::pc_camera_delta(4,{80,-80},2)==jfg::PcLookDelta{512,-512},"stick orbit is a rate");
  check(jfg::pc_camera_delta(4,{80,80},0)==jfg::PcLookDelta{},"paused stick orbit is still");
  keys={};keys[13]=true;keys[39]=true;
  auto menu=jfg::map_pc_menu(jfg::ControllerPortSample{},[&](int key){return keys[static_cast<std::size_t>(key)];});
  check(menu.buttons==0x8000 && menu.x==80,"Enter and arrows work independently of gameplay preset");
  keys={};keys[8]=true;keys[38]=true;keys[40]=true;
  menu=jfg::map_pc_menu(jfg::ControllerPortSample{},[&](int key){return keys[static_cast<std::size_t>(key)];});
  check(menu.buttons==0x4000 && menu.y==0,"Backspace and opposing menu arrows");
  std::cout<<" PC input checks passed\n";
}
