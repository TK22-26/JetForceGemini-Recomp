cmake_minimum_required(VERSION 3.20)

# MSBuild's tracking paths repeat target names and remain subject to MAX_PATH.
# CMAKE_OBJECT_PATH_MAX only shortens object names, not these .tlog paths.
if(CMAKE_HOST_WIN32 AND CMAKE_GENERATOR MATCHES "Visual Studio")
    string(LENGTH "${CMAKE_BINARY_DIR}" jfg_binary_root_length)
    if(jfg_binary_root_length GREATER 80)
        message(FATAL_ERROR "Windows build output path is too long for MSBuild. Use python scripts/build/build_windows.py --test (or --build-root D:/JFG-builds). Existing files are preserved.")
    endif()
endif()


project(
    jfg_recomp
    VERSION 1.5.0
    DESCRIPTION "ROM-free host scaffolding for a Jet Force Gemini native recompilation"
    LANGUAGES C CXX
)

option(JFG_BUILD_TESTS "Build the ROM-free unit tests" ON)
option(JFG_BUILD_SYNTHETIC_GENERATED_TESTS "Build ROM-free generated-code link tests" ON)
option(JFG_WARNINGS_AS_ERRORS "Treat handwritten-code warnings as errors" ON)
option(JFG_ENABLE_GENERATED_CODE "Build locally generated CPU code from a private root" OFF)
option(JFG_BUILD_G2_PRODUCERS "Build private G2 evidence producers" OFF)
option(JFG_BUILD_PHASE5_CAPTURE
    "Build the private Phase 5 boundary-capture producer" OFF)
option(JFG_BUILD_PHASE6_NATIVE_BOOT "Build the private Phase 6 native M2 runner" OFF)
option(JFG_EXPERIMENTAL_NATIVE_PLAY_TIMING "Use qualified native elapsed timing in a private interactive preview" OFF)
option(JFG_EXPERIMENTAL_NATIVE_COLLISION "Build qualified private native collision helpers" OFF)
option(JFG_ENABLE_RT64 "Build the pinned RT64 renderer shell" OFF)
option(JFG_BUILD_PHASE7_RT64_RUNNER
    "Build the private-input Phase 7 RT64 captured-task runner" OFF)
option(JFG_BUILD_PHASE8_LIVE
    "Build the private Phase 8 live generated-code runtime" OFF)
# ExecutorShutdown unwinds through generated extern "C" guest frames. MSVC's
# default /EHsc lets the compiler assume extern "C" callees never throw, which
# makes that unwind undefined for every host of the executor. /EHs keeps
# synchronous exceptions and drops that assumption. Replacing the default flag
# avoids the D9025 override warning a per-target option would add.
if(MSVC)
    string(REPLACE "/EHsc" "/EHs" CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS}")
endif()

option(JFG_ENABLE_ADDRESS_SANITIZER
    "Instrument the complete selected build with AddressSanitizer" OFF)
set(JFG_GENERATED_ROOT "" CACHE PATH "Explicit private root containing generated CPU code")
set(JFG_PHASE6_LIBULTRA_IDENTIFICATION "" CACHE FILEPATH "Explicit private libultra identification JSON")
set(JFG_PHASE6_ROM "" CACHE FILEPATH "Explicit private supported ROM for the Phase 6 M2 test")
set(JFG_PHASE6_EMULATOR_CHECKPOINT "" CACHE FILEPATH "Explicit private emulator checkpoint for the Phase 6 M2 test")
set(JFG_PHASE6_BIZHAWK_EXECUTABLE "" CACHE FILEPATH "Explicit pinned BizHawk executable used for the Phase 6 oracle")
set(JFG_PHASE6_EMULATOR_PROBE "" CACHE FILEPATH "Explicit private Lua probe used for the Phase 6 oracle")
set(JFG_RT64_ROOT "" CACHE PATH "Explicit source root for the pinned RT64 checkout")
set(JFG_RT64_WORKLOAD_CAPACITY "4" CACHE STRING
    "Private composite queue qualification: pinned default 4 or bounded candidates 5/6")
set_property(CACHE JFG_RT64_WORKLOAD_CAPACITY PROPERTY STRINGS 4 5 6)
option(JFG_RT64_PERSISTENT_UPLOAD_MAPPING "Build private persistent D3D12 upload mapping candidate" OFF)
option(JFG_RT64_BUFFER_RESERVATION "Build bounded typed rendering-buffer reservation candidate" OFF)
option(JFG_NATIVE_PLAY_OPTIMIZATIONS "Enable the reviewed native Play and renderer optimization policy" OFF)
option(JFG_V13_PREVIEW_DEFAULTS "Compatibility alias for the earlier 1.3 owner-preview optimization policy" OFF)
if(JFG_V13_PREVIEW_DEFAULTS)
    set(JFG_NATIVE_PLAY_OPTIMIZATIONS ON)
endif()
option(JFG_V13_BLUR_SOURCE_REVIEW "Private diagnostic: show the rendered source before native blur compositing" OFF)
option(JFG_V13_CONTROLS_REVIEW "Private owner preview: memory-buffered control/camera trace" OFF)
if((JFG_V13_BLUR_SOURCE_REVIEW OR JFG_V13_CONTROLS_REVIEW) AND NOT JFG_NATIVE_PLAY_OPTIMIZATIONS)
    message(FATAL_ERROR "Private review diagnostics require the native Play optimization policy")
endif()

set(JFG_PHASE8_PRIVATE_AUDIO_ADAPTER_ROOT "" CACHE PATH
    "Ignored root containing the reviewed generated Phase 8 audio adapter")
set(JFG_PHASE8_PRIVATE_AUDIO_RUNTIME_INCLUDE "" CACHE PATH
    "Ignored include root required by the generated Phase 8 audio adapter")

if(JFG_ENABLE_ADDRESS_SANITIZER)
    add_compile_definitions(JFG_ADDRESS_SANITIZER=1)
    if(MSVC)
        add_compile_options(/fsanitize=address /Zi)
        add_link_options(/DEBUG /INCREMENTAL:NO)
    elseif(CMAKE_CXX_COMPILER_ID MATCHES "Clang|GNU")
        add_compile_options(-fsanitize=address -fno-sanitize-recover=all)
        add_link_options(-fsanitize=address)
    else()
        message(FATAL_ERROR "JFG_ENABLE_ADDRESS_SANITIZER has no supported toolchain flags")
    endif()
endif()
set(JFG_G2_PRIVATE_GRAPHICS_ORACLE_ROOT "" CACHE PATH
    "Ignored/external root implementing the independent G2 graphics oracle ABI")
set(JFG_G2_PRIVATE_AUDIO_ADAPTER_ROOT "" CACHE PATH
    "Ignored/external root implementing the G2 private audio adapter ABI")
set(JFG_G2_PRIVATE_AUDIO_RUNTIME_INCLUDE "" CACHE PATH
    "Ignored/external include root for the private generated RSP adapter")
set(JFG_G2_PRIVATE_AUDIO_ORACLE_ROOT "" CACHE PATH
    "Ignored/external root implementing the independent G2 audio oracle ABI")

if(JFG_BUILD_G2_PRODUCERS AND NOT JFG_ENABLE_GENERATED_CODE)
    message(FATAL_ERROR "JFG_BUILD_G2_PRODUCERS requires JFG_ENABLE_GENERATED_CODE")
endif()

if(JFG_BUILD_PHASE5_CAPTURE AND NOT JFG_ENABLE_GENERATED_CODE)
    message(FATAL_ERROR "JFG_BUILD_PHASE5_CAPTURE requires JFG_ENABLE_GENERATED_CODE")
endif()
if(JFG_BUILD_PHASE6_NATIVE_BOOT AND NOT JFG_ENABLE_GENERATED_CODE)
    message(FATAL_ERROR "JFG_BUILD_PHASE6_NATIVE_BOOT requires JFG_ENABLE_GENERATED_CODE")
endif()
if(JFG_BUILD_PHASE8_LIVE AND
   (NOT JFG_BUILD_PHASE6_NATIVE_BOOT OR NOT JFG_ENABLE_RT64))
    message(FATAL_ERROR
        "JFG_BUILD_PHASE8_LIVE requires JFG_BUILD_PHASE6_NATIVE_BOOT and JFG_ENABLE_RT64")
endif()

list(APPEND CMAKE_MODULE_PATH "${CMAKE_CURRENT_SOURCE_DIR}/cmake")
include(Warnings)
include(GeneratedCode)
include(CTest)

if(WIN32)
    enable_language(RC)
    set(jfg_application_icon "${CMAKE_CURRENT_BINARY_DIR}/jfg-application-icon.rc")
    file(WRITE "${jfg_application_icon}"
        "1 ICON \"${CMAKE_CURRENT_SOURCE_DIR}/launcher/ui/assets/app.ico\"\n")
    add_executable(jfg-frontend WIN32 launcher/native/frontend_win32.cpp launcher/native/video_settings_dialog.cpp launcher/native/video_settings.rc "${jfg_application_icon}")
    target_compile_features(jfg-frontend PRIVATE cxx_std_20)
    target_link_libraries(jfg-frontend PRIVATE user32 gdi32 shell32 ole32 comdlg32 comctl32 dxgi dwmapi)
    target_compile_definitions(jfg-frontend PRIVATE UNICODE _UNICODE)
    jfg_set_project_warnings(jfg-frontend)
    add_executable(jfg-support-capture src/app/support_capture.cpp)
    target_include_directories(jfg-support-capture PRIVATE include)
    target_compile_features(jfg-support-capture PRIVATE cxx_std_20)
    target_link_libraries(jfg-support-capture PRIVATE dbghelp psapi)
    jfg_set_project_warnings(jfg-support-capture)
    if(BUILD_TESTING AND JFG_BUILD_TESTS)
        add_executable(jfg-mouse-input-diagnostics-tests tests/runtime/mouse_input_diagnostics_tests.cpp)
        target_include_directories(jfg-mouse-input-diagnostics-tests PRIVATE include)
        target_compile_features(jfg-mouse-input-diagnostics-tests PRIVATE cxx_std_20)
        jfg_set_project_warnings(jfg-mouse-input-diagnostics-tests)
        add_test(NAME jfg.mouse_input_diagnostics COMMAND jfg-mouse-input-diagnostics-tests
            "${CMAKE_CURRENT_BINARY_DIR}/mouse-diagnostics-test")
        add_executable(jfg-support-fixture tests/runtime/support_snapshot_fixture.cpp)
        target_include_directories(jfg-support-fixture PRIVATE include)
        target_compile_features(jfg-support-fixture PRIVATE cxx_std_20)
        target_link_libraries(jfg-support-fixture PRIVATE psapi)
        jfg_set_project_warnings(jfg-support-fixture)
        if(MSVC)
            target_compile_options(jfg-support-fixture PRIVATE /Zi)
            target_link_options(jfg-support-fixture PRIVATE /DEBUG /INCREMENTAL:NO)
        endif()
        find_package(Python3 REQUIRED COMPONENTS Interpreter)
        add_test(NAME jfg.support_capture COMMAND "${Python3_EXECUTABLE}" "${CMAKE_CURRENT_SOURCE_DIR}/scripts/verification/test_support_capture.py"
            --fixture "$<TARGET_FILE:jfg-support-fixture>" --capture "$<TARGET_FILE:jfg-support-capture>")
        set_tests_properties(jfg.support_capture PROPERTIES TIMEOUT 45)
    endif()
endif()
option(JFG_SUPPORT_SYMBOLS "Keep matching local symbols for support stack traces" OFF)
if(MSVC AND JFG_SUPPORT_SYMBOLS)
    add_compile_options(/Zi)
    add_link_options(/DEBUG /INCREMENTAL:NO)
endif()

include("${CMAKE_CURRENT_SOURCE_DIR}/cmake/RomCatalog.cmake")

add_library(jfg_runtime STATIC
    src/game/descriptor.cpp
    src/game/bindings.cpp
    src/platform/host.cpp
    src/runtime/audio_task_bridge.cpp
    src/runtime/bounded_custom_graphics.cpp
    src/runtime/cic_nus_6105.cpp
    src/runtime/controller_pak.cpp
    src/runtime/custom_overlay_relocator.cpp
    src/runtime/generated_overlay_runtime.cpp
    src/runtime/graphics_task_bridge.cpp
    src/runtime/input_stick.cpp
    src/runtime/input_replay.cpp
    src/runtime/log.cpp
    src/runtime/options.cpp
    src/runtime/renderer_callbacks.cpp
    src/runtime/rom_validator.cpp
    src/runtime/rt64_overlay_address.cpp
    src/runtime/save_device_runtime.cpp
)

target_include_directories(jfg_runtime
    PUBLIC
        "$<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>"
        "$<INSTALL_INTERFACE:include>"
)

target_link_libraries(jfg_runtime PUBLIC jfg_rom_catalog)
target_compile_features(jfg_runtime PUBLIC cxx_std_20)
jfg_set_project_warnings(jfg_runtime)

include("${CMAKE_CURRENT_SOURCE_DIR}/cmake/renderer/Targets.cmake")

add_library(jfg_testkernel STATIC
    src/testkernel/capture.cpp
    src/testkernel/corpus.cpp
    src/testkernel/fakes.cpp
    src/testkernel/journal.cpp
    src/testkernel/scheduler.cpp
    src/testkernel/world.cpp
)

target_include_directories(jfg_testkernel
    PUBLIC
        "$<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>"
        "$<INSTALL_INTERFACE:include>"
)

target_compile_features(jfg_testkernel PUBLIC cxx_std_20)
jfg_set_project_warnings(jfg_testkernel)

add_executable(jfg-test src/app/jfg_test_main.cpp)
target_link_libraries(jfg-test PRIVATE jfg_testkernel)
target_compile_features(jfg-test PRIVATE cxx_std_20)
jfg_set_project_warnings(jfg-test)

add_library(jfg_boot STATIC
    src/boot/runtime.cpp
    src/boot/reset_handoff.cpp
    src/boot/hle.cpp
    src/boot/runlink_module_table.cpp
    src/boot/executor.cpp
    src/boot/thread_scheduler.cpp
)
target_include_directories(jfg_boot
    PUBLIC
        "$<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>"
        "$<INSTALL_INTERFACE:include>"
)
find_package(Threads REQUIRED)
target_link_libraries(jfg_boot PUBLIC jfg_testkernel Threads::Threads)
target_compile_features(jfg_boot PUBLIC cxx_std_20)
jfg_set_project_warnings(jfg_boot)

add_executable(jfg-boot src/app/jfg_boot_main.cpp)
target_link_libraries(jfg-boot PRIVATE jfg_boot)
target_compile_features(jfg-boot PRIVATE cxx_std_20)
jfg_set_project_warnings(jfg-boot)

add_executable(jfg src/app/main.cpp)
target_link_libraries(jfg PRIVATE jfg_runtime)
target_compile_features(jfg PRIVATE cxx_std_20)
jfg_set_project_warnings(jfg)

include("${CMAKE_CURRENT_SOURCE_DIR}/cmake/NativeTargets.cmake")

if(BUILD_TESTING AND JFG_BUILD_TESTS)
    add_subdirectory(tests)
endif()

install(TARGETS jfg RUNTIME DESTINATION bin)
