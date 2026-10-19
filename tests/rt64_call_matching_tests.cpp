#define SDL_MAIN_HANDLED
#include "hle/rt64_game_frame.h"
#include "hle/rt64_workload.h"
#include "../src/renderer/rt64_interpolation_adapter.hpp"
#include <cstdio>
#include <map>

int main() {
    unsigned failed = 0;
    auto check = [&](bool value, const char* name) {
        if (!value) { ++failed; std::printf("FAIL %s\n", name); }
    };
    RT64::Workload shadow;
    shadow.paused = false;
    shadow.fbPairCount = 1;
    shadow.fbPairs.resize(1);
    shadow.fbPairs[0].reset();
    shadow.fbPairs[0].colorImage.width = 64;
    shadow.fbPairs[0].colorImage.address = 0x1000;
    shadow.fbPairs[0].colorImage.fmt = G_IM_FMT_I;
    shadow.fbPairs[0].colorImage.siz = G_IM_SIZ_8b;
    auto snapshot = std::make_shared<jfg::PresentationHistoryFrame>();
    snapshot->tick = 100;
    check(!jfg::independent_shadow_workload(shadow), "unknown workload retains present dependency");
    jfg::publish_presentation_snapshot(&shadow, snapshot);
    check(jfg::independent_shadow_workload(shadow), "isolated shadow is independent of screen present");
    shadow.fbPairs[0].colorImage.width = 320;
    check(!jfg::independent_shadow_workload(shadow), "screen target retains present dependency");
    shadow.fbPairs[0].colorImage.width = 64;
    shadow.fbPairs[0].colorImage.fmt = G_IM_FMT_RGBA;
    check(!jfg::independent_shadow_workload(shadow), "non-mask target retains dependency");
    shadow.fbPairs[0].colorImage.fmt = G_IM_FMT_I;
    shadow.fbPairs[0].depthWrite = true;
    check(!jfg::independent_shadow_workload(shadow), "depth-writing target retains dependency");
    shadow.fbPairs[0].depthWrite = false;
    RT64::FramebufferOperation operation{};
    operation.type = RT64::FramebufferOperation::Type::WriteChanges;
    operation.writeChanges.address = 0x2000;
    shadow.fbPairs[0].startFbOperations.push_back(operation);
    check(!jfg::independent_shadow_workload(shadow), "external framebuffer write retains dependency");
    shadow.fbPairs[0].startFbOperations[0].writeChanges.address = 0x1000;
    check(jfg::independent_shadow_workload(shadow), "own shadow upload remains independent");
    shadow.paused = true;
    check(!jfg::independent_shadow_workload(shadow), "paused workload retains dependency");
    shadow.paused = false;
    snapshot->scene = true;
    check(!jfg::independent_shadow_workload(shadow), "scene classification retains dependency");
    snapshot->scene = false;
    shadow.fbPairs[0].drawColorRect = RT64::FixedRect(0, 0, 64 * 4, 64 * 4);
    check(jfg::cpu_only_shadow_workload(shadow, true, false), "completed CPU mask needs no duplicate queue work");
    check(!jfg::cpu_only_shadow_workload(shadow, false, false), "native readback is mandatory");
    check(!jfg::cpu_only_shadow_workload(shadow, true, true), "GPU texture consumers retain the workload");
    shadow.fbPairs[0].drawColorRect.lry = 65 * 4;
    check(!jfg::cpu_only_shadow_workload(shadow, true, false), "tall intensity target is not a known mask");
    shadow.fbPairs[0].drawColorRect.lry = 64 * 4;
    shadow.fbPairs[0].colorImage.address = 0x800000U - 4095U;
    check(!jfg::cpu_only_shadow_workload(shadow, true, false), "mask extent cannot overrun RDRAM");
    shadow.fbPairs[0].colorImage.address = 0x1000;
    operation.type = RT64::FramebufferOperation::Type::CreateTileCopy;
    operation.createTileCopy.address = 0x1000;
    shadow.fbPairs[0].endFbOperations.push_back(operation);
    check(!jfg::cpu_only_shadow_workload(shadow, true, false), "tile-copy dependency retains queued work");
    shadow.fbPairs[0].endFbOperations.clear();
    shadow.fbPairCount = 2;
    check(!jfg::cpu_only_shadow_workload(shadow, true, false), "multi-target work is not elided");
    shadow.fbPairCount = 1;
    snapshot->scene = true;
    check(!jfg::cpu_only_shadow_workload(shadow, true, false), "displayed scene always retains queued work");
    jfg::publish_presentation_snapshot(&shadow, nullptr);
    RT64::GameFrame frame;
    RT64::Workload workload;
    RT64::Projection projection{};
    RT64::GameCall call{};
    call.callDesc.minWorldMatrix = 0;
    call.callDesc.maxWorldMatrix = 0;
    projection.gameCalls.push_back(call);
    projection.gameCallCount = 1;
    workload.drawData.worldTransformGroups = {0};
    workload.drawData.transformGroups.resize(1);
    const uint32_t modes[]{0U, G_LIGHTING, G_TEXTURE_GEN, G_LIGHTING | G_TEXTURE_GEN};
    const uint8_t tiles[]{G_EX_COMPONENT_SKIP, G_EX_COMPONENT_AUTO, G_EX_COMPONENT_INTERPOLATE};
    for (unsigned transform = 0; transform < 4; ++transform) {
        auto& group = workload.drawData.transformGroups[0];
        group.matrixId = transform == 0 ? G_EX_ID_IGNORE : transform == 1 ? G_EX_ID_AUTO : 7U;
        group.ordering = transform == 3 ? G_EX_ORDER_LINEAR : G_EX_ORDER_AUTO;
        // RT64 currently matches texture generation even when this flag says
        // Skip. Preserve that behavior until a separate change qualifies it.
        group.lookAtInterpolation = G_EX_COMPONENT_SKIP;
        for (auto tile : tiles) for (auto geometry : modes) {
            group.tileInterpolation = tile;
            projection.gameCalls[0].callDesc.geometryMode = geometry;
            std::multimap<uint64_t, RT64::GameCallMap> map;
            frame.buildCallHashMap(3, workload, projection, map);
            const bool transforms = transform == 1 || transform == 2;
            const bool textureTiles = tile != G_EX_COMPONENT_SKIP;
            const bool lookAt = geometry == (G_LIGHTING | G_TEXTURE_GEN);
            check(map.size() == (transforms || textureTiles || lookAt ? 1U : 0U),
                  "only calls capable of contributing a match enter the map");
            if (!map.empty()) {
                const auto& item = map.begin()->second;
                check(item.sceneProjIndex == 3 && item.callIndex == 0, "retained source identity");
                check(static_cast<bool>(item.doTransformMatching) == transforms, "transform eligibility unchanged");
                check(static_cast<bool>(item.doTileInterpolation) == textureTiles, "tile eligibility unchanged");
                check(static_cast<bool>(item.doTileMatching) == (tile == G_EX_COMPONENT_AUTO), "tile matching unchanged");
            }
        }
    }
    auto& group = workload.drawData.transformGroups[0];
    group.matrixId = 7;
    group.ordering = G_EX_ORDER_LINEAR;
    group.tileInterpolation = G_EX_COMPONENT_SKIP;
    std::multimap<uint32_t,uint32_t> ids;
    std::vector<uint32_t> ignored;
    frame.buildTransformIdMap(workload, ids, ignored);
    check(ids.size() == 1 && ids.begin()->first == 7 && ids.begin()->second == 0,
          "explicit linear transform IDs still use their separate matching path");
    group.matrixId = G_EX_ID_IGNORE;
    projection.gameCalls[0].callDesc.geometryMode = 0;
    projection.gameCalls.resize(4096, projection.gameCalls[0]);
    projection.gameCallCount = 4096;
    std::multimap<uint64_t, RT64::GameCallMap> ignoredCalls;
    frame.buildCallHashMap(0, workload, projection, ignoredCalls);
    check(ignoredCalls.empty(), "4096 ignored calls cannot create 16777216 no-op pair visits");
    // A later matrix in a multi-matrix draw can still require tile matching.
    workload.drawData.transformGroups.push_back(group);
    workload.drawData.transformGroups[1].tileInterpolation = G_EX_COMPONENT_AUTO;
    workload.drawData.worldTransformGroups.push_back(1);
    projection.gameCalls.resize(1);
    projection.gameCallCount = 1;
    projection.gameCalls[0].callDesc.maxWorldMatrix = 1;
    ignoredCalls.clear();
    frame.buildCallHashMap(0, workload, projection, ignoredCalls);
    check(ignoredCalls.size() == 1 && ignoredCalls.begin()->second.doTileInterpolation,
          "all matrices in a draw contribute eligibility");
    std::printf("call matching regression failures: %u\n", failed);
    return failed ? 1 : 0;
}
