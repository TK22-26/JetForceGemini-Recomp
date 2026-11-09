#define SDL_MAIN_HANDLED
#include "rt64_f3ddkr.hpp"

#include "hle/rt64_application.h"
#include "hle/rt64_interpreter.h"

#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <memory>
#include <vector>

namespace {
void require(const bool condition, const char* message) {
    if (!condition) {
        std::fprintf(stderr, "%s\n", message);
        std::exit(1);
    }
}
void interrupt() {}

void check_depth_bounds(const bool rsp_updates_depth, const bool rdp_updates_depth) {
    // Execute real CPU command and triangle handlers with synthetic vertices.
    // The workload queue is never started; no window, GPU, ROM, or save is used.
    std::vector<std::uint8_t> rdram(8U * 1024U * 1024U);
    std::uint32_t mi_interrupt = 0U;
    RT64::Application::Core core{};
    core.RDRAM = rdram.data();
    core.MI_INTR_REG = &mi_interrupt;
    core.checkInterrupts = &interrupt;
    RT64::ApplicationConfiguration config{};
    config.detectDataPath = false;
    config.useConfigurationFile = false;
    RT64::Application application(core, config);
    application.state = std::make_unique<RT64::State>(
        rdram.data(), &mi_interrupt, &interrupt);
    application.interpreter = std::make_unique<RT64::Interpreter>();
    application.interpreter->setup(application.state.get());
    jfg::Rt64F3ddkr renderer(application);
    renderer.install();
    renderer.begin(rdram);

    auto queue = std::make_unique<RT64::WorkloadQueue>();
    RT64::EmulatorConfiguration emulator_config{};
    auto& state = *application.state;
    state.ext = {};
    state.ext.workloadQueue = queue.get();
    state.ext.emulatorConfig = &emulator_config;
    auto& rsp = *state.rsp;
    auto& rdp = *state.rdp;
    auto& workload = queue->workloads[queue->writeCursor];
    workload.addFramebufferPair(0x1000U, G_IM_FMT_RGBA, G_IM_SIZ_16b, 320U, 0x30000U);
    auto& pair = workload.fbPairs[workload.currentFramebufferPairIndex()];
    pair.changeProjection(0U, RT64::Projection::Type::Orthographic);
    rdp.colorImage.changed = false;
    rdp.depthImage.changed = false;
    rsp.viewportStack[0].scale = {160.0f, 120.0f, 1.0f};
    rsp.viewportStack[0].translate = {160.0f, 120.0f, 0.0f};
    rsp.geometryModeStack[0] = 0U;
    rdp.scissorRectStack[0] = {0, 0, 1280, 960};
    workload.drawData.worldIndices.assign(3U, 0U);
    workload.drawData.tcFloats.assign(6U, 0.0f);
    workload.drawData.posScreen = {
        {10.0f, 10.0f, 0.5f}, {30.0f, 10.0f, 0.5f}, {10.0f, 30.0f, 0.5f}};
    state.drawStatus.clearChanges();

    // RSP mode commands synchronize the two states; raw EF changes only RDP.
    // Reproduce both disagreement directions rather than copying a predicate.
    rsp.setOtherMode(0U, rsp_updates_depth ? Z_UPD : 0U);
    RT64::DisplayList command{};
    command.w0 = 0xEF00'0000U;
    command.w1 = rdp_updates_depth ? Z_UPD : 0U;
    RT64::DisplayList* cursor = &command;
    application.interpreter->hleGBI->map[0xEFU](&state, &cursor);
    require(renderer.complete(), "raw RDP mode command rejected");
    require(rsp.otherModeStack[0].zUpd() == rsp_updates_depth,
        "raw EF must preserve RSP mode state");
    require(rdp.otherMode.zUpd() == rdp_updates_depth,
        "raw EF must change effective RDP mode state");

    rsp.drawIndexedTri(0U, 1U, 2U, true);
    require(state.drawCall.triangleCount == 1U, "synthetic triangle must be drawn");
    require(state.drawCall.otherMode.zUpd() == rdp_updates_depth,
        "draw call must use the effective RDP mode");
    require(pair.drawColorRect.ulx == 40 && pair.drawColorRect.uly == 40 &&
        pair.drawColorRect.lrx == 120 && pair.drawColorRect.lry == 120,
        "synthetic triangle must have the expected visible bounds");
    if (rdp_updates_depth) {
        require(pair.drawDepthRect.ulx == 40 && pair.drawDepthRect.uly == 40 &&
            pair.drawDepthRect.lrx == 120 && pair.drawDepthRect.lry == 120,
            "RDP depth writes must contribute their visible bounds despite stale RSP mode");
    } else {
        require(pair.drawDepthRect.isNull(),
            "RDP-disabled depth writes must not use stale RSP depth-update bounds");
    }
}
}

int main() {
    check_depth_bounds(false, true);
    check_depth_bounds(true, false);
    check_depth_bounds(true, true);
    check_depth_bounds(false, false);
    std::puts("RDP mode controls triangle depth bounds in all four RSP/RDP combinations");
    return 0;
}
