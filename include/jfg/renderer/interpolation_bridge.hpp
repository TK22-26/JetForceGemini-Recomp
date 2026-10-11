#pragma once
// Build-tree RT64 adapters share immutable host metadata with the decoder.
#include "jfg/renderer/interpolation_history.hpp"
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
    output << event << '\t' << now << '\t' << id << '\t' << source << '\t'
        << target << '\t' << frame << '\t' << count << '\t' << alpha << '\t'
        << matched << '\t' << moving << '\n';
}
} // namespace jfg
