#pragma once
#include <algorithm>
#include <cmath>

// Perspective flight paths use world coordinates. The ends are outside the
// viewport, or beyond the distance where a ship occupies two screen pixels.
namespace launcher_art {
struct Vec3 { float x=0,y=0,z=0; Vec3 operator+(Vec3 v)const{return{x+v.x,y+v.y,z+v.z};} Vec3 operator-(Vec3 v)const{return{x-v.x,y-v.y,z-v.z};} Vec3 operator*(float s)const{return{x*s,y*s,z*s};} };
inline Vec3 cross(Vec3 a,Vec3 b){return{a.y*b.z-a.z*b.y,a.z*b.x-a.x*b.z,a.x*b.y-a.y*b.x};}
inline Vec3 unit(Vec3 v){float length=std::sqrt(v.x*v.x+v.y*v.y+v.z*v.z);return v*(1/std::max(length,.00001f));}
struct Flight { bool active=false;Vec3 position,forward;float bank=0,size=.65f; };
inline Flight flight(int ship,float elapsed,float width,float height) {
  Flight result;
  const float phase=std::fmod(std::max(0.f,elapsed)+150-ship*46,150.f);
  if(phase>=36)return result;
  const float u=phase/36,v=1-u,aspect=width/std::max(height,1.f),focal=.95f*height;
  const float edge=(width*.5f+200)/focal;
  Vec3 p0,p1,p2,p3;
  if(ship==0){p0={-edge*4.8f,1.8f,4.8f};p1={-aspect*.75f,.35f,2.f};p2={aspect*.5f,1.6f,3.2f};p3={edge*4.5f,1.1f,4.5f};}
  else if(ship==1){p0={edge*5.f,1.3f,5.f};p1={aspect*.6f,1.6f,2.4f};p2={-aspect*.6f,-.8f,3.f};p3={-edge*4.8f,-1.1f,4.8f};}
  else {p0={-edge*4.2f,-1.1f,4.2f};p1={-aspect*.9f,.4f,2.1f};p2={aspect*2.f,3.5f,8.f};p3={aspect*54.f,76.f,200.f};}
  result.position=p0*(v*v*v)+p1*(3*v*v*u)+p2*(3*v*u*u)+p3*(u*u*u);
  result.forward=unit((p1-p0)*(3*v*v)+(p2-p1)*(6*v*u)+(p3-p2)*(3*u*u));
  result.bank=(ship==1?-1.f:1.f)*.55f*std::sin(u*6.2831853f);
  result.active=true;
  return result;
}
}
