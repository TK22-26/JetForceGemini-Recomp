
# Only native screen effects may reuse RGBA16 screen targets while CPU shadow
# postprocessing owns intensity masks. Keep global GPU-copy policy unchanged.
function(jfg_screenfx_replace path needle replacement)
 file(READ "${jfg_capacity_source}/${path}" contents)
 string(FIND "${contents}" "${needle}" offset)
 if(offset EQUAL -1)
  message(FATAL_ERROR "Missing screen-effect patch site: ${path}")
 endif()
 string(REPLACE "${needle}" "${replacement}" contents "${contents}")
 file(WRITE "${jfg_capacity_source}/${path}" "${contents}")
endfunction()
file(READ "${jfg_capacity_original_root}/src/hle/rt64_rdp.h" original)
string(REPLACE "\r\n" "\n" original "${original}")
string(SHA256 digest "${original}")
if(NOT digest STREQUAL "876c45dec7672ef37e5a9955df713576b7f8d3806aa644b2461a3df2eeb6eda5")
 message(FATAL_ERROR "Pinned screen-effect input changed: src/hle/rt64_rdp.h")
endif()
file(READ "${jfg_capacity_original_root}/src/hle/rt64_rdp.cpp" original)
string(REPLACE "\r\n" "\n" original "${original}")
string(SHA256 digest "${original}")
if(NOT digest STREQUAL "288e186aa741a0f2ce8ff89a17d22b525fd017da81404ab709f5681c0666194c")
 message(FATAL_ERROR "Pinned screen-effect input changed: src/hle/rt64_rdp.cpp")
endif()
file(READ "${jfg_capacity_original_root}/src/hle/rt64_state.cpp" original)
string(REPLACE "\r\n" "\n" original "${original}")
string(SHA256 digest "${original}")
if(NOT digest STREQUAL "98464b469c2bdf7bb13e17bb204d41476250a23d82bba332a020e7962279ebc8")
 message(FATAL_ERROR "Pinned screen-effect input changed: src/hle/rt64_state.cpp")
endif()

jfg_screenfx_replace("src/hle/rt64_rdp.h"
 [==[        void crash(CrashReason reason);]==]
 [==[        void crash(CrashReason reason);
        bool jfgNativeScreenEffectCopy();]==])
jfg_screenfx_replace("src/hle/rt64_rdp.cpp"
 [==[#include "rt64_rdp.h"]==]
 [==[#include "rt64_rdp.h"
#include "jfg/renderer/native_screen_effect.hpp"]==])
jfg_screenfx_replace("src/hle/rt64_rdp.cpp"
 [==[    void RDP::crash(CrashReason reason) {]==]
 [==[    bool RDP::jfgNativeScreenEffectCopy() {
        if (colorImage.fmt != G_IM_FMT_RGBA || colorImage.siz != G_IM_SIZ_16b ||
            colorImage.width != 320 || texture.fmt != G_IM_FMT_RGBA ||
            texture.siz != G_IM_SIZ_16b || colorCombinerStackSize == 0)
            return false;
        const auto &combine = colorCombinerStack[colorCombinerStackSize - 1];
        if (!jfg::native_screen_effect_material(otherMode.H, otherMode.L,
                                                combine.L, combine.H))
            return false;
        const auto *source = state->framebufferManager.findMostRecentContaining(
            texture.address, texture.address + 2U);
        return source && source->lastWriteType == Framebuffer::Type::Color &&
            source->lastWriteFmt == G_IM_FMT_RGBA && source->siz == G_IM_SIZ_16b &&
            source->width == 320;
    }

    void RDP::crash(CrashReason reason) {]==])
jfg_screenfx_replace("src/hle/rt64_rdp.cpp"
 [==[const bool gpuCopiesEnabled = state->ext.emulatorConfig->framebuffer.copyWithGPU;]==]
 [==[const bool gpuCopiesEnabled = state->ext.emulatorConfig->framebuffer.copyWithGPU ||
                jfgNativeScreenEffectCopy();]==])
jfg_screenfx_replace("src/hle/rt64_state.cpp"
 [==[    void State::loadDrawState() {
        const bool gpuCopiesEnabled = ext.emulatorConfig->framebuffer.copyWithGPU;]==]
 [==[    void State::loadDrawState() {
        const bool gpuCopiesEnabled = ext.emulatorConfig->framebuffer.copyWithGPU ||
            rdp->jfgNativeScreenEffectCopy();]==])
