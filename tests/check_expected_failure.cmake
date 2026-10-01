if(NOT DEFINED PROGRAM OR NOT DEFINED EXPECTED)
    message(FATAL_ERROR "PROGRAM and EXPECTED are required")
endif()

execute_process(
    COMMAND "${PROGRAM}" ${ARGUMENTS}
    RESULT_VARIABLE result
    OUTPUT_VARIABLE standard_output
    ERROR_VARIABLE standard_error
)

if(result EQUAL 0)
    message(FATAL_ERROR "Expected command to fail, but it exited successfully")
endif()

set(combined_output "${standard_output}${standard_error}")
string(FIND "${combined_output}" "${EXPECTED}" match_position)
if(match_position EQUAL -1)
    message(FATAL_ERROR
        "Expected output fragment was not found. Output: ${combined_output}")
endif()
