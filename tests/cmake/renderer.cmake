# Target group included from tests/CMakeLists.txt.
if(TARGET jfg_rt64_renderer)
    add_executable(jfg_rt64_shell_tests
        renderer/rt64_shell_tests.cpp
    )
    target_link_libraries(jfg_rt64_shell_tests PRIVATE jfg_rt64_renderer)
    target_include_directories(jfg_rt64_shell_tests PRIVATE
        "${PROJECT_SOURCE_DIR}/src/renderer"
    )
    target_compile_features(jfg_rt64_shell_tests PRIVATE cxx_std_20)
    jfg_set_project_warnings(jfg_rt64_shell_tests)
    if(WIN32)
        add_custom_command(TARGET jfg_rt64_shell_tests POST_BUILD
            COMMAND "${CMAKE_COMMAND}" -E copy_if_different
                "${jfg_rt64_root}/src/contrib/mupen64plus-win32-deps/SDL2-2.26.3/lib/x64/SDL2.dll"
                "${jfg_rt64_root}/src/contrib/dxc/bin/x64/dxcompiler.dll"
                "${jfg_rt64_root}/src/contrib/dxc/bin/x64/dxil.dll"
                "$<TARGET_FILE_DIR:jfg_rt64_shell_tests>"
            VERBATIM)
    endif()
    add_test(NAME jfg.rt64_shell COMMAND jfg_rt64_shell_tests)

    # Exercise the installed command handlers against RT64's CPU state.
    # These tests do not create a graphics device or require a game ROM.
    add_executable(jfg_rt64_f3ddkr_texture_tests renderer/rt64_f3ddkr_texture_tests.cpp)
    target_link_libraries(jfg_rt64_f3ddkr_texture_tests PRIVATE jfg_rt64_renderer)
    target_include_directories(jfg_rt64_f3ddkr_texture_tests PRIVATE
        "${PROJECT_SOURCE_DIR}/src/renderer"
        $<TARGET_PROPERTY:jfg_rt64_renderer,INCLUDE_DIRECTORIES>)
    target_compile_definitions(jfg_rt64_f3ddkr_texture_tests PRIVATE
        $<TARGET_PROPERTY:jfg_rt64_renderer,COMPILE_DEFINITIONS>)
    target_compile_features(jfg_rt64_f3ddkr_texture_tests PRIVATE cxx_std_20)
    jfg_set_project_warnings(jfg_rt64_f3ddkr_texture_tests)
    if(MSVC)
        target_compile_options(jfg_rt64_f3ddkr_texture_tests PRIVATE
            /wd4201 /wd4244 /wd4324)
    endif()
    if(WIN32)
        add_custom_command(TARGET jfg_rt64_f3ddkr_texture_tests POST_BUILD
            COMMAND "${CMAKE_COMMAND}" -E copy_if_different
                "${jfg_rt64_root}/src/contrib/mupen64plus-win32-deps/SDL2-2.26.3/lib/x64/SDL2.dll"
                "${jfg_rt64_root}/src/contrib/dxc/bin/x64/dxcompiler.dll"
                "${jfg_rt64_root}/src/contrib/dxc/bin/x64/dxil.dll"
                "$<TARGET_FILE_DIR:jfg_rt64_f3ddkr_texture_tests>"
            VERBATIM)
    endif()
    add_test(NAME jfg.rt64_f3ddkr_texture COMMAND jfg_rt64_f3ddkr_texture_tests)
    add_executable(jfg_rt64_interpolation_tests renderer/rt64_interpolation_tests.cpp)
    target_link_libraries(jfg_rt64_interpolation_tests PRIVATE jfg_rt64_renderer)
    target_include_directories(jfg_rt64_interpolation_tests PRIVATE
        "${PROJECT_SOURCE_DIR}/src/renderer"
        $<TARGET_PROPERTY:jfg_rt64_renderer,INCLUDE_DIRECTORIES>)
    target_compile_definitions(jfg_rt64_interpolation_tests PRIVATE
        $<TARGET_PROPERTY:jfg_rt64_renderer,COMPILE_DEFINITIONS>)
    target_compile_features(jfg_rt64_interpolation_tests PRIVATE cxx_std_20)
    jfg_set_project_warnings(jfg_rt64_interpolation_tests)
    if(MSVC)
        target_compile_options(jfg_rt64_interpolation_tests PRIVATE
            /wd4201 /wd4244 /wd4324)
    endif()
    if(WIN32)
        add_custom_command(TARGET jfg_rt64_interpolation_tests POST_BUILD
            COMMAND "${CMAKE_COMMAND}" -E copy_if_different
                "${jfg_rt64_root}/src/contrib/mupen64plus-win32-deps/SDL2-2.26.3/lib/x64/SDL2.dll"
                "${jfg_rt64_root}/src/contrib/dxc/bin/x64/dxcompiler.dll"
                "${jfg_rt64_root}/src/contrib/dxc/bin/x64/dxil.dll"
                "$<TARGET_FILE_DIR:jfg_rt64_interpolation_tests>"
            VERBATIM)
    endif()
    add_test(NAME jfg.rt64_interpolation COMMAND jfg_rt64_interpolation_tests)

    add_executable(jfg_rt64_depth_bounds_tests renderer/rt64_depth_bounds_tests.cpp)
    target_link_libraries(jfg_rt64_depth_bounds_tests PRIVATE jfg_rt64_renderer)
    target_include_directories(jfg_rt64_depth_bounds_tests PRIVATE
        "${PROJECT_SOURCE_DIR}/src/renderer"
        $<TARGET_PROPERTY:jfg_rt64_renderer,INCLUDE_DIRECTORIES>)
    target_compile_definitions(jfg_rt64_depth_bounds_tests PRIVATE
        $<TARGET_PROPERTY:jfg_rt64_renderer,COMPILE_DEFINITIONS>)
    target_compile_features(jfg_rt64_depth_bounds_tests PRIVATE cxx_std_20)
    jfg_set_project_warnings(jfg_rt64_depth_bounds_tests)
    if(MSVC)
        target_compile_options(jfg_rt64_depth_bounds_tests PRIVATE
            /wd4201 /wd4244 /wd4324)
    endif()
    if(WIN32)
        add_custom_command(TARGET jfg_rt64_depth_bounds_tests POST_BUILD
            COMMAND "${CMAKE_COMMAND}" -E copy_if_different
                "${jfg_rt64_root}/src/contrib/mupen64plus-win32-deps/SDL2-2.26.3/lib/x64/SDL2.dll"
                "${jfg_rt64_root}/src/contrib/dxc/bin/x64/dxcompiler.dll"
                "${jfg_rt64_root}/src/contrib/dxc/bin/x64/dxil.dll"
                "$<TARGET_FILE_DIR:jfg_rt64_depth_bounds_tests>"
            VERBATIM)
    endif()
    add_test(NAME jfg.rt64_depth_bounds COMMAND jfg_rt64_depth_bounds_tests)

    add_executable(jfg_rt64_draw_call_key_tests renderer/rt64_draw_call_key_tests.cpp)
    target_link_libraries(jfg_rt64_draw_call_key_tests PRIVATE jfg_rt64_renderer)
    target_include_directories(jfg_rt64_draw_call_key_tests PRIVATE
        "${PROJECT_SOURCE_DIR}/src/renderer"
        $<TARGET_PROPERTY:jfg_rt64_renderer,INCLUDE_DIRECTORIES>)
    target_compile_definitions(jfg_rt64_draw_call_key_tests PRIVATE
        $<TARGET_PROPERTY:jfg_rt64_renderer,COMPILE_DEFINITIONS>)
    target_compile_features(jfg_rt64_draw_call_key_tests PRIVATE cxx_std_20)
    jfg_set_project_warnings(jfg_rt64_draw_call_key_tests)
    if(MSVC)
        target_compile_options(jfg_rt64_draw_call_key_tests PRIVATE
            /wd4201 /wd4244 /wd4324)
    endif()
    if(WIN32)
        add_custom_command(TARGET jfg_rt64_draw_call_key_tests POST_BUILD
            COMMAND "${CMAKE_COMMAND}" -E copy_if_different
                "${jfg_rt64_root}/src/contrib/mupen64plus-win32-deps/SDL2-2.26.3/lib/x64/SDL2.dll"
                "${jfg_rt64_root}/src/contrib/dxc/bin/x64/dxcompiler.dll"
                "${jfg_rt64_root}/src/contrib/dxc/bin/x64/dxil.dll"
                "$<TARGET_FILE_DIR:jfg_rt64_draw_call_key_tests>"
            VERBATIM)
    endif()
    add_test(NAME jfg.rt64_draw_call_key COMMAND jfg_rt64_draw_call_key_tests)

    add_executable(jfg_rt64_call_matching_tests renderer/rt64_call_matching_tests.cpp)
    target_link_libraries(jfg_rt64_call_matching_tests PRIVATE jfg_rt64_renderer)
    target_include_directories(jfg_rt64_call_matching_tests PRIVATE
        "${PROJECT_SOURCE_DIR}/src/renderer"
        $<TARGET_PROPERTY:jfg_rt64_renderer,INCLUDE_DIRECTORIES>)
    target_compile_definitions(jfg_rt64_call_matching_tests PRIVATE
        $<TARGET_PROPERTY:jfg_rt64_renderer,COMPILE_DEFINITIONS>)
    target_compile_features(jfg_rt64_call_matching_tests PRIVATE cxx_std_20)
    jfg_set_project_warnings(jfg_rt64_call_matching_tests)
    if(MSVC)
        target_compile_options(jfg_rt64_call_matching_tests PRIVATE
            /wd4201 /wd4244 /wd4324)
    endif()
    if(WIN32)
        add_custom_command(TARGET jfg_rt64_call_matching_tests POST_BUILD
            COMMAND "${CMAKE_COMMAND}" -E copy_if_different
                "${jfg_rt64_root}/src/contrib/mupen64plus-win32-deps/SDL2-2.26.3/lib/x64/SDL2.dll"
                "${jfg_rt64_root}/src/contrib/dxc/bin/x64/dxcompiler.dll"
                "${jfg_rt64_root}/src/contrib/dxc/bin/x64/dxil.dll"
                "$<TARGET_FILE_DIR:jfg_rt64_call_matching_tests>"
            VERBATIM)
    endif()
    add_test(NAME jfg.rt64_call_matching COMMAND jfg_rt64_call_matching_tests)
endif()
