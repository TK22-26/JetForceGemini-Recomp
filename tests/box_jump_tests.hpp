#pragma once
#include "jfg/mod/box_jump.hpp"
static void box_jump_tests() {
  using namespace jfg::mod;
  BoxJumpPilot pilot;pilot.camera(true,0);
  check(!pilot.command(1,1,1,0,0,1,{80,60,0},20));
  check(pilot.command(1,1,2,0,0,0,{0,0,0},20));
  JumpPoint p{};float vy=0;bool airborne=false;std::int64_t now=0;
  for(int i=0;i<150 && pilot.active();++i) {
    now+=33;
    if(i%10==0)check(pilot.command(1,1,2,now,now,0,{0,0,0},20));
    pilot.tick(p,true,1,1,now);const auto input=pilot.input();
    if(input.buttons && !airborne){check(input.buttons==8);vy=18;airborne=true;}
    if(airborne){vy-=1;p.y+=vy;if(p.y<=0){p.y=0;vy=0;}}
  }
  check(!pilot.active() && pilot.calibrated);
  check(std::abs(pilot.gravity-1)<.1f && pilot.apex>140 && pilot.fit_error<1);
  auto calibrated=pilot;
  check(!pilot.command(1,1,100,now,now,1,{80,60,0},20,32768));
  pilot=calibrated;
  check(pilot.command(1,1,3,now,now,1,{80,60,0},20));
  // Supply a physically descending landing on the requested supported patch.
  for(int i=0;i<10;++i){now+=33;pilot.tick({0,0,0},true,1,1,now);}
  check(pilot.input().buttons!=0);
  for(int i=0;i<35 && pilot.active();++i) {
    now+=33;check(pilot.command(1,1,3,now,now,1,{80,60,0},20));
    float t=float(i+1);float y=17.5f*t-.5f*t*t;
    pilot.tick({std::min(80.0f,t*3),std::max(60.0f,y),0},true,1,1,now);
  }
  for(int i=0;i<8 && pilot.active();++i){now+=33;pilot.tick({80,60,0},true,1,1,now);}
  check(std::string(pilot.state)=="jump_landed" && pilot.completed==1);
  pilot=calibrated;check(pilot.command(1,1,4,now,now,1,{80,60,0},20));
  pilot.stop("manual_takeover");
  check(pilot.command(1,1,4,now+1,now+1,1,{80,60,0},20) && !pilot.active());
  check(!pilot.command(1,1,4,now+2,now+2,1,{90,60,0},20));
  pilot=calibrated;check(pilot.command(1,1,5,now,now,1,{80,60,0},20));
  pilot.tick({},true,1,1,now+1501);check(!pilot.active() && pilot.input().buttons==0);
  pilot=calibrated;check(pilot.command(1,1,6,now,now,1,{80,60,0},20));
  pilot.tick({},true,2,1,now);check(!pilot.active());
  pilot=calibrated;check(pilot.command(1,1,7,now,now,1,{80,300,0},20));
  for(int i=0;i<12;++i)pilot.tick({},true,1,1,now+i*33);
  check(std::string(pilot.state)=="jump_height_unreachable");
  pilot=calibrated;check(pilot.command(1,1,8,now,now,1,{80,60,0},20));
  pilot.camera(false,0);check(!pilot.active());

  // A contact at the right height is not a landing while still sliding.
  pilot=calibrated;check(pilot.command(1,1,20,now,now,1,{80,60,0},20));
  for(int i=0;i<10;++i){now+=33;pilot.tick({},true,1,1,now);}
  now+=33;pilot.tick({20,120,0},true,1,1,now);
  now+=33;pilot.tick({40,60,0},true,1,1,now);
  for(int i=0;i<8;++i){now+=33;pilot.tick({43.0f+static_cast<float>(i)*3.0f,60,0},true,1,1,now);}
  check(pilot.active());
  for(int i=0;i<12;++i){now+=33;pilot.tick({80,60,0},true,1,1,now);}
  check(std::string(pilot.state)=="jump_landed");
  // A stable ceiling/apex contact without descent must not count.
  pilot=calibrated;check(pilot.command(1,1,21,now,now,1,{80,60,0},20));
  for(int i=0;i<10;++i){now+=33;pilot.tick({},true,1,1,now);}
  for(int i=0;i<10;++i){now+=33;pilot.tick({80,60,0},true,1,1,now);}
  check(pilot.active());pilot.stop();
  // Do not turn an intermediate standing platform into a guessed ledge action.
  pilot=calibrated;check(!pilot.command(1,1,22,now,now,2,{80,160,0},20));
  // A close box can require rising vertically before applying lateral input.
  pilot=calibrated;check(pilot.command(1,1,23,now,now,1,{60,60,0},20,8,80));
  for(int i=0;i<10;++i){now+=33;pilot.tick({},true,1,1,now);}
  now+=33;pilot.tick({0,35,0},true,1,1,now);
  check(pilot.input().x==0 && pilot.input().y==0);
  now+=33;pilot.tick({0,85,0},true,1,1,now);
  check(pilot.input().x!=0 || pilot.input().y!=0);
  check(!pilot.command(1,1,23,now,now,1,{60,60,0},20,8,90));
  // A turning response and delayed input must not strand the pilot at a
  // lateral coasting offset. This is a synthetic controller plant, not proof
  // of the game's collision/animation behavior.
  for(float heading : {-2.0f,-1.0f,0.0f,1.0f,2.0f}) {
    BoxJumpPilot trial=calibrated;trial.camera(true,0);
    trial.launch_velocity=23.1f;trial.gravity=1.8f;trial.apex=148.2f;
    std::int64_t stamp=100000;check(trial.command(1,1,99,stamp,stamp,1,{0,60,80},8));
    JumpPoint position{},v{};JumpInput lag0{},lag1{};bool jumping=false;float vertical=0;
    for(int t=0;t<220 && trial.active();++t) {
      stamp+=33;check(trial.command(1,1,99,stamp,stamp,1,{0,60,80},8));
      trial.tick(position,true,1,1,stamp);const auto u=trial.input();
      if(u.buttons && !jumping){jumping=true;vertical=24;}
      float wx=-float(lag0.x),wz=float(lag0.y),mag=std::hypot(wx,wz);
      if(mag>0)heading+=std::remainder(std::atan2(wx,wz)-heading,6.283185307f)*.25f;
      const float force=std::max(0.0f,mag-8)/72*.8f;
      v.x=.9025f*v.x+std::sin(heading)*force;v.z=.9025f*v.z+std::cos(heading)*force;
      position.x+=v.x;position.z+=v.z;lag0=lag1;lag1=u;
      if(jumping){vertical-=1.8f;position.y+=vertical;if(vertical<0&&position.y<60){position.y=60;vertical=0;}}
    }
    check(std::string(trial.state)=="jump_landed");
    check(std::hypot(position.x,position.z-80)<8);
  }
  std::cout<<"box jump: measured arc, landing, manual cancellation, stale command, room and height checks passed\n";
}
