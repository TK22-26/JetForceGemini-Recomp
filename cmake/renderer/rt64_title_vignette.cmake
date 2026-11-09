
# Reconstruct the authored title vignette's I4 alpha at display resolution.
# No source assets are redistributed. The material and tile bounds identify
# the native mask; user-provided high-resolution replacements remain untouched.
file(READ "${jfg_capacity_original_root}/src/shaders/RasterPS.hlsl" original)
string(REPLACE "\r\n" "\n" original "${original}")
string(SHA256 digest "${original}")
if(NOT digest STREQUAL "957b283411550457573421015580f84ca750c68a050981dbc1a4fe2634507820")
 message(FATAL_ERROR "Pinned vignette shader input changed")
endif()
file(READ "${jfg_capacity_source}/src/shaders/RasterPS.hlsl" contents)
set(needle [==[        texVal0 = sampleTexture(otherMode, rp.flags, textureUV, ddxVertexUV, ddyVertexUV, rdpTile, gpuTile, false);]==])
string(FIND "${contents}" "${needle}" offset)
if(offset EQUAL -1)
 message(FATAL_ERROR "Missing vignette texture sampling patch site")
endif()
set(replacement [==[        texVal0 = sampleTexture(otherMode, rp.flags, textureUV, ddxVertexUV, ddyVertexUV, rdpTile, gpuTile, false);
        // Native title mask: only 16 alpha levels. Reconstruct its transition
        // in floating point before blending; never filter the hallway itself.
        if (rp.ccL == 0xFC121624U && rp.ccH == 0xFF2FFFFFU &&
            otherMode.L == 0x00504340U &&
            rdpTile.fmt == G_IM_FMT_I && rdpTile.siz == G_IM_SIZ_4b &&
            rdpTile.lrs - rdpTile.uls == 316.0f &&
            rdpTile.lrt - rdpTile.ult == 236.0f &&
            FbParams.resolutionScale.y > 1.0f && !gpuTileFlagHighRes(gpuTile.flags)) {
            float4 reconstructed = 0.0f;
            // Nine bilinear samples approximate a small separable low-pass
            // kernel. Preserve native tile clamping/mirroring at quadrant joins.
            [unroll] for (int fy = -1; fy <= 1; ++fy) {
                [unroll] for (int fx = -1; fx <= 1; ++fx) {
                    const float weight = (fx == 0 ? 0.5f : 0.25f) * (fy == 0 ? 0.5f : 0.25f);
                    reconstructed += weight * sampleTexture(otherMode, rp.flags,
                        vertexUV + float2(fx, fy) * 1.5f, ddxVertexUV, ddyVertexUV,
                        rdpTile, gpuTile, false);
                }
            }
            texVal0 = reconstructed;
        }]==])
string(REPLACE "${needle}" "${replacement}" contents "${contents}")
file(WRITE "${jfg_capacity_source}/src/shaders/RasterPS.hlsl" "${contents}")
