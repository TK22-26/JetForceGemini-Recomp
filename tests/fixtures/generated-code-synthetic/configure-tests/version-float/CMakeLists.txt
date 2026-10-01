cmake_minimum_required(VERSION 3.20)
project(jfg_generated_version_float_rejection LANGUAGES NONE)

if(NOT JFG_PROJECT_SOURCE_DIR)
    message(FATAL_ERROR "JFG_PROJECT_SOURCE_DIR is required")
endif()

list(APPEND CMAKE_MODULE_PATH "${JFG_PROJECT_SOURCE_DIR}/cmake")
include(Warnings)
include(GeneratedCode)

set(private_root "${CMAKE_BINARY_DIR}/private-root")
file(MAKE_DIRECTORY "${private_root}")
file(WRITE "${private_root}/sources.json" [=[
{
  "version": 1.0,
  "n64recomp_include": "include",
  "baseline_body_sources": ["body.c"],
  "normal_wrapper_sources": ["wrapper.c"],
  "patch_sources": [],
  "game_patch_function_count": 0,
  "support_sources": ["support.c"],
  "link_smoke_sources": ["registry.cpp"],
  "symbol_inventory": "symbol_inventory.json",
  "symbol_inventory_sha256": "0000000000000000000000000000000000000000000000000000000000000000"
}
]=])

jfg_add_generated_code(
    NAME rejected_float_version
    ROOT "${private_root}"
    REQUIRE_PRIVATE_ROOT
)
