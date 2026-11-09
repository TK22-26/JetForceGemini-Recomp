# Included by project(rt64), before its shader commands exist.
# Luke Deardoff identified stale shared shader headers in issue #4:
# https://github.com/TK22-26/JetForceGemini-Recomp/issues/4#issuecomment-5985126218
# Keep the pinned upstream checkout untouched; extend its build graph instead.
function(jfg_rt64_shader_dependencies)
    file(GLOB_RECURSE shader_headers CONFIGURE_DEPENDS
        "${CMAKE_CURRENT_SOURCE_DIR}/src/shared/*.h"
        "${CMAKE_CURRENT_SOURCE_DIR}/src/shaders/*.h"
        "${CMAKE_CURRENT_SOURCE_DIR}/src/shaders/*.hlsli")
    if(NOT shader_headers OR NOT TARGET rt64)
        message(FATAL_ERROR "Pinned RT64 shader dependency inputs are missing")
    endif()
    get_target_property(shader_sources rt64 SOURCES)
    set(shader_outputs)
    foreach(source IN LISTS shader_sources)
        if(source MATCHES "^(.+)\\.(spirv|dxil|metal|rw)\\.c$")
            set(stem "${CMAKE_MATCH_1}")
            set(format "${CMAKE_MATCH_2}")
            if(format STREQUAL "spirv" OR format STREQUAL "metal")
                list(APPEND shader_outputs "${stem}.spv")
            elseif(format STREQUAL "dxil")
                list(APPEND shader_outputs "${stem}.dxil")
            else()
                list(APPEND shader_outputs "${stem}.rw")
            endif()
        endif()
    endforeach()
    if(NOT shader_outputs)
        message(FATAL_ERROR "Pinned RT64 shader commands were not found")
    endif()
    list(REMOVE_DUPLICATES shader_outputs)
    foreach(output IN LISTS shader_outputs)
        # Conservative include set also covers transitive shader includes.
        # CMake's glob check discovers added/removed headers on the next build.
        add_custom_command(OUTPUT "${output}" APPEND DEPENDS ${shader_headers})
    endforeach()
endfunction()
cmake_language(DEFER CALL jfg_rt64_shader_dependencies)
