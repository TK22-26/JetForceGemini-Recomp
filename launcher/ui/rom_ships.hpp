#pragma once
#include "ship_pose.hpp"
#include <RmlUi/Core.h>
#include <RmlUi/Core/RenderManager.h>
#include <RmlUi/Core/CallbackTexture.h>
#include <algorithm>
#include <array>
#include <cmath>
#include <filesystem>
#include <fstream>
#include <numeric>
#include <vector>

// Transient presentation data, produced locally by InventoryImages.ExportShips.
class RomShips {
  struct Texture { int width=0,height=0; std::vector<Rml::byte> pixels; Rml::CallbackTexture gpu; };
  struct Face { int material=-1;std::array<int,3> index{};std::array<Rml::Vector2f,3> uv{}; };
  struct Thruster { int limb=0;launcher_art::Vec3 nozzle;float radius=0; };
  struct Model { std::vector<Thruster> thrusters;std::vector<Texture> textures;std::vector<Rml::Vector3f> vertices;std::vector<int> limbs;std::vector<launcher_art::Joint> joints;launcher_art::Vec3 center;float scale=1;std::vector<Face> faces; };
  // Locate the aft nozzle rims in the locally extracted mesh. Vela and Juno
  // have jointed engines; Lupus has two fixed wing engines on the root limb.
  static void findThrusters(Model& model) {
    std::vector<bool> visible(model.vertices.size(),false);
    for(const auto& face:model.faces)for(int index:face.index)visible[index]=true;
    float halfWidth=0;
    for(size_t i=0;i<visible.size();i++)if(visible[i])halfWidth=std::max(halfWidth,std::abs(model.vertices[i].x));
    const bool jointed=std::any_of(model.limbs.begin(),model.limbs.end(),[](int limb){return limb==1||limb==2;});
    for(int side=0;side<2;side++) {
      const int limb=jointed?side+1:0;
      auto belongs=[&](size_t i){return visible[i]&&model.limbs[i]==limb&&
        (jointed||(side==0?model.vertices[i].x>halfWidth*.65f:model.vertices[i].x<-halfWidth*.65f));};
      float rear=65536,front=-65536;
      for(size_t i=0;i<visible.size();i++)if(belongs(i)){rear=std::min(rear,model.vertices[i].z);front=std::max(front,model.vertices[i].z);}
      if(front<=rear)continue;
      // A fixed engine may end in a pointed cap. Find its first actual rim
      // for the width, then place the exhaust just beyond the aft-most tip.
      std::vector<float> planes;
      for(size_t i=0;i<visible.size();i++)if(belongs(i))planes.push_back(model.vertices[i].z);
      std::sort(planes.begin(),planes.end());planes.erase(std::unique(planes.begin(),planes.end()),planes.end());
      for(float plane:planes) {
        launcher_art::Vec3 low{65536,65536,rear},high{-65536,-65536,rear};
        for(size_t i=0;i<visible.size();i++)if(belongs(i)&&std::abs(model.vertices[i].z-plane)<.01f){
          auto p=model.vertices[i];low.x=std::min(low.x,p.x);low.y=std::min(low.y,p.y);high.x=std::max(high.x,p.x);high.y=std::max(high.y,p.y);
        }
        const float diameter=std::min(high.x-low.x,high.y-low.y);
        if(diameter>(front-rear)*.02f){model.thrusters.push_back({limb,(low+high)*.5f,diameter*.45f});break;}
      }
    }
  }
  std::vector<Model> models;
  std::filesystem::path file;
  std::string source;
  double retry=0;
  const std::filesystem::file_time_type launched=std::filesystem::file_time_type::clock::now();
  struct Reader {
    std::ifstream in;
    explicit Reader(const std::filesystem::path& path):in(path,std::ios::binary|std::ios::ate) {
      if(!in||in.tellg()<12||in.tellg()>8*1024*1024)throw std::runtime_error("Invalid home model size");in.seekg(0);
    }
    void bytes(void* p,size_t count){in.read(static_cast<char*>(p),count);if(!in)throw std::runtime_error("Truncated home model");}
    int integer(int low,int high){int value=0;bytes(&value,4);if(value<low||value>high)throw std::runtime_error("Invalid home model field");return value;}
    float number(){float value=0;bytes(&value,4);if(!std::isfinite(value)||std::abs(value)>65536)throw std::runtime_error("Invalid home model coordinate");return value;}
  };
  void load() {
    if(std::filesystem::last_write_time(file)<launched)return;
    Reader read(file);if(read.integer(0,INT_MAX)!=0x3253474a)return;
    std::string origin(read.integer(1,32768),'\0');read.bytes(origin.data(),origin.size());if(origin!=source)return;
    const int count=read.integer(3,3);std::vector<Model> next(count);
    for(auto& model:next) {
      model.textures.resize(read.integer(0,64));
      for(auto& texture:model.textures){texture.width=read.integer(1,128);texture.height=read.integer(1,128);texture.pixels.resize(texture.width*texture.height*4);read.bytes(texture.pixels.data(),texture.pixels.size());}
      model.joints.resize(read.integer(1,64));
      for(size_t j=0;j<model.joints.size();j++){auto& joint=model.joints[j];joint.parent=read.integer(-1,static_cast<int>(j)-1);joint.translation={read.number(),read.number(),read.number()};}
      model.vertices.resize(read.integer(3,4096));model.limbs.resize(model.vertices.size());
      for(size_t i=0;i<model.vertices.size();i++){auto& vertex=model.vertices[i];vertex.x=read.number();vertex.y=read.number();vertex.z=read.number();model.limbs[i]=read.integer(0,static_cast<int>(model.joints.size())-1);}
      // Normalize in object space once so banking does not change apparent size.
      Rml::Vector3f low(65536,65536,65536),high(-65536,-65536,-65536);
      for(size_t i=0;i<model.vertices.size();i++){auto p=model.vertices[i];auto v=launcher_art::pose_vertex({p.x,p.y,p.z},model.limbs[i],model.joints,0,false);low.x=std::min(low.x,v.x);low.y=std::min(low.y,v.y);low.z=std::min(low.z,v.z);high.x=std::max(high.x,v.x);high.y=std::max(high.y,v.y);high.z=std::max(high.z,v.z);}
      auto center=(low+high)*.5f;float scale=1/std::max({high.x-low.x,high.y-low.y,high.z-low.z,1.f});
      model.center={center.x,center.y,center.z};model.scale=scale;
      model.faces.resize(read.integer(1,8192));
      for(auto& face:model.faces){face.material=read.integer(-1,static_cast<int>(model.textures.size())-1);for(int i=0;i<3;i++){face.index[i]=read.integer(0,static_cast<int>(model.vertices.size())-1);face.uv[i].x=read.number();face.uv[i].y=read.number();}}
      findThrusters(model);
    }
    if(read.in.peek()!=std::char_traits<char>::eof())throw std::runtime_error("Trailing home model data");
    models=std::move(next);
  }
 public:
  void Source(const std::filesystem::path& path,const std::string& rom) {
    if(file==path&&source==rom)return;models.clear();file=path;source=rom;retry=0;
  }
  void Render(Rml::RenderManager& renderer,Rml::Vector2f offset,float t,float w,float h,float dpi,bool reduced) {
    if(source.empty()||reduced)return;
    const double now=Rml::GetSystemInterface()->GetElapsedTime();
    if(models.empty()&&now>=retry){retry=now+2;try{load();}catch(const std::exception&){} }
    if(models.empty())return;
    for(size_t m=0;m<models.size();m++) {
      const auto flight=launcher_art::flight(static_cast<int>(m),t,w,h);if(!flight.active)continue;
      auto& model=models[m];
      const auto forward=flight.forward;
      auto right=launcher_art::unit(launcher_art::cross({0,1,0},forward));
      auto up=launcher_art::cross(forward,right);
      const auto bankRight=right*std::cos(flight.bank)+up*std::sin(flight.bank);
      const auto bankUp=up*std::cos(flight.bank)-right*std::sin(flight.bank);
      const float focal=.95f*h;
      // Receding ships vanish only when their projected diameter is tiny.
      const float pixels=focal*flight.size/flight.position.z;
      const float alpha=.78f*std::clamp(pixels-1.2f,0.f,1.f);
      if(alpha<=0)continue;
      auto project=[&](launcher_art::Vec3 local,int limb) {
        const auto p=(launcher_art::pose_vertex(local,limb,model.joints,t,true)-model.center)*model.scale;
        auto world=flight.position+(bankRight*p.x+bankUp*p.y+forward*p.z)*flight.size;
        const float depth=std::max(world.z,.1f);
        return Rml::Vector3f(w*.5f+focal*world.x/depth,h*.5f-focal*world.y/depth,depth);
      };
      std::vector<Rml::Vector3f> projected;projected.reserve(model.vertices.size());
      for(size_t i=0;i<model.vertices.size();i++){auto p=model.vertices[i];projected.push_back(project({p.x,p.y,p.z},model.limbs[i]));}
      struct Triangle {
        int material=-1;std::array<Rml::Vector3f,3> points;std::array<Rml::Vector2f,3> uv{};
        std::array<Rml::ColourbPremultiplied,3> colors;
        float depth()const{return points[0].z+points[1].z+points[2].z;}
      };
      std::vector<Triangle> triangles;triangles.reserve(model.faces.size()+352);
      auto tint=[](unsigned rgb,float opacity){return Rml::Colourb((rgb>>16)&255,(rgb>>8)&255,rgb&255,
        static_cast<Rml::byte>(std::clamp(opacity,0.f,1.f)*255)).ToPremultiplied();};
      const auto hull=tint(0xffffff,alpha);
      for(const auto& face:model.faces){Triangle tri;tri.material=face.material;tri.uv=face.uv;
        for(int i=0;i<3;i++){tri.points[i]=projected[face.index[i]];tri.colors[i]=hull;}triangles.push_back(tri);}

      // Smooth ignition, a short burn with fine flutter, then a visible coast.
      // Each ship has its own phase; both engines ignite together.
      auto smooth=[](float value){value=std::clamp(value,0.f,1.f);return value*value*(3-2*value);};
      const float cycle=std::fmod(std::max(t,0.f)+static_cast<float>(m)*1.17f,3.8f);
      const float burn=smooth(cycle/.22f)*(1-smooth((cycle-2.55f)/.4f));
      if(burn>.001f)for(size_t engine=0;engine<model.thrusters.size();engine++) {
        const auto& nozzle=model.thrusters[engine];
        const float flutter=.90f+.065f*std::sin(t*23+static_cast<float>(engine)*2.1f)+.035f*std::sin(t*41+static_cast<float>(m));
        const float length=nozzle.radius*(5.6f+2.4f*burn)*flutter;
        const float strength=alpha*burn;
        auto add=[&](std::array<launcher_art::Vec3,3> points,std::array<Rml::ColourbPremultiplied,3> colors){
          Triangle tri;tri.colors=colors;for(int i=0;i<3;i++)tri.points[i]=project(points[i],nozzle.limb);triangles.push_back(tri);
        };
        constexpr int slices=10;
        constexpr float tau=6.2831853f;
        // Layered, tapered volumes share the engine's joint transform and the
        // hull's depth ordering, including when a ship turns its tail toward us.
        for(int layer=0;layer<2;layer++) {
          const float width=nozzle.radius*(layer?.53f:1.f);
          const float reach=length*(layer?.68f:1.f);
          const float z[]={0,.16f,.48f,.78f,1.f};
          const float radius[]={.62f,1.f,.67f,.31f,0};
          const unsigned outer[]={0x6dbbff,0x7894ff,0xffa14a,0xff642c,0xe84b22};
          const unsigned inner[]={0xe8faff,0xffffff,0xfff4c2,0xffc866,0xffa144};
          const float opacity[]={.48f,.58f,.4f,.17f,0};
          auto point=[&](int ring,int slice){float a=tau*slice/slices;
            return nozzle.nozzle+launcher_art::Vec3{std::cos(a)*width*radius[ring],std::sin(a)*width*radius[ring],-reach*z[ring]-nozzle.radius*.035f};};
          for(int ring=0;ring<4;ring++)for(int slice=0;slice<slices;slice++) {
            auto a=point(ring,slice),b=point(ring,slice+1),c=point(ring+1,slice+1),d=point(ring+1,slice);
            auto ringColor=tint(layer?inner[ring]:outer[ring],strength*opacity[ring]*(layer?1.5f:1.f));
            auto nextColor=tint(layer?inner[ring+1]:outer[ring+1],strength*opacity[ring+1]*(layer?1.5f:1.f));
            add({a,b,c},{ringColor,ringColor,nextColor});if(ring<3)add({a,c,d},{ringColor,nextColor,nextColor});
          }
        }
        // Soft blue ignition glow at the mouth, with a transparent rim.
        const auto center=nozzle.nozzle+launcher_art::Vec3{0,0,-nozzle.radius*.05f};
        for(int slice=0;slice<16;slice++){
          const float a=tau*slice/16,b=tau*(slice+1)/16,r=nozzle.radius*1.35f;
          add({center,center+launcher_art::Vec3{r*std::cos(a),r*std::sin(a),0},center+launcher_art::Vec3{r*std::cos(b),r*std::sin(b),0}},
              {tint(0xc9ecff,strength*.7f),tint(0x71b7ff,0),tint(0x71b7ff,0)});
        }
      }
      std::stable_sort(triangles.begin(),triangles.end(),[](const Triangle& a,const Triangle& b){return a.depth()>b.depth();});
      Rml::Mesh mesh;int material=-2;
      auto flush=[&] {
        if(mesh.indices.empty())return;
        Rml::Texture texture;
        if(material>=0){auto& tex=model.textures[material];if(!tex.gpu){auto* stable=&tex;tex.gpu=renderer.MakeCallbackTexture([stable](const Rml::CallbackTextureInterface& cb){return cb.GenerateTexture(stable->pixels,{stable->width,stable->height});});}texture=tex.gpu;}
        auto geometry=renderer.MakeGeometry(std::move(mesh));geometry.Render(offset,texture);mesh={};
      };
      for(const auto& face:triangles) {
        if(face.material!=material){flush();material=face.material;}
        const int base=static_cast<int>(mesh.vertices.size());
        for(int i=0;i<3;i++){const auto p=face.points[i];auto uv=face.uv[i];if(material>=0){uv.x/=model.textures[material].width;uv.y/=model.textures[material].height;}mesh.vertices.push_back({{p.x*dpi,p.y*dpi},face.colors[i],uv});}
        mesh.indices.insert(mesh.indices.end(),{base,base+1,base+2});
      }
      flush();
    }
  }
};
