# Calls ignored by all three matchScene outputs must not enter its Cartesian
# candidate search. Keep the pinned RT64 checkout pristine and fail on drift.
set(jfg_match_source "${jfg_rt64_root}/src/hle/rt64_game_frame.cpp")
file(READ "${jfg_match_source}" jfg_match_contents)
string(REPLACE "\r\n" "\n" jfg_match_contents "${jfg_match_contents}")
string(SHA256 jfg_match_hash "${jfg_match_contents}")
if(NOT jfg_match_hash STREQUAL "a9527bfcdb06b876a45f06a181ca76b6cf7869d01e2c06a0c81ed9f96f1dd87a")
    message(FATAL_ERROR "Pinned RT64 call-matching input differs")
endif()
set(jfg_match_site [=[            hashMap.emplace(hashFromCall(call, matrixIdHash), GameCallMap{ sceneProjIndex, c, doTransformMatching, doTileInterpolation, doTileMatching });]=])
set(jfg_match_replacement [=[            // matchScene can only use a pair for transforms, tiles or look-at.
            // JFG supplies its own transform history and precomputed UVs, so
            // many identically keyed calls contribute to none of these sets.
            // Excluding them avoids a quadratic search without losing a match.
            const uint32_t textureGenMask = G_LIGHTING | G_TEXTURE_GEN;
            const bool doLookAtMatching = (call.callDesc.geometryMode & textureGenMask) == textureGenMask;
            if (!doTransformMatching && !doTileInterpolation && !doLookAtMatching) {
                continue;
            }
            hashMap.emplace(hashFromCall(call, matrixIdHash), GameCallMap{ sceneProjIndex, c, doTransformMatching, doTileInterpolation, doTileMatching });]=])
string(FIND "${jfg_match_contents}" "${jfg_match_site}" jfg_match_at)
if(jfg_match_at EQUAL -1)
    message(FATAL_ERROR "Pinned RT64 call-matching patch site is missing")
endif()
string(REPLACE "${jfg_match_site}" "${jfg_match_replacement}" jfg_match_contents "${jfg_match_contents}")
set(jfg_match_generated "${CMAKE_CURRENT_BINARY_DIR}/generated/rt64/hle/rt64_game_frame.cpp")
file(WRITE "${jfg_match_generated}" "${jfg_match_contents}")
get_target_property(jfg_match_sources rt64 SOURCES)
set(jfg_match_patched)
set(jfg_match_replaced FALSE)
foreach(unit IN LISTS jfg_match_sources)
    get_filename_component(jfg_match_name "${unit}" NAME)
    if(jfg_match_name STREQUAL "rt64_game_frame.cpp")
        list(APPEND jfg_match_patched "${jfg_match_generated}")
        set(jfg_match_replaced TRUE)
    else()
        list(APPEND jfg_match_patched "${unit}")
    endif()
endforeach()
if(NOT jfg_match_replaced)
    message(FATAL_ERROR "Pinned RT64 game-frame source is missing")
endif()
set_property(TARGET rt64 PROPERTY SOURCES "${jfg_match_patched}")
