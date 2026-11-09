#include "jfg/renderer/native_blur.hpp"
#include "jfg/renderer/native_blur_mode.hpp"
#include <iostream>
#include <vector>

// Synthetic GBI fixtures for both original blur layouts. Keep the independent
// command writer separate from the recognizer so a regional offset regression
// cannot silently change the expected list too.
int main() {
    unsigned failures=0;
    const auto check=[&](bool ok,const char* what) {
        if(!ok){std::cerr << what << '\n';++failures;}
    };
    jfg::RendererGameLayout layout{};
    layout.sp_setup=0x80001000U;layout.dp_setup=0x80002000U;layout.viewports=0x80003000U;
    constexpr std::uint32_t source=0x40000U,target=0x80000U,address=0xc0000U;
    for(bool reload_viewport:{false,true}) {
        const std::size_t commands=reload_viewport?623U:621U;
        std::vector<std::uint8_t> memory(address+commands*8U);
        std::size_t cursor=address;
        auto emit=[&](std::uint32_t a,std::uint32_t b) {
            std::memcpy(memory.data()+cursor,&a,4U);
            std::memcpy(memory.data()+cursor+4U,&b,4U);cursor+=8U;
        };
        emit(0xbc000006U,0x80000000U);emit(0xbc000406U,target);
        emit(0xbc000806U,0x10000U);emit(0x06000000U,layout.sp_setup);
        emit(0x06000000U,layout.dp_setup);emit(0xb6000000U,0x10001U);
        emit(0xff10013fU,target);emit(0xed000000U,0x5003c0U);
        emit(0xbc000002U,0U);emit(0xe7000000U,0U);emit(0xb6000000U,0x1000U);
        emit(0xf9000000U,100U);emit(0xfa000000U,0xffffffffU);emit(0xfb000000U,0xffffff64U);
        if(reload_viewport){emit(0xed000000U,0x5003c0U);emit(0x03800010U,0x3000U);}
        emit(0xe7000000U,0U);emit(0xb6000000U,0x10001U);emit(0xb7000000U,0x204U);
        emit(0xfcffffffU,0xfffcf67dU);emit(0xef000ccfU,0x504240U);
        for(std::uint32_t strip=0;strip<60U;++strip) {
            emit(0xfd100000U,0x80000000U+source+strip*2560U);
            emit(0xf5100000U,0x07080200U);emit(0xe6000000U,0U);
            emit(0xf3000000U,0x074ff01aU);emit(0xe7000000U,0U);
            emit(0xf510a000U,0x00080200U);emit(0xf2000000U,0x004fc00cU);
            emit(0xe4500000U|((strip+1U)*16U),strip*16U);
            emit(0xb3000000U,0U);emit(0xb2000000U,0x04000400U);
        }
        emit(0xe9000000U,0U);emit(0xb8000000U,0U);
        check(cursor==memory.size(),"fixture extent");
        const auto pass=jfg::native_blur_pass(layout,memory,address);
        check(pass && pass->source==source && pass->target==target,"regional blur recognized");
        check(jfg::native_blur_pass(layout,memory,address|0x80000000U).has_value(),"guest address alias");
        check(!jfg::native_blur_pass(layout,memory,address+1U),"unaligned list rejected");
        check(!jfg::native_blur_pass(layout,std::span(memory).first(memory.size()-1U),address),"truncated footer rejected");
        // Change both an opcode bit and a fixed first-word parameter bit in
        // every command. Dynamic second-word colors/addresses are tested apart.
        for(std::size_t i=0;i<commands;++i) for(auto byte:{0U,3U}) {
            memory[address+i*8U+byte]^=1U;
            check(!jfg::native_blur_pass(layout,memory,address),"mutated command rejected");
            memory[address+i*8U+byte]^=1U;
        }
        auto invalid=layout;invalid.dp_setup+=8U;
        check(!jfg::native_blur_pass(invalid,memory,address),"foreign layout rejected");
        const auto original=memory;
        for(auto bad_source:{target,target-8U,0xffff0000U,source+1U}) {
            std::memcpy(memory.data()+address+(reload_viewport?21U:19U)*8U+4U,&bad_source,4U);
            check(!jfg::native_blur_pass(layout,memory,address),"invalid source rejected");
            memory=original;
        }
        for(auto mode:{jfg::BlurMode::original,jfg::BlurMode::reduced,jfg::BlurMode::off}) {
            jfg::configure_native_blur(mode);
            const auto alpha=jfg::configured_blur_color(0xffffff64U)&255U;
            check(alpha==(mode==jfg::BlurMode::original?100U:mode==jfg::BlurMode::reduced?216U:255U),"regional blur strength");
        }
    }
    return failures?1:0;
}
