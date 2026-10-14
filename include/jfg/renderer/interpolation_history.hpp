#pragma once
#include "jfg/renderer/rigid_camera.hpp"
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
    // A cross-slot triangle has no complete per-slot topology key. Such a
    // mesh may follow a proven shared transform, but cannot anchor history.
    bool complete_local_topology = true;
    std::optional<RigidPresentationPose> rigid_pose;
};
// F3DDKR may reload one numeric transform into several RT64 matrix slots.
// Equal finite transforms still define one triangle space. Keep incomplete
// local topology out of shape matching; another complete mesh must anchor the
// shared cohort. Actually different/invalid transforms retain endpoint safety.
inline bool allow_shared_matrix_triangle(PresentationMesh& a,
    PresentationMesh& b, PresentationMesh& c) {
    bool equal = a.matrix == b.matrix && a.matrix == c.matrix;
    for(float value:a.matrix) equal = equal && std::isfinite(value);
    if(!equal) {
        a.eligible=b.eligible=c.eligible=false;
        return false;
    }
    a.complete_local_topology=b.complete_local_topology=c.complete_local_topology=false;
    return true;
}
// Known sprite lifetimes own the transform even when animation changes the
// local quad dimensions. Retain vertex count and triangle connectivity; unknown
// meshes still require exact geometry. Texture/local-quad animation itself
// keeps its authored cadence, while the world anchor follows the shared phase.
inline void bind_presentation_billboard(PresentationMesh &mesh,
    const std::array<std::uint64_t, 4> &owner) {
    const auto coordinate_words = mesh.positions.size() * 3U;
    if (owner[0] == 0U || owner[3] == 0U ||
        mesh.key.size() < coordinate_words + 2U ||
        mesh.key[coordinate_words] != 0xFFFFFFFFU)
        return;
    mesh.key.erase(mesh.key.begin(), mesh.key.begin() + coordinate_words);
    mesh.key.insert(mesh.key.begin(), 0x42494C4CU);
    for (auto value : owner) {
        mesh.key.push_back(static_cast<std::uint32_t>(value));
        mesh.key.push_back(static_cast<std::uint32_t>(value >> 32U));
    }
}
// Keep exact rigid geometry, but disambiguate identical assets by actor,
// model instance and camera. Unknown objects retain conservative shape matching.
inline void bind_presentation_rigid(PresentationMesh &mesh,
    const std::array<std::uint64_t, 4> &owner) {
    if (!owner[0] || !owner[3] || mesh.key.empty()) return;
    mesh.key.push_back(0x52494744U);
    for (auto value : owner) {
        mesh.key.push_back(static_cast<std::uint32_t>(value));
        mesh.key.push_back(static_cast<std::uint32_t>(value >> 32U));
    }
}
struct PresentationTransform {
    PresentationMatrix previous{};
    bool matched = false;
    // Semantic skin vertices already carry world-space endpoint motion.
    // Keep the current joint transform and interpolate the shared camera.
    bool semantic_vertices = false;
    PresentationMatrix current_world{}, previous_camera{}, current_camera{};
};
struct PresentationHistoryFrame {
    std::vector<PresentationTransform> transforms;
    std::uint64_t tick = 0;
    unsigned source_rate = 0;
    bool scene = false;
};
template<class Previous>
inline bool continuous_presentation_motion(const Previous& old,
                                          const PresentationMesh& current) noexcept {
    for (float value : old.matrix) if (!std::isfinite(value)) return false;
    for (float value : current.matrix) if (!std::isfinite(value)) return false;
    for (const auto& point : current.positions)
        for (float value : point) if (!std::isfinite(value)) return false;
    if (old.rigid_pose && current.rigid_pose &&
        stationary_rigid_camera_motion(*old.rigid_pose, *current.rigid_pose))
        return true;
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
// Unique shapes anchor shared transforms. Ambiguous groups, invalid cadence
// and jumps use endpoints.
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
        // Real scene intervals vary when an update misses a retrace. Use
        // the actual bounded interval; cadence changes alone are not cuts.
        // Shape/lifetime, pose, finite-coordinate and motion checks below
        // still reject discontinuities. Long gaps and repeated ticks hold.
        const bool continuous = previous_tick_ != 0U && delta >= 1U && delta <= 6U;
        if (continuous && 60U % delta == 0U)
            result.source_rate = static_cast<unsigned>(60U / delta);
        // Borrow current keys for counting; history retains only endpoints.
        struct KeyLess {
            bool operator()(const std::vector<std::uint32_t>* a,
                            const std::vector<std::uint32_t>* b) const { return *a<*b; }
        };
        std::map<const std::vector<std::uint32_t>*, std::size_t, KeyLess> counts;
        for (const auto& mesh : meshes)
            if (mesh.eligible && mesh.complete_local_topology && !mesh.key.empty()) ++counts[&mesh.key];
        std::map<std::vector<std::uint32_t>, HistoryEndpoint> next;
        for (std::size_t i = 0; i < meshes.size(); ++i) {
            const auto& mesh = meshes[i];
            if (!mesh.eligible || !mesh.complete_local_topology || mesh.key.empty() || counts[&mesh.key] != 1U) continue;
            const auto old = previous_.find(mesh.key);
            if (result.source_rate != 0U && old != previous_.end() &&
                continuous_presentation_motion(old->second, mesh))
                result.transforms[i] = {old->second.matrix, true};
            next.emplace(mesh.key,HistoryEndpoint{mesh.matrix,mesh.rigid_pose});
        }
        // A single F3DDKR matrix can feed many vertex batches. Matching or
        // rejecting those batches independently tears their shared edges.
        // One unambiguous shape anchors the whole current matrix; conflicting
        // history or an unsafe batch holds every member at the endpoint.
        struct Cohort {
            PresentationMatrix previous{};
            bool anchored = false;
            bool blocked = false;
        };
        std::map<PresentationMatrix, Cohort> cohorts;
        const auto finite_matrix = [](const PresentationMatrix& matrix) {
            for (float value : matrix) if (!std::isfinite(value)) return false;
            return true;
        };
        for (std::size_t i = 0; i < meshes.size(); ++i) {
            const auto& mesh = meshes[i];
            if (mesh.positions.empty() || !finite_matrix(mesh.matrix)) continue;
            auto& cohort = cohorts[mesh.matrix];
            cohort.blocked = cohort.blocked || !mesh.eligible;
            if (result.transforms[i].matched) {
                const auto& previous = result.transforms[i].previous;
                if (cohort.anchored && cohort.previous != previous)
                    cohort.blocked = true;
                cohort.previous = previous;
                cohort.anchored = true;
            }
        }
        for (std::size_t i = 0; i < meshes.size(); ++i) {
            const auto& mesh = meshes[i];
            if (mesh.positions.empty() || !finite_matrix(mesh.matrix)) continue;
            const auto& cohort = cohorts.at(mesh.matrix);
            result.transforms[i] = {cohort.previous, cohort.anchored && !cohort.blocked};
        }
        previous_ = std::move(next);
        previous_tick_ = tick;
        return result;
    }
private:
    struct HistoryEndpoint {
        PresentationMatrix matrix;
        std::optional<RigidPresentationPose> rigid_pose;
    };
    std::map<std::vector<std::uint32_t>, HistoryEndpoint> previous_;
    std::uint64_t previous_tick_ = 0;
};
} // namespace jfg
