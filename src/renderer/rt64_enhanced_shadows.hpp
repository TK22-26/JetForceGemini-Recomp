#pragma once
#include "jfg/renderer/shadow_settings.hpp"
#include "jfg/renderer/interpolation_bridge.hpp"
#include "render/rt64_framebuffer_renderer.h"
#include <cstring>
#include <map>
#include <stdexcept>
#include <cstdio>
#if defined(_WIN32)
#include "jfg_shadow_mask_vs.dxil.h"
#include "jfg_shadow_mask_vs.spirv.h"
#include "jfg_shadow_mask_ps.dxil.h"
#include "jfg_shadow_mask_ps.spirv.h"
#include "jfg_shadow_receiver_vs.dxil.h"
#include "jfg_shadow_receiver_vs.spirv.h"
#include "jfg_shadow_receiver_ps.dxil.h"
#include "jfg_shadow_receiver_ps.spirv.h"
#endif
namespace jfg {
class EnhancedShadowRenderer {
    [[noreturn]] static void fail(const char* message) {
        // Qualification errors must retain the exact failing scene and its
        // producer evidence even when the render thread terminates.
        std::fprintf(stderr,"%s\n",message);std::fflush(stderr);
        finish_interpolation_trace();
        throw std::runtime_error(message);
    }
#if defined(_WIN32)
    using Device=plume::RenderDevice;
    struct CastSet : plume::RenderDescriptorSetBase {
        unsigned vertices;
        explicit CastSet(Device* d=nullptr) {builder.begin();vertices=builder.addStructuredBuffer(1);builder.end();if(d)create(d);}
    };
    struct ReceiveSet : plume::RenderDescriptorSetBase {
        unsigned vertices,map,screen,framebuffer;
        explicit ReceiveSet(Device* d=nullptr) {
            builder.begin();vertices=builder.addStructuredBuffer(1);map=builder.addTexture(2);
            screen=builder.addStructuredBuffer(3);framebuffer=builder.addConstantBuffer(4);
            builder.end();if(d)create(d);
        }
    };
    struct Map {
        std::unique_ptr<plume::RenderTexture> texture;
        std::unique_ptr<plume::RenderFramebuffer> framebuffer;
        std::unique_ptr<CastSet> set;
    };
    struct Constants {
        std::array<float,4> bounds{},screen{},light{};
        float alpha=1;std::uint32_t first=0;std::uint32_t receiver_first=0,receiver_count=0;
        std::array<float,4> proxy_current{},proxy_previous{},proxy_shape{};
    };
    static_assert(sizeof(Constants)==112);
    std::unique_ptr<plume::RenderPipelineLayout> cast_layout_,receive_layout_;
    std::unique_ptr<plume::RenderPipeline> cast_pipeline_;
    std::unique_ptr<plume::RenderShader> receive_vs_,receive_ps_;
    std::map<std::array<unsigned,3>,std::unique_ptr<plume::RenderPipeline>> receive_pipelines_;
    std::unique_ptr<plume::RenderBuffer> vertices_;
    std::size_t vertex_capacity_=0;
    std::vector<Map> maps_;
    std::vector<std::unique_ptr<ReceiveSet>> receive_sets_;
    std::shared_ptr<const EnhancedShadowFrame> frame_;
    std::map<std::pair<unsigned,unsigned>,unsigned> draws_;
    float alpha_=1;
    std::uint64_t tick_=0;
    void initialize(Device* device,bool dxil) {
        using namespace plume;
        if(cast_pipeline_)return;
        CastSet cs;ReceiveSet rs;
        RenderPipelineLayoutBuilder b;
        b.begin();b.addPushConstant(0,0,sizeof(Constants),RenderShaderStageFlag::VERTEX|RenderShaderStageFlag::PIXEL);
        b.addDescriptorSet(cs);b.end();cast_layout_=b.create(device);
        b.begin();b.addPushConstant(0,0,sizeof(Constants),RenderShaderStageFlag::VERTEX|RenderShaderStageFlag::PIXEL);
        b.addDescriptorSet(rs);b.end();receive_layout_=b.create(device);
        const auto format=dxil?RenderShaderFormat::DXIL:RenderShaderFormat::SPIRV;
#define JFG_SHADOW_SHADER(Name,Entry) (dxil \
        ?device->createShader(Name##BlobDXIL,Name##BlobDXIL_size,Entry,format) \
        :device->createShader(Name##BlobSPIRV,Name##BlobSPIRV_size,Entry,format))
        auto vs=JFG_SHADOW_SHADER(JfgShadowMaskVS,"MaskVS");
        auto ps=JFG_SHADOW_SHADER(JfgShadowMaskPS,"MaskPS");
        receive_vs_=JFG_SHADOW_SHADER(JfgShadowReceiverVS,"ReceiverVS");
        receive_ps_=JFG_SHADOW_SHADER(JfgShadowReceiverPS,"ReceiverPS");
#undef JFG_SHADOW_SHADER
        RenderGraphicsPipelineDesc d;d.pipelineLayout=cast_layout_.get();d.vertexShader=vs.get();d.pixelShader=ps.get();
        d.renderTargetCount=1;d.renderTargetFormat[0]=RenderFormat::R32_FLOAT;
        d.renderTargetBlend[0]=RenderBlendDesc::Copy();
        d.renderTargetBlend[0].blendEnabled=true;d.renderTargetBlend[0].blendOp=RenderBlendOperation::MAX;
        d.renderTargetBlend[0].blendOpAlpha=RenderBlendOperation::MAX;
        cast_pipeline_=device->createGraphicsPipeline(d);
    }
#endif
public:
    void prepare(RT64::RenderWorker* worker,bool dxil,const RT64::Workload& workload,float alpha) {
#if defined(_WIN32)
        using namespace plume;
        frame_.reset();draws_.clear();
        const auto snapshot=presentation_snapshot(&workload);
        if(!snapshot||!snapshot->enhanced_shadows)return;
        const auto& candidate=snapshot->enhanced_shadows;
        if(candidate->unresolved_draws)
            fail("Enhanced shadows: unresolved caster/receiver geometry; qualification blocked");
        if(candidate->draws.empty())return;
        if(!workload.outputBuffers.screenPosBuffer.buffer)
            fail("Enhanced shadows: invalid presentation resources");
        initialize(worker->device,dxil);
        const auto bytes=candidate->vertices.size()*sizeof(EnhancedShadowVertex);
        // WorkloadQueue waits for the previous submission before prepare. The
        // upload, descriptors and maps are owned exclusively by this GPU thread.
        if(bytes>vertex_capacity_) {
            vertices_=worker->device->createBuffer(RenderBufferDesc::UploadBuffer(bytes,RenderBufferFlag::STORAGE));
            vertex_capacity_=bytes;
        }
        std::memcpy(vertices_->map(),candidate->vertices.data(),bytes);vertices_->unmap();
        while(maps_.size()<candidate->actors.size()) {
            Map map;map.texture=worker->device->createTexture(RenderTextureDesc::ColorTarget(512,512,RenderFormat::R32_FLOAT));
            const RenderTexture* texture=map.texture.get();
            map.framebuffer=worker->device->createFramebuffer(RenderFramebufferDesc(&texture,1));
            map.set=std::make_unique<CastSet>(worker->device);
            maps_.push_back(std::move(map));
        }
        while(receive_sets_.size()<candidate->draws.size())receive_sets_.push_back(std::make_unique<ReceiveSet>(worker->device));
        frame_=candidate;alpha_=std::clamp(alpha,0.0f,1.0f);tick_=snapshot->tick;
        auto* c=worker->commandList.get();
        c->setFramebuffer(nullptr);
        for(std::size_t i=0;i<frame_->actors.size();++i) {
            const auto& actor=frame_->actors[i];auto& map=maps_[i];
            map.set->setBuffer(map.set->vertices,vertices_.get(),vertex_capacity_,RenderBufferStructuredView(sizeof(EnhancedShadowVertex)));
            c->barriers(RenderBarrierStage::GRAPHICS,RenderTextureBarrier(map.texture.get(),RenderTextureLayout::COLOR_WRITE));
            c->setFramebuffer(map.framebuffer.get());c->clearColor(0,RenderColor(-1e9f,-1e9f,-1e9f,-1e9f));
            c->setPipeline(cast_pipeline_.get());c->setGraphicsPipelineLayout(cast_layout_.get());
            c->setGraphicsDescriptorSet(map.set->get(),0);c->setVertexBuffers(0,nullptr,0,nullptr);c->setIndexBuffer(nullptr);
            c->setViewports(RenderViewport(0,0,512,512));c->setScissors(RenderRect(0,0,512,512));
            Constants params;params.bounds=actor.bounds;params.light=actor.light;params.alpha=alpha_;params.first=actor.caster_start;
            if(actor.proxy) {
                params.proxy_current=actor.proxy->current;params.proxy_previous=actor.proxy->previous;
                params.proxy_shape={actor.proxy->vertical,actor.proxy->previous_vertical,1,0};
            }
            c->setGraphicsPushConstants(0,&params);c->drawInstanced(actor.proxy?6U:actor.caster_count,1,0,0);
            c->setFramebuffer(nullptr);
            c->barriers(RenderBarrierStage::GRAPHICS,RenderTextureBarrier(map.texture.get(),RenderTextureLayout::SHADER_READ));
        }
        for(unsigned i=0;i<frame_->draws.size();++i) {
            const auto& draw=frame_->draws[i];auto& set=*receive_sets_[i];
            set.setBuffer(set.vertices,vertices_.get(),vertex_capacity_,RenderBufferStructuredView(sizeof(EnhancedShadowVertex)));
            set.setTexture(set.map,maps_[draw.actor_index].texture.get(),RenderTextureLayout::SHADER_READ);
            set.setBuffer(set.screen,workload.outputBuffers.screenPosBuffer.buffer.get(),
                workload.outputBuffers.screenPosBuffer.allocatedSize,RenderBufferStructuredView(sizeof(float)*4));
            draws_[{draw.first_index,draw.index_count}]=i;
        }
        trace_interpolation("enhanced-shadow-render",snapshot->tick,static_cast<unsigned>(frame_->actors.size()),
            static_cast<unsigned>(frame_->draws.size()),512,0,alpha_,frame_->vertices.size(),workload.workloadId);
#else
        (void)worker;(void)dxil;(void)alpha;
        const auto snapshot=presentation_snapshot(&workload);
        if(snapshot&&snapshot->enhanced_shadows)
            fail("Enhanced shadows are unavailable on this renderer platform");
#endif
    }
    bool eligible(const RT64::InstanceDrawCall& call) const {
#if defined(_WIN32)
        return frame_&&call.type==RT64::InstanceDrawCall::Type::IndexedTriangles&&
            draws_.find({call.triangles.indexStart,call.triangles.faceCount*3U})!=draws_.end();
#else
        (void)call;return false;
#endif
    }
    bool draw(RT64::RenderWorker* worker,RT64::RenderFramebufferStorage* target,
              const plume::RenderBuffer* fb_params,const plume::RenderViewport& viewport,
              const RT64::InstanceDrawCall& call) {
#if defined(_WIN32)
        using namespace plume;
        if(!eligible(call))fail("Enhanced shadows: unexpected receiver draw");
        if(call.triangles.vertexTestZ)fail("Enhanced shadows: unexpected vertex-depth-test receiver");
        if(!target->colorTarget||!target->depthTarget)
            fail("Enhanced shadows: receiver is missing its depth target");
        trace_interpolation("enhanced-shadow-draw",tick_,call.triangles.indexStart,
            call.triangles.faceCount*3U,call.triangles.scissor.isEmpty()?0U:1U,
            0,alpha_,0,0);
        if(call.triangles.scissor.isEmpty())return true; // Correctly clipped; no native draw.
        const auto i=draws_.at({call.triangles.indexStart,call.triangles.faceCount*3U});
        const auto& draw=frame_->draws[i];const auto& actor=frame_->actors[draw.actor_index];
        const std::array<unsigned,3> key{unsigned(target->colorTarget->format),
            unsigned(target->depthTarget->format),target->colorTarget->multisampling.sampleCount};
        auto& pipeline=receive_pipelines_[key];
        if(!pipeline) {
            RenderGraphicsPipelineDesc d;d.pipelineLayout=receive_layout_.get();d.vertexShader=receive_vs_.get();d.pixelShader=receive_ps_.get();
            d.renderTargetCount=1;d.renderTargetFormat[0]=target->colorTarget->format;
            d.renderTargetBlend[0]=RenderBlendDesc::AlphaBlend();
            // Preserve framebuffer alpha; the shadow changes scene RGB only.
            d.renderTargetBlend[0].renderTargetWriteMask=7;
            d.depthTargetFormat=target->depthTarget->format;d.depthEnabled=true;
            d.depthFunction=RenderComparisonFunction::LESS_EQUAL;d.depthWriteEnabled=false;d.depthClipEnabled=true;
            d.multisampling=target->colorTarget->multisampling;
            pipeline=worker->device->createGraphicsPipeline(d);
        }
        auto& set=*receive_sets_[i];set.setBuffer(set.framebuffer,fb_params);
        auto* c=worker->commandList.get();
        c->setFramebuffer(target->colorDepthWrite.get());
        c->setPipeline(pipeline.get());c->setGraphicsPipelineLayout(receive_layout_.get());
        c->setGraphicsDescriptorSet(set.get(),0);c->setVertexBuffers(0,nullptr,0,nullptr);c->setIndexBuffer(nullptr);
        c->setViewports(viewport);c->setScissors(call.triangles.scissor);
        Constants params;params.bounds=actor.bounds;params.light=actor.light;params.alpha=alpha_;params.first=draw.receiver_start;
        params.receiver_first=actor.receiver_start;params.receiver_count=actor.receiver_count;
        params.screen={call.triangles.screenScale.x,call.triangles.screenScale.y,call.triangles.screenOffset.x,call.triangles.screenOffset.y};
        c->setGraphicsPushConstants(0,&params);c->drawInstanced(draw.index_count,1,0,0);
        target->colorTarget->markForResolve();return true;
#else
        (void)worker;(void)target;(void)fb_params;(void)viewport;(void)call;return false;
#endif
    }
};
inline EnhancedShadowRenderer& enhanced_shadow_renderer() {
    thread_local EnhancedShadowRenderer renderer;return renderer;
}
}
