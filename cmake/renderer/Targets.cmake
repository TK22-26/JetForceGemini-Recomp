# Target group included from CMakeLists.txt.
if(JFG_ENABLE_RT64)
    if(JFG_RT64_ROOT STREQUAL "")
        message(FATAL_ERROR "JFG_ENABLE_RT64 requires an explicit JFG_RT64_ROOT")
    endif()
    file(REAL_PATH "${JFG_RT64_ROOT}" jfg_rt64_root)
    if(NOT EXISTS "${jfg_rt64_root}/CMakeLists.txt" OR
       NOT EXISTS "${jfg_rt64_root}/LICENSE")
        message(FATAL_ERROR "JFG_RT64_ROOT is not an RT64 source checkout")
    endif()

    find_package(Git REQUIRED)
    execute_process(
        COMMAND "${GIT_EXECUTABLE}" -C "${jfg_rt64_root}" rev-parse HEAD
        RESULT_VARIABLE jfg_rt64_git_result
        OUTPUT_VARIABLE jfg_rt64_revision
        ERROR_VARIABLE jfg_rt64_git_error
        OUTPUT_STRIP_TRAILING_WHITESPACE
    )
    set(jfg_rt64_required_revision
        "5473732a822a4423b5696e7cb18fecc425a59875")
    if(NOT jfg_rt64_git_result EQUAL 0)
        message(FATAL_ERROR
            "Unable to inspect JFG_RT64_ROOT revision: ${jfg_rt64_git_error}")
    endif()
    if(NOT jfg_rt64_revision STREQUAL jfg_rt64_required_revision)
        message(FATAL_ERROR
            "JFG_RT64_ROOT must be pinned to ${jfg_rt64_required_revision}; "
            "found ${jfg_rt64_revision}")
    endif()

    include("${CMAKE_CURRENT_SOURCE_DIR}/cmake/renderer/rt64_workload_capacity.cmake")

    set(RT64_STATIC ON CACHE BOOL "Build RT64 as a static library" FORCE)
    set(ZSTD_BUILD_TESTS OFF CACHE BOOL
        "Do not register dependency-owned Zstd tests" FORCE)
    # Extend shader dependencies in RT64's directory without modifying its checkout.
    set(jfg_saved_rt64_project_include "${CMAKE_PROJECT_rt64_INCLUDE}")
    list(APPEND CMAKE_PROJECT_rt64_INCLUDE
        "${CMAKE_CURRENT_SOURCE_DIR}/cmake/renderer/rt64_shader_dependencies.cmake")
    add_subdirectory("${jfg_rt64_root}"
        "${CMAKE_CURRENT_BINARY_DIR}/_deps/rt64-build" EXCLUDE_FROM_ALL)
    set(CMAKE_PROJECT_rt64_INCLUDE "${jfg_saved_rt64_project_include}")
    unset(jfg_saved_rt64_project_include)

    # The pinned transform uploader treats the mere existence of a previous
    # game frame as proof that every current workload was matched to it. On a
    # scene transition (and on this single-task acceptance harness), an
    # unmatched workload has empty interpolation arrays; uploading those as
    # world matrices produces GPU-only garbage geometry even though RT64's
    # CPU-transformed vertices are valid. Generate a hash-guarded compatibility
    # unit in the build tree and use current matrices until a workload is
    # actually mapped to a previous one.
    set(jfg_rt64_transform_processor
        "${jfg_rt64_root}/src/render/rt64_transform_processor.cpp")
    file(SHA256 "${jfg_rt64_transform_processor}"
        jfg_rt64_transform_processor_sha256)
    # Accept the same pinned file with Git's LF or CRLF checkout convention.
    # These are exact hashes; altered source still fails closed.
    if(NOT jfg_rt64_transform_processor_sha256 STREQUAL
       "68d023aa9e5376737aa02c3b310063b773edccd6092fc2e3af66e9e8d74da973" AND
       NOT jfg_rt64_transform_processor_sha256 STREQUAL
       "ffd56ba45e76a82c18397c4d777b228a2b0963ac28c6ba9c618b417437bebcf0")
        message(FATAL_ERROR
            "Pinned RT64 transform processor does not match the audited "
            "unmatched-workload compatibility patch input")
    endif()
    file(READ "${jfg_rt64_transform_processor}"
        jfg_rt64_transform_processor_contents)
    set(jfg_rt64_transform_previous_old
        "const bool prevFrameValid = (p.prevFrame != nullptr);")
    set(jfg_rt64_transform_previous_new
        "const bool prevFrameValid = (p.prevFrame != nullptr) && p.curFrame->frameMap.workloads[w].mapped;")
    string(FIND "${jfg_rt64_transform_processor_contents}"
        "${jfg_rt64_transform_previous_old}"
        jfg_rt64_transform_previous_offset)
    if(jfg_rt64_transform_previous_offset EQUAL -1)
        message(FATAL_ERROR
            "Unable to apply the audited RT64 unmatched-workload patch")
    endif()
    string(REPLACE "${jfg_rt64_transform_previous_old}"
        "${jfg_rt64_transform_previous_new}"
        jfg_rt64_transform_processor_patched
        "${jfg_rt64_transform_processor_contents}")
    set(jfg_rt64_transform_processor_generated
        "${CMAKE_CURRENT_BINARY_DIR}/generated/rt64/render/rt64_transform_processor.cpp")
    file(MAKE_DIRECTORY
        "${CMAKE_CURRENT_BINARY_DIR}/generated/rt64/render")
    file(WRITE "${jfg_rt64_transform_processor_generated}"
        "${jfg_rt64_transform_processor_patched}")

    get_target_property(jfg_rt64_sources rt64 SOURCES)
    set(jfg_rt64_patched_sources)
    set(jfg_rt64_transform_source_replaced FALSE)
    foreach(jfg_rt64_source IN LISTS jfg_rt64_sources)
        if(jfg_rt64_source MATCHES
           "(^|[/\\\\])rt64_transform_processor\\.cpp$")
            list(APPEND jfg_rt64_patched_sources
                "${jfg_rt64_transform_processor_generated}")
            set(jfg_rt64_transform_source_replaced TRUE)
        else()
            list(APPEND jfg_rt64_patched_sources "${jfg_rt64_source}")
        endif()
    endforeach()
    if(NOT jfg_rt64_transform_source_replaced)
        message(FATAL_ERROR
            "Pinned RT64 target does not contain rt64_transform_processor.cpp")
    endif()
    set_property(TARGET rt64 PROPERTY SOURCES "${jfg_rt64_patched_sources}")
    target_include_directories(rt64 PRIVATE
        "${jfg_rt64_root}/src/render")

    include(cmake/renderer/rt64_vi_presentation.cmake)
    include(cmake/renderer/rt64_gpu_timing.cmake)
    include(cmake/renderer/rt64_texture_profile.cmake)
    include(cmake/renderer/rt64_buffer_profile.cmake)
    if(JFG_RT64_BUFFER_RESERVATION)
        jfg_patch_buffer_reservation_sources()
    endif()
    include(cmake/renderer/rt64_noise_fixture.cmake)
    include(cmake/renderer/rt64_draw_call_key.cmake)
    include(cmake/renderer/rt64_call_matching.cmake)
    include(cmake/renderer/rt64_presentation_timer.cmake)
    include(cmake/renderer/rt64_depth_bounds.cmake)
    include(cmake/renderer/rt64_interpolation.cmake)
    include(cmake/renderer/rt64_enhanced_shadows.cmake)

    # The pinned Plume D3D12 backend assumes every CopyTextureRegion
    # destination is a texture when configuring programmable sample
    # positions. A texture-to-readback-buffer copy legitimately has no
    # destination texture, so the unguarded call dereferences null. Keep the
    # pinned checkout pristine: generate one audited compatibility translation
    # unit in the build tree and replace only that source in Plume's target.
    if(WIN32)
        set(jfg_rt64_plume_d3d12
            "${jfg_rt64_root}/src/contrib/plume/plume_d3d12.cpp")
        file(SHA256 "${jfg_rt64_plume_d3d12}"
            jfg_rt64_plume_d3d12_sha256)
        if(NOT jfg_rt64_plume_d3d12_sha256 STREQUAL
           "b8c45f82da26295b40771e53c200d0e7d60989587324ecaddce1fefeb4c7b4ba" AND
           NOT jfg_rt64_plume_d3d12_sha256 STREQUAL
           "795f1e7d75c450106b7154f4089ea4549fff111e13d6a078b81114c3e0dea317" AND
           NOT jfg_rt64_plume_d3d12_sha256 STREQUAL
           "${jfg_rt64_plume_upload_sha256}")
            message(FATAL_ERROR
                "Pinned RT64 Plume D3D12 source does not match the audited "
                "readback compatibility patch input")
        endif()
        file(READ "${jfg_rt64_plume_d3d12}"
            jfg_rt64_plume_d3d12_contents)
        set(jfg_rt64_plume_readback_old
            "        setSamplePositions(dstLocation.texture);\n        d3d->CopyTextureRegion")
        set(jfg_rt64_plume_readback_new
            "        if (dstLocation.texture != nullptr) {\n            setSamplePositions(dstLocation.texture);\n        }\n        d3d->CopyTextureRegion")
        string(FIND "${jfg_rt64_plume_d3d12_contents}"
            "${jfg_rt64_plume_readback_old}"
            jfg_rt64_plume_readback_offset)
        if(jfg_rt64_plume_readback_offset EQUAL -1)
            message(FATAL_ERROR
                "Unable to apply the audited RT64 Plume readback patch")
        endif()
        string(REPLACE "${jfg_rt64_plume_readback_old}"
            "${jfg_rt64_plume_readback_new}"
            jfg_rt64_plume_d3d12_patched
            "${jfg_rt64_plume_d3d12_contents}")
        set(jfg_rt64_plume_d3d12_generated
            "${CMAKE_CURRENT_BINARY_DIR}/generated/rt64/plume_d3d12.cpp")
        file(MAKE_DIRECTORY
            "${CMAKE_CURRENT_BINARY_DIR}/generated/rt64")
        file(WRITE "${jfg_rt64_plume_d3d12_generated}"
            "${jfg_rt64_plume_d3d12_patched}")

        get_target_property(jfg_rt64_plume_sources plume SOURCES)
        set(jfg_rt64_plume_patched_sources)
        set(jfg_rt64_plume_source_replaced FALSE)
        foreach(jfg_rt64_plume_source IN LISTS jfg_rt64_plume_sources)
            if(jfg_rt64_plume_source MATCHES
               "(^|[/\\\\])plume_d3d12\\.cpp$")
                list(APPEND jfg_rt64_plume_patched_sources
                    "${jfg_rt64_plume_d3d12_generated}")
                set(jfg_rt64_plume_source_replaced TRUE)
            else()
                list(APPEND jfg_rt64_plume_patched_sources
                    "${jfg_rt64_plume_source}")
            endif()
        endforeach()
        if(NOT jfg_rt64_plume_source_replaced)
            message(FATAL_ERROR
                "Pinned RT64 Plume target does not contain plume_d3d12.cpp")
        endif()
        set_property(TARGET plume PROPERTY SOURCES
            "${jfg_rt64_plume_patched_sources}")
    endif()

    add_library(jfg_rt64_renderer STATIC
        src/renderer/rt64_f3ddkr.cpp
        src/renderer/floating_environment.cpp
        src/renderer/rt64_callbacks.cpp
        src/renderer/rt64_shell.cpp
    )
    target_include_directories(jfg_rt64_renderer
        PUBLIC
            "$<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>"
        PRIVATE
            "${jfg_rt64_root}/src"
            "${jfg_rt64_root}/src/contrib"
            "${jfg_rt64_root}/src/contrib/plume"
            "${jfg_rt64_root}/src/contrib/hlslpp/include"
            "${jfg_rt64_root}/src/contrib/imgui"
            "${jfg_rt64_root}/src/contrib/mupen64plus-core/src/api"
            "${jfg_rt64_root}/src/contrib/nativefiledialog-extended/src/include"
            "${jfg_rt64_root}/src/contrib/mupen64plus-win32-deps/SDL2-2.26.3/include"
            "${CMAKE_CURRENT_BINARY_DIR}/src"
    )
    if(WIN32)
        target_include_directories(jfg_rt64_renderer PRIVATE
            "${jfg_rt64_root}/src/contrib/dxc/inc")
        target_link_directories(jfg_rt64_renderer PUBLIC
            "${jfg_rt64_root}/src/contrib/mupen64plus-win32-deps/SDL2-2.26.3/lib/x64")
    endif()
    target_link_libraries(jfg_rt64_renderer PUBLIC jfg_runtime PRIVATE rt64)
    target_compile_features(jfg_rt64_renderer PUBLIC cxx_std_20)
    target_compile_definitions(jfg_rt64_renderer PRIVATE
        RT_ENABLED=0
        SCRIPT_ENABLED=0
        HLSL_CPU
        FFX_GCC
        IMGUI_IMPL_VULKAN_NO_PROTOTYPES
        NOMINMAX
        __PRFCHWINTRIN_H
    )
    jfg_set_project_warnings(jfg_rt64_renderer)
    if(MSVC)
        # The pinned RT64 public headers intentionally use anonymous unions
        # and aligned interop layouts. Keep /WX for project code while
        # suppressing those upstream-header diagnostics on this boundary.
        target_compile_options(jfg_rt64_renderer PRIVATE
            /wd4201 /wd4244 /wd4324)
    endif()

    if(JFG_BUILD_PHASE7_RT64_RUNNER)
        if(NOT WIN32)
            message(FATAL_ERROR
                "JFG_BUILD_PHASE7_RT64_RUNNER currently requires Windows")
        endif()
        add_executable(jfg-phase7-rt64-task
            src/evidence/phase7_rt64_task_runner.cpp)
        target_link_libraries(jfg-phase7-rt64-task PRIVATE
            jfg_rt64_renderer user32)
        target_compile_features(jfg-phase7-rt64-task PRIVATE cxx_std_20)
        jfg_set_project_warnings(jfg-phase7-rt64-task)
        add_executable(jfg-phase7-simulation-hash
            src/evidence/phase7_simulation_hash_runner.cpp)
        target_link_libraries(jfg-phase7-simulation-hash PRIVATE jfg_runtime)
        target_compile_features(jfg-phase7-simulation-hash PRIVATE cxx_std_20)
        jfg_set_project_warnings(jfg-phase7-simulation-hash)
        add_custom_command(TARGET jfg-phase7-rt64-task POST_BUILD
            COMMAND "${CMAKE_COMMAND}" -E copy_if_different
                "${jfg_rt64_root}/src/contrib/mupen64plus-win32-deps/SDL2-2.26.3/lib/x64/SDL2.dll"
                "${jfg_rt64_root}/src/contrib/dxc/bin/x64/dxcompiler.dll"
                "${jfg_rt64_root}/src/contrib/dxc/bin/x64/dxil.dll"
                "$<TARGET_FILE_DIR:jfg-phase7-rt64-task>"
            VERBATIM)
    endif()
endif()
