cmake_minimum_required(VERSION 3.20)
project(jfg_generated_tracked_root_rejection LANGUAGES NONE)

if(NOT JFG_PROJECT_SOURCE_DIR)
    message(FATAL_ERROR "JFG_PROJECT_SOURCE_DIR is required")
endif()

list(APPEND CMAKE_MODULE_PATH "${JFG_PROJECT_SOURCE_DIR}/cmake")
include(Warnings)
include(GeneratedCode)

jfg_add_generated_code(
    NAME rejected_tracked_generated
    ROOT "${JFG_PROJECT_SOURCE_DIR}/tests/fixtures/generated-code-synthetic"
    REQUIRE_PRIVATE_ROOT
)
