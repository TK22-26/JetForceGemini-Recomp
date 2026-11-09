# Observe real swap-chain result codes without changing renderer behavior.
# The pinned sources remain immutable; extend the generated D3D12 unit and
# substitute a hash-checked Vulkan translation unit in the build tree.
function(jfg_result_replace before after)
    string(FIND "${contents}" "${before}" offset)
    if(offset EQUAL -1)
        message(FATAL_ERROR "Pinned renderer diagnostic patch site is missing")
    endif()
    string(REPLACE "${before}" "${after}" contents "${contents}")
    set(contents "${contents}" PARENT_SCOPE)
endfunction()
if(WIN32)
    file(READ "${jfg_rt64_plume_d3d12_generated}" contents)
    jfg_result_replace(
        "        HRESULT res = d3d->Present(syncInterval, flags);"
        "        HRESULT res = d3d->Present(syncInterval, flags);\n        jfg::renderer_result(jfg::GraphicsApi::d3d12, jfg::RendererOperation::present, static_cast<uint32_t>(res));")
    jfg_result_replace(
        "        HRESULT res = d3d->ResizeBuffers(0, 0, 0, DXGI_FORMAT_UNKNOWN, swapChainFlags);"
        "        HRESULT res = d3d->ResizeBuffers(0, 0, 0, DXGI_FORMAT_UNKNOWN, swapChainFlags);\n        jfg::renderer_result(jfg::GraphicsApi::d3d12, jfg::RendererOperation::resize, static_cast<uint32_t>(res));")
    file(WRITE "${jfg_rt64_plume_d3d12_generated}" "#include \"jfg/renderer/renderer_diagnostics.hpp\"\n${contents}")
endif()
file(READ "${jfg_rt64_root}/src/contrib/plume/plume_vulkan.cpp" contents)
string(REPLACE "\r\n" "\n" contents "${contents}")
string(SHA256 digest "${contents}")
if(NOT digest STREQUAL "70ecc88658c7231497836d15ea9f98d80861a6e991cc6128d40c7ac980193038")
    message(FATAL_ERROR "Pinned Plume Vulkan source changed")
endif()
jfg_result_replace(
    "            res = vkQueuePresentKHR(commandQueue->queue->vk, &presentInfo);"
    "            res = vkQueuePresentKHR(commandQueue->queue->vk, &presentInfo);\n            jfg::renderer_result(jfg::GraphicsApi::vulkan, jfg::RendererOperation::present, static_cast<uint32_t>(res));")
jfg_result_replace(
    "        VkResult res = vkAcquireNextImageKHR(commandQueue->device->vk, vk, UINT64_MAX, interfaceSemaphore->vk, VK_NULL_HANDLE, textureIndex);"
    "        VkResult res = vkAcquireNextImageKHR(commandQueue->device->vk, vk, UINT64_MAX, interfaceSemaphore->vk, VK_NULL_HANDLE, textureIndex);\n        jfg::renderer_result(jfg::GraphicsApi::vulkan, jfg::RendererOperation::acquire, static_cast<uint32_t>(res));")
jfg_result_replace(
    "        VkResult res = vkCreateSwapchainKHR(commandQueue->device->vk, &createInfo, nullptr, &vk);"
    "        VkResult res = vkCreateSwapchainKHR(commandQueue->device->vk, &createInfo, nullptr, &vk);\n        jfg::renderer_result(jfg::GraphicsApi::vulkan, jfg::RendererOperation::resize, static_cast<uint32_t>(res));")
set(generated "${CMAKE_CURRENT_BINARY_DIR}/generated/rt64/plume_vulkan.cpp")
file(WRITE "${generated}" "#include \"jfg/renderer/renderer_diagnostics.hpp\"\n${contents}")
get_target_property(units plume SOURCES)
set(patched)
set(found FALSE)
foreach(unit IN LISTS units)
    get_filename_component(name "${unit}" NAME)
    if(name STREQUAL "plume_vulkan.cpp")
        list(APPEND patched "${generated}")
        set(found TRUE)
    else()
        list(APPEND patched "${unit}")
    endif()
endforeach()
if(NOT found)
    message(FATAL_ERROR "Pinned Plume Vulkan target source is missing")
endif()
set_property(TARGET plume PROPERTY SOURCES "${patched}")
target_include_directories(plume PRIVATE "${PROJECT_SOURCE_DIR}/include" "${jfg_rt64_root}/src/contrib/plume")
