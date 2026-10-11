#pragma once
#include <array>
#include <charconv>
#include <cmath>
#include <cstdint>
#include <map>
#include <optional>
#include <string_view>
#include <vector>

namespace jfg {
// Experimental presentation only. Zero preserves the original renderer.
inline std::optional<unsigned> parse_render_fps(std::string_view value) noexcept {
    if (value.empty() || value == "0") return 0U;
    unsigned rate = 0;
    const auto result = std::from_chars(value.data(), value.data() + value.size(), rate);
    if (result.ec != std::errc{} || result.ptr != value.data() + value.size() ||
        rate < 60U || rate > 1000U) return std::nullopt;
    return rate;
}
using PresentationMatrix = std::array<float, 16>;
struct PresentationMesh {
    // Exact vertex positions and local triangle indices, not a guest address.
    std::vector<std::uint32_t> key;
    std::vector<std::array<float, 3>> positions;
    PresentationMatrix matrix{};
    bool eligible = true;
};
struct PresentationTransform {
    PresentationMatrix previous{};
    bool matched = false;
};
struct PresentationHistoryFrame {
    std::vector<PresentationTransform> transforms;
    std::uint64_t tick = 0;
    unsigned source_rate = 0;
    bool scene = false;
};
inline bool continuous_presentation_motion(const PresentationMesh& old,
                                          const PresentationMesh& current) noexcept {
    for (float value : old.matrix) if (!std::isfinite(value)) return false;
    for (float value : current.matrix) if (!std::isfinite(value)) return false;
    bool visible = false;
    for (const auto& point : current.positions) {
        const auto project = [&](const PresentationMatrix& matrix) {
            std::array<float, 4> clip{};
            for (std::size_t c = 0; c < 4; ++c)
                clip[c] = point[0]*matrix[c] + point[1]*matrix[4+c] +
                    point[2]*matrix[8+c] + matrix[12+c];
            return clip;
        };
        const auto a = project(old.matrix), b = project(current.matrix);
        if (!std::isfinite(a[3]) || !std::isfinite(b[3])) return false;
        if (a[3] <= 0.001f && b[3] <= 0.001f) continue;
        if (a[3] <= 0.001f || b[3] <= 0.001f) return false;
        visible = true;
        if (b[3]/a[3] < 0.5f || b[3]/a[3] > 2.0f) return false;
        for (std::size_t c = 0; c < 2; ++c) {
            const float movement = b[c]/b[3] - a[c]/a[3];
            if (!std::isfinite(movement) || std::abs(movement) > 0.35f) return false;
        }
    }
    return visible;
}
// One previous scene; no references into guest or RT64 ring-buffer storage.
// Duplicate shapes, changed geometry, invalid cadence and jumps use endpoints.
// This conservative prototype does not replace semantic actor identities.
class PresentationHistory {
public:
    PresentationHistoryFrame record(const std::vector<PresentationMesh>& meshes,
                                    std::uint64_t tick, bool scene) {
        PresentationHistoryFrame result;
        result.scene = scene;
        result.tick = tick;
        result.transforms.resize(meshes.size());
        if (!scene) return result;
        const auto delta = tick > previous_tick_ ? tick - previous_tick_ : 0U;
        const bool continuous = previous_tick_ != 0U && delta >= 1U && delta <= 6U &&
            (previous_delta_ == 0U || previous_delta_ == delta);
        if (continuous && 60U % delta == 0U)
            result.source_rate = static_cast<unsigned>(60U / delta);
        std::map<std::vector<std::uint32_t>, std::size_t> counts;
        for (const auto& mesh : meshes)
            if (mesh.eligible && !mesh.key.empty()) ++counts[mesh.key];
        std::map<std::vector<std::uint32_t>, PresentationMesh> next;
        for (std::size_t i = 0; i < meshes.size(); ++i) {
            const auto& mesh = meshes[i];
            if (!mesh.eligible || mesh.key.empty() || counts[mesh.key] != 1U) continue;
            const auto old = previous_.find(mesh.key);
            if (result.source_rate != 0U && old != previous_.end() &&
                continuous_presentation_motion(old->second, mesh))
                result.transforms[i] = {old->second.matrix, true};
            next.emplace(mesh.key, mesh);
        }
        previous_ = std::move(next);
        previous_delta_ = previous_tick_ == 0U ? 0U : delta;
        previous_tick_ = tick;
        return result;
    }
private:
    std::map<std::vector<std::uint32_t>, PresentationMesh> previous_;
    std::uint64_t previous_tick_ = 0;
    std::uint64_t previous_delta_ = 0;
};
} // namespace jfg
