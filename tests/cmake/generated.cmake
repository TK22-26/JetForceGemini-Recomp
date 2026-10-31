# Target group included from tests/CMakeLists.txt.
if(JFG_BUILD_SYNTHETIC_GENERATED_TESTS)
    jfg_add_generated_code(
        NAME jfg_synthetic_generated
        ROOT "${CMAKE_CURRENT_SOURCE_DIR}/fixtures/generated-code-synthetic"
        ALLOW_TRACKED_ROM_FREE_FIXTURE
    )
    jfg_add_generated_code_tests(
        NAME jfg_synthetic_generated
        LINK_SMOKE_SOURCE "${CMAKE_CURRENT_SOURCE_DIR}/boot/generated_link_smoke.cpp"
        BASELINE_AUDIT_SOURCE "${CMAKE_CURRENT_SOURCE_DIR}/generated_baseline_audit.cpp"
        PATCH_AUDIT_SOURCE "${CMAKE_CURRENT_SOURCE_DIR}/generated_patch_audit.cpp"
    )

    add_executable(jfg_native_mmio_bridge_tests runtime/native_mmio_bridge_tests.cpp)
    target_include_directories(jfg_native_mmio_bridge_tests PRIVATE "${PROJECT_SOURCE_DIR}/include")
    target_include_directories(jfg_native_mmio_bridge_tests SYSTEM PRIVATE
        "${CMAKE_CURRENT_SOURCE_DIR}/fixtures/generated-code-synthetic/include")
    target_link_libraries(jfg_native_mmio_bridge_tests PRIVATE jfg_synthetic_generated_minimal_runtime_objects)
    target_compile_features(jfg_native_mmio_bridge_tests PRIVATE cxx_std_20)
    jfg_set_project_warnings(jfg_native_mmio_bridge_tests)
    add_test(NAME jfg.native_mmio_bridge COMMAND jfg_native_mmio_bridge_tests)

    add_executable(jfg_generated_runtime_capacity_tests
        runtime/generated_runtime_capacity_tests.cpp
    )
    target_include_directories(jfg_generated_runtime_capacity_tests PRIVATE
        "${PROJECT_SOURCE_DIR}/include")
    target_include_directories(jfg_generated_runtime_capacity_tests SYSTEM PRIVATE
        "${CMAKE_CURRENT_SOURCE_DIR}/fixtures/generated-code-synthetic/include"
    )
    target_link_libraries(jfg_generated_runtime_capacity_tests PRIVATE
        jfg_synthetic_generated_minimal_runtime_objects
    )
    target_compile_features(jfg_generated_runtime_capacity_tests PRIVATE cxx_std_20)
    jfg_set_project_warnings(jfg_generated_runtime_capacity_tests)
    add_test(
        NAME jfg_synthetic_generated.runtime_capacity
        COMMAND jfg_generated_runtime_capacity_tests
    )

    add_test(
        NAME jfg_synthetic_generated.reject_tracked_real_root
        COMMAND "${CMAKE_COMMAND}"
            "-DPROGRAM=${CMAKE_COMMAND}"
            "-DARGUMENTS=-S;${CMAKE_CURRENT_SOURCE_DIR}/fixtures/generated-code-synthetic/configure-tests/tracked-root;-B;${CMAKE_CURRENT_BINARY_DIR}/n-tr;-DJFG_PROJECT_SOURCE_DIR=${PROJECT_SOURCE_DIR}"
            "-DEXPECTED=must be ignored by git"
            -P "${CMAKE_CURRENT_SOURCE_DIR}/cmake/check_expected_failure.cmake"
    )

    add_test(
        NAME jfg_synthetic_generated.reject_include_escape
        COMMAND "${CMAKE_COMMAND}"
            "-DPROGRAM=${CMAKE_COMMAND}"
            "-DARGUMENTS=-S;${CMAKE_CURRENT_SOURCE_DIR}/fixtures/generated-code-synthetic/configure-tests/include-escape;-B;${CMAKE_CURRENT_BINARY_DIR}/n-ie;-DJFG_PROJECT_SOURCE_DIR=${PROJECT_SOURCE_DIR}"
            "-DEXPECTED=n64recomp_include must use a canonical contained path"
            -P "${CMAKE_CURRENT_SOURCE_DIR}/cmake/check_expected_failure.cmake"
    )

    add_test(
        NAME jfg_synthetic_generated.reject_float_version
        COMMAND "${CMAKE_COMMAND}"
            "-DPROGRAM=${CMAKE_COMMAND}"
            "-DARGUMENTS=-S;${CMAKE_CURRENT_SOURCE_DIR}/fixtures/generated-code-synthetic/configure-tests/version-float;-B;${CMAKE_CURRENT_BINARY_DIR}/n-fv;-DJFG_PROJECT_SOURCE_DIR=${PROJECT_SOURCE_DIR}"
            "-DEXPECTED=source-manifest: unsupported-version"
            -P "${CMAKE_CURRENT_SOURCE_DIR}/cmake/check_expected_failure.cmake"
    )

    foreach(rejection_case
        multi-function
        vacuous-registry
        extra-registry-reference
        generated-runtime-data-owner
        extra-generated-data
        compiler-data-near-name
    )
        if(rejection_case STREQUAL "multi-function")
            set(rejection_case_id "mf")
        elseif(rejection_case STREQUAL "vacuous-registry")
            set(rejection_case_id "vr")
        elseif(rejection_case STREQUAL "extra-registry-reference")
            set(rejection_case_id "er")
        elseif(rejection_case STREQUAL "generated-runtime-data-owner")
            set(rejection_case_id "rd")
        elseif(rejection_case STREQUAL "extra-generated-data")
            set(rejection_case_id "gd")
        elseif(rejection_case STREQUAL "compiler-data-near-name")
            set(rejection_case_id "cd")
        else()
            message(FATAL_ERROR "Missing compact ID for generated-code rejection case")
        endif()
        add_test(
            NAME jfg_synthetic_generated.reject_${rejection_case}
            COMMAND "${CMAKE_COMMAND}"
                "-DSOURCE=${CMAKE_CURRENT_SOURCE_DIR}/fixtures/generated-code-synthetic/configure-tests/object-shape"
                "-DBINARY=${CMAKE_CURRENT_BINARY_DIR}/n-${rejection_case_id}"
                "-DCASE=${rejection_case}"
                "-DPROJECT_SOURCE=${PROJECT_SOURCE_DIR}"
                "-DGENERATOR=${CMAKE_GENERATOR}"
                "-DGENERATOR_PLATFORM=${CMAKE_GENERATOR_PLATFORM}"
                "-DMAKE_PROGRAM=${CMAKE_MAKE_PROGRAM}"
                "-DC_COMPILER=${CMAKE_C_COMPILER}"
                "-DCXX_COMPILER=${CMAKE_CXX_COMPILER}"
                "-DRC_COMPILER=${CMAKE_RC_COMPILER}"
                "-DCMAKE_MT_TOOL=${CMAKE_MT}"
                "-DPYTHON_EXECUTABLE=${Python3_EXECUTABLE}"
                "-DCONFIG=$<CONFIG>"
                "-DEXPECTED=$<IF:$<STREQUAL:${rejection_case},multi-function>,external-function-count=2 expected=1,$<IF:$<STREQUAL:${rejection_case},vacuous-registry>,incomplete-coverage,$<IF:$<STREQUAL:${rejection_case},extra-registry-reference>,unexpected-reference-count=1,$<IF:$<STREQUAL:${rejection_case},generated-runtime-data-owner>,forbidden-runtime-data-owner-count=1,data-inventory-mismatch actual-count=2>>>>"
                -P "${CMAKE_CURRENT_SOURCE_DIR}/cmake/check_configure_build_failure.cmake"
        )
    endforeach()

    add_test(
        NAME jfg_synthetic_generated.reject_hidden_patch_anchor
        COMMAND "${CMAKE_COMMAND}"
            "-DPROGRAM=${CMAKE_COMMAND}"
            "-DARGUMENTS=-S;${CMAKE_CURRENT_SOURCE_DIR}/fixtures/generated-code-synthetic/configure-tests/hidden-anchor;-B;${CMAKE_CURRENT_BINARY_DIR}/n-ha;-DJFG_PROJECT_SOURCE_DIR=${PROJECT_SOURCE_DIR}"
            "-DEXPECTED=source-manifest: invalid-member-set"
            -P "${CMAKE_CURRENT_SOURCE_DIR}/cmake/check_expected_failure.cmake"
    )
endif()
