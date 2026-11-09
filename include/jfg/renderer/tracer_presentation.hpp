#pragma once
#include "jfg/renderer/presentation_identity.hpp"
#include "jfg/renderer/semantic_presentation.hpp"
#include <optional>

namespace jfg {
// Exact DMA range and projection binding; ambiguous ownership never matches.
inline const PresentationTracerIdentity* presentation_tracer_batch(
    const PresentationSceneIdentity& scene, std::uint32_t matrix,
    std::uint32_t source, std::uint32_t count) {
  const PresentationTracerIdentity* result=nullptr;
  if(!count || count>4U)return nullptr;
  for(const auto& tracer:scene.tracers) {
    if(tracer.matrix!=matrix || source<tracer.vertices ||
       source-tracer.vertices>=40U || (source-tracer.vertices)%10U ||
       count>(40U-(source-tracer.vertices))/10U)continue;
    if(result)return nullptr;
    result=&tracer;
  }
  return result;
}
struct TracerPresentationVertex {
  SemanticPresentationSample sample{};
  PresentationMatrix world{};
};
// Native objDrawTracer writes view-space corners. Recover their world endpoints
// so camera motion and projectile motion use the same presentation phase.
inline std::optional<TracerPresentationVertex> tracer_presentation_vertex(
    const PresentationTracerIdentity& tracer, std::uint32_t source,
    const PresentationMatrix& emitted, const std::array<float,3>& local) {
  if(!tracer.lifetime || !tracer.camera || !tracer.control ||
     source<tracer.vertices || source-tracer.vertices>=40U ||
     (source-tracer.vertices)%10U)return std::nullopt;
  const PresentationMatrix identity{1,0,0,0,0,1,0,0,0,0,1,0,0,0,0,1};
  if(!rigid_pose_matches_matrix({identity,identity,tracer.pose.projection},emitted))
    return std::nullopt;
  const auto& view=tracer.pose.view;
  for(float v:view)if(!std::isfinite(v))return std::nullopt;
  for(float v:local)if(!std::isfinite(v))return std::nullopt;
  if(view[3]!=0 || view[7]!=0 || view[11]!=0 || view[15]!=1)return std::nullopt;
  const double a=view[0],b=view[1],c=view[2],d=view[4],e=view[5],f=view[6],
      g=view[8],h=view[9],i=view[10];
  const double determinant=a*(e*i-f*h)-b*(d*i-f*g)+c*(d*h-e*g);
  if(!std::isfinite(determinant) || std::abs(determinant)<0.5 ||
     std::abs(determinant)>2.0)return std::nullopt;
  const std::array<double,9> inverse{
      (e*i-f*h)/determinant,(c*h-b*i)/determinant,(b*f-c*e)/determinant,
      (f*g-d*i)/determinant,(a*i-c*g)/determinant,(c*d-a*f)/determinant,
      (d*h-e*g)/determinant,(b*g-a*h)/determinant,(a*e-b*d)/determinant};
  TracerPresentationVertex result{};
  result.world=identity;
  for(unsigned row=0;row<3;++row)for(unsigned col=0;col<3;++col)
    result.world[row*4+col]=static_cast<float>(inverse[row*3+col]);
  for(unsigned col=0;col<3;++col) {
    double translated=0;
    for(unsigned row=0;row<3;++row)translated-=double(view[12+row])*inverse[row*3+col];
    result.world[12+col]=static_cast<float>(translated);
    double point=translated;
    for(unsigned row=0;row<3;++row)point+=double(local[row])*inverse[row*3+col];
    result.sample.world[col]=static_cast<float>(point);
  }
  for(unsigned row=0;row<4;++row)for(unsigned col=0;col<4;++col) {
    float value=0;
    for(unsigned inner=0;inner<4;++inner)value+=view[row*4+inner]*emitted[inner*4+col];
    result.sample.camera[row*4+col]=value;
  }
  for(float value:result.world)if(!std::isfinite(value))return std::nullopt;
  for(float value:result.sample.world)if(!std::isfinite(value))return std::nullopt;
  for(float value:result.sample.camera)if(!std::isfinite(value))return std::nullopt;
  result.sample.key={tracer.lifetime,(std::uint64_t(tracer.actor)<<32U)|tracer.control,
      tracer.header,tracer.camera,0x54524143U,(source-tracer.vertices)/10U};
  result.sample.valid=true;
  return result;
}
} // namespace jfg
