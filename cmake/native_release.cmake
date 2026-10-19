# Initial cache for the qualified Windows native release.
# Supply the existing private generated-code/dependency paths separately.
# This selects the same optimization values as the owner-tested 1.3 preview
# while excluding automatic control/blur capture and source-only comparison.
set(JFG_NATIVE_PLAY_OPTIMIZATIONS ON CACHE BOOL "" FORCE)
set(JFG_V13_PREVIEW_DEFAULTS OFF CACHE BOOL "" FORCE)
set(JFG_V13_CONTROLS_REVIEW OFF CACHE BOOL "" FORCE)
set(JFG_V13_BLUR_SOURCE_REVIEW OFF CACHE BOOL "" FORCE)
set(JFG_EXPERIMENTAL_NATIVE_PLAY_TIMING ON CACHE BOOL "" FORCE)
set(JFG_EXPERIMENTAL_NATIVE_COLLISION ON CACHE BOOL "" FORCE)
set(JFG_RT64_WORKLOAD_CAPACITY "5" CACHE STRING "" FORCE)
set(JFG_RT64_PERSISTENT_UPLOAD_MAPPING ON CACHE BOOL "" FORCE)
set(JFG_RT64_BUFFER_RESERVATION ON CACHE BOOL "" FORCE)
