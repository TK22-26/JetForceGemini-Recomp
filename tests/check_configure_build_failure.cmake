foreach(required SOURCE BINARY CASE PROJECT_SOURCE GENERATOR EXPECTED)
    if(NOT DEFINED ${required} OR "${${required}}" STREQUAL "")
        message(FATAL_ERROR "${required} is required")
    endif()
endforeach()

set(configure_command
    "${CMAKE_COMMAND}"
    --fresh
    -S "${SOURCE}"
    -B "${BINARY}"
    -G "${GENERATOR}"
    "-DJFG_CASE=${CASE}"
    "-DJFG_PROJECT_SOURCE_DIR=${PROJECT_SOURCE}"
)
if(DEFINED GENERATOR_PLATFORM AND NOT GENERATOR_PLATFORM STREQUAL "")
    list(APPEND configure_command -A "${GENERATOR_PLATFORM}")
endif()
if(GENERATOR MATCHES "Ninja|Makefiles")
    foreach(tool_setting
        "CMAKE_MAKE_PROGRAM=${MAKE_PROGRAM}"
        "CMAKE_C_COMPILER=${C_COMPILER}"
        "CMAKE_CXX_COMPILER=${CXX_COMPILER}"
        "CMAKE_RC_COMPILER=${RC_COMPILER}"
        "CMAKE_MT=${CMAKE_MT_TOOL}"
        "Python3_EXECUTABLE=${PYTHON_EXECUTABLE}"
    )
        if(NOT tool_setting MATCHES "=$")
            list(APPEND configure_command "-D${tool_setting}")
        endif()
    endforeach()
endif()

execute_process(
    COMMAND ${configure_command}
    RESULT_VARIABLE configure_result
    OUTPUT_VARIABLE configure_stdout
    ERROR_VARIABLE configure_stderr
)
if(NOT configure_result EQUAL 0)
    # Visual Studio discovery can transiently lose the C toolset while several
    # nested negative fixtures configure in succession. A fresh retry keeps a
    # toolchain-discovery race distinct from the build-audit rejection this
    # harness is intended to observe.
    execute_process(
        COMMAND ${configure_command}
        RESULT_VARIABLE configure_result
        OUTPUT_VARIABLE configure_stdout
        ERROR_VARIABLE configure_stderr
    )
endif()
if(NOT configure_result EQUAL 0)
    message(FATAL_ERROR
        "Negative generated-code fixture failed during configure instead of its build audit\n"
        "configure stdout:\n${configure_stdout}\n"
        "configure stderr:\n${configure_stderr}"
    )
endif()

set(build_command "${CMAKE_COMMAND}" --build "${BINARY}")
if(DEFINED CONFIG AND NOT CONFIG STREQUAL "")
    list(APPEND build_command --config "${CONFIG}")
endif()
execute_process(
    COMMAND ${build_command}
    RESULT_VARIABLE build_result
    OUTPUT_VARIABLE build_stdout
    ERROR_VARIABLE build_stderr
)
if(build_result EQUAL 0)
    message(FATAL_ERROR "Negative generated-code fixture unexpectedly built successfully")
endif()

set(combined_output
    "${configure_stdout}\n${configure_stderr}\n${build_stdout}\n${build_stderr}"
)
string(FIND "${combined_output}" "${EXPECTED}" expected_index)
if(expected_index EQUAL -1)
    message(FATAL_ERROR "Expected public-safe generated-code rejection was not reported")
endif()
