cmake_minimum_required(VERSION 3.20)
project(jfg_generated_object_shape_rejection LANGUAGES C CXX)

if(NOT JFG_PROJECT_SOURCE_DIR OR NOT JFG_CASE)
    message(FATAL_ERROR "JFG_PROJECT_SOURCE_DIR and JFG_CASE are required")
endif()

list(APPEND CMAKE_MODULE_PATH "${JFG_PROJECT_SOURCE_DIR}/cmake")
include(Warnings)
include(GeneratedCode)

set(private_root "${CMAKE_BINARY_DIR}/private-root")
file(COPY
    "${JFG_PROJECT_SOURCE_DIR}/tests/fixtures/generated-code-synthetic/"
    DESTINATION "${private_root}"
)
file(SHA256
    "${JFG_PROJECT_SOURCE_DIR}/scripts/build_private_generated_root.py"
    normalizer_revision_sha256
)
file(READ "${private_root}/sources.json" private_manifest)
string(REPLACE
    "\"version\": 1,"
    "\"version\": 2,\n  \"normalizer_revision_sha256\": \"${normalizer_revision_sha256}\","
    private_manifest
    "${private_manifest}"
)
file(WRITE "${private_root}/sources.json" "${private_manifest}")

if(JFG_CASE STREQUAL "multi-function")
    file(APPEND "${private_root}/body/synthetic_core_recomp.c" [=[

JFG_SYNTHETIC_FUNCTION void synthetic_extra_recomp(uint8_t* rdram, recomp_context* ctx) {
    (void)rdram;
    ctx->r2 = UINT64_C(99);
}
]=])
elseif(JFG_CASE STREQUAL "vacuous-registry")
    file(WRITE "${private_root}/audit/link_smoke_registry.c" [=[
int jfg_generated_link_smoke(void) {
    return 0;
}
]=])
elseif(JFG_CASE STREQUAL "extra-registry-reference")
    # The normal registry retains all required references; this adds one
    # undeclared native reference that the closed audit must reject.
elseif(JFG_CASE STREQUAL "generated-runtime-data-owner")
    # The generated support object attempts to own a fixed-runtime data symbol.
elseif(JFG_CASE STREQUAL "extra-generated-data")
    # The generated support object exports undeclared native data.
elseif(JFG_CASE STREQUAL "compiler-data-near-name")
    # Project data that only resembles an excluded compiler-header symbol
    # remains part of the closed generated-object inventory.
else()
    message(FATAL_ERROR "Unknown JFG_CASE")
endif()

jfg_add_generated_code(
    NAME shape
    ROOT "${private_root}"
    REQUIRE_PRIVATE_ROOT
)

if(JFG_CASE STREQUAL "extra-registry-reference")
    target_compile_definitions(shape_link_smoke_objects PRIVATE
        JFG_NEGATIVE_EXTRA_REFERENCE=1
    )
elseif(JFG_CASE STREQUAL "generated-runtime-data-owner")
    target_compile_definitions(shape_support_objects PRIVATE
        JFG_NEGATIVE_RUNTIME_DATA_OWNER=1
    )
elseif(JFG_CASE STREQUAL "extra-generated-data")
    target_compile_definitions(shape_support_objects PRIVATE
        JFG_NEGATIVE_EXTRA_GENERATED_DATA=1
    )
elseif(JFG_CASE STREQUAL "compiler-data-near-name")
    target_compile_definitions(shape_support_objects PRIVATE
        JFG_NEGATIVE_COMPILER_DATA_NEAR_NAME=1
    )
endif()
