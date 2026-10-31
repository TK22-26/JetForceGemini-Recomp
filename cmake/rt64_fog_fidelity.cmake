# Tawfret fog fidelity candidate; see RENDER-019.
# Patch only the complete build-private RT64 source view. Keep pinned inputs intact.
function(jfg_patch_fog_file relative expected)
    file(READ "${jfg_capacity_original_root}/${relative}" contents)
    string(REPLACE "\r\n" "\n" contents "${contents}")
    string(SHA256 digest "${contents}")
    if(NOT digest STREQUAL expected)
        message(FATAL_ERROR "Pinned fog shader input changed: ${relative}")
    endif()
    if(relative STREQUAL "src/shaders/RSPProcessCS.hlsl")
        string(REPLACE [==[const float fogAlpha = ((max(tfPos.z, 0) / tfPos.w) * rspFog.mul + rspFog.offset);
        vertexColor.a = clamp(fogAlpha / 255.0f, 0.0f, 1.0f);]==] [==[// Keep the signed depth gradient through clipping and interpolation.
        // Clamping endpoints loses fog on camera-crossing sky polygons.
        // Zero multiplier also avoids 0 * infinity when fog is disabled.
        const float fogW = (tfPos.w == 0.0f) ? 1e-6f : tfPos.w;
        const float fogAlpha = (rspFog.mul == 0.0f) ? rspFog.offset
            : ((tfPos.z / fogW) * rspFog.mul + rspFog.offset);
        vertexColor.a = fogAlpha / 255.0f;]==] contents "${contents}")
    elseif(relative STREQUAL "src/shaders/RasterVS.hlsl")
        string(REPLACE [==[    , out float4 oSmoothColor : COLOR0]==] [==[    , out float4 oSmoothColor : COLOR0
    , noperspective out float oLinearAlpha : TEXCOORD1]==] contents "${contents}")
        string(REPLACE [==[    RasterVS(getRenderParams(), iPosition, iUV, iColor, oPosition, oUV, oSmoothColor, oFlatColor);]==] [==[    RasterVS(getRenderParams(), iPosition, iUV, iColor, oPosition, oUV, oSmoothColor, oFlatColor);
    oLinearAlpha = oSmoothColor.a;]==] contents "${contents}")
    elseif(relative STREQUAL "src/shaders/RasterPS.hlsl")
        string(REPLACE [==[    const float4 vertexColor = renderFlagSmoothShade(rp.flags)]==] [==[    vertexSmoothColor.a = saturate(vertexSmoothColor.a);
    const float4 vertexColor = renderFlagSmoothShade(rp.flags)]==] contents "${contents}")
        string(REPLACE [==[    , in float4 vertexSmoothColor : COLOR0]==] [==[    , in float4 vertexSmoothColor : COLOR0
    , noperspective in float vertexLinearAlpha : TEXCOORD1]==] contents "${contents}")
        string(REPLACE [==[    if (!RasterPS(getRenderParams(), vertexPosition, vertexUV, vertexSmoothColor, vertexFlatColor, isFrontFace, resultColor, resultAlpha)) {]==] [==[    vertexSmoothColor.a = vertexLinearAlpha;
    if (!RasterPS(getRenderParams(), vertexPosition, vertexUV, vertexSmoothColor, vertexFlatColor, isFrontFace, resultColor, resultAlpha)) {]==] contents "${contents}")
    elseif(relative STREQUAL "src/render/rt64_raster_shader.cpp")
        string(REPLACE [==["   out float4 oSmoothColor : COLOR0";]==] [==["   out float4 oSmoothColor : COLOR0"
            ", noperspective out float oLinearAlpha : TEXCOORD1";]==] contents "${contents}")
        string(REPLACE [==["   RasterVS(getRenderParams(), iPosition, iUV, iColor, oPosition, oUV, oSmoothColor, oFlatColor);"]==] [==["   RasterVS(getRenderParams(), iPosition, iUV, iColor, oPosition, oUV, oSmoothColor, oFlatColor);"
            "   oLinearAlpha = oSmoothColor.a;"]==] contents "${contents}")
        string(REPLACE [==[", in float4 vertexSmoothColor : COLOR0";]==] [==[", in float4 vertexSmoothColor : COLOR0"
            ", noperspective in float vertexLinearAlpha : TEXCOORD1";]==] contents "${contents}")
        string(REPLACE [==["   if (!RasterPS(getRenderParams(), vertexPosition, vertexUV, vertexSmoothColor, vertexFlatColor, false, resultColor, resultAlpha)) discard;"]==] [==["   vertexSmoothColor.a = vertexLinearAlpha;"
            "   if (!RasterPS(getRenderParams(), vertexPosition, vertexUV, vertexSmoothColor, vertexFlatColor, false, resultColor, resultAlpha)) discard;"]==] contents "${contents}")
    endif()
    set(destination "${jfg_capacity_source}/${relative}")
    set(existing "")
    if(EXISTS "${destination}")
        file(READ "${destination}" existing)
    endif()
    if(NOT existing STREQUAL contents)
        file(WRITE "${destination}" "${contents}")
    endif()
endfunction()
jfg_patch_fog_file("src/shaders/RSPProcessCS.hlsl" "4455dad690da65c0e5d5ddc21fc3df04c4e0bcdad6137ee22e6a9eaa0a3816ec")
jfg_patch_fog_file("src/shaders/RasterVS.hlsl" "cc31c8d4c6ed11ea7f9370725365722916f0eae8ef17dedaa1c80fb7f4af6265")
jfg_patch_fog_file("src/shaders/RasterPS.hlsl" "957b283411550457573421015580f84ca750c68a050981dbc1a4fe2634507820")
jfg_patch_fog_file("src/render/rt64_raster_shader.cpp" "5e5de4bbd8a22192e857c277bae5af033b8606a6464aa73863d2efe0fd0a0d4d")
