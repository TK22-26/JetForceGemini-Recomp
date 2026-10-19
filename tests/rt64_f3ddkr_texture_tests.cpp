#define SDL_MAIN_HANDLED
#include "rt64_f3ddkr.hpp"

#include "hle/rt64_application.h"
#include "hle/rt64_interpreter.h"
#include "hle/rt64_workload_queue.h"

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

void shadow_vertex_reuse_case(bool flat_mask = false) {
    const bool interpolate = true;
    const std::uint32_t width = 64;
    std::vector<std::uint8_t> rdram(8U * 1024U * 1024U), guest(rdram.size());
    std::uint32_t mi_interrupt = 0;
    RT64::Application::Core core{};
    core.RDRAM = rdram.data();
    core.MI_INTR_REG = &mi_interrupt;
    core.checkInterrupts = &interrupt;
    RT64::ApplicationConfiguration config{};
    config.detectDataPath = false;
    config.useConfigurationFile = false;
    RT64::Application application(core, config);
    application.state =
        std::make_unique<RT64::State>(rdram.data(), &mi_interrupt, &interrupt);
    application.interpreter = std::make_unique<RT64::Interpreter>();
    application.interpreter->setup(application.state.get());
    application.workloadQueue = std::make_unique<RT64::WorkloadQueue>();
    RT64::EmulatorConfiguration emulator{};
    auto &state = *application.state;
    state.ext.workloadQueue = application.workloadQueue.get();
    state.ext.interpreter = application.interpreter.get();
    state.ext.emulatorConfig = &emulator;
    auto &workload = application.workloadQueue->workloads[0];
    workload.addFramebufferPair(0x10000, 0, 2, width, 0x20000);
    jfg::Rt64F3ddkr renderer(application, interpolate);
    renderer.install();
    renderer.begin(guest);
    const auto command = [&](std::uint32_t w0, std::uint32_t w1) {
        RT64::DisplayList dl{};
        dl.w0 = w0;
        dl.w1 = w1;
        auto *cursor = &dl;
        application.interpreter->hleGBI->map[w0 >> 24U](&state, &cursor);
    };
    const auto byte = [&](std::uint32_t at, std::uint8_t value) {
        guest[at ^ 3U] = value;
    };
    auto *matrix = reinterpret_cast<RT64::FixedMatrix *>(guest.data() + 0x1000);
    for (unsigned i = 0; i < 4; ++i)
        matrix->integer[i][i ^ 1U] = 1;
    command(0x01000040, 0x1000);
    command((flat_mask ? 0xFF880000 : 0xFF100000) | (width - 1), 0x10000);
    if (flat_mask) command(0xFCFFFFFF, 0xFFFDF6FB); // Primitive color and alpha.

    // This fixture owns a CPU framebuffer pair; no submission or GPU exists.
    state.rdp->colorImage.changed = state.rdp->depthImage.changed = false;
    for (unsigned i = 0; i < 3; ++i) {
        byte(0x2000 + i * 10 + 1, static_cast<std::uint8_t>(i == 1));
        byte(0x2000 + i * 10 + 3, static_cast<std::uint8_t>(i == 2));
        for (unsigned c = 6; c < 10; ++c)
            byte(0x2000 + i * 10 + c, 255);
    }
    command(0x04000000 | (3U << 19U), 0x2000);
    require(renderer.complete(), "visibility fixture vertex load failed");
    byte(0x3000, 0x40);
    byte(0x3001, 0);
    byte(0x3002, 1);
    byte(0x3003, 2);
    command(0x05000000, 0x3000);
    for (unsigned i = 0; i < 100; ++i) command(0x05000000, 0x3000);
    require(renderer.complete() && workload.drawData.faceIndices.size() == 303U,
            "identical offscreen UV commands must retain every triangle");
    require(workload.drawData.vertexCount() == 3U,
            "identical offscreen UVs must not clone used vertices");
    byte(0x3005, 32); // Change only the first corner's S to 1.0.
    command(0x05000000, 0x3000);
    if (flat_mask) {
        require(renderer.complete() && workload.drawData.vertexCount() == 3U,
                "flat I8 masks must not duplicate vertices for unused UVs");
        // Switching the same target to a textured combiner restores UV writes.
        command(0xFCFFFFFF, 0xFFFCF279); // Decal RGBA.
        command(0x05010000, 0x3000);
        require(renderer.complete() && workload.drawData.vertexCount() == 4U,
                "textured I8 draws must restore per-triangle UV ownership");
        require(workload.drawData.tcFloats[6] == 1.0f,
                "textured mask must use the requested texture coordinate");
        return;
    }
    require(renderer.complete() && workload.drawData.vertexCount() == 4U,
            "changed UV must clone a previously drawn vertex");
    require(workload.drawData.tcFloats[0] == 0.0f &&
            workload.drawData.tcFloats[6] == 1.0f,
            "new UV must not alter the earlier triangles");
    state.rsp->used[0] = true;
    workload.drawData.lookAtIndices[state.rsp->indices[0]] = 1;
    command(0x05000000, 0x3000);
    require(renderer.complete() && workload.drawData.vertexCount() == 5U,
            "disabling generated coordinates must still clone a used vertex");
}

void visibility_case(bool interpolate, std::uint32_t width) {
    std::vector<std::uint8_t> rdram(8U * 1024U * 1024U), guest(rdram.size());
    std::uint32_t mi_interrupt = 0;
    RT64::Application::Core core{};
    core.RDRAM = rdram.data();
    core.MI_INTR_REG = &mi_interrupt;
    core.checkInterrupts = &interrupt;
    RT64::ApplicationConfiguration config{};
    config.detectDataPath = false;
    config.useConfigurationFile = false;
    RT64::Application application(core, config);
    application.state =
        std::make_unique<RT64::State>(rdram.data(), &mi_interrupt, &interrupt);
    application.interpreter = std::make_unique<RT64::Interpreter>();
    application.interpreter->setup(application.state.get());
    application.workloadQueue = std::make_unique<RT64::WorkloadQueue>();
    RT64::EmulatorConfiguration emulator{};
    auto &state = *application.state;
    state.ext.workloadQueue = application.workloadQueue.get();
    state.ext.interpreter = application.interpreter.get();
    state.ext.emulatorConfig = &emulator;
    auto &workload = application.workloadQueue->workloads[0];
    workload.addFramebufferPair(0x10000, 0, 2, width, 0x20000);
    jfg::Rt64F3ddkr renderer(application, interpolate);
    renderer.install();
    renderer.begin(guest);
    const auto command = [&](std::uint32_t w0, std::uint32_t w1) {
        RT64::DisplayList dl{};
        dl.w0 = w0;
        dl.w1 = w1;
        auto *cursor = &dl;
        application.interpreter->hleGBI->map[w0 >> 24U](&state, &cursor);
    };
    const auto byte = [&](std::uint32_t at, std::uint8_t value) {
        guest[at ^ 3U] = value;
    };
    auto *matrix = reinterpret_cast<RT64::FixedMatrix *>(guest.data() + 0x1000);
    for (unsigned i = 0; i < 4; ++i)
        matrix->integer[i][i ^ 1U] = 1;
    command(0x01000040, 0x1000);
    command(0xFF100000 | (width - 1), 0x10000);
    // This fixture owns a CPU framebuffer pair; no submission or GPU exists.
    state.rdp->colorImage.changed = state.rdp->depthImage.changed = false;
    for (unsigned i = 0; i < 3; ++i) {
        byte(0x2000 + i * 10 + 1,
             3); // All x=3, beyond the current camera's x/w=1 plane.
        byte(0x2000 + i * 10 + 3, static_cast<std::uint8_t>(i));
        for (unsigned c = 6; c < 10; ++c)
            byte(0x2000 + i * 10 + c, 255);
    }
    command(0x04000000 | (3U << 19U), 0x2000);
    require(renderer.complete(), "visibility fixture vertex load failed");
    require(workload.drawData.posTransformed.size() == 3 &&
                workload.drawData.posTransformed[0].x >
                    workload.drawData.posTransformed[0].w,
            "fixture must be outside the current camera");
    byte(0x3000, 0x40);
    byte(0x3001, 0);
    byte(0x3002, 1);
    byte(0x3003, 2);
    command(0x05000000, 0x3000);
    const bool retained = interpolate && width >= 320;
    require(renderer.complete(), "visibility triangle rejected");
    require(workload.drawData.faceIndices.size() == (retained ? 3U : 0U),
            "interpolated main-scene triangles must survive current-camera "
            "clipping");
    RT64::DisplayList caller{};
    state.returnAddressStack.push_back(&caller);
    command(0xBE000000, 3U * 40U);
    require(renderer.complete() && state.returnAddressStack.empty() != retained,
            "display-list culling must follow presentation eligibility");
    // Keeping geometry must never bypass validation of an unloaded vertex.
    command(0xBE000000, 4U * 40U);
    require(!renderer.complete(),
            "interpolation must reject unloaded cull vertices");
}
}

int main() {
    shadow_vertex_reuse_case();
    shadow_vertex_reuse_case(true);
    visibility_case(false, 320);
    visibility_case(true, 320);
    visibility_case(true, 16);
    // Construct only the CPU command state: no window, GPU, ROM, or user files.
    std::vector<std::uint8_t> rdram(8U * 1024U * 1024U);
    std::vector<std::uint8_t> guest(rdram.size());
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
    renderer.begin(guest);
    const auto command = [&](const std::uint32_t w0, const std::uint32_t w1) {
        RT64::DisplayList dl{};
        dl.w0 = w0;
        dl.w1 = w1;
        RT64::DisplayList* cursor = &dl;
        application.interpreter->hleGBI->map[w0 >> 24U](
            application.state.get(), &cursor);
        require(renderer.complete(), "F3DDKR command rejected");
    };
    constexpr std::uint32_t texture = 0x0002'0000U;
    // Two independent guest offset tables in the renderer's word-swapped
    // snapshot layout, containing shifts 0x100 and 0x200.
    guest[0x1000U ^ 3U] = 1U;
    guest[0x3000U ^ 3U] = 2U;
    command(0x0200'0010U, 0x1000U);
    command(0xFD10'0000U, texture);
    require(application.state->rdp->texture.address == texture + 0x100U,
        "first table must affect RGBA texture addressing");

    // The original microcode's BF handler disables texture offsets, even if
    // no LoadBlock has advanced the cursor. The next model uses its own address.
    command(0xBF00'0040U, 0x80U);
    command(0xFD10'0000U, texture);
    require(application.state->rdp->texture.address == texture,
        "DMA offsets must stop the previous model's texture shift");

    command(0x0200'0010U, 0x3000U);
    command(0xFD10'0000U, texture);
    require(application.state->rdp->texture.address == texture + 0x200U,
        "a new table must re-enable offsets after BF");

    // Also reset a table before its first texture command, then repeat BF.
    command(0x0200'0010U, 0x1000U);
    command(0xBF00'0080U, 0x100U);
    command(0xBF00'0100U, 0x200U);
    command(0xFD10'0000U, texture);
    require(application.state->rdp->texture.address == texture,
        "BF must clear an unused table and remain idempotent");
    command(0x0200'0010U, 0x1000U);
    command(0xFD10'0000U, texture);
    require(application.state->rdp->texture.address == texture + 0x100U,
        "later model must retain explicitly re-enabled texture offsets");
    return 0;
}
