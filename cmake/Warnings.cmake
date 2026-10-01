function(jfg_set_project_warnings target)
    if(MSVC)
        target_compile_options(${target} PRIVATE
            /W4
            "$<$<COMPILE_LANGUAGE:CXX>:/permissive->"
            "$<$<COMPILE_LANGUAGE:CXX>:/Zc:__cplusplus>"
        )
        if(JFG_WARNINGS_AS_ERRORS)
            target_compile_options(${target} PRIVATE /WX)
        endif()
    else()
        target_compile_options(${target} PRIVATE
            -Wall
            -Wextra
            -Wconversion
            -Wpedantic
            -Wshadow
        )
        if(JFG_WARNINGS_AS_ERRORS)
            target_compile_options(${target} PRIVATE -Werror)
        endif()
    endif()
endfunction()

# Generated N64Recomp translation units include a compiler-oriented ABI header
# that intentionally uses extensions such as __int128 and anonymous structs.
# Keep useful diagnostics enabled, but do not apply the handwritten-code
# pedantic/conversion/shadow policy to these targets.
function(jfg_set_generated_warnings target)
    if(MSVC)
        target_compile_options(${target} PRIVATE
            /W4
            /wd4100
            /wd4101
            /wd4102
            /wd4127
            /wd4018
            /wd4189
            /wd4296
            # Linear generated functions can contain source instructions after
            # a terminal transfer. Delay-slot work is emitted before the
            # transfer; MSVC's unreachable-code diagnostic is therefore noise.
            /wd4702
        )
        if(CMAKE_C_COMPILER_ID MATCHES "Clang" OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
            # clang-cl selects the MSVC branch but reports these diagnostics by
            # Clang warning group rather than the corresponding /wd numbers.
            target_compile_options(${target} PRIVATE
                /clang:-Wno-sign-compare
                /clang:-Wno-tautological-compare
                /clang:-Wno-type-limits
                /clang:-Wno-unused-label
                /clang:-Wno-unused-parameter
                /clang:-Wno-unused-variable
                /clang:-Wno-unused-but-set-variable
            )
        endif()
        if(JFG_WARNINGS_AS_ERRORS)
            target_compile_options(${target} PRIVATE /WX)
        endif()
    else()
        target_compile_options(${target} PRIVATE
            -Wall
            -Wextra
            -Wno-sign-compare
            -Wno-tautological-compare
            -Wno-type-limits
            -Wno-unused-label
            -Wno-unused-parameter
            -Wno-unused-variable
            -Wno-unused-but-set-variable
        )
        if(JFG_WARNINGS_AS_ERRORS)
            target_compile_options(${target} PRIVATE -Werror)
        endif()
    endif()
endfunction()
