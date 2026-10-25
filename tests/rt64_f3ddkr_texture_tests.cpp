#define SDL_MAIN_HANDLED
#include "rt64_f3ddkr.hpp"
#include "jfg/renderer/presentation_identity.hpp"
#include "jfg/renderer/actor_lod_presentation.hpp"

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

void player_coverage_case(bool interpolate, std::uint32_t width, bool owner_matches) {
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
    auto identities=std::make_shared<jfg::PresentationSceneIdentity>();
    identities->models.push_back({1U,0x80005000U,0x6000U,0x7000U,{0x1000U,0},0x2000U,3U,1U});
    identities->camera_fades.push_back({owner_matches?0x80005000U:0x80005004U,0.75F});
    renderer.begin(guest,1U,identities);
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
    const float expected=width>=320U && owner_matches ? 0.75F:0.0F;
    require(state.drawCall.rdpParams.cameraFade.x==expected,
            "Only the proven player in a scene target receives close-camera coverage");
    require(state.drawCall.rdpParams.cameraFade.y==(expected>0.0F?0x5000U:0U),
            "Player layer identity must use the proven actor, including Original mode");
    require(state.rdp->jfgCameraFade==0.0F && state.rdp->jfgCameraFadeActor==0U,
            "Player coverage must not leak past a triangle batch");
    // Force UV cloning after submission. Ownership must survive in both
    // Original and interpolated presentation modes.
    byte(0x3005,32);
    command(0x05000000,0x3000);
    require(renderer.complete() && workload.drawData.vertexCount()>3U,
            "Coverage fixture must exercise cloned vertices");
    require(state.drawCall.rdpParams.cameraFade.x==expected &&
            state.drawCall.rdpParams.cameraFade.y==(expected>0.0F?0x5000U:0U),
            "UV-cloned player triangles must retain opacity and actor identity");
    // Reload the same vertices using a matrix outside the player's palette.
    // Screen proximity must never fade unrelated geometry.
    auto* other=reinterpret_cast<RT64::FixedMatrix*>(guest.data()+0x1100);
    for(unsigned i=0;i<4;++i)other->integer[i][i^1U]=1;
    command(0x01000040,0x1100);
    command(0x04000000 | (3U<<19U),0x2000);
    command(0x05000000,0x3000);
    require(renderer.complete() && state.drawCall.rdpParams.cameraFade.x==0.0F,
            "Unowned triangles must restore unmodified native rendering");
}

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

    {
      std::vector<std::uint8_t> bytes(4U*1024U*1024U);
      const auto word=[&](unsigned at,std::uint32_t value){std::memcpy(bytes.data()+(at&0x1fffffffU),&value,4);};
      const auto byte=[&](unsigned at,std::uint8_t value){bytes[(at&0x1fffffffU)^3U]=value;};
      word(0x8000CC64,0x27BDFEE0);word(0x8000D3B8,0x90420A20);
      word(0x8000D3D8,0xC5F000CC);word(0x8000D434,0x00827021);
      const unsigned actor=0x80100000,header=0x80101000,models=0x80102000,instance=0x80103000;
      word(actor+0x40,header);word(actor+0x6c,models);
      byte(header+0x1f,4);byte(actor+0x3a,2);
      word(models+8,instance);word(instance,0x80104000);
      word(header+0xcc,std::bit_cast<std::uint32_t>(500.0f));byte(0x800A0A20,1);
      const auto original=bytes;
      {jfg::ActorLodPresentationScope scope(bytes,0x8000CC64,actor,false);require(!scope.applied()&&bytes==original,"Original LOD changes no guest bytes");}
      {
        jfg::ActorLodPresentationScope scope(bytes,0x8000CC64,actor,true);
        const jfg::PresentationGuestView ram(bytes);
        require(scope.applied()&&ram.u32(header+0xcc)==0&&ram.u8(0x800A0A20)==0,"High disables distance and global detail reduction");
        require(ram.u8(actor+0x3a)==2&&ram.u32(models+8)==instance,"High preserves authored model variant");
        {jfg::ActorLodPresentationScope nested(bytes,0x8000CC64,actor,true);}
        require(ram.u32(header+0xcc)==0,"nested scope retains outer selection");
      }
      require(bytes==original,"High restores every guest byte after drawing");
      // The sky allocation is deliberately absent from the ordinary actor list.
      word(0x800F2CA4,0x80105000);word(0x800F2CA8,0);
      word(0x800F2F88,actor);word(0x800FB114,365);
      word(0x800FA634,0);word(0x800FA630,0);
      const std::array<float,16> identity{1,0,0,0,0,1,0,0,0,0,1,0,0,0,0,1};
      for(unsigned i=0;i<16;++i) {
        word(0x800FAAB0+i*4,std::bit_cast<std::uint32_t>(identity[i]));
        word(0x800FAF78+i*4,std::bit_cast<std::uint32_t>(identity[i]));
        word(0x800FAA70+i*4,std::bit_cast<std::uint32_t>(identity[i]));
      }
      jfg::PresentationIdentityTracker tracker;
      tracker.rigid(bytes,0x80106000,actor,10);
      const auto sky=tracker.capture(bytes,10);
      require(sky.cameras.size()==1&&sky.models.empty(),"separately allocated sky owns camera without joining gameplay actors");
      require(sky.cameras[0].motion_pose&&sky.cameras[0].motion_pose->view==identity&&sky.cameras[0].motion_pose->world==identity,"sky view folds the exact model transform");
      const auto generation=sky.cameras[0].generation;
      tracker.rigid(bytes,0x80106000,actor,12);
      require(tracker.capture(bytes,12).cameras[0].generation==generation,"sky identity survives buffer reuse");
      word(0x80106000,42);
      require(tracker.capture(bytes,12).cameras.empty(),"overwritten sky matrix is rejected");
      tracker.rigid(bytes,0x80106000,actor,14);
      tracker.retire(actor);
      require(tracker.capture(bytes,14).cameras.empty(),"retired sky cannot reuse an emitted endpoint");
      word(0x8000D434,0);
      const auto wrong=bytes;
      {jfg::ActorLodPresentationScope scope(bytes,0x8000CC64,actor,true);require(!scope.applied()&&bytes==wrong,"unknown native selector is untouched");}
      word(0x8000D434,0x00827021);byte(actor+0x3a,4);
      {jfg::ActorLodPresentationScope scope(bytes,0x8000CC64,actor,true);require(!scope.applied(),"invalid base model fails closed");}
    }

    player_coverage_case(false,320,true);
    player_coverage_case(true,320,true);
    player_coverage_case(false,320,false);
    player_coverage_case(true,64,true);
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
