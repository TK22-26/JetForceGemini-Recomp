#pragma once
#include "ship_flight.hpp"
#include <vector>
namespace launcher_art {
struct Joint { int parent=-1; Vec3 translation; };
// ROM vertices are local to their batch's joint, not to the ship origin.
// The background gently gimbals the side engines using their original pivots.
inline Vec3 pose_vertex(Vec3 point,int joint,const std::vector<Joint>& joints,float time,bool animate) {
  for(int steps=0;joint>=0&&steps<64;steps++) {
    const auto& bone=joints.at(static_cast<size_t>(joint));
    const float pitch=animate&&(joint==1||joint==2)? .32f*std::sin(time*1.15f+(joint==1?.15f:-.15f)):0.f;
    const float c=std::cos(pitch),s=std::sin(pitch);
    point={point.x,point.y*c-point.z*s,point.y*s+point.z*c};
    point=point+bone.translation;joint=bone.parent;
  }
  return point;
}
}
