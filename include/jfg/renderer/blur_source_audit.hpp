#pragma once
#include "jfg/renderer/native_blur_mode.hpp"
#include <algorithm>
#include <array>
#include <mutex>
#include <chrono>
#include <cstdint>
#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <string>

namespace jfg {
// Private opt-in evidence only. Fixed-size numeric rows stay in RAM until
// explicit shutdown. No render-frame disk I/O or image readback.
inline bool blur_source_audit_enabled() {
    static const bool requested = [] {
#if defined(_MSC_VER)
        char* value = nullptr; std::size_t length = 0;
        (void)_dupenv_s(&value, &length, "JFG_DIAGNOSTIC_BLUR_AUDIT");
        const bool on = value && value[0] == '1' && value[1] == '\0';
        std::free(value); return on;
#else
        const char* value = std::getenv("JFG_DIAGNOSTIC_BLUR_AUDIT");
        return value && value[0] == '1' && value[1] == '\0';
#endif
    }();
    return requested || diagnostic_blur_mode() == 5U;
}
struct BlurSourceAuditRow {
    std::uint64_t tick = 0, id = 0;
    unsigned event = 0, source = 0, target = 0;
    unsigned source_width = 0, source_height = 0;
    unsigned target_width = 0, target_height = 0;
    unsigned flags = 0, gpu_tiles = 0, tiles = 0;
};
class BlurSourceAudit {
    static constexpr std::size_t capacity = 262144;
    std::array<BlurSourceAuditRow, capacity> rows_{};
    std::size_t count_ = 0;
    std::mutex mutex_;
    std::filesystem::path path_;
    unsigned cap_ = 0;
    bool unlimited_ = false, vsync_ = false, finished_ = false;
public:
    void configure(unsigned cap, bool unlimited, bool vsync) noexcept {
        cap_ = cap; unlimited_ = unlimited; vsync_ = vsync;
        try {
            std::filesystem::path path;
#if defined(_MSC_VER)
            wchar_t* value = nullptr; std::size_t size = 0;
            (void)_wdupenv_s(&value, &size, L"JFG_VIDEO_CONFIG");
            if (value) path = value;
            std::free(value);
#else
            if (const char* value = std::getenv("JFG_VIDEO_CONFIG")) path = value;
#endif
            if (path.empty()) return;
            path = path.parent_path() / "performance";
            std::error_code error;
            std::filesystem::create_directories(path, error);
            if (error) return;
            const auto stamp = std::chrono::system_clock::now().time_since_epoch().count();
            path_ = path / ("blur-source-audit-" + std::to_string(stamp) + ".csv");
            // Startup marker distinguishes an inactive collector from lost
            // shutdown output. This runs before renderer workers start.
            std::ofstream out(path_, std::ios::binary | std::ios::trunc);
            out << "# private blur source audit v2; started render_mode=" << native_blur_render_mode() << " cap=" << cap_
                << " unlimited=" << unlimited_ << " vsync=" << vsync_ << '\n'
                << "# incomplete: buffered rows are saved on explicit game exit\n";
        } catch (...) {}
    }
    void record(BlurSourceAuditRow row) noexcept {
        const std::scoped_lock lock(mutex_);
        if (finished_) return;
        const auto index = count_++;
        if (index < capacity) rows_[index] = row;
    }
    void finish() noexcept {
        // Native Play uses std::_Exit, so a destructor is not sufficient.
        // Stop producers and finish in-flight rows, then release the mutex
        // before writing. Render workers never wait for disk I/O.
        std::unique_lock lock(mutex_);
        if (finished_) return;
        finished_ = true;
        const auto total = count_;
        const auto saved = (std::min)(total, capacity);
        lock.unlock();
        try {
            if (path_.empty()) return;
            std::ofstream out(path_, std::ios::binary | std::ios::trunc);
            if (!out) return;
            out << "# private blur source audit v2; render_mode=" << native_blur_render_mode() << " cap=" << cap_
                << " unlimited=" << unlimited_ << " vsync=" << vsync_ << '\n'
                << "# events: 1 native blur, 2 pairing, 3 source copy, 4 presentation target selected, 5 world targets, 6 source identity\n"
                << "# copy flags: 1 empty source, 2 alias, 4 width, 8 height, 16 format, 32 samples, 64 unpaired/wrong target; 0 copy issued\n"
                << "# pairing flags: 1 previous frame shape, 2 slot, 4 no snapshot, 8 not deferred, 16 no offer, 32 serial, 64 tick, 128 source, 256 no geometry; 0 paired\n"
                << "# event 5: source=color target=depth dimensions=width/siz/fmt/calls flags=1 fill-only 2 depth-clear 4 empty 8 selected; gpu_tiles=rate\n"
                << "# event 6: dimensions=offered serial/accepted serial/offered tick/accepted tick; flags=1 no identity; gpu_tiles/tiles=offered/accepted rate\n"
                << "# event 7: source=pane identities target=owned vertices source_width=matched vertices source_height=moving UV vertices\n"
                << "# event 8: source=command index target=blur preference source_width=native alpha source_height=applied alpha flags=diagnostic override\n"
                << "# event 9: id=actor lifetime source=actor target=model dimensions=invalid/cadence/duplicate/missing flags=motion rejection gpu_tiles=actual matched vertices tiles=submitted vertices; zero submitted can mean native culling\n"
                << "# event 10: id=camera identity source=matrix target=generation dimensions=view0/view2/view12/view14 float bits flags=valid pose\n"
                << "# event 11: id=actor lifetime source=actor target=model source_width=projected rejects accepted with validated camera source_height=actual matched vertices target_width=submitted vertices\n"
                << "tick,id,event,source,target,source_width,source_height,target_width,target_height,flags,gpu_tiles,tiles\n";
            for (std::size_t i = 0; i < saved; ++i) {
                const auto& r = rows_[i];
                out << r.tick << ',' << r.id << ',' << r.event << ',' << r.source << ',' << r.target
                    << ',' << r.source_width << ',' << r.source_height << ',' << r.target_width
                    << ',' << r.target_height << ',' << r.flags << ',' << r.gpu_tiles << ',' << r.tiles << '\n';
            }
            out << "# complete total=" << total << " saved=" << saved << " dropped=" << total - saved << '\n';
        } catch (...) {}
    }
};
inline BlurSourceAudit& blur_source_audit() {
    static BlurSourceAudit state;
    return state;
}
inline void record_blur_source_audit(BlurSourceAuditRow row) noexcept {
    if (blur_source_audit_enabled()) blur_source_audit().record(row);
}
inline void finish_blur_source_audit() noexcept {
    if (blur_source_audit_enabled()) blur_source_audit().finish();
}
} // namespace jfg
