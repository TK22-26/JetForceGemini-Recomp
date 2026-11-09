#pragma once
#include "jfg/renderer/enhanced_shadow.hpp"
#include "jfg/renderer/semantic_presentation.hpp"
#include "jfg/renderer/interpolation_bridge.hpp"
#include "hle/rt64_workload.h"
#include <map>
#include <set>
#include <limits>
#include <tuple>
#include <stdexcept>
namespace jfg {
inline std::shared_ptr<const EnhancedShadowFrame> collect_enhanced_shadows(
    const RT64::Workload& workload,
    std::span<const SemanticPresentationSample> samples,
    std::span<const SemanticPresentationPrevious> previous,
    std::span<const EnhancedShadowReceiver> producer_receivers={},
    std::span<const SemanticPresentationSample> producer_casters={},
    std::span<const SemanticPresentationPrevious> caster_history={},
    std::span<const EnhancedShadowProxy> proxy_casters={}) {
  if(samples.size()!=previous.size())return {};
  const bool canonical=!producer_casters.empty();
  if(canonical&&(producer_casters.size()!=samples.size()||caster_history.size()!=samples.size()))
    throw std::runtime_error("Enhanced shadows: malformed caster stream");
  const auto mesh=canonical?producer_casters:samples;
  const auto mesh_history=canonical?caster_history:previous;
  auto out=std::make_shared<EnhancedShadowFrame>();
  const auto& indices=workload.drawData.faceIndices;
  struct Caster { std::uint64_t lifetime=0; bool conflict=false; std::vector<std::uint32_t> indices; };
  using Owner=std::pair<std::uint32_t,std::uint64_t>;
  std::map<Owner,Caster> casters;
  std::set<Owner> receivers;
  using Projector=std::tuple<std::uint32_t,std::uint64_t,std::uint64_t>;
  std::map<Projector,EnhancedShadowReceiver> projectors;
  std::map<Projector,std::array<float,2>> previous_lights;
  // Viewport ownership comes from the actual draw, independent of whether
  // this scene can match the camera to its preceding interpolation endpoint.
  const auto view=[&](unsigned v){
    return v<workload.drawData.viewProjIndices.size()
        ? std::uint64_t(workload.drawData.viewProjIndices[v]) : samples[v].key[3];
  };
  const auto owner=[&](unsigned v){
    return Owner{static_cast<std::uint32_t>(mesh[v].key[1]>>32U),canonical?0U:view(v)};
  };
  const auto receiver=[&](unsigned v) {
    if(v<producer_receivers.size())return producer_receivers[v];
    const auto& s=samples[v];
    return EnhancedShadowReceiver{
      s.key[4]==0x53484144U?static_cast<std::uint32_t>(s.key[1]>>32U):0U,
      s.world,s.shadow_lift,s.valid&&s.key[4]==0x53484144U};
  };
  const auto finite=[](const auto& s){return std::all_of(s.world.begin(),s.world.end(),[](float v){return std::isfinite(v)&&std::abs(v)<1000000.0f;});};
  for(unsigned v=0;v<samples.size();++v) {
    const auto r=receiver(v);if(r.actor) {
      receivers.insert({r.actor,canonical?0U:view(v)});
      const Projector key{r.actor,view(v),r.projection};projectors[key]=r;
      if(samples[v].valid&&samples[v].key[4]==0x53484144U&&previous[v].matched)
        previous_lights[key]=previous[v].shadow_light;
    }
  }
  if(receivers.empty())return {};
  std::set<std::array<PresentationVertexKey,3>> seen_triangles;
  std::map<PresentationVertexKey,std::array<float,3>> world_points;
  for(std::size_t t=0;t+2<indices.size();t+=3) {
    const auto a=indices[t],b=indices[t+1],c=indices[t+2];
    if(a>=samples.size()||b>=samples.size()||c>=samples.size())continue;
    const auto& s=mesh[a];const auto id=owner(a);
    if(!receivers.contains(id))continue;
    const auto valid=[&](unsigned v){
      const auto& q=mesh[v];
      return q.valid&&q.key[0]&&!(q.key[0]&(1ULL<<63U))&&q.key[4]<1024U&&
        owner(v)==id&&q.key[0]==s.key[0]&&finite(q);
    };
    if(!valid(a)||!valid(b)||!valid(c))continue;
    auto& caster=casters[id];
    if(caster.lifetime&&caster.lifetime!=s.key[0])caster.conflict=true;
    caster.lifetime=s.key[0];
    if(canonical) {
      for(unsigned v:{a,b,c}) {
        const auto [it,inserted]=world_points.emplace(mesh[v].key,mesh[v].world);
        if(!inserted&&it->second!=mesh[v].world)caster.conflict=true;
      }
      std::array<PresentationVertexKey,3> key{mesh[a].key,mesh[b].key,mesh[c].key};
      std::sort(key.begin(),key.end());
      if(!seen_triangles.insert(key).second)continue;
    }
    caster.indices.insert(caster.indices.end(),{a,b,c});
  }
  std::map<Projector,unsigned> actor_map;
  const auto vertex=[&](unsigned v,float opacity) {
    const auto& s=mesh[v];const auto& p=mesh_history[v];
    EnhancedShadowVertex result{s.world,v,p.matched?p.world:s.world,opacity};
    result.current[1]-=s.shadow_lift;
    result.previous[1]-=p.matched?p.shadow_lift:s.shadow_lift;
    return result;
  };
  for(const auto& [projector,light]:projectors) {
    const Owner id{std::get<0>(projector),std::get<1>(projector)};
    const EnhancedShadowProxy* proxy=nullptr;
    for(const auto& candidate:proxy_casters)
      if(candidate.actor==id.first && candidate.projection==std::get<2>(projector)) {
        if(proxy)throw std::runtime_error("Enhanced shadows: ambiguous sprite caster");
        proxy=&candidate;
      }
    const auto found=casters.find({id.first,canonical?0U:id.second});
    if(!proxy && found==casters.end())continue;
    if(proxy && (!proxy->valid||!proxy->lifetime||proxy->current[3]<=0||proxy->previous[3]<=0||
                 proxy->vertical<=0||proxy->previous_vertical<=0))continue;
    if(!proxy && (found->second.conflict||found->second.indices.empty())) {
      trace_interpolation("enhanced-caster-conflict",0U,id.first,0U,0U,
          static_cast<unsigned>(found->second.indices.size()),0,found->second.conflict,canonical);
      continue;
    }
    EnhancedShadowActor actor;actor.actor=id.first;actor.camera=id.second;
    actor.lifetime=proxy?proxy->lifetime:found->second.lifetime;
    if(proxy)actor.proxy=*proxy;
    actor.projection=std::get<2>(projector);
    const auto prior=previous_lights.find(projector);
    const auto old_light=prior==previous_lights.end()?light.light:prior->second;
    actor.light={light.light[0],light.light[1],old_light[0],old_light[1]};
    actor.caster_start=static_cast<unsigned>(out->vertices.size());
    std::array<float,2> lo{1e9f,1e9f},hi{-1e9f,-1e9f};
    bool valid=true;
    if(proxy) {
      for(unsigned endpoint=0;endpoint<2;++endpoint) {
        const auto& center=endpoint?proxy->previous:proxy->current;
        const float vertical=endpoint?proxy->previous_vertical:proxy->vertical;
        for(unsigned l:{0U,2U})for(unsigned c=0;c<2;++c) {
          const float shear=actor.light[l+c];
          const float projected=center[c*2]+center[1]*shear;
          const float radius=std::sqrt(center[3]*center[3]+vertical*vertical*shear*shear);
          valid=valid&&std::isfinite(projected)&&std::isfinite(radius);
          lo[c]=(std::min)(lo[c],projected-radius);hi[c]=(std::max)(hi[c],projected+radius);
        }
      }
    } else for(unsigned v:found->second.indices) {
      const auto point=vertex(v,1);
      for(const auto& p:{point.current,point.previous})for(unsigned l:{0U,2U})for(unsigned c=0;c<2;++c) {
        const auto x=p[c*2]+p[1]*actor.light[l+c];valid=valid&&std::isfinite(x)&&std::abs(x)<1000000.0f;
        lo[c]=(std::min)(lo[c],x);hi[c]=(std::max)(hi[c],x);
      }
      out->vertices.push_back(point);
    }
    float size=128.0f;
    while(size<(std::max)(hi[0]-lo[0],hi[1]-lo[1])+16.0f)size*=2;
    if(!valid||!std::isfinite(size)){out->vertices.resize(actor.caster_start);continue;}
    const float texel=size/512.0f;
    actor.bounds={std::floor(((lo[0]+hi[0]-size)*0.5f)/texel)*texel,
                  std::floor(((lo[1]+hi[1]-size)*0.5f)/texel)*texel,size,1.0f/size};
    actor.caster_count=static_cast<unsigned>(out->vertices.size())-actor.caster_start;
    if(!proxy && mesh[found->second.indices.front()].key[4]==1022U)
      trace_interpolation("enhanced-limb-caster",0U,id.first,
          static_cast<unsigned>(actor.lifetime),actor.caster_count,0,0,
          std::get<2>(projector),id.second);
    actor_map[projector]=static_cast<unsigned>(out->actors.size());out->actors.push_back(actor);
  }
  // RT64 fills meshDesc later in State::fullSync. Derive the immutable
  // index ranges in the same projection/call order before that mutation.
  unsigned face_index=static_cast<unsigned>(workload.drawRanges.faceIndices.first);
  for(unsigned f=0;f<workload.fbPairCount;++f) {
    const auto& fb=workload.fbPairs[f];
    for(unsigned p=0;p<fb.projectionCount;++p) {
      const auto& proj=fb.projections[p];
      for(unsigned d=0;d<proj.gameCallCount;++d) {
        const auto& call=proj.gameCalls[d];
        if(!proj.usesViewport())continue;
        const auto first=face_index,count=call.callDesc.triangleCount*3U;
        face_index+=count;
        if(fb.colorImage.width<320U||fb.colorImage.siz!=G_IM_SIZ_16b)continue;
        if(!count||first>indices.size()||count>indices.size()-first)continue;
        const auto v=indices[first];if(v>=samples.size())continue;
        bool required=false;
        for(unsigned k=0;k<count&&!required;++k)
          required=indices[first+k]<samples.size()&&receiver(indices[first+k]).actor!=0U;
        if(!required)continue;
        const auto start=receiver(v);
        if(!start.actor||!start.valid){
          ++out->unresolved_draws;
          trace_interpolation("enhanced-shadow-missing",0U,1U,v,first,count,0,start.actor,samples[v].key[4]);
          continue;
        }
        const Owner id{start.actor,view(v)};const auto it=actor_map.find({id.first,id.second,start.projection});
        if(it==actor_map.end()){
          ++out->unresolved_draws;
          trace_interpolation("enhanced-shadow-missing",0U,2U,v,first,count,0,id.first,id.second);
          trace_interpolation("enhanced-caster-required",0U,id.first,v,first,count,
              call.callDesc.rdpParams.primColor.w,
              std::bit_cast<std::uint32_t>(start.opacity),start.projection);
          if(interpolation_trace_enabled()) {
            std::map<std::tuple<std::uint64_t,unsigned,unsigned>,unsigned> inventory;
            for(unsigned j=0;j<samples.size();++j) {
              const auto& q=mesh[j];
              if(static_cast<std::uint32_t>(q.key[1]>>32U)==id.first)
                ++inventory[{view(j),static_cast<unsigned>(q.key[4]),
                  (q.valid?1U:0U)|((q.key[0]>>63U)?2U:0U)}];
            }
            for(const auto& [key,n]:inventory)
              trace_interpolation("enhanced-caster-inventory",0U,id.first,
                static_cast<unsigned>(std::get<0>(key)),std::get<1>(key),n,0,
                std::get<2>(key),0U);
          }
          continue;
        }
        bool valid=true;
        for(unsigned k=0;k<count;++k) {
          const auto i=indices[first+k];
          if(i>=samples.size()){valid=false;break;}
          const auto r=receiver(i);
          if(!r.valid||r.actor!=id.first||view(i)!=id.second||r.projection!=start.projection||r.light!=start.light){valid=false;break;}
        }
        if(!valid){
          ++out->unresolved_draws;
          trace_interpolation("enhanced-shadow-missing",0U,3U,v,first,count,0,id.first,id.second);
          continue;
        }
        const float opacity=call.callDesc.rdpParams.primColor.w;
        if(!std::isfinite(opacity)||opacity<0.0f||opacity>1.0f){
          ++out->unresolved_draws;continue;
        }
        EnhancedShadowDraw draw{first,count,static_cast<unsigned>(out->vertices.size()),it->second};
        for(unsigned k=0;k<count;++k) {
          const auto index=indices[first+k];const auto r=receiver(index);
          const auto& sample=samples[index];const auto& prior=previous[index];
          const bool matched=sample.valid&&sample.key[4]==0x53484144U&&
              static_cast<std::uint32_t>(sample.key[1]>>32U)==r.actor&&prior.matched;
          EnhancedShadowVertex point{r.world,index,matched?prior.world:r.world,opacity*r.opacity};
          point.previous_opacity=opacity*(matched?prior.shadow_opacity:r.opacity);
          point.current[1]-=r.lift;
          point.previous[1]-=matched?prior.shadow_lift:r.lift;
          out->vertices.push_back(point);
        }
        out->draws.push_back(draw);
      }
    }
  }
  // Preserve exact receiver triangles per projector for geometric visibility.
  // Sampling a height texture at one texel quantizes raised-object boundaries.
  for(unsigned i=0;i<out->actors.size();++i) {
    std::vector<EnhancedShadowVertex> receiver_geometry;
    for(const auto& draw:out->draws)if(draw.actor_index==i)
      receiver_geometry.insert(receiver_geometry.end(),
        out->vertices.begin()+draw.receiver_start,
        out->vertices.begin()+draw.receiver_start+draw.index_count);
    auto& actor=out->actors[i];
    actor.receiver_start=static_cast<unsigned>(out->vertices.size());
    actor.receiver_count=static_cast<unsigned>(receiver_geometry.size());
    out->vertices.insert(out->vertices.end(),receiver_geometry.begin(),receiver_geometry.end());
  }
  if(out->draws.empty()&&!out->unresolved_draws)return {};
  return out;
}
}
