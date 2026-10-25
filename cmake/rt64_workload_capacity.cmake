# The pinned source checkout stays immutable. All consumers must see the same
# WorkloadQueue layout, including headers included by other upstream headers.
if(NOT JFG_RT64_WORKLOAD_CAPACITY STREQUAL "4" AND
   NOT JFG_RT64_WORKLOAD_CAPACITY STREQUAL "5" AND
   NOT JFG_RT64_WORKLOAD_CAPACITY STREQUAL "6")
    message(FATAL_ERROR "JFG_RT64_WORKLOAD_CAPACITY must be 4, 5 or 6")
endif()
# Fog shaders require this private view even with stock queue capacity.
set(jfg_capacity_original_root "${jfg_rt64_root}")
set(jfg_capacity_header "${jfg_rt64_root}/src/hle/rt64_workload_queue.h")
file(READ "${jfg_capacity_header}" jfg_capacity_contents)
string(REPLACE "\r\n" "\n" jfg_capacity_contents "${jfg_capacity_contents}")
string(SHA256 jfg_capacity_digest "${jfg_capacity_contents}")
if(NOT jfg_capacity_digest STREQUAL "41ab231ee905c9381d792298ee044d9af7167b37cebe162052f0b6048741ad92")
    message(FATAL_ERROR "Pinned RT64 workload layout changed")
endif()
set(jfg_capacity_source "${CMAKE_CURRENT_BINARY_DIR}/generated/rt64-capacity${JFG_RT64_WORKLOAD_CAPACITY}-source")
# A complete build-private source view prevents a mixture of four- and
# expanded class layouts across RT64 and its consumers. Exclude Git metadata.
file(COPY "${jfg_rt64_root}/" DESTINATION "${jfg_capacity_source}"
    PATTERN ".git" EXCLUDE PATTERN "rt64_workload_queue.h" EXCLUDE
    PATTERN "rt64_buffer_uploader.h" EXCLUDE
    PATTERN "plume_d3d12.h" EXCLUDE PATTERN "plume_d3d12.cpp" EXCLUDE)
string(REPLACE "#define WORKLOAD_QUEUE_SIZE 4"
    "#define WORKLOAD_QUEUE_SIZE ${JFG_RT64_WORKLOAD_CAPACITY}" jfg_capacity_contents "${jfg_capacity_contents}")
set(jfg_capacity_output "${jfg_capacity_source}/src/hle/rt64_workload_queue.h")
set(jfg_capacity_existing "")
if(EXISTS "${jfg_capacity_output}")
    file(READ "${jfg_capacity_output}" jfg_capacity_existing)
    string(REPLACE "\r\n" "\n" jfg_capacity_existing "${jfg_capacity_existing}")
endif()
if(NOT jfg_capacity_existing STREQUAL jfg_capacity_contents)
    file(WRITE "${jfg_capacity_output}" "${jfg_capacity_contents}")
endif()
include("${CMAKE_CURRENT_LIST_DIR}/rt64_persistent_upload_mapping.cmake")
include("${CMAKE_CURRENT_LIST_DIR}/rt64_buffer_reservation.cmake")
include("${CMAKE_CURRENT_LIST_DIR}/rt64_fog_fidelity.cmake")
include("${CMAKE_CURRENT_LIST_DIR}/rt64_camera_fade.cmake")
set(jfg_rt64_root "${jfg_capacity_source}")
