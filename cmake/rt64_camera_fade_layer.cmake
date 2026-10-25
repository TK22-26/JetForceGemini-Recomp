# Depth-resolved player layer. Pinned upstream sources remain immutable.
file(READ "${jfg_capacity_original_root}/src/shaders/RasterPS.hlsl" original)
string(REPLACE "\r\n" "\n" original "${original}")
string(SHA256 digest "${original}")
if(NOT digest STREQUAL "957b283411550457573421015580f84ca750c68a050981dbc1a4fe2634507820")
 message(FATAL_ERROR "Pinned camera layer input changed: src/shaders/RasterPS.hlsl")
endif()
file(READ "${jfg_capacity_source}/src/shaders/RasterPS.hlsl" contents)
string(REPLACE "\r\n" "\n" contents "${contents}")
string(FIND "${contents}" [==[    // Preserve the value in the destination.]==] offset)
if(offset EQUAL -1)
 message(FATAL_ERROR "Camera layer patch site missing: src/shaders/RasterPS.hlsl")
endif()
string(REPLACE [==[    // Preserve the value in the destination.]==] [==[    // Resolve the closest player surface opaquely, then composite the layer once.
    if (instanceRDPParams[instanceIndex].cameraFade.x > 0.0f) resultAlpha.a = 1.0f;

    // Preserve the value in the destination.]==] contents "${contents}")
file(WRITE "${jfg_capacity_source}/src/shaders/RasterPS.hlsl" "${contents}")
file(READ "${jfg_capacity_original_root}/CMakeLists.txt" original)
string(REPLACE "\r\n" "\n" original "${original}")
string(SHA256 digest "${original}")
if(NOT digest STREQUAL "4d6cb49be103302c019405794995aac6b526b759f257f4786a7a2a00d4de3fa2")
 message(FATAL_ERROR "Pinned camera layer input changed: CMakeLists.txt")
endif()
file(READ "${jfg_capacity_source}/CMakeLists.txt" contents)
string(REPLACE "\r\n" "\n" contents "${contents}")
string(FIND "${contents}" [==[build_pixel_shader(  rt64 "src/shaders/TextureCopyPS.hlsl")]==] offset)
if(offset EQUAL -1)
 message(FATAL_ERROR "Camera layer patch site missing: CMakeLists.txt")
endif()
string(REPLACE [==[build_pixel_shader(  rt64 "src/shaders/TextureCopyPS.hlsl")]==] [==[build_pixel_shader(  rt64 "src/shaders/TextureCopyPS.hlsl")
build_pixel_shader(  rt64 "src/shaders/JfgCameraFadePS.hlsl")
build_pixel_shader(  rt64 "src/shaders/JfgCameraFadePS.hlsl" "src/shaders/JfgCameraFadePSMS.hlsl" "-D MULTISAMPLING")]==] contents "${contents}")
file(WRITE "${jfg_capacity_source}/CMakeLists.txt" "${contents}")
file(READ "${jfg_capacity_original_root}/src/render/rt64_shader_library.h" original)
string(REPLACE "\r\n" "\n" original "${original}")
string(SHA256 digest "${original}")
if(NOT digest STREQUAL "582214e47482b6f97b57b451a0051ff10711372c29b53e2dc870c398d8c1e075")
 message(FATAL_ERROR "Pinned camera layer input changed: src/render/rt64_shader_library.h")
endif()
file(READ "${jfg_capacity_source}/src/render/rt64_shader_library.h" contents)
string(REPLACE "\r\n" "\n" contents "${contents}")
string(FIND "${contents}" [==[        ShaderRecord textureCopy;]==] offset)
if(offset EQUAL -1)
 message(FATAL_ERROR "Camera layer patch site missing: src/render/rt64_shader_library.h")
endif()
string(REPLACE [==[        ShaderRecord textureCopy;]==] [==[        ShaderRecord textureCopy;
        ShaderRecord jfgCameraFade;]==] contents "${contents}")
file(WRITE "${jfg_capacity_source}/src/render/rt64_shader_library.h" "${contents}")
file(READ "${jfg_capacity_original_root}/src/render/rt64_shader_library.cpp" original)
string(REPLACE "\r\n" "\n" original "${original}")
string(SHA256 digest "${original}")
if(NOT digest STREQUAL "72421375b232d5449f2f90f153c8452420084f43809c3234bc9727eddfde6ffd")
 message(FATAL_ERROR "Pinned camera layer input changed: src/render/rt64_shader_library.cpp")
endif()
file(READ "${jfg_capacity_source}/src/render/rt64_shader_library.cpp" contents)
string(REPLACE "\r\n" "\n" contents "${contents}")
string(FIND "${contents}" [==[#include "shaders/TextureCopyPS.hlsl.spirv.h"]==] offset)
if(offset EQUAL -1)
 message(FATAL_ERROR "Camera layer patch site missing: src/render/rt64_shader_library.cpp")
endif()
string(REPLACE [==[#include "shaders/TextureCopyPS.hlsl.spirv.h"]==] [==[#include "shaders/TextureCopyPS.hlsl.spirv.h"
#include "shaders/JfgCameraFadePS.hlsl.spirv.h"
#include "shaders/JfgCameraFadePSMS.hlsl.spirv.h"]==] contents "${contents}")
string(FIND "${contents}" [==[#   include "shaders/TextureCopyPS.hlsl.dxil.h"]==] offset)
if(offset EQUAL -1)
 message(FATAL_ERROR "Camera layer patch site missing: src/render/rt64_shader_library.cpp")
endif()
string(REPLACE [==[#   include "shaders/TextureCopyPS.hlsl.dxil.h"]==] [==[#   include "shaders/TextureCopyPS.hlsl.dxil.h"
#   include "shaders/JfgCameraFadePS.hlsl.dxil.h"
#   include "shaders/JfgCameraFadePSMS.hlsl.dxil.h"]==] contents "${contents}")
string(FIND "${contents}" [==[#   include "shaders/TextureCopyPS.hlsl.metal.h"]==] offset)
if(offset EQUAL -1)
 message(FATAL_ERROR "Camera layer patch site missing: src/render/rt64_shader_library.cpp")
endif()
string(REPLACE [==[#   include "shaders/TextureCopyPS.hlsl.metal.h"]==] [==[#   include "shaders/TextureCopyPS.hlsl.metal.h"
#   include "shaders/JfgCameraFadePS.hlsl.metal.h"
#   include "shaders/JfgCameraFadePSMS.hlsl.metal.h"]==] contents "${contents}")
string(FIND "${contents}" [==[        // Texture Resolve.
]==] offset)
if(offset EQUAL -1)
 message(FATAL_ERROR "Camera layer patch site missing: src/render/rt64_shader_library.cpp")
endif()
string(REPLACE [==[        // Texture Resolve.
]==] [==[        // Composite the depth-resolved proximity fade, preserving native coverage.
        {
            TextureCopyDescriptorSet descriptorSet;
            layoutBuilder.begin();
            layoutBuilder.addPushConstant(0, 0, sizeof(float) * 4, RenderShaderStageFlag::PIXEL);
            layoutBuilder.addDescriptorSet(descriptorSet);
            layoutBuilder.end();
            jfgCameraFade.pipelineLayout = layoutBuilder.create(device);
            std::unique_ptr<RenderShader> pixelShader;
            if (multisampling.sampleCount > 1)
                pixelShader = device->createShader(CREATE_SHADER_INPUTS(JfgCameraFadePSMSBlobDXIL, JfgCameraFadePSMSBlobSPIRV, JfgCameraFadePSMSBlobMSL, "PSMain", shaderFormat));
            else
                pixelShader = device->createShader(CREATE_SHADER_INPUTS(JfgCameraFadePSBlobDXIL, JfgCameraFadePSBlobSPIRV, JfgCameraFadePSBlobMSL, "PSMain", shaderFormat));
            RenderGraphicsPipelineDesc pipelineDesc;
            pipelineDesc.pipelineLayout = jfgCameraFade.pipelineLayout.get();
            pipelineDesc.renderTargetBlend[0] = RenderBlendDesc::AlphaBlend();
            pipelineDesc.renderTargetBlend[0].renderTargetWriteMask = 0x7;
            pipelineDesc.renderTargetFormat[0] = RenderTarget::colorBufferFormat(usesHDR);
            pipelineDesc.renderTargetCount = 1;
            pipelineDesc.vertexShader = fullScreenVertexShader.get();
            pipelineDesc.pixelShader = pixelShader.get();
            pipelineDesc.multisampling = multisampling;
            jfgCameraFade.pipeline = device->createGraphicsPipeline(pipelineDesc);
        }

        // Texture Resolve.
]==] contents "${contents}")
file(WRITE "${jfg_capacity_source}/src/render/rt64_shader_library.cpp" "${contents}")
file(READ "${jfg_capacity_original_root}/src/render/rt64_framebuffer_renderer_call.h" original)
string(REPLACE "\r\n" "\n" original "${original}")
string(SHA256 digest "${original}")
if(NOT digest STREQUAL "e2f5eb51fd03144a02b4d7be86badfc640451cfe10477e0e1caea15b84f4ccc7")
 message(FATAL_ERROR "Pinned camera layer input changed: src/render/rt64_framebuffer_renderer_call.h")
endif()
file(READ "${jfg_capacity_source}/src/render/rt64_framebuffer_renderer_call.h" contents)
string(REPLACE "\r\n" "\n" contents "${contents}")
string(FIND "${contents}" [==[        Type type;]==] offset)
if(offset EQUAL -1)
 message(FATAL_ERROR "Camera layer patch site missing: src/render/rt64_framebuffer_renderer_call.h")
endif()
string(REPLACE [==[        Type type;]==] [==[        Type type;
        float jfgCameraOpacity = 0.0f;
        uint32_t jfgCameraActor = 0;]==] contents "${contents}")
file(WRITE "${jfg_capacity_source}/src/render/rt64_framebuffer_renderer_call.h" "${contents}")
file(READ "${jfg_capacity_original_root}/src/render/rt64_framebuffer_renderer.h" original)
string(REPLACE "\r\n" "\n" original "${original}")
string(SHA256 digest "${original}")
if(NOT digest STREQUAL "8bfe7b0d4ad16b7d8334c2e33abfdc1b288717c42c996bf4e0ac54aea918c278")
 message(FATAL_ERROR "Pinned camera layer input changed: src/render/rt64_framebuffer_renderer.h")
endif()
file(READ "${jfg_capacity_source}/src/render/rt64_framebuffer_renderer.h" contents)
string(REPLACE "\r\n" "\n" contents "${contents}")
string(FIND "${contents}" [==[            RenderViewport viewport;]==] offset)
if(offset EQUAL -1)
 message(FATAL_ERROR "Camera layer patch site missing: src/render/rt64_framebuffer_renderer.h")
endif()
string(REPLACE [==[            RenderViewport viewport;]==] [==[            RenderViewport viewport;
            std::unique_ptr<RenderTarget> jfgFadeColor;
            std::unique_ptr<RenderTarget> jfgFadeDepth;
            std::unique_ptr<RenderFramebufferStorage> jfgFadeStorage;
            std::unique_ptr<TextureCopyDescriptorSet> jfgFadeSet;]==] contents "${contents}")
string(FIND "${contents}" [==[const RasterScene &rasterScene, bool &depthState);]==] offset)
if(offset EQUAL -1)
 message(FATAL_ERROR "Camera layer patch site missing: src/render/rt64_framebuffer_renderer.h")
endif()
string(REPLACE [==[const RasterScene &rasterScene, bool &depthState);]==] [==[const RasterScene &rasterScene, bool &depthState, bool fadeLayer = false);]==] contents "${contents}")
file(WRITE "${jfg_capacity_source}/src/render/rt64_framebuffer_renderer.h" "${contents}")
file(READ "${jfg_capacity_original_root}/src/render/rt64_framebuffer_renderer.cpp" original)
string(REPLACE "\r\n" "\n" original "${original}")
string(SHA256 digest "${original}")
if(NOT digest STREQUAL "73870c23b2340611b930b668d52aec9e687fd74b7da310962b7b1ef35dee015d")
 message(FATAL_ERROR "Pinned camera layer input changed: src/render/rt64_framebuffer_renderer.cpp")
endif()
file(READ "${jfg_capacity_source}/src/render/rt64_framebuffer_renderer.cpp" contents)
string(REPLACE "\r\n" "\n" contents "${contents}")
string(FIND "${contents}" [==[        targetDrawCall.sceneIndices.clear();
]==] offset)
if(offset EQUAL -1)
 message(FATAL_ERROR "Camera layer patch site missing: src/render/rt64_framebuffer_renderer.cpp")
endif()
string(REPLACE [==[        targetDrawCall.sceneIndices.clear();
]==] [==[        targetDrawCall.sceneIndices.clear();

        const bool hasCameraFade = p.fbStorage->colorTarget && p.fbStorage->depthTarget && [&] {
            // Only this framebuffer's calls can need a layer. Color-only and
            // unrelated offscreen targets must not allocate player resources.
            for (uint32_t pr = 0; pr < fbPair.projectionCount; ++pr) {
                const Projection &proj = fbPair.projections[pr];
                if (proj.scissorRect.isNull()) continue;
                for (uint32_t d = 0; d < proj.gameCallCount; ++d) {
                    const auto index = proj.gameCalls[d].callDesc.callIndex;
                    if (index < drawData.rdpParams.size() && drawData.rdpParams[index].cameraFade.x > 0.0f)
                        return true;
                }
            }
            return false;
        }();
        if (hasCameraFade) {
            auto *color = p.fbStorage->colorTarget;
            auto *depth = p.fbStorage->depthTarget;
            if (!framebuffer.jfgFadeColor || framebuffer.jfgFadeColor->width != color->width ||
                framebuffer.jfgFadeColor->height != color->height || framebuffer.jfgFadeDepth->width != depth->width ||
                framebuffer.jfgFadeDepth->height != depth->height || framebuffer.jfgFadeColor->format != color->format ||
                framebuffer.jfgFadeColor->multisampling.sampleCount != color->multisampling.sampleCount) {
                framebuffer.jfgFadeStorage.reset();
                framebuffer.jfgFadeSet.reset();
                framebuffer.jfgFadeColor = std::make_unique<RenderTarget>(0, RT64::Framebuffer::Type::Color, color->multisampling, color->usesHDR);
                framebuffer.jfgFadeDepth = std::make_unique<RenderTarget>(0, RT64::Framebuffer::Type::Depth, depth->multisampling, depth->usesHDR);
                framebuffer.jfgFadeColor->resize(p.worker, color->width, color->height);
                framebuffer.jfgFadeDepth->resize(p.worker, depth->width, depth->height);
                framebuffer.jfgFadeStorage = std::make_unique<RenderFramebufferStorage>();
                framebuffer.jfgFadeStorage->setup(p.worker->device, {}, framebuffer.jfgFadeColor.get(), framebuffer.jfgFadeDepth.get());
                framebuffer.jfgFadeSet = std::make_unique<TextureCopyDescriptorSet>(p.worker->device);
                framebuffer.jfgFadeSet->setTexture(framebuffer.jfgFadeSet->gInput, framebuffer.jfgFadeColor->texture.get(), RenderTextureLayout::SHADER_READ, framebuffer.jfgFadeColor->textureView.get());
            }
        }
]==] contents "${contents}")
string(FIND "${contents}" [==[                uint32_t cycleType = call.callDesc.otherMode.cycleType();]==] offset)
if(offset EQUAL -1)
 message(FATAL_ERROR "Camera layer patch site missing: src/render/rt64_framebuffer_renderer.cpp")
endif()
string(REPLACE [==[                uint32_t cycleType = call.callDesc.otherMode.cycleType();]==] [==[                const auto &fade = drawData.rdpParams[call.callDesc.callIndex].cameraFade;
                instanceDrawCall.jfgCameraOpacity = hasCameraFade ? fade.x : 0.0f;
                instanceDrawCall.jfgCameraActor = hasCameraFade ? uint32_t(fade.y) : 0U;
                uint32_t cycleType = call.callDesc.otherMode.cycleType();]==] contents "${contents}")
string(FIND "${contents}" [==[                        triangles.faceCount = call.callDesc.triangleCount;]==] offset)
if(offset EQUAL -1)
 message(FATAL_ERROR "Camera layer patch site missing: src/render/rt64_framebuffer_renderer.cpp")
endif()
string(REPLACE [==[                        triangles.faceCount = call.callDesc.triangleCount;]==] [==[                        if (instanceDrawCall.jfgCameraOpacity > 0.0f) {
                            // Native transparent order, private opaque depth resolution.
                            triangles.pipeline = rasterShaderUber->getPipeline(true, true, false);
                        }
                        triangles.faceCount = call.callDesc.triangleCount;]==] contents "${contents}")
string(FIND "${contents}" [==[bool depthWrite = otherMode.zUpd();]==] offset)
if(offset EQUAL -1)
 message(FATAL_ERROR "Camera layer patch site missing: src/render/rt64_framebuffer_renderer.cpp")
endif()
string(REPLACE [==[bool depthWrite = otherMode.zUpd();]==] [==[bool depthWrite = otherMode.zUpd() || drawCall.jfgCameraOpacity > 0.0f;]==] contents "${contents}")
string(FIND "${contents}" [==[    void FramebufferRenderer::submitRasterScene(RenderWorker *worker, const Framebuffer &framebuffer, RenderFramebufferStorage *fbStorage, const RasterScene &rasterScene, bool &depthState) {]==] offset)
if(offset EQUAL -1)
 message(FATAL_ERROR "Camera layer patch site missing: src/render/rt64_framebuffer_renderer.cpp")
endif()
string(REPLACE [==[    void FramebufferRenderer::submitRasterScene(RenderWorker *worker, const Framebuffer &framebuffer, RenderFramebufferStorage *fbStorage, const RasterScene &rasterScene, bool &depthState) {]==] [==[    void FramebufferRenderer::submitRasterScene(RenderWorker *worker, const Framebuffer &framebuffer, RenderFramebufferStorage *fbStorage, const RasterScene &rasterScene, bool &depthState, bool fadeLayer) {
        const bool hasFade = !fadeLayer && framebuffer.jfgFadeStorage &&
            std::any_of(rasterScene.instanceIndices.begin(), rasterScene.instanceIndices.end(), [&](uint32_t i) { return instanceDrawCallVector[i].jfgCameraOpacity > 0.0f; });
        if (hasFade) {
            size_t pos = 0;
            while (pos < rasterScene.instanceIndices.size()) {
                const auto &first = instanceDrawCallVector[rasterScene.instanceIndices[pos]];
                const float opacity = first.jfgCameraOpacity;
                const uint32_t actor = first.jfgCameraActor;
                RasterScene group;
                do { group.instanceIndices.push_back(rasterScene.instanceIndices[pos++]); }
                while (pos < rasterScene.instanceIndices.size() &&
                    instanceDrawCallVector[rasterScene.instanceIndices[pos]].jfgCameraOpacity == opacity &&
                    instanceDrawCallVector[rasterScene.instanceIndices[pos]].jfgCameraActor == actor);
                if (opacity <= 0.0f) {
                    submitRasterScene(worker, framebuffer, fbStorage, group, depthState, true);
                    continue;
                }
                auto *layer = framebuffer.jfgFadeStorage.get();
                // Preserve both world inputs. Private depth resolves the closest model
                // surface; the main depth remains valid for later transparent objects.
                worker->commandList->setFramebuffer(nullptr);
                worker->commandList->barriers(RenderBarrierStage::COPY, {
                    RenderTextureBarrier(fbStorage->colorTarget->texture.get(), RenderTextureLayout::COPY_SOURCE),
                    RenderTextureBarrier(fbStorage->depthTarget->texture.get(), RenderTextureLayout::COPY_SOURCE),
                    RenderTextureBarrier(layer->colorTarget->texture.get(), RenderTextureLayout::COPY_DEST),
                    RenderTextureBarrier(layer->depthTarget->texture.get(), RenderTextureLayout::COPY_DEST)
                });
                worker->commandList->copyTexture(layer->colorTarget->texture.get(), fbStorage->colorTarget->texture.get());
                worker->commandList->copyTexture(layer->depthTarget->texture.get(), fbStorage->depthTarget->texture.get());
                worker->commandList->barriers(RenderBarrierStage::GRAPHICS, {
                    RenderTextureBarrier(fbStorage->colorTarget->texture.get(), RenderTextureLayout::COLOR_WRITE),
                    RenderTextureBarrier(fbStorage->depthTarget->texture.get(), RenderTextureLayout::DEPTH_WRITE),
                    RenderTextureBarrier(layer->colorTarget->texture.get(), RenderTextureLayout::COLOR_WRITE),
                    RenderTextureBarrier(layer->depthTarget->texture.get(), RenderTextureLayout::DEPTH_WRITE)
                });
                depthState = false;
                bool layerDepthState = false;
                worker->commandList->setFramebuffer(layer->colorDepthWrite.get());
                submitRasterScene(worker, framebuffer, layer, group, layerDepthState, true);
                worker->commandList->setFramebuffer(nullptr);
                worker->commandList->barriers(RenderBarrierStage::GRAPHICS,
                    RenderTextureBarrier(layer->colorTarget->texture.get(), RenderTextureLayout::SHADER_READ));
                fbStorage->colorTarget->setupColorFramebuffer(worker);
                worker->commandList->setFramebuffer(fbStorage->colorTarget->textureFramebuffer.get());
                const auto &shader = shaderLibrary->jfgCameraFade;
                worker->commandList->setGraphicsPipelineLayout(shader.pipelineLayout.get());
                worker->commandList->setPipeline(shader.pipeline.get());
                worker->commandList->setGraphicsDescriptorSet(framebuffer.jfgFadeSet->get(), 0);
                const float params[4] = { opacity, 0.0f, 0.0f, 0.0f };
                worker->commandList->setGraphicsPushConstants(0, params);
                worker->commandList->setViewports(RenderViewport(0, 0, float(fbStorage->colorTarget->width), float(fbStorage->colorTarget->height)));
                worker->commandList->setScissors(RenderRect(0, 0, fbStorage->colorTarget->width, fbStorage->colorTarget->height));
                worker->commandList->setVertexBuffers(0, nullptr, 0, nullptr);
                worker->commandList->setIndexBuffer(nullptr);
                worker->commandList->drawInstanced(3, 1, 0, 0);
                worker->commandList->setFramebuffer(fbStorage->colorDepthWrite.get());
            }
            return;
        }]==] contents "${contents}")
file(WRITE "${jfg_capacity_source}/src/render/rt64_framebuffer_renderer.cpp" "${contents}")
configure_file("${CMAKE_CURRENT_LIST_DIR}/../src/renderer/shaders/camera_fade_composite.hlsl" "${jfg_capacity_source}/src/shaders/JfgCameraFadePS.hlsl" COPYONLY)
