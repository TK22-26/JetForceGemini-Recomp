#include "jfg/renderer/door_indicator_presentation.hpp"
#include "jfg/runtime/rt64_overlay_address.hpp"
#include "jfg/renderer/glass_uv_history.hpp"
#include "jfg/renderer/presentation_identity.hpp"
#include "jfg/renderer/semantic_presentation.hpp"
#include <cstdlib>
#include <limits>
#include <random>
static void require(bool v) {
  if (!v)
    std::abort();
}
int main() {
  {
    jfg::PresentationMatrix collapsed{};
    collapsed[12]=-44.875F;collapsed[13]=-213.5F;collapsed[14]=1342;collapsed[15]=1;
    require(jfg::semantic_point_collapse(collapsed));
    auto not_collapsed=collapsed;not_collapsed[0]=1.0F/65536.0F;
    require(!jfg::semantic_point_collapse(not_collapsed));
    not_collapsed=collapsed;not_collapsed[15]=0;
    require(!jfg::semantic_point_collapse(not_collapsed));
    not_collapsed=collapsed;not_collapsed[12]=std::numeric_limits<float>::infinity();
    require(!jfg::semantic_point_collapse(not_collapsed));
    const jfg::PresentationMatrix camera{1,0,0,0,0,1,0,0,0,0,1,0,0,0,0,1};
    std::vector<jfg::SemanticPresentationSample> original(6);
    for(unsigned i=0;i<6;++i) {
      original[i].key={1,2,3,4,i<3?0U:21U,i};
      original[i].camera=camera;
      original[i].world=i<3?std::array<float,3>{float(i)*0.01F,0,0}:
          std::array<float,3>{-44.875F,-213.5F,1342};
      original[i].valid=i<3;
      original[i].point_collapsed=i>=3;
    }
    const std::array<std::uint32_t,6> triangles{0,1,2,3,4,5};
    auto samples=original;
    require(jfg::exclude_collapsed_semantic_samples(samples,triangles)==3);
    jfg::SemanticPresentationHistory history;
    (void)history.record(samples,10,true,true);
    auto moved=original;
    for(unsigned i=0;i<3;++i)moved[i].world[0]+=0.01F;
    require(jfg::exclude_collapsed_semantic_samples(moved,triangles)==3);
    const auto result=history.record(moved,12,true,true);
    for(unsigned i=0;i<3;++i)require(result[i].matched);
    for(unsigned i=3;i<6;++i)require(!result[i].matched && !moved[i].key[0]);

    // A hidden point connected to visible geometry must still reject the
    // actor, preserving the safeguard against interpolated seam gaps.
    samples=original;
    const std::array<std::uint32_t,9> connected{0,1,2,3,4,5,3,1,2};
    require(jfg::exclude_collapsed_semantic_samples(samples,connected)==2);
    require(samples[3].key[0]!=0);
    const auto held=history.record(samples,14,true,true);
    for(unsigned i=0;i<3;++i)require(!held[i].matched);

    samples=original;samples[4].world[0]+=1.0F;
    require(jfg::exclude_collapsed_semantic_samples(samples,triangles)==0);
    samples=original;samples[4].key[0]=2;
    require(jfg::exclude_collapsed_semantic_samples(samples,triangles)==0);
    samples=original;samples[4].point_collapsed=false;
    require(jfg::exclude_collapsed_semantic_samples(samples,triangles)==0);
    samples=original;
    const std::array<std::uint32_t,3> invalid{3,4,100};
    require(jfg::exclude_collapsed_semantic_samples(samples,invalid)==0);
    require(samples[3].key==original[3].key);
    const std::array<std::uint32_t,2> incomplete{3,4};
    require(jfg::exclude_collapsed_semantic_samples(samples,incomplete)==0);
  }
  // Reproduce the native opaque/transparent boundary without changing saved
  // actor state. Hidden, locked and animating indicators must remain native.
  {
    std::vector<std::uint8_t> bytes(0x1000U,0);
    const auto put8=[&](unsigned a,unsigned v){bytes[(a&0xFFFFFFU)^3U]=static_cast<std::uint8_t>(v);};
    const auto put32=[&](unsigned a,unsigned v){for(unsigned i=0;i<4;++i)put8(a+i,v>>(24-i*8));};
    constexpr unsigned actor=0x80000100U,control=0x80000300U;
    put8(actor+0x49U,67);put32(actor+0x68U,control);
    put8(control+8U,1);put32(actor+0x28U,0x3F800000U);
    jfg::PresentationGuestView ram(bytes);
    for(unsigned alpha=0;alpha<=255;++alpha) {
      put8(actor+0x39U,alpha);const auto original=bytes;
      { jfg::DoorIndicatorPresentationScope scope(bytes,actor);
        require(ram.u8(actor+0x39U)==(alpha==0?0:255));
        require(scope.applied()==(alpha>0 && alpha<255));
        if(alpha%2==0)scope.restore();
      }
      require(bytes==original);
    }
    for(unsigned scenario=0;scenario<5;++scenario) {
      put8(actor+0x39U,254);put8(actor+0x49U,67);put8(control+8U,1);
      put8(actor+0x93U,0);put32(actor+0x28U,0x3F800000U);put32(actor+0x68U,control);
      if(scenario==0)put8(control+8U,0);
      if(scenario==1)put32(actor+0x28U,0x3F000000U);
      if(scenario==2)put8(actor+0x49U,78);
      if(scenario==3)put8(actor+0x93U,6);
      if(scenario==4)put32(actor+0x68U,0x80800000U);
      const auto original=bytes;
      { jfg::DoorIndicatorPresentationScope scope(bytes,actor);require(!scope.applied()); }
      require(bytes==original);
    }
    const auto original=bytes;
    for(unsigned invalid:{0U,0x80000FFCU,0xFFFFFFFFU}) {
      jfg::DoorIndicatorPresentationScope scope(bytes,invalid);require(!scope.applied());
    }
    require(bytes==original);
  }

  // Compare the batch algorithm with the independent scalar definition,
  // including overlaps, palette ambiguity, LOD ownership and wrapped ranges.
  {
    std::mt19937 random(0x4a464742U);
    // mt19937 emits 32-bit values; result_type is wider on LP64 hosts.
    const auto random32 = [&]() { return static_cast<std::uint32_t>(random()); };
    jfg::PresentationSceneIdentity scene;
    std::array<jfg::PresentationVertexIdentity,33> batch;
    std::size_t geometry_cases=0;
    const auto check=[&](std::uint32_t matrix,std::uint32_t source,std::size_t count) {
      auto output=std::span<jfg::PresentationVertexIdentity>(batch).first(count);
      jfg::presentation_vertex_identities(scene,matrix,source,output);
      for(std::size_t i=0;i<count;++i) {
        const auto expected=jfg::presentation_vertex_identity(scene,matrix,
            source+static_cast<std::uint32_t>(i*10U));
        geometry_cases+=expected.geometry!=nullptr;
        require(output[i].owner==expected.owner && output[i].geometry==expected.geometry &&
                output[i].joint==expected.joint && output[i].vertex==expected.vertex);
      }
    };
    for(unsigned trial=0;trial<256;++trial) {
      scene.models.clear();
      for(unsigned i=0;i<32;++i) {
        jfg::PresentationModelIdentity model;
        model.actor=random32()%4U;model.lifetime=random32()%3U;
        model.palettes={0x1000U+(random32()%8U)*64U,random32()%2U?0U:0x1000U+(random32()%8U)*64U};
        model.bone_count=random32()%16U;
        model.vertices=0x4000U+(random32()%64U)*10U+(trial%7U==0?1U:0U);
        model.vertex_count=random32()%64U;
        if(trial%2U==0) {
          model.actor=i%4U;model.lifetime=1;
          model.palettes={i<4U?0x1000U+i*1024U:0U,0U};model.bone_count=8U;
        }
        if(trial%11U==0)model.vertex_count=0x80000000U+random32()%64U;
        if(trial%13U==0)model.bone_count=0x80000000U+random32()%16U;
        scene.models.push_back(model);
      }
      for(unsigned pass=0;pass<2;++pass) {
        for(const auto& model:scene.models)
          for(unsigned count:{0U,1U,16U,32U,33U})
            check(model.palettes[0]+(random32()%8U)*64U,model.vertices-(random32()%8U)*10U,count);
        check(0x1000U,0xfffffff0U,32);
        check(0x1001U,0x4000U,32);
        std::reverse(scene.models.begin(),scene.models.end());
      }
    }
    scene.models.clear();check(0,0,32);require(geometry_cases>1000U);
  }

  // Caller-owned output must reset stale matches, positions and cameras on
  // every call, including same-size, smaller and offscreen submissions.
  {
    jfg::SemanticPresentationHistory history;
    jfg::SemanticPresentationSample point{{1,2,3,4,5,6},{0,0,0},
        {1,0,0,0,0,1,0,0,0,0,1,0,0,0,0,1},true};
    std::vector<jfg::SemanticPresentationPrevious> output(64);
    history.record_into({point},10,true,true,output);
    require(output.size()==1 && !output[0].matched);
    history.record_into({point},12,true,true,output);
    require(output[0].matched && output[0].camera==point.camera);
    const auto capacity=output.capacity();
    history.record_into({point},13,false,false,output);
    require(!output[0].matched && output[0].camera==jfg::PresentationMatrix{} &&
            output[0].world==std::array<float,3>{} && output.capacity()==capacity);
    history.record_into({point},14,true,true,output);
    require(output[0].matched);
    history.record_into({},16,true,true,output);
    require(output.empty() && output.capacity()==capacity);
    history.record_into({point},18,true,true,output);
    require(!output[0].matched);
  }

  // Reusing storage must preserve identity through growth, reordered subsets,
  // offscreen passes and empty scenes; stale slots must not revive old actors.
  {
    jfg::SemanticPresentationHistory history;
    std::vector<jfg::SemanticPresentationSample> points(512);
    for (std::size_t i=0;i<points.size();++i) {
      auto& point=points[i];point.key={i+1,1,2,3,4,i};
      point.camera={1,0,0,0,0,1,0,0,0,0,1,0,0,0,0,1};
      point.world={float(i%17)*0.001f,0,0};point.valid=true;
    }
    (void)history.record(points,10,true,true);
    auto old=points;for(auto& point:points)point.world[0]+=0.01f;
    auto result=history.record(points,12,true,true);
    for(std::size_t i=0;i<points.size();++i)
      require(result[i].matched && result[i].world==old[i].world);
    for(std::size_t i=512;i<2048;++i) {
      auto point=points[i%512];point.key[0]=i+1;point.key[5]=i;points.push_back(point);
    }
    result=history.record(points,14,true,true);
    for(std::size_t i=0;i<points.size();++i)require(result[i].matched==(i<512));
    std::reverse(points.begin(),points.end());points.resize(256);
    result=history.record(points,16,true,true);
    for(const auto& point:result)require(point.matched);
    (void)history.record({},17,false,false);
    result=history.record(points,18,true,true);
    for(const auto& point:result)require(point.matched);
    (void)history.record({},20,true,true);
    result=history.record(points,22,true,true);
    for(const auto& point:result)require(!point.matched);
  }

  const jfg::PresentationMatrix identity{1, 0, 0, 0, 0, 1, 0, 0,
                                         0, 0, 1, 0, 0, 0, 0, 1};
  // A near-plane vertex can move a large screen distance during a tiny,
  // valid camera move. A bending bridge uses owned camera operands, while
  // character joints and real camera/model/deformation cuts remain strict.
  {
    jfg::RigidPresentationPose pose{identity,identity,identity};
    pose.projection[11]=1;pose.projection[15]=0;
    jfg::SemanticPresentationSample old{{90,2,3,4,0x42524944U,0},
        {1,0,0.01f},pose.projection,true};
    auto moved=old;moved.camera[12]=0.1f;moved.world[1]=0.05f;
    require(!jfg::semantic_motion_continuous(old,moved));
    jfg::SemanticRigidPoses poses{{90,pose}};
    jfg::SemanticPresentationHistory bridge;
    (void)bridge.record({old},10,true,true,nullptr,&poses);
    poses[90].view[12]=0.1f;
    require(bridge.record({moved},12,true,true,nullptr,&poses)[0].matched);
    auto jump=moved;jump.world[1]=200;
    require(!bridge.record({jump},14,true,true,nullptr,&poses)[0].matched);
    jfg::SemanticPresentationHistory camera_cut;
    (void)camera_cut.record({old},10,true,true,nullptr,&poses);
    poses[90].view[12]=1000;
    require(!camera_cut.record({moved},12,true,true,nullptr,&poses)[0].matched);
    jfg::SemanticPresentationHistory invalid_camera;
    poses[90]=pose;
    (void)invalid_camera.record({old},10,true,true,nullptr,&poses);
    auto nan_camera=moved;nan_camera.camera[0]=std::numeric_limits<float>::quiet_NaN();
    poses[90].view[12]=0.1f;
    require(!invalid_camera.record({nan_camera},12,true,true,nullptr,&poses)[0].matched);
    old.key[4]=moved.key[4]=1;
    jfg::SemanticPresentationHistory character;
    poses[90]=pose;
    (void)character.record({old},10,true,true,nullptr,&poses);
    poses[90].view[12]=0.1f;
    require(!character.record({moved},12,true,true,nullptr,&poses)[0].matched);
  }
  // A large character remains visible while an extremity crosses the camera
  // plane. Camera movement must not freeze every joint at the current phase.
  {
    const auto multiply=[](const auto& a,const auto& b) {
      jfg::PresentationMatrix out{};
      for(unsigned r=0;r<4;++r)for(unsigned c=0;c<4;++c)
        for(unsigned k=0;k<4;++k)out[r*4+c]+=a[r*4+k]*b[k*4+c];
      return out;
    };
    jfg::RigidPresentationPose old_pose;
    old_pose.world=old_pose.view=identity;
    old_pose.projection={1,0,0,0,0,1,0,0,0,0,1,1,0,0,-1,0};
    auto new_pose=old_pose;
    const float angle=0.10f,c=std::cos(angle),s=std::sin(angle);
    new_pose.view={c,0,-s,0,0,1,0,0,s,0,c,0,0,0,0,1};
    const auto old_camera=multiply(old_pose.view,old_pose.projection);
    const auto new_camera=multiply(new_pose.view,new_pose.projection);
    require(jfg::rigid_pose_matches_matrix(old_pose,old_camera));
    require(jfg::rigid_pose_matches_matrix(new_pose,new_camera));
    require(jfg::continuous_owned_camera_motion(old_pose,new_pose));
    jfg::SemanticPresentationSample body{{901,2,3,4,0,0},{0,0,100},old_camera,true};
    auto extremity=body;extremity.key[4]=1;extremity.world={100,0,5};
    const std::vector before{body,extremity};
    auto after=before;for(auto& point:after)point.camera=new_camera;
    require(jfg::semantic_motion_continuous(before[0],after[0]));
    require(!jfg::semantic_motion_continuous(before[1],after[1]));
    jfg::SemanticCameraFrames cameras{{4,{10,old_pose,old_camera}}};
    const auto run=[&](auto changed,auto next_camera, bool expected) {
      jfg::SemanticPresentationHistory h;
      cameras[4]={10,old_pose,old_camera};
      require(!h.record(before,100,true,true,nullptr,nullptr,&cameras)[0].matched);
      cameras[4]=next_camera;
      jfg::SemanticPresentationDiagnostics why;
      const auto result=h.record(changed,102,true,true,&why,nullptr,&cameras);
      for(const auto& point:result)require(point.matched==expected);
      return result;
    };
    const jfg::SemanticCameraFrame next{10,new_pose,new_camera};
    auto result=run(after,next,true);
    require(result[0].world==before[0].world && result[1].world==before[1].world);
    require(result[0].camera==old_camera && result[1].camera==old_camera);
    // At every output phase the camera and both joints share one continuous
    // endpoint pair (120 and 360 FPS), including the off-screen extremity.
    for(unsigned output_rate:{120U,360U}) {
      const unsigned phases=output_rate/30U;
      float last_x=0;bool have_last=false;
      for(unsigned phase=0;phase<=phases;++phase) {
        const float alpha=float(phase)/float(phases);
        const float x=100.0f*(old_camera[8]*(1-alpha)+new_camera[8]*alpha);
        const float w=100.0f*(old_camera[11]*(1-alpha)+new_camera[11]*alpha);
        require(std::isfinite(x/w));
        if(have_last)require(x/w>last_x);
        last_x=x/w;have_last=true;
      }
    }
    auto changed=after;changed[1].world[0]+=200;
    (void)run(changed,next,false); // actual world relocation poisons all joints
    changed=after;changed[1].valid=false;
    (void)run(changed,next,false);
    changed=after;changed[1].key[5]++; // missing logical vertex
    (void)run(changed,next,false);
    changed=after;changed[1].key[2]++; // changed model
    (void)run(changed,next,false);
    changed=after;changed[1].world[0]=std::numeric_limits<float>::quiet_NaN();
    (void)run(changed,next,false);
    changed=after;changed.push_back(after[1]);changed.back().world[1]+=1;
    (void)run(changed,next,false); // conflicting duplicate
    auto generation=next;generation.generation++;
    (void)run(after,generation,false);
    auto camera_cut=next;camera_cut.pose.view[12]=1000;
    camera_cut.matrix=multiply(camera_cut.pose.view,camera_cut.pose.projection);
    changed=after;for(auto& point:changed)point.camera=camera_cut.matrix;
    (void)run(changed,camera_cut,false);
    auto zoom_cut=next;zoom_cut.pose.projection[0]*=2;zoom_cut.pose.projection[5]*=2;
    zoom_cut.matrix=multiply(zoom_cut.pose.view,zoom_cut.pose.projection);
    changed=after;for(auto& point:changed)point.camera=zoom_cut.matrix;
    (void)run(changed,zoom_cut,false);
    auto stale=next;stale.matrix[0]+=0.1f;
    (void)run(after,stale,false); // operands must belong to the emitted matrix
    jfg::SemanticPresentationHistory unknown;
    (void)unknown.record(before,100,true,true);
    require(!unknown.record(after,102,true,true)[0].matched);
    jfg::SemanticPresentationHistory gap;
    cameras[4]={10,old_pose,old_camera};
    (void)gap.record(before,100,true,true,nullptr,nullptr,&cameras);
    cameras[4]=next;
    require(!gap.record(after,110,true,true,nullptr,nullptr,&cameras)[0].matched);
  }
  jfg::SemanticPresentationSample a{
      {1, 2, 3, 4, 5, 6}, {0, 0, 0}, identity, true};
  auto b = a;
  b.world[0] = 0.1f;
  b.camera[12] = 0.02f;
  jfg::SemanticPresentationHistory history;
  require(!history.record({a, a}, 100, true, false)[0].matched);
  auto current = history.record({b, b}, 102, true, true);
  require(current[0].matched && current[1].matched &&
          current[0].world == a.world);
  history.record({}, 103, false,
                 false); // Offscreen work cannot consume the scene history.
  a = b;
  a.world[0] = 0.2f;
  require(history.record({a}, 104, true, true)[0].matched);
  auto cut = a;
  cut.camera[12] = 2.0f;
  require(!history.record({cut}, 106, true, true)[0].matched);
  auto different = a;
  different.key[3]++;
  require(!history.record({different}, 108, true, true)[0].matched);
  require(history.record({different}, 110, true, true)[0].matched);
  different.key[0]++; // Reused actor address, new lifetime.
  require(!history.record({different}, 112, true, true)[0].matched);
  require(!history.record({different}, 200, true, true)[0].matched);

  jfg::SemanticPresentationHistory coherent;
  a.world = {0, 0, 0};
  a.camera = identity;
  b = a;
  b.key[4]++; // A second joint of the same actor.
  coherent.record({a, b}, 100, true, false);
  a.world[0] = 0.1f;
  b.world[0] = 0.1f;
  b.valid = false;
  auto blocked = coherent.record({a, b}, 102, true, true);
  require(!blocked[0].matched && !blocked[1].matched);
  b.valid = true;
  require(!coherent.record({a, b}, 104, true, true)[0].matched);
  current = coherent.record({a, b}, 106, true, true);
  require(current[0].matched && current[1].matched);
  auto duplicate = a;
  duplicate.world[0] = 0.2f;
  current = coherent.record({a, b, duplicate}, 108, true, true);
  require(!current[0].matched && !current[1].matched);
  require(!coherent.record({a, b}, 110, true, true)[0].matched);
  a.world[0] = std::numeric_limits<float>::quiet_NaN();
  require(!coherent.record({a, b}, 112, true, true)[0].matched);
  // A nonfinite vertex poisons the entire stored actor endpoint even if that
  // vertex is culled in the next scene. Valid visible parts must not reuse it.
  require(!coherent.record({b}, 114, true, true)[0].matched);
  require(coherent.record({b}, 116, true, true)[0].matched);

  // Synthetic guest layout: changing palette buffers keeps identity; frees,
  // absent actors, level changes and camera selection invalidate ownership.
  std::vector<std::uint8_t> ram(8U * 1024U * 1024U);
  const auto w32 = [&](std::uint32_t at, std::uint32_t value) {
    std::memcpy(ram.data() + (at & 0xffffffU), &value, 4);
  };
  const auto w8 = [&](std::uint32_t at, std::uint8_t value) {
    ram[(at & 0xffffffU) ^ 3U] = value;
  };
  w32(0x800FB114U, 1);
  w32(0x800F2CA4U, 0x80130000U);
  w32(0x800F2CA8U, 1);
  w32(0x80130000U, 0x80100000U);
  w32(0x80100040U, 0x80110000U);
  w32(0x8010006CU, 0x80120000U);
  w8(0x8011001FU, 1);
  w32(0x80120000U, 0x80140000U);
  w32(0x80140000U, 0x80150000U);
  w8(0x8015004EU, 1);
  w8(0x8015004FU, 2);
  w8(0x80150013U, 3);
  w32(0x80140004U, 0x80160000U);
  w32(0x80140010U, 0x80170000U);
  w32(0x80140014U, 0x80170100U);
  w32(0x80180000U, 0x80190000U);
  w32(0x800FA630U, 1);
  w32(0x800FA634U, 0);
  jfg::PresentationIdentityTracker tracker;
  tracker.camera(ram, 0x80180000U, 100);
  const auto first = tracker.capture(ram, 100);
  require(first.models.size() == 1 && first.models[0].bone_count == 2 &&
          first.models[0].vertex_count == 3);
  require(first.cameras.size() == 1 && first.cameras[0].matrix == 0x190000U);
  require(tracker.capture(ram, 102).models[0].lifetime ==
          first.models[0].lifetime);
  tracker.retire(0x80100000U);
  const auto reused = tracker.capture(ram, 104);
  require(reused.models[0].lifetime != first.models[0].lifetime);
  require(first.models[0].palettes[0] ==
          0x170000U); // Retained task metadata is immutable.
  w32(0x800F2CA8U, 0);
  tracker.capture(ram, 106);
  w32(0x800F2CA8U, 1);
  require(tracker.capture(ram, 108).models[0].lifetime !=
          reused.models[0].lifetime);
  require(tracker.capture(ram, 108)
              .cameras.empty()); // Stale camera buffer ownership expires.
  w32(0x800FB114U, 2);
  require(tracker.capture(ram, 110).models[0].lifetime !=
          reused.models[0].lifetime);
  w8(0x801000A0U, 1);
  require(tracker.capture(ram, 112).models.empty());
  w8(0x801000A0U, 0);
  w32(0x800F2CA8U, 257);
  require(tracker.capture(ram, 114).models.empty());
  // Camera snapshots must retain captured operands and reject buffer reuse.
  w32(0x800F2CA8U,1);w32(0x80180000U,0x80190000U);
  tracker.camera(ram,0x80180000U,114);
  for(unsigned i=0;i<16;++i) {
    w32(0x800FAF78U+i*4U,0x3f800000U);w32(0x800FAA70U+i*4U,0x40000000U);
    w32(0x80190000U+i*4U,i+17U);
  }
  tracker.camera_completed(ram,0x80190000U,114);
  const auto captured_camera=tracker.capture(ram,114);
  require(captured_camera.cameras.size()==1 && captured_camera.cameras[0].pose_valid);
  require(captured_camera.cameras[0].generation!=0);
  w32(0x800FAF78U,0x40800000U);
  require(tracker.capture(ram,115).cameras[0].pose.view[0]==1.0f);
  w32(0x80190004U,999U);
  require(!tracker.capture(ram,115).cameras[0].pose_valid);
  // Byte-swapped access must remain bounded even for a partial final word.
  const std::array<std::uint8_t, 5> truncated{0, 1, 2, 3, 4};
  const jfg::PresentationGuestView short_ram(truncated);
  require(short_ram.u8(4) == 0 && short_ram.u8(1) == 2);
  require(short_ram.u32(4) == 0 && short_ram.u32(0x81100000U) == 0);
  w32(0x800F2CA8U, 1);
  w8(0x8015004FU, 128);
  require(
      tracker.capture(ram, 116).models.empty()); // Guest bone count is signed.
  // Goldwood drones: compact LOD geometry shares the full model's palette.
  // A second identical enemy must not acquire the first one's vertices.
  jfg::PresentationSceneIdentity scene;
  scene.models.push_back(
      {1, 0x1000, 0x2000, 0x3000, {0x4000, 0x5000}, 0x6000, 20, 2});
  scene.models.push_back({1, 0x1000, 0x2100, 0x3100, {}, 0x7000, 8, 2});
  scene.models.push_back(
      {2, 0x1100, 0x2200, 0x3000, {0x8000, 0x9000}, 0xa000, 20, 2});
  scene.models.push_back({2, 0x1100, 0x2300, 0x3100, {}, 0xb000, 8, 2});
  auto vertex = jfg::presentation_vertex_identity(scene, 0x4040, 0x701e);
  require(vertex.owner && vertex.geometry && vertex.geometry->model == 0x3100 &&
          vertex.geometry->instance == 0x2100 && vertex.joint == 1 &&
          vertex.vertex == 3);
  vertex = jfg::presentation_vertex_identity(scene, 0x5040, 0x701e);
  require(vertex.geometry &&
          vertex.geometry->instance == 0x2100); // palette swap
  require(!jfg::presentation_vertex_identity(scene, 0x4040, 0xb01e).geometry);
  require(!jfg::presentation_vertex_identity(scene, 0x4040, 0x701f).geometry);
  require(!jfg::presentation_vertex_identity(scene, 0x4041, 0x701e).owner);
  scene.models.push_back(scene.models[0]);
  const auto ambiguous_palette = jfg::presentation_vertex_identity(scene, 0x4040, 0x701e);
  require(ambiguous_palette.owner && !ambiguous_palette.geometry);

  // Compact instances still appear in the task identity snapshot. Their
  // inline vertex bytes are not treated as pointers to a private palette.
  w8(0x8015004FU, 2);
  w8(0x8011001FU, 2);
  w32(0x80120004U, 0x80140100U);
  w32(0x80140100U, 0x80150100U);
  w32(0x80140104U, 0x80160100U);
  w8(0x8015014EU, 1);
  w8(0x8015014FU, 2);
  w8(0x80150113U, 3);
  w32(0x80140110U, 0xffff0001U);
  w32(0x80140114U, 0x00140020U);
  const auto lod = tracker.capture(ram, 118);
  require(lod.models.size() == 2 && lod.models[1].palettes[0] == 0 &&
          lod.models[1].vertices == 0x160100U);
  vertex = jfg::presentation_vertex_identity(lod, 0x170040U, 0x16010aU);
  require(vertex.geometry && vertex.geometry->instance == 0x80140100U &&
          vertex.vertex == 1);

  // Inline compact vertices can accidentally look like in-range pointers.
  // Their overlap with the palette fields must still prevent ownership.
  w32(0x80140104U, 0x80140110U);
  w32(0x80140110U, 0x80171000U);
  w32(0x80140114U, 0x80171100U);
  const auto inline_lod = tracker.capture(ram, 118);
  require(inline_lod.models.size() == 2 &&
          inline_lod.models[1].palettes[0] == 0);

  // Identical billboard assets retain distinct actor lifetimes. Address
  // reuse, object frees, expiry and level changes cannot reuse old ownership.
  w32(0x80180000U, 0x80190000U);
  tracker.sprite(ram, 0x80180000U, 0x80100000U, 0x801a0000U, 118);
  auto sprites = tracker.capture(ram, 118);
  require(sprites.sprites.size() == 1 &&
          sprites.sprites[0].anchor == 0x190000U &&
          sprites.sprites[0].lifetime == sprites.models[0].lifetime);
  const auto old_sprite = sprites.sprites[0].lifetime;
  tracker.retire(0x80100000U);
  require(tracker.capture(ram, 120).sprites.empty());
  tracker.sprite(ram, 0x80180000U, 0x80100000U, 0x801a0000U, 120);
  sprites = tracker.capture(ram, 120);
  require(sprites.sprites.size() == 1 &&
          sprites.sprites[0].lifetime != old_sprite);
  require(tracker.capture(ram, 127).sprites.empty());
  tracker.sprite(ram, 0x80180000U, 0x80100000U, 0x801a0000U, 128);
  w32(0x800FB114U, 3);
  require(tracker.capture(ram, 128).sprites.empty());
  // Multiple pickups with the same asset are separate owners, including
  // a sprite-only actor with no model array. Freeing one preserves the other.
  w32(0x800F2CA8U, 2);
  w32(0x80130004U, 0x80100200U);
  w32(0x80100240U, 0x80110200U);
  w32(0x8010026CU, 0);
  w8(0x8011021FU, 0);
  w32(0x80180004U, 0x80190010U);
  tracker.sprite(ram, 0x80180000U, 0x80100000U, 0x801a0000U, 130);
  tracker.sprite(ram, 0x80180004U, 0x80100200U, 0x801a0000U, 130);
  sprites = tracker.capture(ram, 130);
  require(sprites.sprites.size() == 2 &&
          sprites.sprites[0].sprite == sprites.sprites[1].sprite &&
          sprites.sprites[0].actor != sprites.sprites[1].actor &&
          sprites.sprites[0].lifetime != sprites.sprites[1].lifetime);
  tracker.retire(0x80100000U);
  sprites = tracker.capture(ram, 132);
  require(sprites.sprites.size() == 1 && sprites.sprites[0].actor == 0x80100200U);
  scene.models.resize(3);
  scene.models.push_back(scene.models[1]);
  scene.models.back().instance++;
  require(!jfg::presentation_vertex_identity(scene, 0x4040, 0x701e).geometry);
  // Pool particles share assets but never lifetimes. Free and immediate
  // reuse between captures must invalidate the old interpolation history.
  tracker.particles_clear();
  tracker.retire(0x80100200U);
  w8(0x801b002dU, 2);
  w32(0x801b004cU, 0x801c0000U);
  tracker.particle_sprite(ram,0x80180000U,0x801b0000U,0x801c0000U,134);
  require(tracker.capture(ram,134).sprites.empty()); // no observed allocation
  tracker.particle_allocate(ram,0x801b0000U);
  tracker.particle_sprite(ram,0x80180000U,0x801b0000U,0x801c0000U,134);
  sprites = tracker.capture(ram,134);
  require(sprites.sprites.size()==1 && sprites.sprites[0].actor==0x801b0000U);
  const auto particle_lifetime = sprites.sprites[0].lifetime;
  w8(0x801b00a5U,2);
  w32(0x801b00c4U,0x801c0000U);
  tracker.particle_allocate(ram,0x801b0078U);
  tracker.particle_sprite(ram,0x80180004U,0x801b0078U,0x801c0000U,134);
  sprites = tracker.capture(ram,134);
  require(sprites.sprites.size()==2 &&
          sprites.sprites[0].lifetime!=sprites.sprites[1].lifetime);
  tracker.particle_retire(0x801b0000U);
  tracker.particle_allocate(ram,0x801b0000U);
  require(tracker.capture(ram,136).sprites.size()==1);
  tracker.particle_sprite(ram,0x80180000U,0x801b0000U,0x801c0000U,136);
  sprites=tracker.capture(ram,136);
  require(sprites.sprites.size()==2 && sprites.sprites[0].lifetime!=particle_lifetime);
  w32(0x801b004cU,0x801c0100U); // asset changed without a fresh anchor
  require(tracker.capture(ram,136).sprites.size()==1);
  tracker.particle_sprite(ram,0x80180000U,0x801b0000U,0x801c0000U,136);
  require(tracker.capture(ram,136).sprites.size()==1);
  require(tracker.capture(ram,143).sprites.empty()); // stale anchors
  tracker.particle_allocate(ram,0); // failed allocation cannot mint ownership
  w8(0x801b00a5U,0x80); // a freed slot is never captured
  tracker.particle_sprite(ram,0x80180004U,0x801b0078U,0x801c0000U,144);
  require(tracker.capture(ram,144).sprites.empty());
  w8(0x801b00a5U,2);
  tracker.particle_sprite(ram,0x80180004U,0x801b0078U,0x801c0000U,144);
  require(tracker.capture(ram,144).sprites.size()==1);
  tracker.particles_clear();
  require(tracker.capture(ram,144).sprites.empty());
  tracker.particle_allocate(ram,0x801b0078U);
  tracker.particle_sprite(ram,0x80180004U,0x801b0078U,0x801c0000U,144);
  w32(0x800FB114U,4);
  require(tracker.capture(ram,144).sprites.empty());

  // Two-frame rigid matrix buffers preserve actor/model identity, while
  // overwritten memory, freed actors and changed camera/level must not.
  w32(0x800FB114U, 5); w32(0x800F2CA8U, 1);
  w8(0x801000A0U, 0); w8(0x8011001FU, 1);
  w32(0x80120000U, 0x80140000U); w32(0x80140000U,0x80150000U);
  w32(0x80140004U,0x80160000U); w8(0x80150013U,3);
  w8(0x8015004EU,0); w8(0x8015004FU,0);
  w32(0x800FA630U,1); w32(0x800FA634U,0);
  w32(0x800FAAB0U,0x3f800000U); w32(0x800FAF78U,0x40000000U);w32(0x800FAA70U,0x40400000U);
  jfg::PresentationIdentityTracker rigid_tracker;
  rigid_tracker.rigid(ram,0x80190000U,0x80100000U,200);
  auto rigid_scene=rigid_tracker.capture(ram,200);
  require(rigid_scene.rigids[0].pose.world[0]==1 && rigid_scene.rigids[0].pose.view[0]==2 && rigid_scene.rigids[0].pose.projection[0]==3);
  w32(0x800FAAB0U,0x40800000U); // Scratch is reused; captured operands remain immutable.
  require(rigid_tracker.capture(ram,200).rigids[0].pose.world[0]==1);
  require(rigid_scene.rigids.size()==1 && rigid_scene.models.size()==1);
  const auto rigid_key=jfg::presentation_rigid_key(rigid_scene,0x190000U,0x160000U,3);
  require(rigid_key[0]!=0 && rigid_key[3]!=0 && rigid_key[2]==0x80150000U);
  require(jfg::presentation_rigid_key(rigid_scene,0x190000U,0x160001U,1)[0]==0);
  require(jfg::presentation_rigid_key(rigid_scene,0x190000U,0x160000U,4)[0]==0);
  require(jfg::presentation_rigid_key(rigid_scene,0x190000U,0x160000U,0)[0]==0);
  rigid_tracker.rigid(ram,0x80190100U,0x80100000U,202);
  rigid_scene=rigid_tracker.capture(ram,202);
  require(jfg::presentation_rigid_key(rigid_scene,0x190100U,0x160000U,3)==rigid_key);
  w32(0x80190000U,123); // old transient buffer now belongs to other work
  require(rigid_tracker.capture(ram,202).rigids.size()==1);
  rigid_tracker.rigid(ram,0x80190200U,0x80100200U,202); // not in live actor list
  require(rigid_tracker.capture(ram,202).rigids.size()==1);
  require(rigid_tracker.capture(ram,209).rigids.empty());
  rigid_tracker.retire(0x80100000U);
  rigid_tracker.rigid(ram,0x80190000U,0x80100000U,210);
  rigid_scene=rigid_tracker.capture(ram,210);
  const auto reused_rigid=jfg::presentation_rigid_key(rigid_scene,0x190000U,0x160000U,3);
  require(reused_rigid[0]!=0 && reused_rigid[0]!=rigid_key[0]);
  rigid_scene.models.push_back(rigid_scene.models[0]);
  require(jfg::presentation_rigid_key(rigid_scene,0x190000U,0x160000U,3)[0]==0);
  w32(0x800FA634U,1);
  rigid_tracker.rigid(ram,0x80190000U,0x80100000U,212);
  rigid_scene=rigid_tracker.capture(ram,212);
  require(jfg::presentation_rigid_key(rigid_scene,0x190000U,0x160000U,3)[3]!=rigid_key[3]);
  w32(0x800FB114U,6);
  require(rigid_tracker.capture(ram,214).rigids.empty());
  rigid_tracker.rigid(ram,0x80190001U,0x80100000U,216);
  require(rigid_tracker.capture(ram,216).rigids.empty());
  {
    const auto saved_ram = ram;
    // A grounded severed body has no model array. Its explicit baked DMA
    // ranges must acquire the same rigid camera interpolation as live actors.
    w32(0x800FB114U,7); w32(0x800F2CA8U,1);
    w8(0x8011001FU,0); w32(0x8010006CU,0);
    w8(0x80100048U,0); w8(0x80100049U,64);
    w32(0x80100068U,0x801a0000U);
    w32(0x801a0004U,0x801b0000U);
    w32(0x801a000cU,0x801c0000U);
    w32(0x801a0010U,0x801c0100U);
    for (const auto dl : {0x801c0000U,0x801c0100U}) {
      w32(dl,0xE7000000U);w32(dl+4,0);
      w32(dl+8,0x04180026U);w32(dl+12,0x001b0000U);
      w32(dl+16,0x04180026U);w32(dl+20,0x001b001eU);
      w32(dl+24,0xB8000000U);w32(dl+28,0);
    }
    jfg::PresentationIdentityTracker limb_tracker;
    limb_tracker.rigid(ram,0x80190000U,0x80100000U,220);
    auto limbs=limb_tracker.capture(ram,220);
    require(limbs.models.empty() && limbs.limbs.size()==1 &&
        limbs.limbs[0].ranges.size()==2);
    const auto key=jfg::presentation_rigid_key(limbs,0x190000U,0x1b0000U,3);
    require(key[0]!=0 && key[3]!=0);
    require(jfg::presentation_rigid_key(limbs,0x190000U,0x1b001eU,3)==key);
    require(jfg::presentation_rigid_key(limbs,0x190000U,0x1b0001U,3)[0]==0);
    require(jfg::presentation_rigid_key(limbs,0x190000U,0x1b0000U,4)[0]==0);
    require(jfg::presentation_rigid_key(limbs,0x190000U,0x1b003cU,1)[0]==0);
    limb_tracker.rigid(ram,0x80190100U,0x80100000U,222);
    require(jfg::presentation_rigid_key(limb_tracker.capture(ram,222),
        0x190100U,0x1b0000U,3)==key); // transient matrix buffer swap
    limb_tracker.retire(0x80100000U);
    limb_tracker.rigid(ram,0x80190000U,0x80100000U,224);
    require(jfg::presentation_rigid_key(limb_tracker.capture(ram,224),
        0x190000U,0x1b0000U,3)[0]!=key[0]); // same addresses, new lifetime
    w32(0x801c000cU,0x001afff6U);
    require(limb_tracker.capture(ram,224).limbs.empty()); // before allocation
    w32(0x801c000cU,0x001b0001U);
    require(limb_tracker.capture(ram,224).limbs.empty()); // misaligned vertex
    w32(0x801c000cU,0x001b0000U);w32(0x801c0008U,0x06000000U);
    require(limb_tracker.capture(ram,224).limbs.empty()); // unproven nested list
    w32(0x801c0008U,0x04180026U);w32(0x801c0018U,0);w32(0x801c0118U,0);
    require(limb_tracker.capture(ram,224).limbs.empty()); // no terminator
    w32(0x801c0018U,0xB8000000U);w32(0x801c0118U,0xB8000000U);
    w8(0x80100049U,63);
    require(limb_tracker.capture(ram,224).limbs.empty()); // only native limb path
    ram = saved_ram;
  }
  {
    jfg::GlassUvHistory glass_history;
    jfg::GlassUvSample glass_sample{{1,2,3,4,5},{31.5F,8.0F},{32,32}};
    std::array samples{glass_sample};
    require(glass_history.record(samples,100)[0]==std::array<float,2>{});
    samples[0].uv={0.5F,10.0F};
    const auto velocity=glass_history.record(samples,102)[0];
    require(velocity==std::array<float,2>{1,2});
    // At half phase the reflected coordinate is the shortest wrapped midpoint.
    require(samples[0].uv[0]-velocity[0]*0.5F==0.0F);
    require(glass_history.record(samples,102)[0]==std::array<float,2>{});
    samples[0].key[0]++;
    require(glass_history.record(samples,104)[0]==std::array<float,2>{});
    samples[0].uv={2,12};
    require(glass_history.record(samples,106)[0]==std::array<float,2>{1.5F,2});
    auto glass_duplicate=samples[0];glass_duplicate.uv[0]+=1;
    std::array conflicting{samples[0],glass_duplicate};
    const auto rejected=glass_history.record(conflicting,108);
    require(rejected[0]==std::array<float,2>{} && rejected[1]==std::array<float,2>{});
    require(glass_history.record(samples,110)[0]==std::array<float,2>{});
    samples[0].uv={5,14};
    require(glass_history.record(samples,120)[0]==std::array<float,2>{}); // Missing scene.
    glass_history.clear();require(glass_history.record(samples,122)[0]==std::array<float,2>{});
    samples[0].period={0,32};
    require(glass_history.record(samples,124)[0]==std::array<float,2>{});
  }
  // Intact glass shares one quad across panes. Actor lifetime and control
  // own its motion even when the triangle/UV buffer flips. Shards and invalid
  // selectors must never keep that intact-pane key.
  {
    w8(0x80100048U,0);w8(0x80100049U,78);
    w32(0x80100068U,0x801D0000U);
    w32(0x80100088U,1);w32(0x8010008CU,0);
    w32(0x801D000CU,0x801E0000U);
    w32(0x801D0004U,0x801E0100U);w32(0x801D0008U,0x801E0200U);
    rigid_tracker.rigid(ram,0x80190000U,0x80100000U,218);
    auto panes=rigid_tracker.capture(ram,218);
    require(panes.glass.size()==1);
    // Real intact glass refers to a linked overlay constant, while F3DDKR
    // sees the translated copy in its expanded RDRAM snapshot.
    w32(0x801D000CU,0x86501134U);
    require(rigid_tracker.capture(ram,218).glass.empty());
    const auto resolve_glass=[](std::uint32_t address) {
      return jfg::translate_rt64_overlay_address(address,4U*1024U*1024U,
          {0x86500000U,0x1200U,0x00400000U});
    };
    auto expanded_ram=ram;expanded_ram.resize(8U*1024U*1024U);
    const auto resolved_panes=rigid_tracker.capture(expanded_ram,218,resolve_glass);
    require(resolved_panes.glass.size()==1);
    require(resolved_panes.glass[0].vertices==0x00401134U);
    require(jfg::presentation_rigid_key(resolved_panes,0x190000U,0x00401134U,4)[0]);
    w32(0x801D000CU,0x865011F0U); // Incomplete quad at the overlay boundary.
    expanded_ram=ram;expanded_ram.resize(8U*1024U*1024U);
    require(rigid_tracker.capture(expanded_ram,218,resolve_glass).glass.empty());
    w32(0x801D000CU,0x86501200U);
    expanded_ram=ram;expanded_ram.resize(8U*1024U*1024U);
    require(rigid_tracker.capture(expanded_ram,218,resolve_glass).glass.empty());
    w32(0x801D000CU,0x801E0000U);
    panes=rigid_tracker.capture(ram,218);
    const auto key=jfg::presentation_rigid_key(panes,0x190000U,0x1E0000U,4);
    require(key[0] && key[3]);
    w32(0x8010008CU,1);
    rigid_tracker.rigid(ram,0x80190100U,0x80100000U,220);
    panes=rigid_tracker.capture(ram,220);
    require(jfg::presentation_rigid_key(panes,0x190100U,0x1E0000U,4)==key);
    require(!jfg::presentation_rigid_key(panes,0x190100U,0x1E0001U,1)[0]);
    require(!jfg::presentation_rigid_key(panes,0x190100U,0x1E0000U,5)[0]);
    auto second=panes.glass[0];second.actor+=0x200U;second.lifetime++;
    panes.glass.push_back(second); // Shared source must not cause cross-pane ambiguity.
    require(jfg::presentation_rigid_key(panes,0x190100U,0x1E0000U,4)==key);
    panes.glass.push_back(panes.glass[0]);
    require(!jfg::presentation_rigid_key(panes,0x190100U,0x1E0000U,4)[0]);
    w32(0x8010008CU,2);require(rigid_tracker.capture(ram,220).glass.empty());
    w32(0x8010008CU,0);w32(0x80100088U,0);
    require(rigid_tracker.capture(ram,220).glass.empty());
    w32(0x80100088U,0xFFFFFFFFU);
    require(rigid_tracker.capture(ram,220).glass.empty());
    w32(0x80100088U,1);w32(0x801D0004U,0);
    require(rigid_tracker.capture(ram,220).glass.empty());
    w32(0x80100068U,0);
  }
  // Bending bridge geometry has stable actor/model/vertex ownership, even
  // when its vertex buffer changes. No other behavior gets this path.
  w8(0x80100048U,0);w8(0x80100049U,55);
  rigid_tracker.rigid(ram,0x80190000U,0x80100000U,218);
  auto bridge_scene=rigid_tracker.capture(ram,218);
  require(bridge_scene.models[0].deforming_bridge && bridge_scene.rigids.size()==1);
  const auto* bridge=jfg::presentation_bridge_vertices(
      bridge_scene,bridge_scene.rigids[0],0x16000aU,2);
  require(bridge && bridge->instance==0x80140000U);
  const auto bridge_lifetime=bridge->lifetime;
  require(!jfg::presentation_bridge_vertices(bridge_scene,bridge_scene.rigids[0],0x16000aU,3));
  require(!jfg::presentation_bridge_vertices(bridge_scene,bridge_scene.rigids[0],0x160001U,1));
  require(!jfg::presentation_bridge_vertices(bridge_scene,bridge_scene.rigids[0],0x160000U,0));
  auto wrong_bridge_owner=bridge_scene.rigids[0];++wrong_bridge_owner.actor;
  require(!jfg::presentation_bridge_vertices(bridge_scene,wrong_bridge_owner,0x160000U,1));
  wrong_bridge_owner=bridge_scene.rigids[0];++wrong_bridge_owner.lifetime;
  require(!jfg::presentation_bridge_vertices(bridge_scene,wrong_bridge_owner,0x160000U,1));
  w32(0x80140004U,0x80161000U);
  bridge_scene=rigid_tracker.capture(ram,218);
  bridge=jfg::presentation_bridge_vertices(bridge_scene,bridge_scene.rigids[0],0x16100aU,2);
  require(bridge && bridge->lifetime==bridge_lifetime && bridge->instance==0x80140000U);
  require(!jfg::presentation_bridge_vertices(bridge_scene,bridge_scene.rigids[0],0x16000aU,1));
  bridge_scene.models.push_back(bridge_scene.models[0]);
  require(!jfg::presentation_bridge_vertices(bridge_scene,bridge_scene.rigids[0],0x16100aU,1));
  w8(0x80100049U,54);bridge_scene=rigid_tracker.capture(ram,218);
  require(!jfg::presentation_bridge_vertices(bridge_scene,bridge_scene.rigids[0],0x16100aU,1));
  w32(0x80140004U,0x80160000U);
  // Procedural beam vertices retain their logical index across the two DMA
  // buffers, but never bind another owner, stale matrix or malformed state.
  w8(0x80100048U,0); w8(0x80100049U,68);
  w32(0x80100068U,0x801d0000U);
  w8(0x801d00ccU,1);w8(0x801d00cdU,0);w8(0x801d00cfU,6);
  rigid_tracker.rigid(ram,0x80190000U,0x80100000U,220);
  auto beam_scene=rigid_tracker.capture(ram,220);
  require(beam_scene.beams.size()==1 && beam_scene.rigids.size()==1);
  const auto* beam=jfg::presentation_beam_vertex(beam_scene,beam_scene.rigids[0],0x1d0046U);
  require(beam && (0x1d0046U-beam->vertices)/10U==7U);
  require(!jfg::presentation_beam_vertex(beam_scene,beam_scene.rigids[0],0x1d0050U));
  require(!jfg::presentation_beam_vertex(beam_scene,beam_scene.rigids[0],0x1d0001U));
  const auto beam_life=beam->lifetime;
  w8(0x801d00cdU,1);
  beam_scene=rigid_tracker.capture(ram,222);
  beam=jfg::presentation_beam_vertex(beam_scene,beam_scene.rigids[0],0x1d0096U);
  require(beam && beam->lifetime==beam_life && (0x1d0096U-beam->vertices)/10U==7U);
  require(!jfg::presentation_beam_vertex(beam_scene,beam_scene.rigids[0],0x1d0046U));
  auto wrong_owner=beam_scene.rigids[0];++wrong_owner.actor;
  require(!jfg::presentation_beam_vertex(beam_scene,wrong_owner,0x1d0050U));
  wrong_owner=beam_scene.rigids[0];++wrong_owner.lifetime;
  require(!jfg::presentation_beam_vertex(beam_scene,wrong_owner,0x1d0050U));
  beam_scene.beams.push_back(beam_scene.beams[0]);
  require(!jfg::presentation_beam_vertex(beam_scene,beam_scene.rigids[0],0x1d0050U));
  w8(0x801d00cdU,2);require(rigid_tracker.capture(ram,224).beams.empty());
  w8(0x801d00cdU,0);w8(0x801d00cfU,8);require(rigid_tracker.capture(ram,224).beams.empty());
  w8(0x801d00cfU,6);w8(0x801d00ccU,0);require(rigid_tracker.capture(ram,224).beams.empty());
  w8(0x801d00ccU,1);w8(0x80100049U,67);require(rigid_tracker.capture(ram,224).beams.empty());
  w8(0x80100049U,68);rigid_tracker.retire(0x80100000U);
  require(rigid_tracker.capture(ram,226).beams[0].lifetime!=beam_life);
  require(rigid_tracker.capture(ram,226).rigids.empty());
  return 0;
}
