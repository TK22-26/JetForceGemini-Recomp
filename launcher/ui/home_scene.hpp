// Procedural launcher decoration based on the supplied home-screen reference.
// Game model data is supplied locally by the verified-ROM helper, never embedded.
#pragma once
#include "rom_ships.hpp"
#include <RmlUi/Core.h>
#include <RmlUi/Core/RenderManager.h>
#include <RmlUi/Core/ElementInstancer.h>
#include <algorithm>
#include <array>
#include <cmath>
#include <filesystem>
#include <fstream>
#include <numeric>
#include <vector>

class HomeScene final : public Rml::Element {
  static constexpr float pi = 3.14159265359f;
  using Point = Rml::Vector2f;
  using Color = Rml::ColourbPremultiplied;
  Rml::Mesh mesh;
  Rml::Geometry geometry;
  double epoch = -1;
  static Color color(unsigned rgb, float alpha = 1) {
    auto a = static_cast<Rml::byte>(std::clamp(alpha, 0.f, 1.f) * 255);
    return Rml::Colourb((rgb >> 16) & 255, (rgb >> 8) & 255, rgb & 255, a).ToPremultiplied();
  }
  void triangle(Point a, Point b, Point c, Color tint) {
    int start = static_cast<int>(mesh.vertices.size());
    mesh.vertices.push_back({a, tint, {}}); mesh.vertices.push_back({b, tint, {}}); mesh.vertices.push_back({c, tint, {}});
    mesh.indices.insert(mesh.indices.end(), {start, start + 1, start + 2});
  }
  void line(Point a, Point b, float width, Color tint) {
    float dx=b.x-a.x, dy=b.y-a.y, length=std::sqrt(dx*dx+dy*dy);
    if(length < .001f) return;
    Point n(-dy*width*.5f/length, dx*width*.5f/length);
    triangle(a+n,b+n,b-n,tint);triangle(a+n,b-n,a-n,tint);
  }
  void disc(Point c, float r, Color tint) {
    constexpr int segments=96;
    for(int i=0;i<segments;i++) {float a=2*pi*i/segments,b=2*pi*(i+1)/segments;triangle(c,c+Point(std::cos(a),std::sin(a))*r,c+Point(std::cos(b),std::sin(b))*r,tint);}
  }
  Point ellipsePoint(Point c,float rx,float ry,float a,float tilt=0) {
    float x=rx*std::cos(a),y=ry*std::sin(a);return c+Point(x*std::cos(tilt)-y*std::sin(tilt),x*std::sin(tilt)+y*std::cos(tilt));
  }
  void arc(Point c,float rx,float ry,float begin,float end,float width,Color tint,float tilt=0,bool dotted=false) {
    const int count=std::max(16,static_cast<int>(std::abs(end-begin)*std::max(rx,ry)/3));
    for(int i=0;i<count;i++)if(!dotted||i%3==0)line(ellipsePoint(c,rx,ry,begin+(end-begin)*i/count,tilt),ellipsePoint(c,rx,ry,begin+(end-begin)*(i+1)/count,tilt),width,tint);
  }
  void ring(Point c,float r,float width,Color tint,bool dotted=false){arc(c,r,r,0,2*pi,width,tint,0,dotted);}
  void band(Point c,float radius,float y,float width,Color tint,float shift=0,bool broken=false) {
    for(float yy=y-width*.5f;yy<y+width*.5f;yy+=1) {
      float dy=yy-c.y;if(std::abs(dy)>=radius)continue;
      float dx=std::sqrt(radius*radius-dy*dy);
      if(!broken)line({c.x-dx,yy},{c.x+dx,yy},1.1f,tint);
      else for(float x=c.x-dx;x<c.x+dx;x+=1)if(std::fmod(x+shift+2000,83.f)<45)line({x,yy},{x+1,yy},1.1f,tint);
    }
  }
 public:
  bool reducedMotion=false;
  RomShips ships;
  explicit HomeScene(const Rml::String& tag):Rml::Element(tag){}
 protected:
  void OnRender() override {
    auto* context=GetContext();if(!context)return;
    const auto dimensions=GetBox().GetSize(Rml::BoxArea::Content);
    const float dpi=context->GetDensityIndependentPixelRatio(),w=dimensions.x/dpi,h=dimensions.y/dpi;
    double now=Rml::GetSystemInterface()->GetElapsedTime();if(epoch<0)epoch=now;
    float t=reducedMotion?0.f:static_cast<float>(now-epoch);
    mesh={};
    const Point sun(w-160,180);
    for(float r:{290.f,232.f,170.f,112.f,64.f})ring(sun,r,.65f,color(0x29334b,.55f),r==290||r==64);
    disc(sun,30.f+6.f*std::sin(t*pi/4),color(0xffb23e,.025f));
    ring(sun,18,.8f,color(0xffb23e,.35f));disc(sun,13,color(0xffb23e,.85f));
    const float radii[]={64,112,170,232,290},periods[]={9,22,41,70,120},offsets[]={0,8,14,50,30};
    for(int i=0;i<5;i++) {
      float a=2*pi*(t+offsets[i])/periods[i];Point p=sun+Point(std::cos(a),std::sin(a))*radii[i];
      if(i==0)disc(p,4,color(0x6fd3ee,.85f));
      if(i==1){ring(p,16,.55f,color(0x536078,.5f),true);disc(p,7,color(0x566079,.85f));Point moon=p+Point(std::cos(t*pi/2),std::sin(t*pi/2))*16;disc(moon,2,color(0xa7b0c2,.85f));}
      if(i==2){arc(p,20,5,pi,2*pi,1,color(0xa87537,.7f),-.35f);disc(p,11,color(0x2a2018));ring(p,11,.8f,color(0xa87537,.7f));arc(p,20,5,0,pi,1,color(0xa87537,.7f),-.35f);}
      if(i==3)disc(p,5,color(0x6fd3ee,.55f));
      if(i==4){triangle(p+Point(0,-4),p+Point(4,0),p+Point(0,4),color(0x8691a8,.65f));triangle(p+Point(0,-4),p+Point(0,4),p+Point(-4,0),color(0x8691a8,.65f));}
    }
    const Point planet(70,h-30);const float tilt=-14*pi/180;
    arc(planet,124,30,pi,2*pi,5,color(0x2a3550,.75f),tilt);
    disc(planet,78,color(0x10151f));
    for(float offset:{-38.f,-14.f,10.f,38.f})band(planet,78,planet.y+offset,7,color(0x1c2438,.85f));
    for(float offset:{-26.f,24.f})band(planet,78,planet.y+offset,4,color(0x222b40,.8f),t*9,true);
    // Clip the offset shadow to the globe analytically, keeping bands inside its rim.
    for(float y=-77;y<78;y+=1){float edge=std::sqrt(std::max(0.f,78*78-y*y));float sy=y+2;float shadow=std::sqrt(std::max(0.f,78*78-sy*sy));float right=std::min(edge,-36+shadow);if(right>-edge)line(planet+Point(-edge,y),planet+Point(right,y),1,color(0x0b0f17,.45f));}
    ring(planet,78,1.2f,color(0x2e3a57,.85f));
    arc(planet,124,30,0,pi,5,color(0x3a4663,.8f),tilt);arc(planet,124,30,0,pi,1,color(0xffb23e,.2f),tilt);
    for(int i=0;i<26;i++){float x=std::fmod(i*137.53f+83,w),y=std::fmod(i*91.7f+48,h);float a=.15f+.5f*(.5f+.5f*std::sin(t*1.8f+i*1.7f));disc({x,y},i%6==0?1.2f:.75f,color(i%7==0?0x6fd3ee:0x8691a8,a));}
    for(int side=0;side<2;side++)for(int bottom=0;bottom<2;bottom++){Point p(side?w-18:18,bottom?h-18:18);line(p,p+Point(side?-22.f:22.f,0),.7f,color(0x3a4663,.8f));line(p,p+Point(0,bottom?-22.f:22.f),.7f,color(0x3a4663,.8f));}
    for(float x=112;x<w-72;x+=16){bool major=static_cast<int>(x-112)%128==0;line({x,h-17},{x,h-(major?24.f:20.f)},.6f,color(0x3a4663,.55f));}
    float scan=std::fmod(t/14,1.f)*w;line({scan,0},{scan,h},.7f,color(0xffb23e,.055f));
    for(int i=0;i<6;i++){float height=7+15*(.5f+.5f*std::sin(t*1.9f-i*.9f));line({w-105+i*6.f,h-30},{w-105+i*6.f,h-30-height},3,color(i==3?0xffb23e:0x3a4663,i==3?.65f:.9f));}
    for(auto& v:mesh.vertices)v.position*=dpi;
    auto& renderer=context->GetRenderManager();geometry=renderer.MakeGeometry(std::move(mesh));geometry.Render(GetAbsoluteOffset(Rml::BoxArea::Content));
    RenderShips(t,w,h,dpi);
  }
  void RenderShips(float t,float w,float h,float dpi){ships.Render(GetContext()->GetRenderManager(),GetAbsoluteOffset(Rml::BoxArea::Content),t,w,h,dpi,reducedMotion);}
};
