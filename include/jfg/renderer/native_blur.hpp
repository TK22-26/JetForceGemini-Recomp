#pragma once
#include <array>
#include "jfg/renderer/game_layout.hpp"
#include <cstdint>
#include <cstring>
#include <cstdlib>
#include <optional>
#include <span>
namespace jfg {
struct NativeBlurPass { std::uint32_t source, target; };
// Recognize the complete bounded RGBA16 320x240, sixty-strip blur operation.
// Input uses the renderer's host-word RDRAM layout. Unrecognized lists retain
// the CPU texture path required by softened intensity shadow masks.
inline std::optional<NativeBlurPass> native_blur_pass(
        const RendererGameLayout& layout,
        std::span<const std::uint8_t> memory, std::uint32_t address) noexcept {
    // PAL/JP emit the same operation without the redundant US scissor and
    // viewport reload. Validate either complete form, never a partial prefix.
    constexpr std::size_t bytes = 621U * 8U;
    address &= 0x00ffffffU;
    if ((address & 7U) || address > memory.size() || bytes > memory.size()-address)
        return std::nullopt;
    const auto word=[&](std::size_t index, unsigned half) {
        std::uint32_t value;
        std::memcpy(&value,memory.data()+address+index*8U+half*4U,4U);
        return value;
    };
    const auto command=[&](std::size_t index,std::uint32_t a,std::uint32_t b) {
        return word(index,0)==a && word(index,1)==b;
    };
    const bool reload_viewport = command(14,0xed000000U,0x5003c0U);
    const std::size_t first_strip = reload_viewport ? 21U : 19U;
    if ((first_strip+602U)*8U > memory.size()-address) return std::nullopt;
    const auto target=word(6,1), source=word(first_strip,1)&0x00ffffffU;
    constexpr std::uint32_t frame_bytes=320U*240U*2U;
    const auto framebuffer=[&](std::uint32_t value) {
        return value>=frame_bytes && !(value&7U) &&
            value<=memory.size() && frame_bytes<=memory.size()-value;
    };
    if (!framebuffer(target) || !framebuffer(source) || target==source ||
        !(target+frame_bytes<=source || source+frame_bytes<=target))
        return std::nullopt;
    const std::array<std::array<std::uint32_t,2>,14> prefix{{
        {0xbc000006U,0x80000000U},{0xbc000406U,target},
        {0xbc000806U,word(2,1)},{0x06000000U,layout.sp_setup},
        {0x06000000U,layout.dp_setup},{0xb6000000U,0x10001U},
        {0xff10013fU,target},{0xed000000U,0x5003c0U},
        {0xbc000002U,0U},{0xe7000000U,0U},{0xb6000000U,0x1000U},
        {0xf9000000U,word(11,1)&255U},{0xfa000000U,0xffffffffU},
        {0xfb000000U,0xffffff00U|(word(11,1)&255U)}}};
    if (reload_viewport && !command(15,0x03800010U,layout.viewports&0x1FFFFFFFU))
        return std::nullopt;
    const std::array<std::array<std::uint32_t,2>,5> state{{
        {0xe7000000U,0U},{0xb6000000U,0x10001U},
        {0xb7000000U,0x204U},{0xfcffffffU,0xfffcf67dU},
        {0xef000ccfU,0x504240U}}};
    if (word(2,1)>=memory.size() || (word(2,1)&7U)) return std::nullopt;
    for (std::size_t i=0;i<prefix.size();++i)
        if (!command(i,prefix[i][0],prefix[i][1])) return std::nullopt;
    for (std::size_t i=0;i<state.size();++i)
        if (!command(first_strip-state.size()+i,state[i][0],state[i][1])) return std::nullopt;
    for (std::uint32_t strip=0;strip<60U;++strip) {
        const auto i=first_strip+strip*10U;
        if (!command(i,0xfd100000U,0x80000000U+source+strip*2560U) ||
            !command(i+1,0xf5100000U,0x07080200U) ||
            !command(i+2,0xe6000000U,0U) ||
            !command(i+3,0xf3000000U,0x074ff01aU) ||
            !command(i+4,0xe7000000U,0U) ||
            !command(i+5,0xf510a000U,0x00080200U) ||
            !command(i+6,0xf2000000U,0x004fc00cU) ||
            !command(i+7,0xe4500000U|((strip+1U)*16U),strip*16U) ||
            !command(i+8,0xb3000000U,0U) ||
            !command(i+9,0xb2000000U,0x04000400U)) return std::nullopt;
    }
    if (!command(first_strip+600U,0xe9000000U,0U) || !command(first_strip+601U,0xb8000000U,0U))
        return std::nullopt;
    return NativeBlurPass{source,target};
}
}
