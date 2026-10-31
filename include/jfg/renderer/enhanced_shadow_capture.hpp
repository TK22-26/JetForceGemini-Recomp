#pragma once
// Bounded, opt-in shadow evidence. No disk writes occur during presentation.
#include "jfg/renderer/enhanced_shadow.hpp"
#include <cstdlib>
#include <fstream>
#include <mutex>
#include <string>
namespace jfg {
inline void write_enhanced_shadow_geometry(const EnhancedShadowFrame& frame,
        std::uint64_t tick,const std::string& path) {
    std::ofstream file(path,std::ios::trunc);
    if(!file)return;
    file.precision(9);
    file << "{\"tick\":" << tick << ",\"actors\":[";
    bool comma=false;
    for(const auto& actor:frame.actors) {
        if(comma)file<<',';
        comma=true;
        file<<"{\"actor\":"<<actor.actor<<",\"caster_start\":"<<actor.caster_start
            <<",\"caster_count\":"<<actor.caster_count
            <<",\"receiver_start\":"<<actor.receiver_start<<",\"receiver_count\":"<<actor.receiver_count
            <<",\"bounds\":[";
        for(unsigned i=0;i<4;++i){if(i)file<<',';file<<actor.bounds[i];}
        file<<"],\"light\":[";
        for(unsigned i=0;i<4;++i){if(i)file<<',';file<<actor.light[i];}
        file<<"]}";
    }
    file<<"],\"vertices\":[";comma=false;
    for(const auto& v:frame.vertices) {
        if(comma)file<<',';
        comma=true;
        file<<'[';
        for(unsigned i=0;i<3;++i){if(i)file<<',';file<<v.current[i];}
        for(unsigned i=0;i<3;++i)file<<','<<v.previous[i];
        file<<','<<v.opacity<<','<<v.previous_opacity<<']';
    }
    file<<"],\"draws\":[";comma=false;
    for(const auto& d:frame.draws) {
        if(comma)file<<',';
        comma=true;
        file<<'['<<d.actor_index<<','<<d.receiver_start<<','<<d.index_count<<']';
    }
    file<<"]}";
}
class EnhancedShadowCapture {
public:
        std::string path;
        std::shared_ptr<const EnhancedShadowFrame> frame;
        std::uint64_t tick=0;
        std::mutex mutex;
        bool closed=false;
        EnhancedShadowCapture() {
            const auto environment=[](const char* key) {
#if defined(_MSC_VER)
                char* value=nullptr;std::size_t size=0;
                (void)_dupenv_s(&value,&size,key);
                std::string result=value?value:"";std::free(value);return result;
#else
                const char* value=std::getenv(key);return std::string(value?value:"");
#endif
            };
            path=environment("JFG_ENHANCED_SHADOW_CAPTURE");
            if(path.empty()) {
                const auto trace=environment("JFG_GAMEPLAY_TRACE");
                if(!trace.empty()) {
                    const auto slash=trace.find_last_of("/\\");
                    path=(slash==std::string::npos?std::string{}:trace.substr(0,slash+1))+
                        "enhanced-shadow.json";
                }
            }
        }
        void record(const std::shared_ptr<const EnhancedShadowFrame>& next,
                    std::uint64_t next_tick) {
            if(path.empty()||!next)return;
            const std::scoped_lock lock(mutex);
            if(closed)return;
            frame=next;tick=next_tick;
        }
        void finish() noexcept {
            try {
                const std::scoped_lock lock(mutex);
                if(closed)return;
                closed=true;
                if(!path.empty()&&frame)write_enhanced_shadow_geometry(*frame,tick,path);
                frame.reset();
            } catch(...) {} // Diagnostics must never break shutdown.
        }
        ~EnhancedShadowCapture() { finish(); }
};

inline EnhancedShadowCapture& enhanced_shadow_capture() {
    static EnhancedShadowCapture capture;return capture;
}
inline void capture_enhanced_shadow_geometry(
        const std::shared_ptr<const EnhancedShadowFrame>& frame,std::uint64_t tick) {
    enhanced_shadow_capture().record(frame,tick);
}
inline void finish_enhanced_shadow_capture() noexcept {
    enhanced_shadow_capture().finish();
}
} // namespace jfg
