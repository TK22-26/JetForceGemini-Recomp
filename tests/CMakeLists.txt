add_executable(jfg_original_os_probe_tests boot/original_os_probe_tests.cpp)
target_include_directories(jfg_original_os_probe_tests PRIVATE "${PROJECT_SOURCE_DIR}/include")
target_compile_features(jfg_original_os_probe_tests PRIVATE cxx_std_20)
jfg_set_project_warnings(jfg_original_os_probe_tests)
add_test(NAME jfg.original_os_probe COMMAND jfg_original_os_probe_tests)
add_executable(jfg_save_namespace_tests runtime/save_namespace_tests.cpp)
target_link_libraries(jfg_save_namespace_tests PRIVATE jfg_runtime)
target_compile_features(jfg_save_namespace_tests PRIVATE cxx_std_20)
jfg_set_project_warnings(jfg_save_namespace_tests)
add_test(NAME jfg.save_namespace COMMAND jfg_save_namespace_tests)
add_executable(jfg_vi_device_clock_tests boot/vi_device_clock_tests.cpp)
target_include_directories(jfg_vi_device_clock_tests PRIVATE "${PROJECT_SOURCE_DIR}/include")
target_compile_features(jfg_vi_device_clock_tests PRIVATE cxx_std_20)
jfg_set_project_warnings(jfg_vi_device_clock_tests)
add_test(NAME jfg.vi_device_clock COMMAND jfg_vi_device_clock_tests)
add_executable(jfg_game_descriptor_tests runtime/game_descriptor_tests.cpp)
target_link_libraries(jfg_game_descriptor_tests PRIVATE jfg_runtime)
target_compile_features(jfg_game_descriptor_tests PRIVATE cxx_std_20)
jfg_set_project_warnings(jfg_game_descriptor_tests)
add_test(NAME jfg.game_descriptor COMMAND jfg_game_descriptor_tests)

add_executable(jfg_native_audio_source_tests runtime/native_audio_source_tests.cpp)
target_link_libraries(jfg_native_audio_source_tests PRIVATE jfg_boot)
target_compile_features(jfg_native_audio_source_tests PRIVATE cxx_std_20)
jfg_set_project_warnings(jfg_native_audio_source_tests)
add_test(NAME jfg.native_audio_source COMMAND jfg_native_audio_source_tests)

add_executable(jfg_audio_dma_broker_tests runtime/audio_dma_broker_tests.cpp)
target_include_directories(jfg_audio_dma_broker_tests PRIVATE "${PROJECT_SOURCE_DIR}/include")
target_compile_features(jfg_audio_dma_broker_tests PRIVATE cxx_std_20)
jfg_set_project_warnings(jfg_audio_dma_broker_tests)
add_test(NAME jfg.audio_dma_broker COMMAND jfg_audio_dma_broker_tests)

add_executable(jfg_timer_tests boot/timer_tests.cpp)
add_executable(jfg_guest_thread_transport_tests runtime/guest_thread_transport_tests.cpp)
target_link_libraries(jfg_guest_thread_transport_tests PRIVATE jfg_boot)
target_compile_features(jfg_guest_thread_transport_tests PRIVATE cxx_std_20)
jfg_set_project_warnings(jfg_guest_thread_transport_tests)
add_test(NAME jfg.guest_thread_transport COMMAND jfg_guest_thread_transport_tests)
add_executable(jfg_guest_eret_observation_tests boot/guest_eret_observation_tests.cpp)
target_link_libraries(jfg_guest_eret_observation_tests PRIVATE jfg_boot)
target_compile_features(jfg_guest_eret_observation_tests PRIVATE cxx_std_20)
jfg_set_project_warnings(jfg_guest_eret_observation_tests)
add_test(NAME jfg.guest_eret_observation COMMAND jfg_guest_eret_observation_tests)
add_executable(jfg_eret_transfer_probe_tests boot/eret_transfer_probe_tests.cpp)
target_include_directories(jfg_eret_transfer_probe_tests PRIVATE "${PROJECT_SOURCE_DIR}/include")
target_compile_features(jfg_eret_transfer_probe_tests PRIVATE cxx_std_20)
jfg_set_project_warnings(jfg_eret_transfer_probe_tests)
add_test(NAME jfg.eret_transfer_probe COMMAND jfg_eret_transfer_probe_tests)
add_executable(jfg_instruction_effect_trace_tests boot/instruction_effect_trace_tests.cpp)
target_include_directories(jfg_instruction_effect_trace_tests PRIVATE "${PROJECT_SOURCE_DIR}/include")
target_compile_features(jfg_instruction_effect_trace_tests PRIVATE cxx_std_20)
jfg_set_project_warnings(jfg_instruction_effect_trace_tests)
add_test(NAME jfg.instruction_effect_trace COMMAND jfg_instruction_effect_trace_tests
  "${CMAKE_CURRENT_BINARY_DIR}/instruction-effect-test.bin")
add_executable(jfg_reference_pif_boot_tests boot/reference_pif_boot_tests.cpp)
target_include_directories(jfg_reference_pif_boot_tests PRIVATE "${PROJECT_SOURCE_DIR}/include")
target_compile_features(jfg_reference_pif_boot_tests PRIVATE cxx_std_20)
jfg_set_project_warnings(jfg_reference_pif_boot_tests)
add_test(NAME jfg.reference_pif_boot COMMAND jfg_reference_pif_boot_tests)
add_executable(jfg_recorded_input_timeline_tests runtime/recorded_input_timeline_tests.cpp)
target_include_directories(jfg_recorded_input_timeline_tests PRIVATE "${PROJECT_SOURCE_DIR}/include")
target_compile_features(jfg_recorded_input_timeline_tests PRIVATE cxx_std_20)
jfg_set_project_warnings(jfg_recorded_input_timeline_tests)
add_test(NAME jfg.recorded_input_timeline COMMAND jfg_recorded_input_timeline_tests)
add_executable(jfg_host_count_clock_tests boot/host_count_clock_tests.cpp)
target_include_directories(jfg_host_count_clock_tests PRIVATE "${PROJECT_SOURCE_DIR}/include")
target_compile_features(jfg_host_count_clock_tests PRIVATE cxx_std_20)
jfg_set_project_warnings(jfg_host_count_clock_tests)
add_test(NAME jfg.host_count_clock COMMAND jfg_host_count_clock_tests)
add_executable(jfg_execution_clock_tests boot/execution_clock_tests.cpp)
target_link_libraries(jfg_execution_clock_tests PRIVATE jfg_boot)
target_compile_features(jfg_execution_clock_tests PRIVATE cxx_std_20)
jfg_set_project_warnings(jfg_execution_clock_tests)
add_test(NAME jfg.execution_clock COMMAND jfg_execution_clock_tests)
add_executable(jfg_tlb_tests boot/tlb_tests.cpp)
target_include_directories(jfg_tlb_tests PRIVATE "${PROJECT_SOURCE_DIR}/include")
target_compile_features(jfg_tlb_tests PRIVATE cxx_std_20)
jfg_set_project_warnings(jfg_tlb_tests)
add_test(NAME jfg.tlb COMMAND jfg_tlb_tests)
add_executable(jfg_mi_interrupt_mask_tests boot/mi_interrupt_mask_tests.cpp)
target_include_directories(jfg_mi_interrupt_mask_tests PRIVATE "${PROJECT_SOURCE_DIR}/include")
target_compile_features(jfg_mi_interrupt_mask_tests PRIVATE cxx_std_20)
jfg_set_project_warnings(jfg_mi_interrupt_mask_tests)
add_test(NAME jfg.mi_interrupt_mask COMMAND jfg_mi_interrupt_mask_tests)
add_executable(jfg_sp_status_tests boot/sp_status_tests.cpp)
target_include_directories(jfg_sp_status_tests PRIVATE "${PROJECT_SOURCE_DIR}/include")
target_compile_features(jfg_sp_status_tests PRIVATE cxx_std_20)
jfg_set_project_warnings(jfg_sp_status_tests)
add_test(NAME jfg.sp_status COMMAND jfg_sp_status_tests)
add_executable(jfg_point_probe_tests boot/point_probe_tests.cpp)
target_include_directories(jfg_point_probe_tests PRIVATE "${PROJECT_SOURCE_DIR}/include")
target_compile_features(jfg_point_probe_tests PRIVATE cxx_std_20)
jfg_set_project_warnings(jfg_point_probe_tests)
add_test(NAME jfg.point_probe COMMAND jfg_point_probe_tests)

add_executable(jfg_device_event_probe_tests boot/device_event_probe_tests.c)
target_include_directories(jfg_device_event_probe_tests PRIVATE "${PROJECT_SOURCE_DIR}/include")
target_compile_features(jfg_device_event_probe_tests PRIVATE c_std_11)
jfg_set_project_warnings(jfg_device_event_probe_tests)
add_test(NAME jfg.device_event_probe COMMAND jfg_device_event_probe_tests)
add_executable(jfg_device_event_probe_cpp_tests platform/device_event_probe_cpp_tests.cpp)
target_include_directories(jfg_device_event_probe_cpp_tests PRIVATE "${PROJECT_SOURCE_DIR}/include")
target_compile_features(jfg_device_event_probe_cpp_tests PRIVATE cxx_std_20)
jfg_set_project_warnings(jfg_device_event_probe_cpp_tests)
add_test(NAME jfg.device_event_probe_cpp COMMAND jfg_device_event_probe_cpp_tests)

add_executable(jfg_reference_event_commit_tests boot/reference_event_commit_tests.cpp)
target_include_directories(jfg_reference_event_commit_tests PRIVATE "${PROJECT_SOURCE_DIR}/include")
target_compile_features(jfg_reference_event_commit_tests PRIVATE cxx_std_20)
jfg_set_project_warnings(jfg_reference_event_commit_tests)
add_test(NAME jfg.reference_event_commit COMMAND jfg_reference_event_commit_tests)

add_executable(jfg_flash_device_tests boot/flash_device_tests.cpp)
target_link_libraries(jfg_flash_device_tests PRIVATE jfg_runtime)
target_compile_features(jfg_flash_device_tests PRIVATE cxx_std_20)
jfg_set_project_warnings(jfg_flash_device_tests)
add_test(NAME jfg.flash_device COMMAND jfg_flash_device_tests)

add_executable(jfg_reference_flash_bus_tests boot/reference_flash_bus_tests.cpp)
target_link_libraries(jfg_reference_flash_bus_tests PRIVATE jfg_runtime)
target_compile_features(jfg_reference_flash_bus_tests PRIVATE cxx_std_20)
jfg_set_project_warnings(jfg_reference_flash_bus_tests)
add_test(NAME jfg.reference_flash_bus COMMAND jfg_reference_flash_bus_tests)

add_executable(jfg_reference_ai_dma_tests boot/reference_ai_dma_tests.cpp)
target_include_directories(jfg_reference_ai_dma_tests PRIVATE "${PROJECT_SOURCE_DIR}/include")
target_compile_features(jfg_reference_ai_dma_tests PRIVATE cxx_std_20)
jfg_set_project_warnings(jfg_reference_ai_dma_tests)
add_test(NAME jfg.reference_ai_dma COMMAND jfg_reference_ai_dma_tests)

add_executable(jfg_reference_si_dma_tests boot/reference_si_dma_tests.cpp)
target_link_libraries(jfg_reference_si_dma_tests PRIVATE jfg_runtime)
target_include_directories(jfg_reference_si_dma_tests PRIVATE "${PROJECT_SOURCE_DIR}/include")
target_compile_features(jfg_reference_si_dma_tests PRIVATE cxx_std_20)
jfg_set_project_warnings(jfg_reference_si_dma_tests)
add_test(NAME jfg.reference_si_dma COMMAND jfg_reference_si_dma_tests)

add_executable(jfg_reference_compare_tests boot/reference_compare_tests.cpp)
target_include_directories(jfg_reference_compare_tests PRIVATE "${PROJECT_SOURCE_DIR}/include")
target_compile_features(jfg_reference_compare_tests PRIVATE cxx_std_20)
jfg_set_project_warnings(jfg_reference_compare_tests)
add_test(NAME jfg.reference_compare COMMAND jfg_reference_compare_tests)

add_executable(jfg_reference_pi_dma_tests boot/reference_pi_dma_tests.cpp)
target_include_directories(jfg_reference_pi_dma_tests PRIVATE "${PROJECT_SOURCE_DIR}/include")
target_compile_features(jfg_reference_pi_dma_tests PRIVATE cxx_std_20)
jfg_set_project_warnings(jfg_reference_pi_dma_tests)
add_test(NAME jfg.reference_pi_dma COMMAND jfg_reference_pi_dma_tests)

add_executable(jfg_reference_sp_dma_tests boot/reference_sp_dma_tests.cpp)
target_include_directories(jfg_reference_sp_dma_tests PRIVATE "${PROJECT_SOURCE_DIR}/include")
target_compile_features(jfg_reference_sp_dma_tests PRIVATE cxx_std_20)
jfg_set_project_warnings(jfg_reference_sp_dma_tests)
add_test(NAME jfg.reference_sp_dma COMMAND jfg_reference_sp_dma_tests)
add_executable(jfg_reference_device_timing_tests boot/reference_device_timing_tests.cpp)
target_include_directories(jfg_reference_device_timing_tests PRIVATE "${PROJECT_SOURCE_DIR}/include")
target_compile_features(jfg_reference_device_timing_tests PRIVATE cxx_std_20)
jfg_set_project_warnings(jfg_reference_device_timing_tests)
add_test(NAME jfg.reference_device_timing COMMAND jfg_reference_device_timing_tests)
add_executable(jfg_oracle_round_even_tests diagnostics/oracle_round_even_tests.c)
target_compile_features(jfg_oracle_round_even_tests PRIVATE c_std_99)
if(NOT MSVC)
    target_link_libraries(jfg_oracle_round_even_tests PRIVATE m)
    target_compile_options(jfg_oracle_round_even_tests PRIVATE -frounding-math)
endif()
add_test(NAME jfg.oracle_round_even COMMAND jfg_oracle_round_even_tests)
target_link_libraries(jfg_timer_tests PRIVATE jfg_boot)
target_compile_features(jfg_timer_tests PRIVATE cxx_std_20)
jfg_set_project_warnings(jfg_timer_tests)
add_test(NAME jfg.timers COMMAND jfg_timer_tests)

add_executable(jfg_unit_tests
    runtime/runtime_tests.cpp
)

target_link_libraries(jfg_unit_tests PRIVATE jfg_runtime)
target_compile_features(jfg_unit_tests PRIVATE cxx_std_20)
jfg_set_project_warnings(jfg_unit_tests)

add_test(NAME jfg.unit COMMAND jfg_unit_tests)

# This deliberately does not link jfg_runtime or any generated-code target:
# the probe exports the alternate trap ABI symbols that minimal_runtime.cpp
# normally owns.  It is a ROM-free mechanics test only, not G2 evidence.
add_executable(jfg_g2_trap_probe_runtime_tests
    "${PROJECT_SOURCE_DIR}/src/evidence/g2_trap_probe_runtime.cpp"
    runtime/g2_trap_probe_runtime_tests.cpp
)
target_include_directories(jfg_g2_trap_probe_runtime_tests PRIVATE
    "${PROJECT_SOURCE_DIR}/include"
)
target_compile_features(jfg_g2_trap_probe_runtime_tests PRIVATE cxx_std_20)
target_compile_definitions(jfg_g2_trap_probe_runtime_tests PRIVATE JFG_G2_TRAP_PROBE_TESTING=1)
find_package(Threads REQUIRED)
target_link_libraries(jfg_g2_trap_probe_runtime_tests PRIVATE Threads::Threads)
jfg_set_project_warnings(jfg_g2_trap_probe_runtime_tests)
add_test(
    NAME jfg.g2_trap_probe_runtime
    COMMAND jfg_g2_trap_probe_runtime_tests
)

add_executable(jfg_audio_task_bridge_tests
    runtime/audio_task_bridge_tests.cpp
)
target_link_libraries(jfg_audio_task_bridge_tests PRIVATE jfg_runtime)
target_compile_features(jfg_audio_task_bridge_tests PRIVATE cxx_std_20)
jfg_set_project_warnings(jfg_audio_task_bridge_tests)
add_test(NAME jfg.audio_task_bridge COMMAND jfg_audio_task_bridge_tests)

add_executable(jfg_input_replay_tests
    runtime/input_replay_tests.cpp
)
target_link_libraries(jfg_input_replay_tests PRIVATE jfg_runtime)
target_compile_features(jfg_input_replay_tests PRIVATE cxx_std_20)
jfg_set_project_warnings(jfg_input_replay_tests)
add_test(NAME jfg.input_replay COMMAND jfg_input_replay_tests)

add_executable(jfg_input_stick_tests
    runtime/input_stick_tests.cpp
)
target_link_libraries(jfg_input_stick_tests PRIVATE jfg_runtime)
target_compile_features(jfg_input_stick_tests PRIVATE cxx_std_20)
jfg_set_project_warnings(jfg_input_stick_tests)
add_test(NAME jfg.input_stick COMMAND jfg_input_stick_tests)

add_executable(jfg_cic_nus_6105_tests
    runtime/cic_nus_6105_tests.cpp
)
target_link_libraries(jfg_cic_nus_6105_tests PRIVATE jfg_runtime)
target_compile_features(jfg_cic_nus_6105_tests PRIVATE cxx_std_20)
jfg_set_project_warnings(jfg_cic_nus_6105_tests)
add_test(NAME jfg.cic_nus_6105 COMMAND jfg_cic_nus_6105_tests)

add_executable(jfg_controller_pak_tests
    runtime/controller_pak_tests.cpp
)
target_link_libraries(jfg_controller_pak_tests PRIVATE jfg_runtime)
target_compile_features(jfg_controller_pak_tests PRIVATE cxx_std_20)
jfg_set_project_warnings(jfg_controller_pak_tests)
add_test(NAME jfg.controller_pak COMMAND jfg_controller_pak_tests)

add_executable(jfg_custom_overlay_relocator_tests
    runtime/custom_overlay_relocator_tests.cpp
)
target_link_libraries(jfg_custom_overlay_relocator_tests PRIVATE jfg_runtime)
target_compile_features(jfg_custom_overlay_relocator_tests PRIVATE cxx_std_20)
jfg_set_project_warnings(jfg_custom_overlay_relocator_tests)
add_test(
    NAME jfg.custom_overlay_relocator
    COMMAND jfg_custom_overlay_relocator_tests
)

add_executable(jfg_save_device_runtime_tests
    runtime/save_device_runtime_tests.cpp
)
target_link_libraries(jfg_save_device_runtime_tests PRIVATE jfg_runtime)
target_compile_features(jfg_save_device_runtime_tests PRIVATE cxx_std_20)
jfg_set_project_warnings(jfg_save_device_runtime_tests)
add_test(NAME jfg.save_device_runtime COMMAND jfg_save_device_runtime_tests)

add_executable(jfg_generated_overlay_runtime_tests
    runtime/generated_overlay_runtime_tests.cpp
)
target_link_libraries(jfg_generated_overlay_runtime_tests PRIVATE jfg_runtime)
target_compile_features(jfg_generated_overlay_runtime_tests PRIVATE cxx_std_20)
jfg_set_project_warnings(jfg_generated_overlay_runtime_tests)
add_test(
    NAME jfg.generated_overlay_runtime
    COMMAND jfg_generated_overlay_runtime_tests
)

add_executable(jfg_graphics_task_bridge_tests
    renderer/graphics_task_bridge_tests.cpp
)
target_link_libraries(jfg_graphics_task_bridge_tests PRIVATE jfg_runtime)
target_compile_features(jfg_graphics_task_bridge_tests PRIVATE cxx_std_20)
jfg_set_project_warnings(jfg_graphics_task_bridge_tests)
add_test(NAME jfg.graphics_task_bridge COMMAND jfg_graphics_task_bridge_tests)

add_executable(jfg_rt64_overlay_address_tests
    renderer/rt64_overlay_address_tests.cpp
)
target_link_libraries(jfg_rt64_overlay_address_tests PRIVATE jfg_runtime)
target_compile_features(jfg_rt64_overlay_address_tests PRIVATE cxx_std_20)
jfg_set_project_warnings(jfg_rt64_overlay_address_tests)
add_test(NAME jfg.rt64_overlay_address COMMAND jfg_rt64_overlay_address_tests)

add_executable(jfg_renderer_callbacks_tests
    renderer/renderer_callbacks_tests.cpp
)
target_link_libraries(jfg_renderer_callbacks_tests PRIVATE jfg_runtime)
target_compile_features(jfg_renderer_callbacks_tests PRIVATE cxx_std_20)
jfg_set_project_warnings(jfg_renderer_callbacks_tests)
add_test(NAME jfg.renderer_callbacks COMMAND jfg_renderer_callbacks_tests)

include("${CMAKE_CURRENT_SOURCE_DIR}/cmake/renderer.cmake")

add_executable(jfg_bounded_custom_graphics_tests
    renderer/bounded_custom_graphics_tests.cpp
)
target_link_libraries(jfg_bounded_custom_graphics_tests PRIVATE jfg_runtime)
target_compile_features(jfg_bounded_custom_graphics_tests PRIVATE cxx_std_20)
jfg_set_project_warnings(jfg_bounded_custom_graphics_tests)
add_test(
    NAME jfg.bounded_custom_graphics
    COMMAND jfg_bounded_custom_graphics_tests
)

add_executable(jfg_testkernel_tests
    testkernel/testkernel_tests.cpp
)
target_link_libraries(jfg_testkernel_tests PRIVATE jfg_testkernel)
target_compile_features(jfg_testkernel_tests PRIVATE cxx_std_20)
jfg_set_project_warnings(jfg_testkernel_tests)
add_test(NAME jfg.testkernel COMMAND jfg_testkernel_tests)

add_test(NAME jfg.testkernel_self_check COMMAND jfg-test self-check)
add_test(NAME jfg.testkernel_repeat COMMAND jfg-test repeat 5)

add_executable(jfg_boot_tests
    boot/boot_tests.cpp
)
target_link_libraries(jfg_boot_tests PRIVATE jfg_boot)
target_compile_features(jfg_boot_tests PRIVATE cxx_std_20)
jfg_set_project_warnings(jfg_boot_tests)
add_test(NAME jfg.boot COMMAND jfg_boot_tests)

add_executable(jfg_reset_handoff_tests boot/reset_handoff_tests.cpp)
target_link_libraries(jfg_reset_handoff_tests PRIVATE jfg_boot)
target_compile_features(jfg_reset_handoff_tests PRIVATE cxx_std_20)
jfg_set_project_warnings(jfg_reset_handoff_tests)
add_test(NAME jfg.reset_handoff COMMAND jfg_reset_handoff_tests)

add_executable(jfg_hle_tests
    boot/hle_tests.cpp
)
target_link_libraries(jfg_hle_tests PRIVATE jfg_boot)
target_compile_features(jfg_hle_tests PRIVATE cxx_std_20)
jfg_set_project_warnings(jfg_hle_tests)
add_test(NAME jfg.hle COMMAND jfg_hle_tests)

add_executable(jfg_runlink_module_table_tests
    runtime/runlink_module_table_tests.cpp
)
target_link_libraries(jfg_runlink_module_table_tests PRIVATE jfg_boot)
target_compile_features(jfg_runlink_module_table_tests PRIVATE cxx_std_20)
jfg_set_project_warnings(jfg_runlink_module_table_tests)
add_test(
    NAME jfg.runlink_module_table
    COMMAND jfg_runlink_module_table_tests
)

add_executable(jfg_executor_tests
    runtime/executor_tests.cpp
)
target_link_libraries(jfg_executor_tests PRIVATE jfg_boot)
target_compile_features(jfg_executor_tests PRIVATE cxx_std_20)
jfg_set_project_warnings(jfg_executor_tests)
add_test(NAME jfg.executor COMMAND jfg_executor_tests)

add_executable(jfg_thread_scheduler_tests
    runtime/thread_scheduler_tests.cpp
)
target_link_libraries(jfg_thread_scheduler_tests PRIVATE jfg_boot)
target_compile_features(jfg_thread_scheduler_tests PRIVATE cxx_std_20)
jfg_set_project_warnings(jfg_thread_scheduler_tests)
add_test(NAME jfg.thread_scheduler COMMAND jfg_thread_scheduler_tests)

add_test(NAME jfg.boot_self_check COMMAND jfg-boot self-check)
add_test(NAME jfg.boot_repeat COMMAND jfg-boot repeat 5)
add_test(NAME jfg.boot_invalid_rom COMMAND jfg-boot invalid-rom)

add_test(
    NAME jfg.no_rom
    COMMAND "${CMAKE_COMMAND}"
        "-DPROGRAM=$<TARGET_FILE:jfg>"
        "-DEXPECTED=No ROM was provided"
        -P "${CMAKE_CURRENT_SOURCE_DIR}/cmake/check_expected_failure.cmake"
)

add_test(
    NAME jfg.missing_rom
    COMMAND "${CMAKE_COMMAND}"
        "-DPROGRAM=$<TARGET_FILE:jfg>"
        "-DARGUMENTS=--rom;definitely-missing.z64"
        "-DEXPECTED=ROM validation failed"
        -P "${CMAKE_CURRENT_SOURCE_DIR}/cmake/check_expected_failure.cmake"
)

include("${CMAKE_CURRENT_SOURCE_DIR}/cmake/generated.cmake")

add_executable(jfg_controller_mapping_tests runtime/controller_mapping_tests.cpp)
target_link_libraries(jfg_controller_mapping_tests PRIVATE jfg_runtime)
target_compile_features(jfg_controller_mapping_tests PRIVATE cxx_std_20)
jfg_set_project_warnings(jfg_controller_mapping_tests)
add_test(NAME jfg.controller_mapping COMMAND jfg_controller_mapping_tests "${PROJECT_SOURCE_DIR}/tests/fixtures/controller-default.ini")

add_executable(jfg_ipl_handoff_tests boot/ipl_handoff_tests.cpp)
target_include_directories(jfg_ipl_handoff_tests PRIVATE "${PROJECT_SOURCE_DIR}/include")
target_compile_features(jfg_ipl_handoff_tests PRIVATE cxx_std_20)
jfg_set_project_warnings(jfg_ipl_handoff_tests)
add_test(NAME jfg.ipl_handoff COMMAND jfg_ipl_handoff_tests)

add_executable(jfg_gameplay_trace_tests boot/gameplay_trace_tests.cpp)
target_include_directories(jfg_gameplay_trace_tests PRIVATE "${PROJECT_SOURCE_DIR}/include")
target_compile_features(jfg_gameplay_trace_tests PRIVATE cxx_std_20)
jfg_set_project_warnings(jfg_gameplay_trace_tests)
add_test(NAME jfg.gameplay_trace COMMAND jfg_gameplay_trace_tests "${CMAKE_CURRENT_BINARY_DIR}/gameplay-trace-test.tsv")

add_executable(jfg_vi_presentation_tests renderer/vi_presentation_tests.cpp)
target_include_directories(jfg_vi_presentation_tests PRIVATE "${PROJECT_SOURCE_DIR}/include")
target_compile_features(jfg_vi_presentation_tests PRIVATE cxx_std_20)
jfg_set_project_warnings(jfg_vi_presentation_tests)
add_test(NAME jfg.vi_presentation COMMAND jfg_vi_presentation_tests)

add_executable(jfg_navigation_mod_tests runtime/navigation_mod_tests.cpp)
target_include_directories(jfg_navigation_mod_tests PRIVATE "${PROJECT_SOURCE_DIR}/include")
target_compile_features(jfg_navigation_mod_tests PRIVATE cxx_std_20)
target_link_libraries(jfg_navigation_mod_tests PRIVATE jfg_runtime)
jfg_set_project_warnings(jfg_navigation_mod_tests)
add_test(NAME jfg.navigation_mod COMMAND jfg_navigation_mod_tests)

add_executable(jfg_master_volume_tests platform/master_volume_tests.cpp)
target_include_directories(jfg_master_volume_tests PRIVATE "${PROJECT_SOURCE_DIR}/include")
target_compile_features(jfg_master_volume_tests PRIVATE cxx_std_20)
jfg_set_project_warnings(jfg_master_volume_tests)
add_test(NAME jfg.master_volume COMMAND jfg_master_volume_tests)


add_executable(jfg_sound_queue_recovery_tests boot/sound_queue_recovery_tests.cpp)
target_link_libraries(jfg_sound_queue_recovery_tests PRIVATE jfg_boot)
target_compile_features(jfg_sound_queue_recovery_tests PRIVATE cxx_std_20)
jfg_set_project_warnings(jfg_sound_queue_recovery_tests)
add_test(NAME jfg.sound_queue_recovery COMMAND jfg_sound_queue_recovery_tests)

find_package(Python3 REQUIRED COMPONENTS Interpreter)
add_test(NAME jfg.rt64_shader_dependencies
    COMMAND "${Python3_EXECUTABLE}" "${PROJECT_SOURCE_DIR}/scripts/verification/test_rt64_shader_dependencies.py"
        --cmake "${CMAKE_COMMAND}" --generator "${CMAKE_GENERATOR}"
        --make-program "${CMAKE_MAKE_PROGRAM}"
        --work-root "${CMAKE_CURRENT_BINARY_DIR}/shader-fixtures")

add_executable(jfg_playback_buffer_tests platform/playback_buffer_tests.cpp)
target_include_directories(jfg_playback_buffer_tests PRIVATE "${PROJECT_SOURCE_DIR}/include")
target_compile_features(jfg_playback_buffer_tests PRIVATE cxx_std_20)
jfg_set_project_warnings(jfg_playback_buffer_tests)
add_test(NAME jfg.playback_buffer COMMAND jfg_playback_buffer_tests)

add_executable(jfg_controller_ports_tests runtime/controller_ports_tests.cpp)
target_link_libraries(jfg_controller_ports_tests PRIVATE jfg_runtime)
target_include_directories(jfg_controller_ports_tests PRIVATE "${PROJECT_SOURCE_DIR}/include")
target_compile_features(jfg_controller_ports_tests PRIVATE cxx_std_20)
jfg_set_project_warnings(jfg_controller_ports_tests)
add_test(NAME jfg.controller_ports COMMAND jfg_controller_ports_tests)

add_executable(jfg_modern_controls_tests runtime/modern_controls_tests.cpp)
target_link_libraries(jfg_modern_controls_tests PRIVATE jfg_runtime)
target_compile_features(jfg_modern_controls_tests PRIVATE cxx_std_20)
jfg_set_project_warnings(jfg_modern_controls_tests)
add_test(NAME jfg.modern_controls COMMAND jfg_modern_controls_tests)

add_executable(jfg_modern_roll_tests runtime/modern_roll_tests.cpp)
target_link_libraries(jfg_modern_roll_tests PRIVATE jfg_runtime)
target_compile_features(jfg_modern_roll_tests PRIVATE cxx_std_20)
jfg_set_project_warnings(jfg_modern_roll_tests)
add_test(NAME jfg.modern_roll COMMAND jfg_modern_roll_tests)

add_executable(jfg_pc_input_tests runtime/pc_input_tests.cpp)
target_link_libraries(jfg_pc_input_tests PRIVATE jfg_runtime)
target_compile_features(jfg_pc_input_tests PRIVATE cxx_std_20)
jfg_set_project_warnings(jfg_pc_input_tests)
add_test(NAME jfg.pc_input COMMAND jfg_pc_input_tests)

add_executable(jfg_original_timing_runtime_tests runtime/original_timing_runtime_tests.cpp)
target_include_directories(jfg_original_timing_runtime_tests PRIVATE "${PROJECT_SOURCE_DIR}/include")
target_compile_features(jfg_original_timing_runtime_tests PRIVATE cxx_std_20)
jfg_set_project_warnings(jfg_original_timing_runtime_tests)
add_test(NAME jfg.original_timing_runtime COMMAND jfg_original_timing_runtime_tests)

foreach(async_test async_diagnostic_file async_snapshots)
  add_executable(jfg_${async_test}_tests runtime/${async_test}_tests.cpp)
  target_include_directories(jfg_${async_test}_tests PRIVATE "${PROJECT_SOURCE_DIR}/include")
  target_compile_features(jfg_${async_test}_tests PRIVATE cxx_std_20)
  target_compile_definitions(jfg_${async_test}_tests PRIVATE NOMINMAX)
  jfg_set_project_warnings(jfg_${async_test}_tests)
  add_test(NAME jfg.${async_test} COMMAND jfg_${async_test}_tests "${CMAKE_CURRENT_BINARY_DIR}/${async_test}.txt")
endforeach()

add_executable(jfg_original_timing_fast_tests boot/original_timing_fast_tests.cpp)
target_include_directories(jfg_original_timing_fast_tests PRIVATE
    "${PROJECT_SOURCE_DIR}/include" "${CMAKE_CURRENT_SOURCE_DIR}/fixtures/original-timing-context")
target_compile_features(jfg_original_timing_fast_tests PRIVATE cxx_std_20)
jfg_set_project_warnings(jfg_original_timing_fast_tests)
add_test(NAME jfg.original_timing_fast COMMAND jfg_original_timing_fast_tests)

add_executable(jfg_pc_rumble_tests runtime/pc_rumble_tests.cpp)
target_compile_features(jfg_pc_rumble_tests PRIVATE cxx_std_20)
target_link_libraries(jfg_pc_rumble_tests PRIVATE jfg_runtime)
jfg_set_project_warnings(jfg_pc_rumble_tests)
add_test(NAME jfg.pc_rumble COMMAND jfg_pc_rumble_tests)

add_executable(jfg_controller_catalog_tests runtime/controller_catalog_tests.cpp)
target_link_libraries(jfg_controller_catalog_tests PRIVATE jfg_runtime)
target_compile_features(jfg_controller_catalog_tests PRIVATE cxx_std_20)
jfg_set_project_warnings(jfg_controller_catalog_tests)
add_test(NAME jfg.controller_catalog COMMAND jfg_controller_catalog_tests)
if(WIN32)
 include("${PROJECT_SOURCE_DIR}/cmake/ControllerSdk.cmake")
 add_executable(jfg_sdl_controller_backend_tests runtime/sdl_controller_backend_tests.cpp)
 target_include_directories(jfg_sdl_controller_backend_tests PRIVATE "${PROJECT_SOURCE_DIR}/include")
 target_include_directories(jfg_sdl_controller_backend_tests SYSTEM PRIVATE "${JFG_CONTROLLER_SDL_ROOT}/include")
 target_compile_features(jfg_sdl_controller_backend_tests PRIVATE cxx_std_20)
 jfg_set_project_warnings(jfg_sdl_controller_backend_tests)
 target_link_libraries(jfg_sdl_controller_backend_tests PRIVATE "${JFG_CONTROLLER_SDL_ROOT}/lib/x64/SDL2.lib")
 add_custom_command(TARGET jfg_sdl_controller_backend_tests POST_BUILD COMMAND ${CMAKE_COMMAND} -E copy_if_different "${JFG_CONTROLLER_SDL_ROOT}/lib/x64/SDL2.dll" "$<TARGET_FILE_DIR:jfg_sdl_controller_backend_tests>")
 add_test(NAME jfg.sdl_controller_backend COMMAND jfg_sdl_controller_backend_tests)
endif()

add_executable(jfg_menu_pointer_tests runtime/menu_pointer_tests.cpp)
target_include_directories(jfg_menu_pointer_tests PRIVATE "${PROJECT_SOURCE_DIR}/include")
target_compile_features(jfg_menu_pointer_tests PRIVATE cxx_std_20)
jfg_set_project_warnings(jfg_menu_pointer_tests)
add_test(NAME jfg.menu_pointer COMMAND jfg_menu_pointer_tests)

add_executable(jfg_native_event_batch_tests boot/native_event_batch_tests.cpp)
target_include_directories(jfg_native_event_batch_tests PRIVATE "${PROJECT_SOURCE_DIR}/include")
target_compile_features(jfg_native_event_batch_tests PRIVATE cxx_std_20)
jfg_set_project_warnings(jfg_native_event_batch_tests)
add_test(NAME jfg.native_event_batch COMMAND jfg_native_event_batch_tests)

if(WIN32)
  add_executable(jfg_host_deadline_wait_tests boot/host_deadline_wait_tests.cpp)
  target_include_directories(jfg_host_deadline_wait_tests PRIVATE "${PROJECT_SOURCE_DIR}/include")
  target_compile_features(jfg_host_deadline_wait_tests PRIVATE cxx_std_20)
  jfg_set_project_warnings(jfg_host_deadline_wait_tests)
  add_test(NAME jfg.host_deadline_wait COMMAND jfg_host_deadline_wait_tests)
  add_executable(jfg_presentation_deadline_wait_tests renderer/presentation_deadline_wait_tests.cpp)
  target_include_directories(jfg_presentation_deadline_wait_tests PRIVATE "${PROJECT_SOURCE_DIR}/include")
  target_compile_features(jfg_presentation_deadline_wait_tests PRIVATE cxx_std_20)
  jfg_set_project_warnings(jfg_presentation_deadline_wait_tests)
  add_test(NAME jfg.presentation_deadline_wait COMMAND jfg_presentation_deadline_wait_tests)
endif()

add_executable(jfg_interpolation_history_tests renderer/interpolation_history_tests.cpp)
target_include_directories(jfg_interpolation_history_tests PRIVATE "${PROJECT_SOURCE_DIR}/include")
target_compile_features(jfg_interpolation_history_tests PRIVATE cxx_std_20)
jfg_set_project_warnings(jfg_interpolation_history_tests)
add_test(NAME jfg.interpolation_history COMMAND jfg_interpolation_history_tests)

add_executable(jfg_video_settings_tests renderer/video_settings_tests.cpp)
target_include_directories(jfg_video_settings_tests PRIVATE "${PROJECT_SOURCE_DIR}/include")
target_compile_features(jfg_video_settings_tests PRIVATE cxx_std_20)
jfg_set_project_warnings(jfg_video_settings_tests)
add_test(NAME jfg.video_settings COMMAND jfg_video_settings_tests)

if(WIN32)
    add_executable(jfg_video_dialog_tests platform/video_dialog_tests.cpp ../launcher/native/video_settings_dialog.cpp ../launcher/native/video_settings.rc)
    target_compile_features(jfg_video_dialog_tests PRIVATE cxx_std_20)
    target_compile_definitions(jfg_video_dialog_tests PRIVATE UNICODE _UNICODE)
    target_link_libraries(jfg_video_dialog_tests PRIVATE user32 gdi32 comctl32)
    jfg_set_project_warnings(jfg_video_dialog_tests)
    add_test(NAME jfg.video_dialog COMMAND jfg_video_dialog_tests)
endif()

if(WIN32)
    add_executable(jfg_video_frontend_tests renderer/video_frontend_tests.cpp)
    target_include_directories(jfg_video_frontend_tests PRIVATE "${PROJECT_SOURCE_DIR}/include")
    target_compile_features(jfg_video_frontend_tests PRIVATE cxx_std_20)
    target_compile_definitions(jfg_video_frontend_tests PRIVATE UNICODE _UNICODE)
    target_link_libraries(jfg_video_frontend_tests PRIVATE user32)
    jfg_set_project_warnings(jfg_video_frontend_tests)
endif()

add_executable(jfg_semantic_presentation_tests renderer/semantic_presentation_tests.cpp)
target_link_libraries(jfg_semantic_presentation_tests PRIVATE jfg_runtime)
target_include_directories(jfg_semantic_presentation_tests PRIVATE "${PROJECT_SOURCE_DIR}/include")
target_compile_features(jfg_semantic_presentation_tests PRIVATE cxx_std_20)
jfg_set_project_warnings(jfg_semantic_presentation_tests)
add_test(NAME jfg.semantic_presentation COMMAND jfg_semantic_presentation_tests)

add_executable(jfg_count_sample_tape_tests boot/count_sample_tape_tests.cpp)
target_include_directories(jfg_count_sample_tape_tests PRIVATE "${PROJECT_SOURCE_DIR}/include")
target_compile_features(jfg_count_sample_tape_tests PRIVATE cxx_std_20)
jfg_set_project_warnings(jfg_count_sample_tape_tests)
add_test(NAME jfg.count_sample_tape COMMAND jfg_count_sample_tape_tests)

add_executable(jfg_interpolation_trace_tests renderer/interpolation_trace_tests.cpp)
target_include_directories(jfg_interpolation_trace_tests PRIVATE "${PROJECT_SOURCE_DIR}/include")
target_compile_features(jfg_interpolation_trace_tests PRIVATE cxx_std_20)
jfg_set_project_warnings(jfg_interpolation_trace_tests)
add_test(NAME jfg.interpolation_trace COMMAND jfg_interpolation_trace_tests "${CMAKE_CURRENT_BINARY_DIR}/interpolation-trace-test.tsv")

add_executable(jfg_runlink_native_identity_tests boot/runlink_native_identity_tests.cpp)
target_include_directories(jfg_runlink_native_identity_tests PRIVATE "${PROJECT_SOURCE_DIR}/include")
target_compile_features(jfg_runlink_native_identity_tests PRIVATE cxx_std_20)
jfg_set_project_warnings(jfg_runlink_native_identity_tests)
add_test(NAME jfg.runlink_native_identity COMMAND jfg_runlink_native_identity_tests)

add_executable(jfg_floating_environment_tests renderer/floating_environment_tests.cpp
    "${PROJECT_SOURCE_DIR}/src/renderer/floating_environment.cpp")
target_include_directories(jfg_floating_environment_tests PRIVATE "${PROJECT_SOURCE_DIR}/include")
target_compile_features(jfg_floating_environment_tests PRIVATE cxx_std_20)
jfg_set_project_warnings(jfg_floating_environment_tests)
add_test(NAME jfg.floating_environment COMMAND jfg_floating_environment_tests)

add_executable(jfg_function_profile_tests boot/function_profile_tests.cpp)
target_include_directories(jfg_function_profile_tests PRIVATE "${PROJECT_SOURCE_DIR}/include")
target_compile_features(jfg_function_profile_tests PRIVATE cxx_std_20)
jfg_set_project_warnings(jfg_function_profile_tests)
add_test(NAME jfg.function_profile COMMAND jfg_function_profile_tests)

add_executable(jfg_submission_profile_tests renderer/submission_profile_tests.cpp)
target_include_directories(jfg_submission_profile_tests PRIVATE "${PROJECT_SOURCE_DIR}/include")
target_compile_features(jfg_submission_profile_tests PRIVATE cxx_std_20)
jfg_set_project_warnings(jfg_submission_profile_tests)
add_test(NAME jfg.submission_profile COMMAND jfg_submission_profile_tests)

add_executable(jfg_async_volume_file_tests runtime/async_volume_file_tests.cpp)
target_include_directories(jfg_async_volume_file_tests PRIVATE "${PROJECT_SOURCE_DIR}/include")
target_compile_features(jfg_async_volume_file_tests PRIVATE cxx_std_20)
target_link_libraries(jfg_async_volume_file_tests PRIVATE Threads::Threads)
jfg_set_project_warnings(jfg_async_volume_file_tests)
add_test(NAME jfg.async_volume_file COMMAND jfg_async_volume_file_tests)

add_executable(jfg_async_config_files_tests runtime/async_config_files_tests.cpp)
target_include_directories(jfg_async_config_files_tests PRIVATE "${PROJECT_SOURCE_DIR}/include")
target_compile_features(jfg_async_config_files_tests PRIVATE cxx_std_20)
target_link_libraries(jfg_async_config_files_tests PRIVATE Threads::Threads)
jfg_set_project_warnings(jfg_async_config_files_tests)
add_test(NAME jfg.async_config_files COMMAND jfg_async_config_files_tests)

add_executable(jfg_navigation_mesh_json_tests runtime/navigation_mesh_json_tests.cpp)
target_include_directories(jfg_navigation_mesh_json_tests PRIVATE "${PROJECT_SOURCE_DIR}/include")
target_compile_features(jfg_navigation_mesh_json_tests PRIVATE cxx_std_20)
target_link_libraries(jfg_navigation_mesh_json_tests PRIVATE jfg_runtime)
jfg_set_project_warnings(jfg_navigation_mesh_json_tests)
add_test(NAME jfg.navigation_mesh_json COMMAND jfg_navigation_mesh_json_tests)

add_executable(jfg_cutscene_skip_tests runtime/cutscene_skip_tests.cpp)
target_include_directories(jfg_cutscene_skip_tests PRIVATE "../include")
target_compile_features(jfg_cutscene_skip_tests PRIVATE cxx_std_20)
jfg_set_project_warnings(jfg_cutscene_skip_tests)
add_test(NAME jfg.cutscene_skip COMMAND jfg_cutscene_skip_tests)

add_executable(jfg_rain_fade_tests renderer/rain_fade_tests.cpp)
target_include_directories(jfg_rain_fade_tests PRIVATE "${PROJECT_SOURCE_DIR}/include")
target_compile_features(jfg_rain_fade_tests PRIVATE cxx_std_20)
jfg_set_project_warnings(jfg_rain_fade_tests)
add_test(NAME jfg.rain_fade COMMAND jfg_rain_fade_tests)

add_executable(jfg_cutscene_review_tests runtime/cutscene_review_tests.cpp)
target_include_directories(jfg_cutscene_review_tests PRIVATE "${PROJECT_SOURCE_DIR}/include")
target_compile_features(jfg_cutscene_review_tests PRIVATE cxx_std_20)
add_test(NAME jfg.cutscene_review COMMAND jfg_cutscene_review_tests)

add_executable(jfg_cutscene_audio_tests runtime/cutscene_audio_tests.cpp)
target_include_directories(jfg_cutscene_audio_tests PRIVATE "../include")
target_compile_features(jfg_cutscene_audio_tests PRIVATE cxx_std_20)
target_link_libraries(jfg_cutscene_audio_tests PRIVATE jfg_runtime)
jfg_set_project_warnings(jfg_cutscene_audio_tests)
add_test(NAME jfg.cutscene_audio COMMAND jfg_cutscene_audio_tests)


add_executable(jfg_daynight_fog_tests renderer/daynight_fog_tests.cpp)
target_include_directories(jfg_daynight_fog_tests PRIVATE "../include")
target_compile_features(jfg_daynight_fog_tests PRIVATE cxx_std_20)
jfg_set_project_warnings(jfg_daynight_fog_tests)
add_test(NAME jfg.daynight_fog COMMAND jfg_daynight_fog_tests)

add_executable(jfg_latency_recovery_tests platform/latency_recovery_tests.cpp)
target_include_directories(jfg_latency_recovery_tests PRIVATE "${PROJECT_SOURCE_DIR}/include")
target_compile_features(jfg_latency_recovery_tests PRIVATE cxx_std_20)
jfg_set_project_warnings(jfg_latency_recovery_tests)
add_test(NAME jfg.latency_recovery COMMAND jfg_latency_recovery_tests)

add_executable(jfg_flying_motion_tests runtime/flying_motion_tests.cpp)
target_include_directories(jfg_flying_motion_tests PRIVATE "../include")
target_compile_features(jfg_flying_motion_tests PRIVATE cxx_std_20)
jfg_set_project_warnings(jfg_flying_motion_tests)
add_test(NAME jfg.flying_motion COMMAND jfg_flying_motion_tests)

add_executable(jfg_flying_motion_adapter_tests runtime/flying_motion_adapter_tests.cpp)
target_include_directories(jfg_flying_motion_adapter_tests PRIVATE "../include")
target_compile_features(jfg_flying_motion_adapter_tests PRIVATE cxx_std_20)
target_link_libraries(jfg_flying_motion_adapter_tests PRIVATE jfg_runtime)
jfg_set_project_warnings(jfg_flying_motion_adapter_tests)
add_test(NAME jfg.flying_motion_adapter COMMAND jfg_flying_motion_adapter_tests)

add_executable(jfg_flight_transition_music_tests runtime/flight_transition_music_tests.cpp)
target_include_directories(jfg_flight_transition_music_tests PRIVATE "../include")
target_compile_features(jfg_flight_transition_music_tests PRIVATE cxx_std_20)
target_link_libraries(jfg_flight_transition_music_tests PRIVATE jfg_runtime)
jfg_set_project_warnings(jfg_flight_transition_music_tests)
add_test(NAME jfg.flight_transition_music COMMAND jfg_flight_transition_music_tests)

add_executable(jfg_game_resident_memory_tests runtime/game_resident_memory_tests.cpp)
target_compile_features(jfg_game_resident_memory_tests PRIVATE cxx_std_20)
target_link_libraries(jfg_game_resident_memory_tests PRIVATE jfg_runtime)
jfg_set_project_warnings(jfg_game_resident_memory_tests)
add_test(NAME jfg.game_resident_memory COMMAND jfg_game_resident_memory_tests)

add_executable(jfg_game_memory_view_tests runtime/game_memory_view_tests.cpp)
target_link_libraries(jfg_game_memory_view_tests PRIVATE jfg_runtime)
target_compile_features(jfg_game_memory_view_tests PRIVATE cxx_std_20)
jfg_set_project_warnings(jfg_game_memory_view_tests)
add_test(NAME jfg.game_memory_view COMMAND jfg_game_memory_view_tests)

add_executable(jfg_rom_assets_tests runtime/rom_assets_tests.cpp)
target_include_directories(jfg_rom_assets_tests PRIVATE "${PROJECT_SOURCE_DIR}/include")
target_compile_features(jfg_rom_assets_tests PRIVATE cxx_std_20)
jfg_set_project_warnings(jfg_rom_assets_tests)
add_test(NAME jfg.rom_assets COMMAND jfg_rom_assets_tests)
