# Private resource-recycling experiment. Reuse begins only at the existing
# last-user retirement point, with exact dimensions/formats and bounded storage.
jfg_texture_profile_replace(
 "#include \"rt64_texture_cache.h\""
 "#include \"rt64_texture_cache.h\"\n#include \"jfg/renderer/texture_resource_pool.hpp\"")
jfg_texture_profile_replace(
 "        this->shaderLibrary = shaderLibrary;"
 "        this->shaderLibrary = shaderLibrary;\n        jfg::create_texture_resource_pool(this);")
jfg_texture_profile_replace(
 "        uploadResourcePool.reset(nullptr);"
 "        uploadResourcePool.reset(nullptr);\n        jfg::destroy_texture_resource_pool(this);")
jfg_texture_profile_replace(
 "                    Texture *newTexture = new Texture();"
 "                    Texture *newTexture = new Texture();\n                    jfg::take_texture_resources(this,*newTexture,upload.width,upload.height,upload.bytesTMEM.size(),upload.decodeTMEM);")
jfg_texture_profile_replace(
 "                    newTexture->tmem = copyWorker->device->createTexture("
 "                    if (!newTexture->tmem) newTexture->tmem = copyWorker->device->createTexture(")
jfg_texture_profile_replace(
 "                        dstTexture->texture = directWorker->device->createTexture("
 "                        if (!dstTexture->texture) dstTexture->texture = directWorker->device->createTexture(")
jfg_texture_profile_replace(
 "            for (Texture *texture : textureMap.evictedTextures) {\n                delete texture;"
 "            for (Texture *texture : textureMap.evictedTextures) {\n                jfg::recycle_texture_resources(this,*texture);\n                delete texture;")
jfg_texture_profile_replace(
 "                jfgUploadProfile.finish();"
 "                jfgUploadProfile.finish();\n                jfg::trace_texture_resource_pool(this);")

# TMEM is read on a direct queue, but uploaded on a copy queue. The pinned
# D3D12 copy worker intentionally emits no transition barriers. Retired reused
# TMEM must reach COMMON on the direct queue before any new copy is submitted.
jfg_texture_profile_replace(
 "        std::vector<RenderTextureBarrier> beforeCopyBarriers;"
 "        std::vector<RenderTextureBarrier> beforeCopyBarriers;\n        std::vector<RenderTextureBarrier> jfgRecycledTMEMBarriers;")
jfg_texture_profile_replace(
 "            beforeCopyBarriers.clear();"
 "            beforeCopyBarriers.clear();\n            jfgRecycledTMEMBarriers.clear();")
jfg_texture_profile_replace(
 "                    jfg::take_texture_resources(this,*newTexture,upload.width,upload.height,upload.bytesTMEM.size(),upload.decodeTMEM);"
 "                    jfg::take_texture_resources(this,*newTexture,upload.width,upload.height,upload.bytesTMEM.size(),upload.decodeTMEM);\n                    if (newTexture->tmem) jfgRecycledTMEMBarriers.emplace_back(newTexture->tmem.get(),RenderTextureLayout::GENERAL);")
jfg_texture_profile_replace(
 "                copyWorker->commandList->barriers(RenderBarrierStage::COPY, beforeCopyBarriers);"
 "                if (!jfgRecycledTMEMBarriers.empty()) {\n                    const auto jfgHandoffStart=std::chrono::steady_clock::now();\n                    directWorker->commandList->begin();\n                    directWorker->commandList->barriers(RenderBarrierStage::GRAPHICS_AND_COMPUTE,jfgRecycledTMEMBarriers);\n                    directWorker->commandList->end();\n                    directWorker->execute();\n                    directWorker->wait();\n                    if (jfg::interpolation_trace_enabled()) jfg::trace_interpolation(\"texture-recycle-handoff\",0U,static_cast<unsigned>(jfgRecycledTMEMBarriers.size()),0U,0U,0U,0.0f,\n                        std::chrono::duration_cast<std::chrono::nanoseconds>(std::chrono::steady_clock::now()-jfgHandoffStart).count(),0U);\n                }\n                copyWorker->commandList->barriers(RenderBarrierStage::COPY, beforeCopyBarriers);")
