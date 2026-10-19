#pragma once
#include "render/rt64_render_target.h"
#if defined(_WIN32)
#include "jfg_blur_history.dxil.h"
#include "jfg_blur_history.spirv.h"
#include "shaders/FullScreenVS.hlsl.dxil.h"
#include "shaders/FullScreenVS.hlsl.spirv.h"
#endif
namespace jfg {
// Private mode-four qualification: interpolate the older temporal image too.
// The normal native blur draw and its blend coefficient are still executed.
class BlurHistoryBlend {
#if defined(_WIN32)
    using Device = plume::RenderDevice;
    struct Descriptors : plume::RenderDescriptorSetBase {
        unsigned previous, current;
        explicit Descriptors(Device* device = nullptr) {
            builder.begin();previous=builder.addTexture(1);current=builder.addTexture(2);builder.end();
            if(device)create(device);
        }
    };
    std::unique_ptr<plume::RenderPipeline> pipeline_;
    std::unique_ptr<plume::RenderPipelineLayout> layout_;
    std::unique_ptr<Descriptors> descriptors_;
#endif
public:
    void prepare(plume::RenderDevice* device, bool dxil, bool hdr) {
#if defined(_WIN32)
        using namespace RT64;
        using namespace plume;
        if(pipeline_) return;
        Descriptors description;
        RenderPipelineLayoutBuilder layout;
        layout.begin();layout.addPushConstant(0,0,16U,RenderShaderStageFlag::PIXEL);
        layout.addDescriptorSet(description);layout.end();
        layout_=layout.create(device);
        const auto format=dxil ? RenderShaderFormat::DXIL : RenderShaderFormat::SPIRV;
        auto vertex=dxil
            ? device->createShader(FullScreenVSBlobDXIL,FullScreenVSBlobDXIL_size,"VSMain",format)
            : device->createShader(FullScreenVSBlobSPIRV,FullScreenVSBlobSPIRV_size,"VSMain",format);
        auto pixel=dxil
            ? device->createShader(JfgBlurHistoryBlobDXIL,JfgBlurHistoryBlobDXIL_size,"PSMain",format)
            : device->createShader(JfgBlurHistoryBlobSPIRV,JfgBlurHistoryBlobSPIRV_size,"PSMain",format);
        RenderGraphicsPipelineDesc desc;
        desc.pipelineLayout=layout_.get();desc.vertexShader=vertex.get();desc.pixelShader=pixel.get();
        desc.renderTargetBlend[0]=RenderBlendDesc::Copy();
        desc.renderTargetFormat[0]=RenderTarget::colorBufferFormat(hdr);desc.renderTargetCount=1;
        pipeline_=device->createGraphicsPipeline(desc);
        descriptors_=std::make_unique<Descriptors>(device);
#else
        (void)device;(void)dxil;(void)hdr;
#endif
    }
    bool draw(RT64::RenderWorker* worker, RT64::RenderTarget& previous,
              RT64::RenderTarget& current, RT64::RenderTarget& target, float alpha) {
#if defined(_WIN32)
        using namespace RT64;
        using namespace plume;
        if(!pipeline_ || target.multisampling.sampleCount!=1U) return false;
        auto* commands=worker->commandList.get();
        RenderTextureBarrier barriers[]={
            RenderTextureBarrier(previous.texture.get(),RenderTextureLayout::SHADER_READ),
            RenderTextureBarrier(current.texture.get(),RenderTextureLayout::SHADER_READ),
            RenderTextureBarrier(target.texture.get(),RenderTextureLayout::COLOR_WRITE)
        };
        commands->barriers(RenderBarrierStage::GRAPHICS,barriers,3U);
        descriptors_->setTexture(descriptors_->previous,previous.texture.get(),RenderTextureLayout::SHADER_READ,previous.textureView.get());
        descriptors_->setTexture(descriptors_->current,current.texture.get(),RenderTextureLayout::SHADER_READ,current.textureView.get());
        target.setupColorFramebuffer(worker);
        commands->setFramebuffer(target.textureFramebuffer.get());
        commands->setPipeline(pipeline_.get());commands->setGraphicsPipelineLayout(layout_.get());
        commands->setVertexBuffers(0,nullptr,0,nullptr);
        commands->setViewports(RenderViewport(0.0f,0.0f,float(target.width),float(target.height)));
        commands->setScissors(RenderRect(0,0,target.width,target.height));
        commands->setGraphicsDescriptorSet(descriptors_->get(),0U);
        const float constants[4]={alpha,0.0f,0.0f,0.0f};
        commands->setGraphicsPushConstants(0U,constants);
        commands->drawInstanced(3,1,0,0);target.markForResolve();
        return true;
#else
        (void)worker;(void)previous;(void)current;(void)target;(void)alpha;return false;
#endif
    }
};
inline BlurHistoryBlend& blur_history_blend() {
    thread_local BlurHistoryBlend blend;
    return blend;
}
}
