#pragma once
#include "render/rt64_texture.h"
#include "jfg/renderer/interpolation_bridge.hpp"
#include <cstddef>
#include <cstdint>
#include <cstdlib>
#include <memory>
#include <mutex>
#include <unordered_map>
#include <vector>
namespace jfg {
// Reuse only resources that RT64 would otherwise destroy after its last
// texture-map lock releases. Contents are fully uploaded/decoded again.
// The cache's existing versions, barriers, descriptors and fences are unchanged.
// Mode 1 reuses both resources with an explicit queue handoff. Mode 2 reuses
// only decoded RGBA textures on the direct queue; each TMEM upload stays fresh.
inline unsigned texture_recycling_mode() {
    static const unsigned mode=[] {
#if defined(_MSC_VER)
        char* value=nullptr;std::size_t size=0;
        (void)_dupenv_s(&value,&size,"JFG_DIAGNOSTIC_TEXTURE_RECYCLING");
#else
        const char* value=std::getenv("JFG_DIAGNOSTIC_TEXTURE_RECYCLING");
#endif
        const unsigned result=value && value[0] && value[1]=='\0' &&
            (value[0]=='1'||value[0]=='2') ? unsigned(value[0]-'0') : 0U;
#if defined(_MSC_VER)
        std::free(value);
#endif
        return result;
    }();
    return mode;
}
inline bool texture_recycling_enabled() { return texture_recycling_mode()!=0U; }
struct TextureResourceKey {
    std::uint32_t bytes=0,width=0,height=0;
    bool decode=false;
    bool operator==(const TextureResourceKey& other) const noexcept {
        return bytes==other.bytes && width==other.width && height==other.height && decode==other.decode;
    }
};
struct TextureResourceKeyHash {
    std::size_t operator()(const TextureResourceKey& k) const noexcept {
        std::size_t h=k.bytes;
        for(auto value:{k.width,k.height,static_cast<std::uint32_t>(k.decode)})
            h^=std::size_t(value)+0x9e3779b9U+(h<<6U)+(h>>2U);
        return h;
    }
};
struct RecycledTextureResources {
    std::unique_ptr<plume::RenderTexture> tmem,rgba;
    std::size_t bytes=0;
};
struct TextureResourcePool {
    std::unordered_map<TextureResourceKey,std::vector<RecycledTextureResources>,TextureResourceKeyHash> free;
    std::size_t bytes=0,peak_bytes=0,count=0;
    std::uint64_t hits=0,misses=0,recycled=0;
};
struct TextureResourcePools {
    std::mutex mutex;
    std::unordered_map<const void*,TextureResourcePool> owners;
};
inline TextureResourcePools& texture_resource_pools() {
    static TextureResourcePools pools;
    return pools;
}
inline void create_texture_resource_pool(const void* owner) {
    if(!texture_recycling_enabled())return;
    auto& pools=texture_resource_pools();std::scoped_lock lock(pools.mutex);
    pools.owners.try_emplace(owner);
}
inline void destroy_texture_resource_pool(const void* owner) {
    if(!texture_recycling_enabled())return;
    auto& pools=texture_resource_pools();std::scoped_lock lock(pools.mutex);
    pools.owners.erase(owner);
}
inline void take_texture_resources(const void* owner,RT64::Texture& texture,
        std::uint32_t width,std::uint32_t height,std::size_t bytes,bool decode) {
    const auto mode=texture_recycling_mode();
    if(!mode || bytes>4096U || (mode==2U && !decode))return;
    auto& pools=texture_resource_pools();std::scoped_lock lock(pools.mutex);
    auto found=pools.owners.find(owner);if(found==pools.owners.end())return;
    auto& pool=found->second;
    const TextureResourceKey key{mode==2U?0U:static_cast<std::uint32_t>(bytes),width,height,decode};
    auto bucket=pool.free.find(key);
    if(bucket==pool.free.end() || bucket->second.empty()){++pool.misses;return;}
    auto resource=std::move(bucket->second.back());bucket->second.pop_back();
    if(bucket->second.empty())pool.free.erase(bucket);
    texture.tmem=std::move(resource.tmem);texture.texture=std::move(resource.rgba);
    pool.bytes-=resource.bytes;--pool.count;++pool.hits;
}
inline void recycle_texture_resources(const void* owner,RT64::Texture& texture) {
    const auto mode=texture_recycling_mode();
    if(!mode || (mode==2U && !texture.decodeTMEM) || !texture.tmem || texture.bytesTMEM.size()>4096U ||
       texture.mipmaps!=0U || texture.decodeTMEM!=bool(texture.texture) ||
       texture.format!=(texture.decodeTMEM?plume::RenderFormat::R8G8B8A8_UNORM:plume::RenderFormat::R8_UINT) ||
       texture.width>4096U || texture.height>4096U)return;
    constexpr std::size_t quantum=65536U,limit=64U*1024U*1024U;
    const auto rgba_bytes=std::size_t(texture.width)*texture.height*4U;
    const auto estimate=(mode==2U?0U:quantum)+(texture.decodeTMEM?(rgba_bytes+quantum-1U)/quantum*quantum:0U);
    if(estimate>limit)return;
    auto& pools=texture_resource_pools();std::scoped_lock lock(pools.mutex);
    auto found=pools.owners.find(owner);if(found==pools.owners.end())return;
    auto& pool=found->second;
    if(pool.count>=256U || pool.bytes>limit-estimate)return;
    const TextureResourceKey key{mode==2U?0U:static_cast<std::uint32_t>(texture.bytesTMEM.size()),
        texture.width,texture.height,texture.decodeTMEM};
    RecycledTextureResources resource;
    if(mode==1U)resource.tmem=std::move(texture.tmem);
    resource.rgba=std::move(texture.texture);resource.bytes=estimate;
    pool.free[key].push_back(std::move(resource));
    pool.bytes+=estimate;pool.peak_bytes=(std::max)(pool.peak_bytes,pool.bytes);
    ++pool.count;++pool.recycled;
}
inline void trace_texture_resource_pool(const void* owner) {
    if(!texture_recycling_enabled() || !interpolation_trace_enabled())return;
    std::uint64_t hits=0,misses=0,recycled=0;std::size_t bytes=0,peak=0,count=0;
    {
        auto& pools=texture_resource_pools();std::scoped_lock lock(pools.mutex);
        auto found=pools.owners.find(owner);if(found==pools.owners.end())return;
        const auto& pool=found->second;
        hits=pool.hits;misses=pool.misses;recycled=pool.recycled;
        bytes=pool.bytes;peak=pool.peak_bytes;count=pool.count;
    }
    trace_interpolation("texture-resource-pool",recycled,static_cast<unsigned>(hits),
        static_cast<unsigned>(misses),static_cast<unsigned>(count),0U,0.0f,bytes,peak);
}
}
