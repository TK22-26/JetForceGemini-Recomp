#pragma once
#include "jfg/renderer/interpolation_bridge.hpp"
#if defined(_WIN32)
#include <Windows.h>
#endif
namespace jfg {
// Private worker-side attribution. No changes to queue ownership, uploads or
// waits. Emit only after the batch; diagnostics are excluded from FPS acceptance.
class TextureUploadProfile {
    struct Stamp {
        std::uint64_t ns=0, cycles=0;
        bool valid=false;
    };
    std::array<Stamp,8> stamps_{};
    unsigned size_=0, count_=1;
    bool enabled_=false;
    static bool selected() {
        static const bool result=[] {
#if defined(_MSC_VER)
            char* value=nullptr;std::size_t size=0;
            (void)_dupenv_s(&value,&size,"JFG_DIAGNOSTIC_TEXTURE_UPLOAD_PROFILE");
#else
            const char* value=std::getenv("JFG_DIAGNOSTIC_TEXTURE_UPLOAD_PROFILE");
#endif
            const bool enabled=value && value[0]=='1' && value[1]=='\0';
#if defined(_MSC_VER)
            std::free(value);
#endif
            return enabled;
        }();
        return result;
    }
    static Stamp sample() {
        Stamp s;
        s.ns=std::chrono::duration_cast<std::chrono::nanoseconds>(
            std::chrono::steady_clock::now().time_since_epoch()).count();
#if defined(_WIN32)
        ULONG64 cycles=0;
        s.valid=QueryThreadCycleTime(GetCurrentThread(),&cycles)!=0;
        s.cycles=cycles;
#endif
        return s;
    }
public:
    explicit TextureUploadProfile(std::size_t size)
        :size_(static_cast<unsigned>(size)),enabled_(selected() && interpolation_trace_enabled()) {
        if(enabled_)stamps_[0]=sample();
    }
    void mark() {
        if(enabled_ && count_<stamps_.size())stamps_[count_++]=sample();
    }
    void finish() {
        if(!enabled_)return;
        for(unsigned i=1;i<count_;++i) {
            const auto& a=stamps_[i-1];const auto& b=stamps_[i];
            const bool valid=a.valid && b.valid && b.cycles>=a.cycles;
            trace_interpolation("texture-upload-stage",stamps_[0].ns/1000U,
                size_,i,0U,valid?1U:0U,0.0f,b.ns-a.ns,valid?b.cycles-a.cycles:0U);
        }
    }
};
}
