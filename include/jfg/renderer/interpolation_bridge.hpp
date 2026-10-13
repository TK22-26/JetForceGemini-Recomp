#pragma once
// Build-tree RT64 adapters share immutable host metadata with the decoder.
#include "jfg/renderer/interpolation_history.hpp"
#include "jfg/renderer/presentation_policy.hpp"
#include <chrono>
#include <cstdlib>
#include <fstream>
#include <memory>
#include <mutex>
#include <unordered_map>
namespace jfg {
struct PresentationSnapshots {
    std::mutex mutex;
    std::unordered_map<const void*, std::shared_ptr<const PresentationHistoryFrame>> frames;
};
inline PresentationSnapshots& presentation_snapshots() {
    static PresentationSnapshots snapshots;
    return snapshots;
}
inline void publish_presentation_snapshot(const void* owner,
        std::shared_ptr<const PresentationHistoryFrame> frame) {
    auto& storage = presentation_snapshots();
    const std::scoped_lock lock(storage.mutex);
    if (frame) storage.frames[owner] = std::move(frame);
    else storage.frames.erase(owner);
}
inline std::shared_ptr<const PresentationHistoryFrame> presentation_snapshot(const void* owner) {
    auto& storage = presentation_snapshots();
    const std::scoped_lock lock(storage.mutex);
    const auto found = storage.frames.find(owner);
    return found == storage.frames.end() ? nullptr : found->second;
}
inline bool interpolation_trace_enabled() {
    static const bool enabled = [] {
#if defined(_MSC_VER)
        char* path = nullptr; std::size_t size = 0;
        (void)_dupenv_s(&path, &size, "JFG_RT64_INTERPOLATION_TRACE");
        const bool result = path != nullptr && *path != 0;
        std::free(path); return result;
#else
        const char* path = std::getenv("JFG_RT64_INTERPOLATION_TRACE");
        return path != nullptr && *path != 0;
#endif
    }();
    return enabled;
}
struct PresentationOutputSample {
    std::uint64_t tick = 0;
    unsigned source = 0, frame = 0, count = 0;
    float alpha = 1.0f;
};
struct PresentationOutputDiagnostics {
    std::mutex mutex;
    std::map<std::pair<const void*, unsigned>, PresentationOutputSample> samples;
};
inline PresentationOutputDiagnostics& presentation_output_diagnostics() {
    static PresentationOutputDiagnostics state; return state;
}
inline void record_presentation_output(const void* counters, unsigned index,
        PresentationOutputSample sample) {
    if (!interpolation_trace_enabled()) return;
    auto& state = presentation_output_diagnostics();
    const std::scoped_lock lock(state.mutex);
    state.samples[{counters,index}] = sample;
}
inline PresentationOutputSample presentation_output_sample(const void* counters,
        unsigned index) {
    if (!interpolation_trace_enabled()) return {};
    auto& state = presentation_output_diagnostics();
    const std::scoped_lock lock(state.mutex);
    const auto it = state.samples.find({counters,index});
    return it == state.samples.end() ? PresentationOutputSample{} : it->second;
}
inline void trace_interpolation(const char* event, std::uint64_t id,
        unsigned source, unsigned target, unsigned frame, unsigned count,
        float alpha, std::size_t matched, std::size_t moving) {
    static std::mutex mutex;
    static std::ofstream output([] {
#if defined(_MSC_VER)
        char* path = nullptr;
        std::size_t size = 0;
        (void)_dupenv_s(&path, &size, "JFG_RT64_INTERPOLATION_TRACE");
        const std::string result = path == nullptr ? "" : path;
        std::free(path);
        return result;
#else
        const char* path = std::getenv("JFG_RT64_INTERPOLATION_TRACE");
        return std::string(path == nullptr ? "" : path);
#endif
    }());
    if (!output.is_open()) return;
    const auto now = std::chrono::duration_cast<std::chrono::microseconds>(
        std::chrono::steady_clock::now().time_since_epoch()).count();
    const std::scoped_lock lock(mutex);
    if (target == kUnlimitedPresentation) target = 0;
    if (count == kUnlimitedPresentation) count = 0;
    output << event << '\t' << now << '\t' << id << '\t' << source << '\t'
        << target << '\t' << frame << '\t' << count << '\t' << alpha << '\t'
        << matched << '\t' << moving << '\n';
}
} // namespace jfg
