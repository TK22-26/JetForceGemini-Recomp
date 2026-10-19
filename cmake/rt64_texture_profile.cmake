# Private texture-upload attribution; preserve the pinned dependency and all
# original operations. Timings are emitted by the owning upload worker only.
set(jfg_texture_profile_source "${jfg_rt64_root}/src/render/rt64_texture_cache.cpp")
file(SHA256 "${jfg_texture_profile_source}" jfg_texture_profile_hash)
if(NOT jfg_texture_profile_hash STREQUAL "723d43fe5ba112452264f15ce075fdd4b7e525bd01f5d483c73f78e7d1f4e9fc" AND
   NOT jfg_texture_profile_hash STREQUAL "9477e4b36eedcf15da36d08312f98c05fc2d80f62c8a3514f66804843d99a73c")
 message(FATAL_ERROR "Pinned texture cache differs from upload profile input")
endif()
file(READ "${jfg_texture_profile_source}" jfg_texture_profile_contents)
string(REPLACE "\r\n" "\n" jfg_texture_profile_contents "${jfg_texture_profile_contents}")
function(jfg_texture_profile_replace old new)
 string(FIND "${jfg_texture_profile_contents}" "${old}" at)
 if(at EQUAL -1)
  message(FATAL_ERROR "Texture upload profile site missing: ${old}")
 endif()
 string(REPLACE "${old}" "${new}" jfg_texture_profile_contents "${jfg_texture_profile_contents}")
 set(jfg_texture_profile_contents "${jfg_texture_profile_contents}" PARENT_SCOPE)
endfunction()
jfg_texture_profile_replace(
 "                const size_t queueSize = queueCopy.size();"
 "                const size_t queueSize = queueCopy.size();\n                jfg::TextureUploadProfile jfgUploadProfile(queueSize);")
jfg_texture_profile_replace(
 "                // Upload all textures in the queue using the copy worker."
 "                jfgUploadProfile.mark(); // 1: upload buffers and descriptor allocation\n                // Upload all textures in the queue using the copy worker.")
jfg_texture_profile_replace(
 "                copyWorker->commandList->barriers(RenderBarrierStage::COPY, beforeCopyBarriers);"
 "                jfgUploadProfile.mark(); // 2: TMEM resources, copies and mapping\n                copyWorker->commandList->barriers(RenderBarrierStage::COPY, beforeCopyBarriers);")
jfg_texture_profile_replace(
 "                replacementMapAdditions.clear();"
 "                jfgUploadProfile.mark(); // 3: decoded resources, descriptors and replacement lookup\n                replacementMapAdditions.clear();")
jfg_texture_profile_replace(
 "                // Execute the copy worker and signal a semaphore"
 "                jfgUploadProfile.mark(); // 4: replacement preparation\n                // Execute the copy worker and signal a semaphore")
jfg_texture_profile_replace(
 "                // Execute the direct worker but make it wait"
 "                jfgUploadProfile.mark(); // 5: copy submission and decode recording\n                // Execute the direct worker but make it wait")
jfg_texture_profile_replace(
 "                directWorker->wait();"
 "                directWorker->wait();\n                jfgUploadProfile.mark(); // 6: direct submission and completion")
jfg_texture_profile_replace(
 "                uploadQueueFinished.notify_all();"
 "                uploadQueueFinished.notify_all();\n                jfgUploadProfile.mark(); // 7: cache publication and queue cleanup\n                jfgUploadProfile.finish();")
# These pinned upload sites only write CPU data; no readback mapping is changed.
jfg_texture_profile_replace("dstUploadResource->map()"
    "[&]() { const RenderRange noReads(0,0); return dstUploadResource->map(0,jfg::write_only_upload_map_enabled() ? &noReads : nullptr); }()")
jfg_texture_profile_replace("tmemUploadResources[i]->map()"
    "[&]() { const RenderRange noReads(0,0); return tmemUploadResources[i]->map(0,jfg::write_only_upload_map_enabled() ? &noReads : nullptr); }()")

# Warm only reusable staging buffers/descriptors; process no extra textures.
jfg_texture_profile_replace("                const uint64_t TMEMSize = 0x1000;"
    "                const uint64_t TMEMSize = 0x1000;\n                const size_t jfgUploadReserve = jfg::texture_upload_reservation_enabled() ? std::max(queueSize,size_t(256)) : queueSize;")
jfg_texture_profile_replace("for (size_t i = tmemUploadResources.size(); i < queueSize; i++)"
    "for (size_t i = tmemUploadResources.size(); i < jfgUploadReserve; i++)")
jfg_texture_profile_replace("for (size_t i = descriptorSets.size(); i < queueSize; i++)"
    "for (size_t i = descriptorSets.size(); i < jfgUploadReserve; i++)")
include(cmake/rt64_texture_recycling.cmake)
set(jfg_texture_profile_generated "${CMAKE_CURRENT_BINARY_DIR}/generated/rt64/render/rt64_texture_cache.cpp")
file(MAKE_DIRECTORY "${CMAKE_CURRENT_BINARY_DIR}/generated/rt64/render")
file(WRITE "${jfg_texture_profile_generated}" "#include \"jfg/renderer/texture_upload_profile.hpp\"\n#include \"jfg/renderer/resource_worker_profile.hpp\"\n${jfg_texture_profile_contents}")
get_target_property(jfg_texture_profile_sources rt64 SOURCES)
set(jfg_texture_profile_patched)
set(jfg_texture_profile_replaced FALSE)
foreach(unit IN LISTS jfg_texture_profile_sources)
 if(unit MATCHES "(^|[/\\\\])rt64_texture_cache\\.cpp$")
  list(APPEND jfg_texture_profile_patched "${jfg_texture_profile_generated}")
  set(jfg_texture_profile_replaced TRUE)
 else()
  list(APPEND jfg_texture_profile_patched "${unit}")
 endif()
endforeach()
if(NOT jfg_texture_profile_replaced)
 message(FATAL_ERROR "RT64 texture cache translation unit missing")
endif()
set_property(TARGET rt64 PROPERTY SOURCES "${jfg_texture_profile_patched}")
