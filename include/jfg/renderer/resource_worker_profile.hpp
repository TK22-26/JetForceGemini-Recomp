#pragma once
#include "jfg/renderer/interpolation_bridge.hpp"
#if defined(_WIN32)
#include <Windows.h>
#endif
namespace jfg {
inline bool render_target_size_trace_enabled() {
    static const bool enabled=[] {
#if defined(_MSC_VER)
        char* value=nullptr;std::size_t size=0;
        (void)_dupenv_s(&value,&size,"JFG_DIAGNOSTIC_RENDER_TARGET_SIZE");
#else
        const char* value=std::getenv("JFG_DIAGNOSTIC_RENDER_TARGET_SIZE");
#endif
        const bool result=value && value[0]=='1' && value[1]=='\0';
#if defined(_MSC_VER)
        std::free(value);
#endif
        return result;
    }();
    return enabled;
}
inline bool texture_upload_reservation_enabled() {
    static const bool enabled=[] {
#if defined(_MSC_VER)
        char* value=nullptr;std::size_t size=0;
        (void)_dupenv_s(&value,&size,"JFG_DIAGNOSTIC_TEXTURE_UPLOAD_RESERVE");
#else
        const char* value=std::getenv("JFG_DIAGNOSTIC_TEXTURE_UPLOAD_RESERVE");
#endif
        const bool result=value && value[0]=='1' && value[1]=='\0';
#if defined(_MSC_VER)
        std::free(value);
#endif
        return result;
    }();
    return enabled;
}
inline bool buffer_reservation_enabled() {
    static const bool enabled=[] {
#if defined(_MSC_VER)
        char* value=nullptr;std::size_t size=0;
        (void)_dupenv_s(&value,&size,"JFG_DIAGNOSTIC_BUFFER_RESERVATION");
#else
        const char* value=std::getenv("JFG_DIAGNOSTIC_BUFFER_RESERVATION");
#endif
        const bool result=value && value[0]=='1' && value[1]=='\0';
#if defined(_MSC_VER)
        std::free(value);
#endif
        return result;
    }();
    return enabled;
}
inline bool write_only_upload_map_enabled() {
    static const bool enabled=[] {
#if defined(_MSC_VER)
        char* value=nullptr;std::size_t size=0;
        (void)_dupenv_s(&value,&size,"JFG_DIAGNOSTIC_WRITE_ONLY_UPLOAD_MAP");
#else
        const char* value=std::getenv("JFG_DIAGNOSTIC_WRITE_ONLY_UPLOAD_MAP");
#endif
        const bool result=value && value[0]=='1' && value[1]=='\0';
#if defined(_MSC_VER)
        std::free(value);
#endif
        return result;
    }();
    return enabled;
}
inline bool fixed_raster_noise_fixture_enabled() {
    static const bool enabled=[] {
#if defined(_MSC_VER)
        char* value=nullptr;std::size_t size=0;
        (void)_dupenv_s(&value,&size,"JFG_DIAGNOSTIC_FIXED_RASTER_NOISE");
#else
        const char* value=std::getenv("JFG_DIAGNOSTIC_FIXED_RASTER_NOISE");
#endif
        const bool result=value && value[0]=='1' && value[1]=='\0';
#if defined(_MSC_VER)
        std::free(value);
#endif
        return result;
    }();
    return enabled;
}
inline bool resource_worker_profile_enabled() {
    static const bool enabled=[] {
#if defined(_MSC_VER)
        char* value=nullptr;std::size_t size=0;
        (void)_dupenv_s(&value,&size,"JFG_DIAGNOSTIC_BUFFER_UPLOAD_PROFILE");
#else
        const char* value=std::getenv("JFG_DIAGNOSTIC_BUFFER_UPLOAD_PROFILE");
#endif
        const bool result=value && value[0]=='1' && value[1]=='\0';
#if defined(_MSC_VER)
        std::free(value);
#endif
        return result;
    }();
    return enabled && interpolation_trace_enabled();
}
// Private stage attribution. Preserve operations and synchronization; no pointer
// dereference or cross-thread state read, and no clock reads while disabled.
class ResourceWorkerProfile {
    const char* kind_;
    std::uintptr_t owner_;
    unsigned count_;
    bool enabled_;
    std::uint64_t started_=0, cycles_=0;
    bool cycles_valid_=false;
    static std::uint64_t now_ns() {
        return std::chrono::duration_cast<std::chrono::nanoseconds>(
            std::chrono::steady_clock::now().time_since_epoch()).count();
    }
public:
    ResourceWorkerProfile(const char* kind,const void* owner,unsigned count)
        :kind_(kind),owner_(reinterpret_cast<std::uintptr_t>(owner)),count_(count),
         enabled_(resource_worker_profile_enabled()) {
        if(!enabled_)return;
        started_=now_ns();
#if defined(_WIN32)
        ULONG64 value=0;cycles_valid_=QueryThreadCycleTime(GetCurrentThread(),&value)!=0;
        cycles_=value;
#endif
    }
    ~ResourceWorkerProfile() {
        if(!enabled_)return;
        const auto finished=now_ns();std::uint64_t delta=0;
#if defined(_WIN32)
        ULONG64 value=0;
        if(cycles_valid_ && QueryThreadCycleTime(GetCurrentThread(),&value) && value>=cycles_)
            delta=value-cycles_;
#endif
        trace_interpolation(kind_,started_/1000U,static_cast<unsigned>(owner_),
            static_cast<unsigned>(owner_>>32U),count_,0U,0.0f,finished-started_,delta);
    }
};
}
