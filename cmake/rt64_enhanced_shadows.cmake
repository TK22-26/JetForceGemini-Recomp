# GPU actor shadow maps at presentation cadence. Pinned RT64 stays pristine.
function(jfg_shadow_replace before after)
 string(FIND "${contents}" "${before}" at)
 if(at EQUAL -1)
  message(FATAL_ERROR "Enhanced shadow integration site is missing")
 endif()
 string(REPLACE "${before}" "${after}" contents "${contents}")
 set(contents "${contents}" PARENT_SCOPE)
endfunction()
set(generated "${CMAKE_CURRENT_BINARY_DIR}/generated/rt64/rt64_workload_queue.cpp")
file(READ "${generated}" contents)
jfg_shadow_replace(
[=[            // Record all framebuffer pairs.]=]
[=[            jfg::enhanced_shadow_renderer().prepare(ext.workloadGraphicsWorker,
                ext.createdGraphicsAPI == UserConfiguration::GraphicsAPI::D3D12,
                workload, curFrameWeight);
            // Record all framebuffer pairs.]=])
file(WRITE "${generated}" "#include \"rt64_enhanced_shadows.hpp\"\n${contents}")
set(generated "${CMAKE_CURRENT_BINARY_DIR}/generated/rt64/render/rt64_framebuffer_renderer.cpp")
file(READ "${generated}" contents)
jfg_shadow_replace(
[=[                const bool typeDifferent = (drawCall.type != previousCallType);]=]
[=[                if (jfg::enhanced_shadow_renderer().eligible(drawCall)) {
                    switchToDepthWrite();
                    jfg::enhanced_shadow_renderer().draw(worker, fbStorage,
                        framebuffer.paramsBuffer.get(), framebuffer.viewport, drawCall);
                    switchToGraphicsPipeline();
                    continue;
                }
                const bool typeDifferent = (drawCall.type != previousCallType);]=])
file(WRITE "${generated}" "#include \"rt64_enhanced_shadows.hpp\"\n${contents}")
if(WIN32)
 function(jfg_build_shadow_shaders)
  set(DXC "${jfg_rt64_root}/src/contrib/dxc/bin/x64/dxc.exe")
  set(DXC_DXIL_OPTS "-Wno-ignored-attributes")
  set(DXC_SPV_OPTS "-spirv" "-fspv-target-env=vulkan1.0" "-fvk-use-dx-layout")
  set(input "${PROJECT_SOURCE_DIR}/src/renderer/enhanced_shadow.hlsl")
  set(outputs)
  foreach(kind IN ITEMS MaskVS MaskPS ReceiverVS ReceiverPS)
   if(kind MATCHES "VS$")
    set(profile vs_6_3)
   else()
    set(profile ps_6_3)
   endif()
   if(kind STREQUAL "MaskVS")
    set(name mask_vs)
   elseif(kind STREQUAL "MaskPS")
    set(name mask_ps)
   elseif(kind STREQUAL "ReceiverVS")
    set(name receiver_vs)
   elseif(kind STREQUAL "ReceiverPS")
    set(name receiver_ps)
   endif()
   set(output "${CMAKE_CURRENT_BINARY_DIR}/generated/rt64/jfg_shadow_${name}")
   build_shader_dxil_impl(rt64 "${input}" "JfgShadow${kind}" "${output}" -E ${kind} -T ${profile})
   build_shader_spirv_impl(rt64 "${input}" "JfgShadow${kind}" "${output}" -E ${kind} -T ${profile})
   list(APPEND outputs "${output}.dxil.c" "${output}.spirv.c")
  endforeach()
  add_custom_target(jfg_shadow_shaders DEPENDS ${outputs})
  add_dependencies(rt64 jfg_shadow_shaders)
 endfunction()
 jfg_build_shadow_shaders()
endif()
