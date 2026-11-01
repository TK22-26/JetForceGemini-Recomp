# All native targets consume a generated view of the one ROM catalog.
find_package(Python3 REQUIRED COMPONENTS Interpreter)
set(jfg_rom_catalog_include "${CMAKE_CURRENT_BINARY_DIR}/catalog/include")
set_property(DIRECTORY APPEND PROPERTY CMAKE_CONFIGURE_DEPENDS
    "${CMAKE_CURRENT_SOURCE_DIR}/config/roms/revisions.json"
    "${CMAKE_CURRENT_SOURCE_DIR}/config/roms/native-build-admission.json"
    "${CMAKE_CURRENT_SOURCE_DIR}/scripts/build/rom_profiles.py"
    "${CMAKE_CURRENT_SOURCE_DIR}/scripts/build/generate_rom_catalog.py")
execute_process(
    COMMAND "${Python3_EXECUTABLE}" -B "${CMAKE_CURRENT_SOURCE_DIR}/scripts/build/generate_rom_catalog.py"
        --cpp "${jfg_rom_catalog_include}/jfg/game/rom_catalog.hpp"
    RESULT_VARIABLE jfg_rom_catalog_result
    ERROR_VARIABLE jfg_rom_catalog_error)
if(NOT jfg_rom_catalog_result EQUAL 0)
    message(FATAL_ERROR "ROM catalog generation failed: ${jfg_rom_catalog_error}")
endif()
add_library(jfg_rom_catalog INTERFACE)
target_include_directories(jfg_rom_catalog INTERFACE "${jfg_rom_catalog_include}")
