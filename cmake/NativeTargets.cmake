# Target group included from CMakeLists.txt.
if(JFG_ENABLE_GENERATED_CODE)
    if(JFG_GENERATED_ROOT STREQUAL "")
        message(FATAL_ERROR
            "JFG_ENABLE_GENERATED_CODE requires an explicit JFG_GENERATED_ROOT. "
            "An in-worktree root must be ignored by git; an external root must remain outside the worktree."
        )
    endif()

    jfg_add_generated_code(
        NAME jfg_generated
        ROOT "${JFG_GENERATED_ROOT}"
        REQUIRE_PRIVATE_ROOT
    )
    target_link_libraries(jfg PRIVATE jfg_generated_link)

    if(JFG_BUILD_PHASE5_CAPTURE)
        find_package(Python3 REQUIRED COMPONENTS Interpreter)
        set(jfg_phase5_capture_table
            "${CMAKE_CURRENT_BINARY_DIR}/phase5-private/capture-table.inc")
        add_custom_command(
            OUTPUT "${jfg_phase5_capture_table}"
            COMMAND "${Python3_EXECUTABLE}"
                "${CMAKE_CURRENT_SOURCE_DIR}/scripts/build/prepare_phase5_capture_table.py"
                --generated-root "${JFG_GENERATED_ROOT}"
                --output "${jfg_phase5_capture_table}"
            DEPENDS
                "${CMAKE_CURRENT_SOURCE_DIR}/scripts/build/prepare_phase5_capture_table.py"
                "${JFG_GENERATED_ROOT}/symbol_inventory.json"
            COMMENT "Generating the private Phase 5 capture table"
            VERBATIM
        )
        add_executable(jfg_phase5_capture_producer
            src/evidence/phase5_capture_producer.cpp
            "${jfg_phase5_capture_table}"
        )
        set_source_files_properties("${jfg_phase5_capture_table}"
            PROPERTIES HEADER_FILE_ONLY TRUE)
        target_include_directories(jfg_phase5_capture_producer SYSTEM PRIVATE
            "${JFG_GENERATED_ROOT}/include"
        )
        target_compile_definitions(jfg_phase5_capture_producer PRIVATE
            "JFG_PHASE5_CAPTURE_TABLE_INC=\"${jfg_phase5_capture_table}\"")
        target_link_libraries(jfg_phase5_capture_producer PRIVATE
            jfg_testkernel
            jfg_generated_link
        )
        target_compile_features(jfg_phase5_capture_producer PRIVATE cxx_std_20)
        jfg_set_project_warnings(jfg_phase5_capture_producer)
    endif()

    if(JFG_BUILD_PHASE6_NATIVE_BOOT)
        jfg_resolve_private_file(jfg_phase6_libultra_identification
            "${JFG_PHASE6_LIBULTRA_IDENTIFICATION}"
            "JFG_PHASE6_LIBULTRA_IDENTIFICATION")
        find_package(Python3 REQUIRED COMPONENTS Interpreter)
        set(jfg_phase6_dispatch_table "${CMAKE_CURRENT_BINARY_DIR}/phase6-private/native-dispatch-table.inc")
        add_custom_command(OUTPUT "${jfg_phase6_dispatch_table}"
            COMMAND "${Python3_EXECUTABLE}" "${CMAKE_CURRENT_SOURCE_DIR}/scripts/build/prepare_phase6_native_dispatch_table.py"
                --identification "${jfg_phase6_libultra_identification}" --output "${jfg_phase6_dispatch_table}"
            DEPENDS "${CMAKE_CURRENT_SOURCE_DIR}/scripts/build/prepare_phase6_native_dispatch_table.py" "${jfg_phase6_libultra_identification}"
            VERBATIM)
        add_executable(jfg-native-boot src/app/jfg_native_boot_main.cpp src/boot/native_boot.cpp "${jfg_phase6_dispatch_table}")
        target_sources(jfg-native-boot PRIVATE
            src/boot/native/guest_memory.cpp
            src/boot/native/host_audio_device.cpp
            src/boot/native/generated_overlay_table.cpp
            src/boot/native/live_window.cpp
            src/boot/native/controller_input.cpp
            src/boot/native/live_frontend.cpp
            src/boot/native/runtime_reports.cpp
            src/boot/native/save_storage.cpp
            src/boot/native/overlay_loading.cpp
            src/boot/native/live_tasks.cpp
            src/boot/native/runtime_diagnostics.cpp
            src/boot/native/guest_execution.cpp
            src/boot/native/rom_image.cpp
            src/boot/native/process_supervisor.cpp
        )
        set_source_files_properties("${jfg_phase6_dispatch_table}" PROPERTIES HEADER_FILE_ONLY TRUE)
        target_include_directories(jfg-native-boot SYSTEM PRIVATE "${JFG_GENERATED_ROOT}/include" "${JFG_GENERATED_ROOT}")
        target_compile_definitions(jfg-native-boot PRIVATE "JFG_PHASE6_DISPATCH_TABLE_INC=\"${jfg_phase6_dispatch_table}\"")
        if(JFG_ENABLE_ADDRESS_SANITIZER)
            set(jfg_phase6_sanitizer_id "address")
            set(jfg_phase6_build_suffix "-ASAN")
        else()
            set(jfg_phase6_sanitizer_id "none")
            set(jfg_phase6_build_suffix "")
        endif()
        if(JFG_EXPERIMENTAL_NATIVE_PLAY_TIMING)
            if(NOT JFG_BUILD_PHASE8_LIVE)
                message(FATAL_ERROR "Experimental native play timing requires the live runtime")
            endif()
            target_compile_definitions(jfg-native-boot PRIVATE JFG_EXPERIMENTAL_NATIVE_PLAY_TIMING=1)
            string(APPEND jfg_phase6_build_suffix "-NativeTimingPreview")
        endif()
        if(JFG_NATIVE_PLAY_OPTIMIZATIONS)
            if(NOT WIN32 OR NOT MSVC OR NOT JFG_EXPERIMENTAL_NATIVE_PLAY_TIMING OR
               NOT JFG_RT64_WORKLOAD_CAPACITY STREQUAL "5" OR
               NOT JFG_RT64_PERSISTENT_UPLOAD_MAPPING OR NOT JFG_RT64_BUFFER_RESERVATION)
                message(FATAL_ERROR "Native Play optimizations require Windows native timing, five workload slots, persistent upload support and reservation support")
            endif()
            target_compile_definitions(jfg-native-boot PRIVATE JFG_NATIVE_PLAY_OPTIMIZATIONS=1)
            if(JFG_V13_CONTROLS_REVIEW)
                target_compile_definitions(jfg-native-boot PRIVATE JFG_V13_CONTROLS_REVIEW=1)
            endif()
            if(JFG_V13_BLUR_SOURCE_REVIEW)
                target_compile_definitions(jfg-native-boot PRIVATE JFG_V13_BLUR_SOURCE_REVIEW=1)
            endif()
            string(APPEND jfg_phase6_build_suffix "-NativePlayOptimized")
        endif()
        target_compile_definitions(jfg-native-boot PRIVATE
            "JFG_PHASE6_BUILD_IDENTITY=\"${CMAKE_CXX_COMPILER_ID}-${CMAKE_CXX_COMPILER_VERSION}-$<CONFIG>${jfg_phase6_build_suffix}\""
            "JFG_PHASE6_SANITIZER_ID=\"${jfg_phase6_sanitizer_id}\"")
        target_link_libraries(jfg-native-boot PRIVATE jfg_boot jfg_runtime jfg_generated_link)
        if(JFG_EXPERIMENTAL_NATIVE_COLLISION)
            if(NOT WIN32 OR NOT MSVC OR NOT JFG_BUILD_PHASE8_LIVE OR
               NOT JFG_EXPERIMENTAL_NATIVE_PLAY_TIMING)
                message(FATAL_ERROR "Native collision requires the MSVC Windows native timing preview")
            endif()
            set(jfg_native_collision_body "${CMAKE_CURRENT_BINARY_DIR}/phase6-private/native-collision.inc")
            add_custom_command(OUTPUT "${jfg_native_collision_body}"
                COMMAND "${Python3_EXECUTABLE}" "${CMAKE_CURRENT_SOURCE_DIR}/scripts/build/prepare_native_collision.py"
                    --generated-root "${JFG_GENERATED_ROOT}" --output "${jfg_native_collision_body}"
                DEPENDS "${CMAKE_CURRENT_SOURCE_DIR}/scripts/build/prepare_native_collision.py"
                    "${JFG_GENERATED_ROOT}/baseline/fn_003_0168_recomp.c"
                    "${JFG_GENERATED_ROOT}/baseline/fn_003_0167_recomp.c"
                    "${JFG_GENERATED_ROOT}/baseline/fn_003_0054_recomp.c"
                VERBATIM)
            set_source_files_properties("${jfg_native_collision_body}" PROPERTIES HEADER_FILE_ONLY TRUE)
            target_sources(jfg-native-boot PRIVATE src/boot/native_collision.cpp "${jfg_native_collision_body}")
            target_compile_definitions(jfg-native-boot PRIVATE JFG_NATIVE_COLLISION_ENABLED=1
                "JFG_NATIVE_COLLISION_BODY=\"${jfg_native_collision_body}\"")
            # MSVC emits this generated-code warning during deferred code generation.
            set_property(SOURCE src/boot/native_collision.cpp APPEND PROPERTY COMPILE_OPTIONS /wd4702)
        endif()

        if(WIN32 AND MSVC AND JFG_BUILD_PHASE8_LIVE AND JFG_EXPERIMENTAL_NATIVE_PLAY_TIMING)
            set(jfg_direct_mi_mask_body "${CMAKE_CURRENT_BINARY_DIR}/phase6-private/direct-mi-mask-access.inc")
            add_custom_command(OUTPUT "${jfg_direct_mi_mask_body}"
                COMMAND "${Python3_EXECUTABLE}" "${CMAKE_CURRENT_SOURCE_DIR}/scripts/build/prepare_direct_mi_mask_access.py"
                    --generated-root "${JFG_GENERATED_ROOT}" --output "${jfg_direct_mi_mask_body}"
                DEPENDS "${CMAKE_CURRENT_SOURCE_DIR}/scripts/build/prepare_direct_mi_mask_access.py"
                    "${CMAKE_CURRENT_SOURCE_DIR}/scripts/build/prepare_direct_sp_access.py"
                    "${JFG_GENERATED_ROOT}/baseline/fn_000_1226_recomp.c"
                    "${JFG_GENERATED_ROOT}/baseline/fn_000_1231_recomp.c"
                    "${JFG_GENERATED_ROOT}/baseline/fn_000_1235_recomp.c"
                VERBATIM)
            set_source_files_properties("${jfg_direct_mi_mask_body}" PROPERTIES HEADER_FILE_ONLY TRUE)
            target_sources(jfg-native-boot PRIVATE src/boot/direct_mi_mask_access.cpp "${jfg_direct_mi_mask_body}")
            target_compile_definitions(jfg-native-boot PRIVATE JFG_DIRECT_MI_MASK_ACCESS_ENABLED=1
                "JFG_DIRECT_MI_MASK_ACCESS_BODY=\"${jfg_direct_mi_mask_body}\"")
            set_property(SOURCE src/boot/direct_mi_mask_access.cpp APPEND PROPERTY COMPILE_OPTIONS /wd4702)
            set(jfg_direct_sp_body "${CMAKE_CURRENT_BINARY_DIR}/phase6-private/direct-sp-access.inc")
            add_custom_command(OUTPUT "${jfg_direct_sp_body}"
                COMMAND "${Python3_EXECUTABLE}" "${CMAKE_CURRENT_SOURCE_DIR}/scripts/build/prepare_direct_sp_access.py"
                    --generated-root "${JFG_GENERATED_ROOT}" --output "${jfg_direct_sp_body}"
                DEPENDS "${CMAKE_CURRENT_SOURCE_DIR}/scripts/build/prepare_direct_sp_access.py"
                    "${JFG_GENERATED_ROOT}/baseline/fn_000_1226_recomp.c"
                    "${JFG_GENERATED_ROOT}/baseline/fn_000_1558_recomp.c"
                    "${JFG_GENERATED_ROOT}/baseline/fn_000_1643_recomp.c"
                    "${JFG_GENERATED_ROOT}/baseline/fn_000_1644_recomp.c"
                    "${JFG_GENERATED_ROOT}/baseline/fn_000_1645_recomp.c"
                    "${JFG_GENERATED_ROOT}/baseline/fn_000_1646_recomp.c"
                VERBATIM)
            set_source_files_properties("${jfg_direct_sp_body}" PROPERTIES HEADER_FILE_ONLY TRUE)
            target_sources(jfg-native-boot PRIVATE src/boot/direct_sp_access.cpp "${jfg_direct_sp_body}")
            target_compile_definitions(jfg-native-boot PRIVATE JFG_DIRECT_SP_ACCESS_ENABLED=1
                "JFG_DIRECT_SP_ACCESS_BODY=\"${jfg_direct_sp_body}\"")
            set_property(SOURCE src/boot/direct_sp_access.cpp APPEND PROPERTY COMPILE_OPTIONS /wd4702)
            set(jfg_native_shadow_body "${CMAKE_CURRENT_BINARY_DIR}/phase6-private/native-shadow-filter.inc")
            add_custom_command(OUTPUT "${jfg_native_shadow_body}"
                COMMAND "${Python3_EXECUTABLE}" "${CMAKE_CURRENT_SOURCE_DIR}/scripts/build/prepare_native_shadow_filter.py"
                    --generated-root "${JFG_GENERATED_ROOT}" --output "${jfg_native_shadow_body}"
                DEPENDS "${CMAKE_CURRENT_SOURCE_DIR}/scripts/build/prepare_native_shadow_filter.py"
                    "${CMAKE_CURRENT_SOURCE_DIR}/scripts/build/prepare_native_collision.py"
                    "${JFG_GENERATED_ROOT}/baseline/fn_004_0008_recomp.c"
                VERBATIM)
            set_source_files_properties("${jfg_native_shadow_body}" PROPERTIES HEADER_FILE_ONLY TRUE)
            target_sources(jfg-native-boot PRIVATE src/boot/native_shadow_filter.cpp "${jfg_native_shadow_body}")
            target_compile_definitions(jfg-native-boot PRIVATE JFG_NATIVE_SHADOW_FILTER_ENABLED=1
                "JFG_NATIVE_SHADOW_FILTER_BODY=\"${jfg_native_shadow_body}\"")
            set_property(SOURCE src/boot/native_shadow_filter.cpp APPEND PROPERTY COMPILE_OPTIONS /wd4702)
            set(jfg_native_cache_all_body "${CMAKE_CURRENT_BINARY_DIR}/phase6-private/native-cache-all.inc")
            add_custom_command(OUTPUT "${jfg_native_cache_all_body}"
                COMMAND "${Python3_EXECUTABLE}" "${CMAKE_CURRENT_SOURCE_DIR}/scripts/build/prepare_native_cache_all.py"
                    --generated-root "${JFG_GENERATED_ROOT}" --output "${jfg_native_cache_all_body}"
                DEPENDS "${CMAKE_CURRENT_SOURCE_DIR}/scripts/build/prepare_native_cache_all.py"
                    "${CMAKE_CURRENT_SOURCE_DIR}/scripts/build/prepare_native_collision.py"
                    "${JFG_GENERATED_ROOT}/baseline/fn_000_1568_recomp.c"
                VERBATIM)
            set_source_files_properties("${jfg_native_cache_all_body}" PROPERTIES HEADER_FILE_ONLY TRUE)
            target_sources(jfg-native-boot PRIVATE src/boot/native_cache_all.cpp "${jfg_native_cache_all_body}")
            target_compile_definitions(jfg-native-boot PRIVATE JFG_NATIVE_CACHE_ALL_ENABLED=1
                "JFG_NATIVE_CACHE_ALL_BODY=\"${jfg_native_cache_all_body}\"")
            set_property(SOURCE src/boot/native_cache_all.cpp APPEND PROPERTY COMPILE_OPTIONS /wd4702)
        endif()

        if(JFG_BUILD_PHASE8_LIVE)
            jfg_resolve_private_root(jfg_phase8_private_audio_adapter_root
                "${JFG_PHASE8_PRIVATE_AUDIO_ADAPTER_ROOT}"
                "JFG_PHASE8_PRIVATE_AUDIO_ADAPTER_ROOT")
            jfg_resolve_private_root(jfg_phase8_private_audio_runtime_include
                "${JFG_PHASE8_PRIVATE_AUDIO_RUNTIME_INCLUDE}"
                "JFG_PHASE8_PRIVATE_AUDIO_RUNTIME_INCLUDE")
            set(jfg_phase8_private_audio_adapter_source
                "${jfg_phase8_private_audio_adapter_root}/production-audio-adapter.cpp")
            set(jfg_phase8_private_audio_generated_source
                "${jfg_phase8_private_audio_adapter_root}/brokered-jfg-audio-probe.cpp")
            foreach(jfg_phase8_private_audio_file IN ITEMS
                "${jfg_phase8_private_audio_adapter_source}"
                "${jfg_phase8_private_audio_generated_source}")
                if(IS_SYMLINK "${jfg_phase8_private_audio_file}" OR
                   NOT EXISTS "${jfg_phase8_private_audio_file}" OR
                   IS_DIRECTORY "${jfg_phase8_private_audio_file}")
                    message(FATAL_ERROR
                        "The Phase 8 private audio adapter closure is incomplete")
                endif()
            endforeach()
            get_filename_component(jfg_phase8_private_audio_runtime_root
                "${jfg_phase8_private_audio_runtime_include}/../.." ABSOLUTE)
            target_sources(jfg-native-boot PRIVATE
                "${jfg_phase8_private_audio_adapter_source}"
                "${jfg_phase8_private_audio_generated_source}")
            set_property(SOURCE "${jfg_phase8_private_audio_generated_source}"
                APPEND PROPERTY COMPILE_OPTIONS
                "$<$<CXX_COMPILER_ID:MSVC>:/wd4100>"
                "$<$<CXX_COMPILER_ID:MSVC>:/wd4702>"
                "$<$<NOT:$<CXX_COMPILER_ID:MSVC>>:-Wno-unused-parameter>")
            set_property(SOURCE
                "${jfg_phase8_private_audio_adapter_source}"
                "${jfg_phase8_private_audio_generated_source}"
                APPEND PROPERTY COMPILE_OPTIONS
                "$<$<NOT:$<CXX_COMPILER_ID:MSVC>>:-msse4.2>")
            target_include_directories(jfg-native-boot PRIVATE
                "${jfg_phase8_private_audio_adapter_root}")
            target_include_directories(jfg-native-boot SYSTEM PRIVATE
                "${jfg_phase8_private_audio_runtime_include}"
                "${jfg_phase8_private_audio_runtime_root}/ultramodern/include"
                "${jfg_rt64_root}/src/contrib/mupen64plus-win32-deps/SDL2-2.26.3/include")
            target_compile_definitions(jfg-native-boot PRIVATE
                JFG_PHASE8_LIVE_RUNTIME=1
                SDL_MAIN_HANDLED=1)
            target_link_directories(jfg-native-boot PRIVATE
                "${jfg_rt64_root}/src/contrib/mupen64plus-win32-deps/SDL2-2.26.3/lib/x64")
            target_link_libraries(jfg-native-boot PRIVATE
                jfg_rt64_renderer SDL2 user32)
            add_custom_command(TARGET jfg-native-boot POST_BUILD
                COMMAND "${CMAKE_COMMAND}" -E copy_if_different
                    "${jfg_rt64_root}/src/contrib/mupen64plus-win32-deps/SDL2-2.26.3/lib/x64/SDL2.dll"
                    "${jfg_rt64_root}/src/contrib/dxc/bin/x64/dxcompiler.dll"
                    "${jfg_rt64_root}/src/contrib/dxc/bin/x64/dxil.dll"
                    "$<TARGET_FILE_DIR:jfg-native-boot>"
                VERBATIM)
            if(MSVC)
                target_link_options(jfg-native-boot PRIVATE
                    "/MAP:${CMAKE_CURRENT_BINARY_DIR}/phase8-private-native-boot.map")
            endif()
        endif()
        if(WIN32)
            target_sources(jfg-native-boot PRIVATE "${jfg_application_icon}")
            target_link_libraries(jfg-native-boot PRIVATE advapi32 psapi)
            add_dependencies(jfg-native-boot jfg-support-capture)
            # Recompiled MIPS calls are ordinary host calls; boot-time overlay
            # initialization is substantially deeper than the MSVC 1 MiB
            # default, including on the deterministic guest-thread workers.
            target_link_options(jfg-native-boot PRIVATE /STACK:16777216)
            if(JFG_ENABLE_ADDRESS_SANITIZER AND MSVC)
                get_filename_component(jfg_msvc_tool_directory
                    "${CMAKE_CXX_COMPILER}" DIRECTORY)
                set(jfg_msvc_asan_runtime
                    "${jfg_msvc_tool_directory}/clang_rt.asan_dynamic-x86_64.dll")
                if(NOT EXISTS "${jfg_msvc_asan_runtime}")
                    message(FATAL_ERROR "MSVC AddressSanitizer runtime is unavailable")
                endif()
                add_custom_command(TARGET jfg-native-boot POST_BUILD
                    COMMAND "${CMAKE_COMMAND}" -E copy_if_different
                        "${jfg_msvc_asan_runtime}" "$<TARGET_FILE_DIR:jfg-native-boot>"
                    VERBATIM)
            endif()
        endif()
        target_compile_features(jfg-native-boot PRIVATE cxx_std_20)
        jfg_set_project_warnings(jfg-native-boot)

        if(BUILD_TESTING AND JFG_BUILD_TESTS)
            if((JFG_PHASE6_ROM STREQUAL "" AND
                (NOT JFG_PHASE6_EMULATOR_CHECKPOINT STREQUAL "" OR
                 NOT JFG_PHASE6_BIZHAWK_EXECUTABLE STREQUAL "" OR
                 NOT JFG_PHASE6_EMULATOR_PROBE STREQUAL "")) OR
               (NOT JFG_PHASE6_ROM STREQUAL "" AND
                (JFG_PHASE6_EMULATOR_CHECKPOINT STREQUAL "" OR
                 JFG_PHASE6_BIZHAWK_EXECUTABLE STREQUAL "" OR
                 JFG_PHASE6_EMULATOR_PROBE STREQUAL "")))
                message(FATAL_ERROR
                    "Phase 6 ROM, checkpoint, BizHawk executable, and probe must be supplied together")
            endif()
            if(NOT JFG_PHASE6_ROM STREQUAL "")
                jfg_resolve_private_file(jfg_phase6_rom
                    "${JFG_PHASE6_ROM}" "JFG_PHASE6_ROM")
                jfg_resolve_private_file(jfg_phase6_emulator_checkpoint
                    "${JFG_PHASE6_EMULATOR_CHECKPOINT}"
                    "JFG_PHASE6_EMULATOR_CHECKPOINT")
                jfg_resolve_private_file(jfg_phase6_bizhawk_executable
                    "${JFG_PHASE6_BIZHAWK_EXECUTABLE}"
                    "JFG_PHASE6_BIZHAWK_EXECUTABLE")
                jfg_resolve_private_file(jfg_phase6_emulator_probe
                    "${JFG_PHASE6_EMULATOR_PROBE}"
                    "JFG_PHASE6_EMULATOR_PROBE")
                add_test(
                    NAME jfg.phase6_native_m2
                    COMMAND "${Python3_EXECUTABLE}"
                        "${CMAKE_CURRENT_SOURCE_DIR}/scripts/verification/verify_phase6_native_boot.py"
                        --executable "$<TARGET_FILE:jfg-native-boot>"
                        --rom "${jfg_phase6_rom}"
                        --oracle "${jfg_phase6_emulator_checkpoint}"
                        --generated-root "${JFG_GENERATED_ROOT}"
                        --identification "${jfg_phase6_libultra_identification}"
                        --bizhawk-executable "${jfg_phase6_bizhawk_executable}"
                        --oracle-probe "${jfg_phase6_emulator_probe}"
                        --expected-build-identity "${CMAKE_CXX_COMPILER_ID}-${CMAKE_CXX_COMPILER_VERSION}-$<CONFIG>"
                        --private-out "${CMAKE_CURRENT_BINARY_DIR}/phase6-private/native-boot-evidence.json"
                        --public-out "${CMAKE_CURRENT_BINARY_DIR}/phase6-private/native-boot-summary.json"
                        --stub-ledger-out "${CMAKE_CURRENT_BINARY_DIR}/phase6-private/native-stub-ledger.json"
                        --repeat 3)
                set_tests_properties(jfg.phase6_native_m2 PROPERTIES TIMEOUT 240)
            endif()
        endif()
    endif()

    if(JFG_BUILD_G2_PRODUCERS)
        function(jfg_add_g2_producer target)
            add_executable(${target} ${ARGN})
            target_include_directories(${target} PRIVATE
                "${CMAKE_CURRENT_SOURCE_DIR}/include"
            )
            target_compile_features(${target} PRIVATE cxx_std_20)
            jfg_set_project_warnings(${target})
        endfunction()

        add_executable(jfg_g2_overlay_producer
            src/evidence/g2_overlay_producer.cpp
            src/evidence/g2_trap_probe_runtime.cpp
        )
        target_include_directories(jfg_g2_overlay_producer SYSTEM PRIVATE
            "${JFG_GENERATED_ROOT}/include"
            "${JFG_GENERATED_ROOT}"
        )
        target_link_libraries(jfg_g2_overlay_producer PRIVATE
            jfg_runtime
            jfg_generated_g2_trap_link
        )
        target_compile_features(jfg_g2_overlay_producer PRIVATE cxx_std_20)
        jfg_set_project_warnings(jfg_g2_overlay_producer)

        foreach(required_private_variable IN ITEMS
            JFG_G2_PRIVATE_GRAPHICS_ORACLE_ROOT
            JFG_G2_PRIVATE_AUDIO_ADAPTER_ROOT
            JFG_G2_PRIVATE_AUDIO_RUNTIME_INCLUDE
            JFG_G2_PRIVATE_AUDIO_ORACLE_ROOT
        )
            if("${${required_private_variable}}" STREQUAL "")
                message(FATAL_ERROR
                    "JFG_BUILD_G2_PRODUCERS requires ${required_private_variable}")
            endif()
        endforeach()

        jfg_resolve_private_root(jfg_g2_private_graphics_oracle_root
            "${JFG_G2_PRIVATE_GRAPHICS_ORACLE_ROOT}"
            "JFG_G2_PRIVATE_GRAPHICS_ORACLE_ROOT")
        jfg_resolve_private_root(jfg_g2_private_audio_adapter_root
            "${JFG_G2_PRIVATE_AUDIO_ADAPTER_ROOT}"
            "JFG_G2_PRIVATE_AUDIO_ADAPTER_ROOT")
        jfg_resolve_private_root(jfg_g2_private_audio_runtime_include
            "${JFG_G2_PRIVATE_AUDIO_RUNTIME_INCLUDE}"
            "JFG_G2_PRIVATE_AUDIO_RUNTIME_INCLUDE")
        jfg_resolve_private_root(jfg_g2_private_audio_oracle_root
            "${JFG_G2_PRIVATE_AUDIO_ORACLE_ROOT}"
            "JFG_G2_PRIVATE_AUDIO_ORACLE_ROOT")

        if(jfg_g2_private_audio_adapter_root STREQUAL
                jfg_g2_private_audio_oracle_root)
            message(FATAL_ERROR
                "G2 native and oracle adapters must use distinct private roots")
        endif()

        set(jfg_g2_private_graphics_oracle_source
            "${jfg_g2_private_graphics_oracle_root}/production-graphics-oracle-adapter.cpp")
        set(jfg_g2_private_audio_adapter_source
            "${jfg_g2_private_audio_adapter_root}/production-audio-adapter.cpp")
        set(jfg_g2_private_audio_generated_source
            "${jfg_g2_private_audio_adapter_root}/brokered-jfg-audio-probe.cpp")
        set(jfg_g2_private_audio_oracle_source
            "${jfg_g2_private_audio_oracle_root}/production-audio-oracle-adapter.cpp")
        foreach(required_private_file IN ITEMS
            "${jfg_g2_private_graphics_oracle_source}"
            "${jfg_g2_private_audio_adapter_source}"
            "${jfg_g2_private_audio_generated_source}"
            "${jfg_g2_private_audio_oracle_source}"
        )
            if(IS_SYMLINK "${required_private_file}" OR
               NOT EXISTS "${required_private_file}" OR
               IS_DIRECTORY "${required_private_file}")
                message(FATAL_ERROR
                    "A fixed G2 private adapter closure file is absent")
            endif()
        endforeach()

        jfg_add_g2_producer(jfg_g2_graphics_native_producer
            src/evidence/g2_graphics_native_producer.cpp
            src/evidence/g2_graphics_bounded_adapter.cpp
        )
        target_link_libraries(jfg_g2_graphics_native_producer PRIVATE
            jfg_runtime)

        jfg_add_g2_producer(jfg_g2_graphics_oracle_producer
            src/evidence/g2_graphics_oracle_producer.cpp
            "${jfg_g2_private_graphics_oracle_source}"
        )

        get_filename_component(jfg_g2_private_audio_runtime_root
            "${jfg_g2_private_audio_runtime_include}/../.." ABSOLUTE)
        jfg_add_g2_producer(jfg_g2_audio_native_producer
            src/evidence/g2_audio_native_producer.cpp
            "${jfg_g2_private_audio_adapter_source}"
            "${jfg_g2_private_audio_generated_source}"
        )
        set_property(SOURCE "${jfg_g2_private_audio_generated_source}"
            APPEND PROPERTY COMPILE_OPTIONS
            "$<$<CXX_COMPILER_ID:MSVC>:/wd4100>"
            "$<$<CXX_COMPILER_ID:MSVC>:/wd4702>"
            "$<$<NOT:$<CXX_COMPILER_ID:MSVC>>:-Wno-unused-parameter>"
        )
        # librecomp's RSP vector unit uses SSE4 intrinsics behind always_inline
        # wrappers; GCC and Clang require the target feature explicitly, while
        # x64 MSVC exposes these intrinsics unconditionally.
        set_property(SOURCE
            "${jfg_g2_private_audio_adapter_source}"
            "${jfg_g2_private_audio_generated_source}"
            APPEND PROPERTY COMPILE_OPTIONS
            "$<$<NOT:$<CXX_COMPILER_ID:MSVC>>:-msse4.2>"
        )
        target_include_directories(jfg_g2_audio_native_producer PRIVATE
            "${jfg_g2_private_audio_adapter_root}"
        )
        target_include_directories(jfg_g2_audio_native_producer SYSTEM PRIVATE
            "${jfg_g2_private_audio_runtime_include}"
            "${jfg_g2_private_audio_runtime_root}/ultramodern/include"
            "${JFG_GENERATED_ROOT}/include"
            "${JFG_GENERATED_ROOT}"
        )
        target_link_libraries(jfg_g2_audio_native_producer PRIVATE jfg_runtime)

        jfg_add_g2_producer(jfg_g2_audio_oracle_producer
            src/evidence/g2_audio_oracle_producer.cpp
            "${jfg_g2_private_audio_oracle_source}"
        )
        # The independent audio oracle ABI is implemented against an HLE core
        # whose build is described by the ignored oracle root itself.
        add_subdirectory("${jfg_g2_private_audio_oracle_root}"
            jfg-g2-private-audio-oracle-core EXCLUDE_FROM_ALL)
        target_link_libraries(jfg_g2_audio_oracle_producer PRIVATE
            jfg_private_mupen_hle)

        jfg_add_g2_producer(jfg_g2_save_native_producer
            src/evidence/g2_save_native_producer.cpp
        )
        target_link_libraries(jfg_g2_save_native_producer PRIVATE jfg_runtime)

        jfg_add_g2_producer(jfg_g2_save_oracle_producer
            src/evidence/g2_save_oracle_producer.cpp
        )

        jfg_add_g2_producer(jfg_g2_cpu_producer
            src/evidence/g2_cpu_producer.cpp
        )
        jfg_add_g2_producer(jfg_g2_rsp_producer
            src/evidence/g2_rsp_producer.cpp
        )
        jfg_add_g2_producer(jfg_g2_trap_producer
            src/evidence/g2_trap_producer.cpp
            src/evidence/g2_trap_probe_runtime.cpp
        )
        jfg_add_g2_producer(jfg_g2_trap_oracle_producer
            src/evidence/g2_trap_oracle_producer.cpp
        )
    endif()

    if(BUILD_TESTING AND JFG_BUILD_TESTS)
        jfg_add_generated_code_tests(
            NAME jfg_generated
            LINK_SMOKE_SOURCE "${CMAKE_CURRENT_SOURCE_DIR}/tests/boot/generated_link_smoke.cpp"
            BASELINE_AUDIT_SOURCE "${CMAKE_CURRENT_SOURCE_DIR}/tests/generated_baseline_audit.cpp"
            PATCH_AUDIT_SOURCE "${CMAKE_CURRENT_SOURCE_DIR}/tests/generated_patch_audit.cpp"
        )
    endif()
endif()
