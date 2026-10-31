#include "jfg/runtime/flying_motion.hpp"
#include <array>
#include <cmath>
#include <cstdlib>
#include <iostream>
static void require(bool condition,const char* message) {
  if(!condition){std::cerr<<message<<'\n';std::abort();}
}
static bool near(float a,float b,float tolerance=0.002f) {
  return std::abs(a-b)<=tolerance;
}
int main() {
  using namespace jfg::flight;
  require(supported(5,1),"flying class absent");
  for(unsigned movement=0;movement<8;++movement)
    for(unsigned death=0;death<8;++death)
      require(supported(movement,death)==(movement==5&&death==1),"ground or special actor changed");
  require(ticks(0)==0&&ticks(3)==1&&ticks(6)==2,"VI clock units");
  for(float v:{-20.f,-1.f,0.f,7.f,25.f}) {
    require(accelerated_distance(v,v-1,1)==v-1,"one-tick gravity changed");
    require(damp(v,.99f,1)==v*.99f,"one-tick drag changed");
    require(damped_distance(v,.99f,1)==v*.99f,"one-tick travel changed");
  }
  // Equal game time with 60, 30 or 20 updates/s and bounded update stalls.
  // Acceleration and drag must not acquire an output-FPS multiplier.
  for(unsigned vi:{1U,2U,3U,6U,12U}) {
    float v=0,p=0,drag_v=15,drag_p=0;
    for(unsigned elapsed=0;elapsed<120;elapsed+=vi) {
      const auto q=ticks(vi),old=v,old_drag=drag_v;
      v-=q;p+=accelerated_distance(old,v,q);
      drag_v=damp(old_drag,.99f,q);
      drag_p+=damped_distance(old_drag,.99f,q);
    }
    require(near(v,-40),"fall velocity depends on update rate");
    require(near(p,-820,.01f),"fall distance depends on update rate");
    require(near(drag_v,15*std::pow(.99f,40.0f),.001f),"drag velocity depends on update rate");
    require(near(drag_p,15*.99f*(1-std::pow(.99f,40.0f))/(1-.99f),.02f),
            "drag distance depends on update rate");
  }
  require(approach_angle(65500,50,1)==50,"angle wrap");
  require(approach_angle(100,500,1)==500,"turn overshot near target");
  require(approach_angle(0,10000,1)==1000,"legacy turn rate");
  require(approach_angle(0,10000,ticks(2))==667,"time-based turn rate");
  require(approach_angle(0,65000,ticks(2))==65000,"negative wrap turn");
  std::cout<<"Flight clock, reference-step parity and split-step checks passed\n";
}
