# Optional buffer-worker attribution in a pinned build-private source copy.
set(jfg_buffer_source "${jfg_rt64_root}/src/render/rt64_buffer_uploader.cpp")
file(READ "${jfg_buffer_source}" jfg_buffer_contents)
string(REPLACE "\r\n" "\n" jfg_buffer_contents "${jfg_buffer_contents}")
string(SHA256 jfg_buffer_digest "${jfg_buffer_contents}")
if(NOT jfg_buffer_digest STREQUAL "d1add014be5f6bf1df77b6f3342c6772bb5235e834b1cb1b7a4e83de167acb40")
    message(FATAL_ERROR "Pinned buffer uploader changed")
endif()
function(jfg_buffer_replace old new)
    string(FIND "${jfg_buffer_contents}" "${old}" offset)
    if(offset EQUAL -1)
        message(FATAL_ERROR "Missing buffer profile site: ${old}")
    endif()
    string(REPLACE "${old}" "${new}" jfg_buffer_contents "${jfg_buffer_contents}")
    set(jfg_buffer_contents "${jfg_buffer_contents}" PARENT_SCOPE)
endfunction()
jfg_buffer_replace("    void BufferUploader::submit(RenderWorker *worker, const std::vector<Upload> &uploads) {"
    "    void BufferUploader::submit(RenderWorker *worker, const std::vector<Upload> &uploads) {\n        jfg::ResourceWorkerProfile jfgProfile(\"buffer-submit\",this,static_cast<unsigned>(uploads.size()));")
jfg_buffer_replace("    void BufferUploader::updateResources(RenderWorker *worker, std::vector<Upload> &blankUploads) {"
    "    void BufferUploader::updateResources(RenderWorker *worker, std::vector<Upload> &blankUploads) {\n        jfg::ResourceWorkerProfile jfgProfile(\"buffer-resources\",this,static_cast<unsigned>(blankUploads.size()));")
jfg_buffer_replace("        const RenderRange writtenRange(srcOffset, srcOffset + srcSize);"
    "        jfg::ResourceWorkerProfile jfgProfile(\"buffer-copy\",this,static_cast<unsigned>(srcSize));\n        const RenderRange writtenRange(srcOffset, srcOffset + srcSize);")
jfg_buffer_replace("    void BufferUploader::wait() {"
    "    void BufferUploader::wait() {\n        jfg::ResourceWorkerProfile jfgProfile(\"buffer-wait\",this,0U);")
jfg_buffer_replace([=[        uint8_t *dstData = static_cast<uint8_t *>(upload.dstPair->uploadBuffer->map());
        memcpy(dstData + srcOffset, static_cast<const uint8_t *>(upload.srcData) + srcOffset, srcSize);
        upload.dstPair->uploadBuffer->unmap(0, &writtenRange);]=]
[=[        uint8_t *dstData = nullptr;
        {
            jfg::ResourceWorkerProfile profile("buffer-map",this,static_cast<unsigned>(srcSize));
            const RenderRange noReads(0,0);
            dstData = static_cast<uint8_t *>(upload.dstPair->uploadBuffer->map(0,
                jfg::write_only_upload_map_enabled() ? &noReads : nullptr));
        }
        {
            jfg::ResourceWorkerProfile profile("buffer-memcpy",this,static_cast<unsigned>(srcSize));
            memcpy(dstData + srcOffset, static_cast<const uint8_t *>(upload.srcData) + srcOffset, srcSize);
        }
        {
            jfg::ResourceWorkerProfile profile("buffer-unmap",this,static_cast<unsigned>(srcSize));
            upload.dstPair->uploadBuffer->unmap(0, &writtenRange);
        }]=])

jfg_buffer_replace("            bufferPair.defaultViews.clear();"
[=[            if (jfg::resource_worker_profile_enabled()) {
                const auto id=reinterpret_cast<std::uintptr_t>(&bufferPair);
                jfg::trace_interpolation("buffer-grow",static_cast<std::uint64_t>(id),
                    static_cast<unsigned>(u.srcDataStride),static_cast<unsigned>(u.bufferFlags),
                    static_cast<unsigned>(bufferPair.allocatedSize),static_cast<unsigned>(requiredSize),
                    0.0f,u.formatViews.size(),0U);
            }
            bufferPair.defaultViews.clear();]=])
jfg_buffer_replace("            bufferPair.uploadBuffer = worker->device->createBuffer(RenderBufferDesc::UploadBuffer(bufferPair.allocatedSize));"
[=[            {
                jfg::ResourceWorkerProfile profile("buffer-upload-create",&bufferPair,
                    static_cast<unsigned>(bufferPair.allocatedSize));
                bufferPair.uploadBuffer = worker->device->createBuffer(RenderBufferDesc::UploadBuffer(bufferPair.allocatedSize));
            }]=])
jfg_buffer_replace("            bufferPair.defaultBuffer = worker->device->createBuffer(RenderBufferDesc::DefaultBuffer(bufferPair.allocatedSize, u.bufferFlags));"
[=[            {
                jfg::ResourceWorkerProfile profile("buffer-default-create",&bufferPair,
                    static_cast<unsigned>(bufferPair.allocatedSize));
                bufferPair.defaultBuffer = worker->device->createBuffer(RenderBufferDesc::DefaultBuffer(bufferPair.allocatedSize, u.bufferFlags));
            }]=])


if(JFG_RT64_BUFFER_RESERVATION)
    # Keep CPU staging ownership separate from GPU destination capacity. Growing
    # a destination still reuploads its entire valid range, with original fences.
    jfg_buffer_replace("                bufferPair.uploadBuffer = worker->device->createBuffer(RenderBufferDesc::UploadBuffer(bufferPair.allocatedSize));"
[=[                if (!bufferPair.uploadBuffer || bufferPair.uploadAllocatedSize < bufferPair.allocatedSize) {
                    bufferPair.uploadAllocatedSize = std::max(bufferPair.allocatedSize, bufferPair.minimumUploadSize);
                    bufferPair.uploadBuffer = worker->device->createBuffer(RenderBufferDesc::UploadBuffer(bufferPair.uploadAllocatedSize));
                    if (jfg::resource_worker_profile_enabled())
                        jfg::trace_interpolation("buffer-reserve",reinterpret_cast<std::uintptr_t>(&bufferPair),
                            0U,0U,static_cast<unsigned>(bufferPair.allocatedSize),
                            static_cast<unsigned>(bufferPair.minimumUploadSize),0.0f,
                            bufferPair.uploadAllocatedSize,0U);
                }]=])
endif()
set(jfg_buffer_generated "${CMAKE_CURRENT_BINARY_DIR}/generated/rt64/render/rt64_buffer_uploader.cpp")
file(WRITE "${jfg_buffer_generated}" "#include \"jfg/renderer/resource_worker_profile.hpp\"\n${jfg_buffer_contents}")
get_target_property(jfg_buffer_sources rt64 SOURCES)
set(jfg_buffer_patched)
set(jfg_buffer_found FALSE)
foreach(unit IN LISTS jfg_buffer_sources)
    get_filename_component(name "${unit}" NAME)
    if(name STREQUAL "rt64_buffer_uploader.cpp")
        list(APPEND jfg_buffer_patched "${jfg_buffer_generated}")
        set(jfg_buffer_found TRUE)
    else()
        list(APPEND jfg_buffer_patched "${unit}")
    endif()
endforeach()
if(NOT jfg_buffer_found)
    message(FATAL_ERROR "Buffer uploader target source missing")
endif()
set_property(TARGET rt64 PROPERTY SOURCES "${jfg_buffer_patched}")
