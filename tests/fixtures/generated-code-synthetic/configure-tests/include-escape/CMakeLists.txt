cmake_minimum_required(VERSION 3.20)
project(jfg_generated_include_escape_rejection LANGUAGES NONE)

if(NOT JFG_PROJECT_SOURCE_DIR)
    message(FATAL_ERROR "JFG_PROJECT_SOURCE_DIR is required")
endif()

list(APPEND CMAKE_MODULE_PATH "${JFG_PROJECT_SOURCE_DIR}/cmake")
include(Warnings)
include(GeneratedCode)

file(REAL_PATH "${CMAKE_CURRENT_SOURCE_DIR}/root" escape_test_root)
_jfg_resolve_contained_path(
    escaped_include
    "${escape_test_root}"
    "../../../include"
    "n64recomp_include"
)
