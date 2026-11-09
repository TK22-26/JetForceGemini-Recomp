# Restore the pristine view when disabled; only the private view is ever written.
foreach(ext IN ITEMS h cpp)
    file(READ "${jfg_capacity_original_root}/src/contrib/plume/plume_d3d12.${ext}" jfg_upload_${ext})
    string(REPLACE "\r\n" "\n" jfg_upload_${ext} "${jfg_upload_${ext}}")
    string(SHA256 digest "${jfg_upload_${ext}}")
    if(ext STREQUAL "h")
        set(expected "c656dd4905634746a0ba660ad59bfa9d482a22d39908c1547c84c00628d06143")
    else()
        set(expected "795f1e7d75c450106b7154f4089ea4549fff111e13d6a078b81114c3e0dea317")
    endif()
    if(NOT digest STREQUAL expected)
        message(FATAL_ERROR "Pinned Plume upload mapping source changed: ${ext}")
    endif()
endforeach()
if(JFG_RT64_PERSISTENT_UPLOAD_MAPPING)
    set(old [=[        RenderBufferDesc desc;

        D3D12Buffer() = default;]=])
    set(new [=[        RenderBufferDesc desc;
        // Set before publication; immutable until resource destruction.
        void *jfgPersistentUploadData = nullptr;

        D3D12Buffer() = default;]=])
    string(FIND "${jfg_upload_h}" "${old}" found)
    if(found EQUAL -1)
        message(FATAL_ERROR "Missing pinned D3D12Buffer mapping member site")
    endif()
    string(REPLACE "${old}" "${new}" jfg_upload_h "${jfg_upload_h}")
    set(old "    D3D12Buffer::D3D12Buffer(D3D12Device *device, D3D12Pool *pool, const RenderBufferDesc &desc) {")
    set(new [=[    static bool jfgPersistentUploadMappingEnabled() {
        static const bool enabled=[] {
            char selected[2]{};
            return GetEnvironmentVariableA("JFG_DIAGNOSTIC_PERSISTENT_UPLOAD_MAP",selected,2U)==1U &&
                selected[0]=='1';
        }();
        return enabled;
    }

    D3D12Buffer::D3D12Buffer(D3D12Device *device, D3D12Pool *pool, const RenderBufferDesc &desc) {]=])
    string(FIND "${jfg_upload_cpp}" "${old}" begin)
    if(begin EQUAL -1)
        message(FATAL_ERROR "Missing pinned D3D12Buffer constructor")
    endif()
    string(REPLACE "${old}" "${new}" jfg_upload_cpp "${jfg_upload_cpp}")
    set(old [=[    }

    D3D12Buffer::~D3D12Buffer() {
        if (allocation != nullptr) {]=])
    set(new [=[        if (desc.heapType == RenderHeapType::UPLOAD && jfgPersistentUploadMappingEnabled()) {
            // CPU writes finish before the existing command submissions/fences.
            // Readback/default buffers and their mapping behavior are untouched.
            const D3D12_RANGE noReads = { 0, 0 };
            void *mapped = nullptr;
            if (SUCCEEDED(d3d->Map(0, &noReads, &mapped)))
                jfgPersistentUploadData = mapped;
        }
    }

    D3D12Buffer::~D3D12Buffer() {
        if (jfgPersistentUploadData != nullptr) {
            d3d->Unmap(0, nullptr);
            jfgPersistentUploadData = nullptr;
        }
        if (allocation != nullptr) {]=])
    string(FIND "${jfg_upload_cpp}" "${old}" found)
    if(found EQUAL -1)
        message(FATAL_ERROR "Missing pinned D3D12Buffer constructor/destructor boundary")
    endif()
    string(REPLACE "${old}" "${new}" jfg_upload_cpp "${jfg_upload_cpp}")
    foreach(operation IN ITEMS map unmap)
        if(operation STREQUAL "map")
            set(old "    void *D3D12Buffer::map(uint32_t subresource, const RenderRange *readRange) {")
            set(new "${old}\n        if (subresource == 0U && jfgPersistentUploadData != nullptr) return jfgPersistentUploadData;")
        else()
            set(old "    void D3D12Buffer::unmap(uint32_t subresource, const RenderRange *writtenRange) {")
            set(new "${old}\n        if (subresource == 0U && jfgPersistentUploadData != nullptr) return;")
        endif()
        string(FIND "${jfg_upload_cpp}" "${old}" found)
        if(found EQUAL -1)
            message(FATAL_ERROR "Missing pinned D3D12Buffer ${operation}")
        endif()
        string(REPLACE "${old}" "${new}" jfg_upload_cpp "${jfg_upload_cpp}")
    endforeach()
endif()
# Export only the result of the pinned, site-checked transformation above.

foreach(ext IN ITEMS h cpp)
    set(destination "${jfg_capacity_source}/src/contrib/plume/plume_d3d12.${ext}")
    set(existing "")
    if(EXISTS "${destination}")
        file(READ "${destination}" existing)
        string(REPLACE "\r\n" "\n" existing "${existing}")
    endif()
    if(NOT existing STREQUAL jfg_upload_${ext})
        file(WRITE "${destination}" "${jfg_upload_${ext}}")
    endif()
endforeach()
# CMake writes platform line endings; verify normalized contents before
# exporting the byte-level digest expected by the existing readback patch.
file(READ "${jfg_capacity_source}/src/contrib/plume/plume_d3d12.cpp" jfg_upload_written)
string(REPLACE "\r\n" "\n" jfg_upload_written "${jfg_upload_written}")
if(NOT jfg_upload_written STREQUAL jfg_upload_cpp)
    message(FATAL_ERROR "Persistent upload mapping generated source content mismatch")
endif()
file(SHA256 "${jfg_capacity_source}/src/contrib/plume/plume_d3d12.cpp" jfg_rt64_plume_upload_sha256)
