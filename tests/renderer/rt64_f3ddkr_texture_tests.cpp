#include "renderer_game_fixture.hpp"
#define SDL_MAIN_HANDLED
#include "rt64_f3ddkr.hpp"
#include "enhanced_shadow_collect.hpp"
#include "jfg/renderer/enhanced_shadow_caster.hpp"
#include "jfg/renderer/presentation_identity.hpp"
#include "jfg/renderer/level_solid_core.hpp"
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

void enhanced_shadow_collection_case() {
    RT64::Workload work;
    work.fbPairCount=1;work.fbPairs.resize(1);
    auto& pair=work.fbPairs[0];pair.colorImage.width=320;pair.colorImage.siz=G_IM_SIZ_16b;
    pair.projectionCount=1;pair.projections.resize(1);
    auto& projection=pair.projections[0];projection.type=RT64::Projection::Type::Perspective;
    projection.gameCallCount=2;projection.gameCalls.resize(2);
    projection.gameCalls[0].callDesc.triangleCount=1;
    auto& call=projection.gameCalls[1];
    call.meshDesc.faceIndicesStart=999; // Not finalized at collection time.
    call.callDesc.triangleCount=1;call.callDesc.rdpParams.primColor.w=0.8f;
    work.drawData.faceIndices={0,1,2,3,4,5};
    std::vector<jfg::SemanticPresentationSample> samples(6);
    std::vector<jfg::SemanticPresentationPrevious> previous(6);
    for(unsigned i=0;i<6;++i) {
        auto& v=samples[i];v.valid=true;
        v.key={4,(std::uint64_t(0x80005000U)<<32U)|0x1000U,0x2000U,9,i<3?0:0x53484144U,i};
        v.world={float(i%3)*10.0f,i<3?25.0f:1.0f,float(i%2)*10.0f};
        previous[i].world=v.world;previous[i].world[0]-=2;previous[i].matched=true;
    }
    auto frame=jfg::collect_enhanced_shadows(work,samples,previous);
    require(frame&&frame->unresolved_draws==0&&frame->actors.size()==1&&frame->draws.size()==1,
            "complete caster/receiver geometry must form one enhanced shadow");
    require(frame->vertices[0].previous[0]==-2&&frame->actors[0].caster_count==3&&frame->vertices.size()==9,
            "shadow geometry must retain actual presentation pose endpoints");
    require(frame->actors[0].bounds[2]>=128&&frame->draws[0].first_index==3,
            "shadow map bounds and native receiver draw association missing");
    require(frame->actors[0].receiver_count==3 &&
            frame->vertices[frame->actors[0].receiver_start].current==frame->vertices[3].current &&
            frame->vertices[frame->actors[0].receiver_start].previous==frame->vertices[3].previous,
            "receiver visibility must use the physical triangle at both presentation endpoints");
    samples[3].shadow_lift=1;previous[3].shadow_lift=2;
    frame=jfg::collect_enhanced_shadows(work,samples,previous);
    require(frame->vertices[3].current[1]==0 && frame->vertices[3].previous[1]==-1,
            "height comparison must use each endpoint's physical floor, not its depth lift");
    const auto bounds=frame->actors[0].bounds;
    samples[0].world[0]+=0.01f;
    frame=jfg::collect_enhanced_shadows(work,samples,previous);
    require(frame&&frame->actors[0].bounds==bounds,"small idle changes must not resize the shadow map");
    auto native_receivers=std::vector<jfg::EnhancedShadowReceiver>(samples.size());
    for(unsigned i=3;i<6;++i)native_receivers[i]={0x80005000U,samples[i].world,1.0f,true};
    const auto saved_samples=samples;
    work.drawData.viewProjIndices.assign(samples.size(),0U);
    for(unsigned i=3;i<6;++i)samples[i]={}; // A camera cut has no old receiver history.
    frame=jfg::collect_enhanced_shadows(work,samples,previous,native_receivers);
    require(frame&&frame->unresolved_draws==0&&frame->draws.size()==1,
            "producer-owned floor geometry must survive unavailable camera history");
    native_receivers[4].valid=false;
    frame=jfg::collect_enhanced_shadows(work,samples,previous,native_receivers);
    require(frame&&frame->unresolved_draws==1,
            "unproved floor geometry blocks qualification rather than using a native shadow");
    samples=saved_samples;work.drawData.viewProjIndices.clear();
    call.callDesc.rdpParams.primColor.w=0;
    frame=jfg::collect_enhanced_shadows(work,samples,previous);
    require(frame&&frame->draws.size()==1&&frame->vertices.back().opacity==0,
            "zero-opacity enhanced receivers still replace the native draw");
    call.callDesc.rdpParams.primColor.w=0.8f;
    const auto north=jfg::shadow_light_shear(0,0x2000);
    const auto east=jfg::shadow_light_shear(0x4000,0x2000);
    const auto overhead=jfg::shadow_light_shear(0,0x4000);
    const auto horizon=jfg::shadow_light_shear(0,0);
    require(std::abs(north[0])<0.001f&&std::abs(north[1]-1)<0.001f&&
            std::abs(east[0]-1)<0.001f&&std::abs(east[1])<0.001f&&
            std::abs(overhead[0])+std::abs(overhead[1])<0.001f&&horizon[1]==2,
            "authored light yaw/elevation must produce a bounded downward projection");
    for(unsigned i=3;i<6;++i) {
        native_receivers[i].valid=true;native_receivers[i].projection=33;
        native_receivers[i].light=north;native_receivers[i].opacity=0.6f;
        previous[i].shadow_light=east;previous[i].shadow_opacity=0.2f;
    }
    frame=jfg::collect_enhanced_shadows(work,samples,previous,native_receivers);
    require(frame&&frame->actors.size()==1&&frame->actors[0].projection==33&&
            frame->actors[0].light[1]==north[1]&&frame->actors[0].light[2]==east[0],
            "shadow maps must retain both light direction endpoints");
    require(std::abs(frame->vertices.back().opacity-0.48f)<0.0001f&&
            std::abs(frame->vertices.back().previous_opacity-0.16f)<0.0001f,
            "authored shadow fading must interpolate with the geometry");
    samples[0].key[0]|=1ULL<<63U;
    frame=jfg::collect_enhanced_shadows(work,samples,previous);
    require(frame&&frame->unresolved_draws==1&&frame->draws.empty(),
            "a reflected actor cannot silently substitute for missing caster geometry");
    samples[0].key[0]=4;samples[1].key[3]=10;
    frame=jfg::collect_enhanced_shadows(work,samples,previous);
    require(frame&&frame->unresolved_draws==1,"caster geometry from different views must be rejected");
    samples[1].key[3]=9;samples[4].key[1]=0;
    frame=jfg::collect_enhanced_shadows(work,samples,previous);
    require(frame&&frame->unresolved_draws==1,"mixed receiver ownership is a blocker, never a legacy fallback");
    // The shadow pass consumes the original palette pose even when the only
    // visible actor draw is its reflection, or a camera has no history.
    samples=saved_samples;
    auto canonical=saved_samples;
    for(unsigned i=3;i<6;++i)canonical[i]={};
    work.drawData.viewProjIndices={7,7,7,3,3,3};
    for(unsigned i=0;i<3;++i) {
        samples[i].key[0]|=1ULL<<63U;
        samples[i].world[1]=-25.0f;
        samples[i].key[3]=0; // No normal view/camera lifetime is required.
    }
    frame=jfg::collect_enhanced_shadows(work,samples,previous,native_receivers,canonical,previous);
    require(frame&&frame->unresolved_draws==0&&frame->actors.size()==1&&
            frame->vertices[0].current[1]==25.0f&&frame->vertices[0].previous[0]==-2,
            "canonical caster pose must stay unmirrored and independent of the visible camera");
    canonical[0].valid=false;
    frame=jfg::collect_enhanced_shadows(work,samples,previous,native_receivers,canonical,previous);
    require(frame&&frame->unresolved_draws==1,
            "invalid canonical geometry remains a blocker, never native-mask fallback");
    work.drawData.viewProjIndices.clear();
    // A deliberately sprite-authored object must not depend on an unrelated
    // model or the old native shadow image. A missing mesh stays an error.
    jfg::EnhancedShadowProxy proxy;
    proxy.actor=0x80005000U;proxy.lifetime=4;proxy.projection=33;
    proxy.current={0,30,0,16};proxy.previous={-2,30,0,16};
    proxy.vertical=proxy.previous_vertical=12;proxy.valid=true;
    for(auto& q:canonical)q={};
    frame=jfg::collect_enhanced_shadows(work,samples,previous,native_receivers,canonical,previous,
        std::span<const jfg::EnhancedShadowProxy>(&proxy,1));
    require(frame&&frame->unresolved_draws==0&&frame->actors.size()==1&&
            frame->actors[0].proxy&&frame->actors[0].caster_count==0&&
            frame->actors[0].proxy->previous[0]==-2,
            "sprite-authored caster needs analytic volume with both pose endpoints");
    proxy.valid=false;
    frame=jfg::collect_enhanced_shadows(work,samples,previous,native_receivers,canonical,previous,
        std::span<const jfg::EnhancedShadowProxy>(&proxy,1));
    require(frame&&frame->unresolved_draws==1,
            "invalid sprite volume must not become a substitute mesh or native shadow");
    frame=jfg::collect_enhanced_shadows(work,samples,previous,native_receivers,canonical,previous);
    require(frame&&frame->unresolved_draws==1,
            "unclassified missing casters must never silently become blob shadows");

    jfg::PresentationModelIdentity model{4,0x80005000U,0x1000,0x2000,{0x3000,0x4000},0x5000,3,1};
    jfg::PresentationVertexIdentity identity;
    identity.owner=identity.geometry=&model;identity.joint=0;identity.vertex=1;
    jfg::PresentationMatrix palette{1,0,0,0,0,1,0,0,0,0,1,0,10,20,30,1};
    const auto caster=jfg::enhanced_shadow_caster(identity,palette,{1,2,3});
    require(caster.valid&&caster.key[0]==4&&caster.key[3]==1&&
            caster.world==std::array<float,3>{11,22,33},
            "caster must use the live model's original palette matrix");
    jfg::PresentationSceneIdentity rigid_scene;
    rigid_scene.models.push_back(model);
    jfg::PresentationRigidIdentity rigid;
    rigid.actor=model.actor;rigid.lifetime=model.lifetime;rigid.camera=3;
    rigid.pose.world=palette;
    rigid.pose.view={1,0,0,0,0,1,0,0,0,0,1,0,0,0,0,1};
    rigid.pose.projection={1,0,0,0,0,1,0,0,0,0,1,1,0,0,0,0};
    jfg::PresentationMatrix combined={1,0,0,0,0,1,0,0,0,0,1,1,10,20,30,30};
    const auto rigid_caster=jfg::enhanced_shadow_rigid_caster(rigid_scene,rigid,0x500a,combined,{1,2,3});
    require(rigid_caster.valid&&rigid_caster.world==caster.world&&
            rigid_caster.key[4]==1023&&rigid_caster.key[5]==1,
            "rigid pickups need their verified world pose without a bone palette");
    combined[12]+=1;
    require(!jfg::enhanced_shadow_rigid_caster(rigid_scene,rigid,0x500a,combined,{1,2,3}).valid,
            "reused rigid matrix must not claim another model's shadow");
    combined[12]-=1;
    require(!jfg::enhanced_shadow_rigid_caster(rigid_scene,rigid,0x5020,combined,{1,2,3}).valid,
            "out-of-allocation rigid vertices must not become shadow casters");
    rigid_scene.models.clear();
    rigid_scene.limbs.push_back({4,model.actor,0x6000,0x7000,0x8000,{{0x8000,3},{0x8100,2}}});
    const auto limb_caster=jfg::enhanced_shadow_rigid_caster(rigid_scene,rigid,0x810a,combined,{1,2,3});
    require(limb_caster.valid&&limb_caster.world==caster.world&&limb_caster.key[4]==1022,
            "detached body geometry needs a world-space mesh caster");
    require(!jfg::enhanced_shadow_rigid_caster(rigid_scene,rigid,0x8020,combined,{1,2,3}).valid,
            "gaps outside proven limb DMA ranges are not caster vertices");
    rigid_scene.limbs[0].lifetime=5;
    require(!jfg::enhanced_shadow_rigid_caster(rigid_scene,rigid,0x810a,combined,{1,2,3}).valid,
            "recycled limb allocations must not retain caster ownership");
    rigid_scene.limbs[0].lifetime=4;rigid_scene.limbs.push_back(rigid_scene.limbs[0]);
    require(!jfg::enhanced_shadow_rigid_caster(rigid_scene,rigid,0x810a,combined,{1,2,3}).valid,
            "ambiguous limb provenance must be rejected");
    jfg::SemanticPresentationHistory history;
    const auto reference=jfg::enhanced_shadow_world_frame();
    const std::vector<jfg::SemanticPresentationSample> pose{caster};
    history.record(pose,100,true,true,nullptr,nullptr,&reference);
    const auto next=history.record(pose,102,true,true,nullptr,nullptr,&reference);
    require(next.size()==1&&next[0].matched&&next[0].world==caster.world,
            "canonical shadow history must continue without a rendered camera");
    // Two authored lights share the caster mesh, but never share a height map
    // or silently replace one another through an actor-only key.
    samples=saved_samples;samples.resize(9);previous.resize(9);native_receivers.resize(9);
    projection.gameCallCount=3;projection.gameCalls.resize(3);
    projection.gameCalls[2].callDesc.triangleCount=1;
    projection.gameCalls[2].callDesc.rdpParams.primColor.w=0.8f;
    for(unsigned i=0;i<3;++i) {
        samples[6+i]=samples[3+i];samples[6+i].key[5]+=3;
        previous[6+i]=previous[3+i];
        native_receivers[6+i]=native_receivers[3+i];
        native_receivers[6+i].projection=55;native_receivers[6+i].light=east;
        native_receivers[6+i].world[1]+=40;
        work.drawData.faceIndices.push_back(6+i);
    }
    frame=jfg::collect_enhanced_shadows(work,samples,previous,native_receivers);
    require(frame&&frame->unresolved_draws==0&&frame->actors.size()==2&&frame->draws.size()==2&&
            frame->draws[0].actor_index!=frame->draws[1].actor_index,
            "distinct authored lights must keep separate complete shadow maps");
    require(frame->actors[0].caster_count==3&&frame->actors[1].caster_count==3,
            "every light must receive the complete caster mesh");
    for(const auto& draw:frame->draws) {
        const auto& actor=frame->actors[draw.actor_index];
        require(actor.receiver_count==3 &&
                frame->vertices[actor.receiver_start].current==
                    frame->vertices[draw.receiver_start].current,
                "receiver occlusion must not leak across independently authored lights");
    }
}


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
    jfg::Rt64F3ddkr renderer(application, interpolate, jfg::test::renderer_layout);
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

void menu_icon_alpha_case(bool flip,bool qualifying) {
    const bool interpolate=false;const std::uint32_t width=320;
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
    state.ext.enhancementConfig=&application.enhancementConfig;
    state.ext.userConfig=&application.userConfig;
    auto &workload = application.workloadQueue->workloads[0];
    workload.addFramebufferPair(0x10000, 0, 2, width, 0x20000);
    jfg::Rt64F3ddkr renderer(application, interpolate, jfg::test::renderer_layout);
    renderer.install();
    renderer.begin(guest);
    const auto command = [&](std::uint32_t w0, std::uint32_t w1) {
        RT64::DisplayList dl{};
        dl.w0 = w0;
        dl.w1 = w1;
        auto *cursor = &dl;
        application.interpreter->hleGBI->map[w0 >> 24U](&state, &cursor);
    };

    command(0xFF10013F,0x10000);
    state.rdp->colorImage.changed=state.rdp->depthImage.changed=false;
    command(0xED000000,0x005003C0);
    command(0xEF000000,0x00552048);
    command(0xFC119623,0xFF2FFFFF);
    state.rdp->setTile(0,G_IM_FMT_RGBA,G_IM_SIZ_16b,11,0,0,2,2,0,0,0,0);
    state.rdp->setTileSize(0,0,0,qualifying?172:168,172);
    state.rdp->setBlendColor(0x11223380);
    const auto old=state.rdp->blendColorStack[state.rdp->blendColorStackSize-1];
    RT64::DisplayList list[3]{};
    list[0].w0=(flip?0xE5000000U:0xE4000000U)|0x000B00B0U;
    list[0].w1=0;list[1].w0=0xB3000000;list[1].w1=0;
    list[2].w0=0xB2000000;list[2].w1=0x03000400;
    auto* cursor=list;
    application.interpreter->hleGBI->map[flip?0xE5:0xE4](&state,&cursor);
    require(cursor==list+2,"icon wrapper must retain native texrect command advancement");
    require((state.drawCall.otherMode.L&3U)==(qualifying?1U:0U),"only exact native widescreen icon material receives alpha test");
    if(qualifying)require(std::abs(state.drawCall.rdpParams.blendColor.w-1.0f/255.0f)<0.0001f,"cutout owns a nonzero threshold independent of previous draws");
    require(state.rdp->otherMode.L==0x00552048U &&
        state.rdp->blendColorStack[state.rdp->blendColorStackSize-1].w==old.w,
        "icon alpha mode and threshold must not leak to later rendering");
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
    jfg::Rt64F3ddkr renderer(application, interpolate, jfg::test::renderer_layout);
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

void reflection_culling_case(bool interpolate, std::uint32_t width) {
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
    jfg::Rt64F3ddkr renderer(application, interpolate, jfg::test::renderer_layout);
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
    state.rdp->colorImage.changed = state.rdp->depthImage.changed = false;
    for (unsigned i = 0; i < 3; ++i)
        for (unsigned c = 6; c < 10; ++c)
            byte(0x2000 + i * 10 + c, 255);
    command(0x04000000 | (3U << 19U), 0x2000);
    byte(0x3001, 0); byte(0x3002, 1); byte(0x3003, 2);
    const auto culling = [&]() {
        return state.rsp->geometryModeStack[state.rsp->geometryModeStackSize - 1] &
            state.rsp->cullBothMask;
    };
    auto &viewport = state.rsp->viewportStack[state.rsp->viewportStackSize - 1];
    viewport.scale.x = 160.0F;
    command(0x05000000, 0x3000);
    require(culling() == 0x2000, "normal model must cull back faces");
    // realReflectPrint brackets mirrored geometry with these native commands.
    command(0xB7000000, 0x1000);
    command(0x05000000, 0x3000);
    require(culling() == 0x1000, "mirrored model must preserve native front-face culling");
    byte(0x3000, 0x40);
    command(0x05000000, 0x3000);
    require(culling() == 0, "native double-sided faces remain double-sided in reflections");
    byte(0x3000, 0);
    command(0x05000000, 0x3000);
    require(culling() == 0x1000, "double-sided triangles must not erase the native reflection mode");
    viewport.scale.x = -160.0F;
    command(0x05000000, 0x3000);
    require(culling() == 0x2000, "negative viewport and mirrored model reversals must cancel");
    command(0xB6000000, 0x1000);
    command(0x05000000, 0x3000);
    require(culling() == 0x1000, "negative viewport alone reverses culling");
    viewport.scale.x = 160.0F;
    command(0x05000000, 0x3000);
    require(culling() == 0x2000, "reflection end restores ordinary model culling");
    require(renderer.complete(), "reflection culling fixture failed");
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
    jfg::Rt64F3ddkr renderer(application, interpolate, jfg::test::renderer_layout);
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


void level_solid_core_case() {
    std::vector<std::uint8_t> bytes(4U*1024U*1024U);
    const auto put8=[&](unsigned a,unsigned v){bytes[(a&0x3FFFFFU)^3U]=static_cast<std::uint8_t>(v);};
    const auto put16=[&](unsigned a,unsigned v){put8(a,v>>8);put8(a+1,v);};
    const auto put32=[&](unsigned a,unsigned v){put16(a,v>>16);put16(a+2,v);};
    put32(0x800A0D60U,0x80001000U);
    put32(0x1000,0x80002000);put32(0x1004,0x80003000);
    put16(0x1018,1);put16(0x101A,1);
    put32(0x2000,0x80004000);put8(0x4000,2);put8(0x4001,2);put16(0x4006,4);
    put32(0x3004,0x80005000);put32(0x300C,0x80006000);
    put16(0x3026,2);put16(0x3028,1);put16(0x6018,2);put32(0x600C,8);
    jfg::PresentationGuestView ram(bytes);
    require(jfg::level_solid_core_ranges(jfg::test::renderer_layout,ram).empty(),"Fully translucent material must not gain solid depth");
    put8(0x4023,255);
    auto ranges=jfg::level_solid_core_ranges(jfg::test::renderer_layout,ram);
    require(ranges.size()==1&&jfg::level_solid_core_batch(ranges,0x5000,2),"Opaque alpha must bind to its actual level faces");
    require(!jfg::level_solid_core_batch(ranges,0x5000,3)&&
            !jfg::level_solid_core_batch(ranges,0x5001,1)&&
            !jfg::level_solid_core_batch(ranges,0x5020,1),
            "Unrelated/cross-boundary actor geometry must not receive material override");
    put32(0x600C,0);
    require(jfg::level_solid_core_ranges(jfg::test::renderer_layout,ram).empty(),"Opaque native batches must remain untouched");
    put32(0x600C,8);put16(0x6018,3);
    require(jfg::level_solid_core_ranges(jfg::test::renderer_layout,ram).empty(),"Invalid level material range must fail closed");
    put32(0x1004,0x803FFFF0);
    require(jfg::level_solid_core_ranges(jfg::test::renderer_layout,ram).empty(),"Stale level pointer must be rejected");
}


void level_solid_core_draw_case() {
    std::vector<std::uint8_t> rdram(8U*1024U*1024U),guest(rdram.size());
    const auto byte=[&](unsigned a,unsigned v){guest[(a&0x7FFFFFU)^3U]=static_cast<std::uint8_t>(v);};
    const auto half=[&](unsigned a,unsigned v){byte(a,v>>8);byte(a+1,v);};
    const auto word=[&](unsigned a,unsigned v){half(a,v>>16);half(a+2,v);};
    word(0xA0D60,0x80004000);word(0x4000,0x80005000);word(0x4004,0x80006000);
    half(0x4018,1);half(0x401A,1);word(0x5000,0x80007000);
    byte(0x7000,2);byte(0x7001,2);half(0x7006,4);byte(0x7023,255);
    word(0x6004,0x80003000);word(0x600C,0x80008000);
    half(0x6026,2);half(0x6028,1);half(0x8018,2);word(0x800C,8);
    std::uint32_t mi=0;
    RT64::Application::Core core{};core.RDRAM=rdram.data();core.MI_INTR_REG=&mi;core.checkInterrupts=&interrupt;
    RT64::ApplicationConfiguration config{};config.detectDataPath=false;config.useConfigurationFile=false;
    RT64::Application app(core,config);
    app.state=std::make_unique<RT64::State>(rdram.data(),&mi,&interrupt);
    app.interpreter=std::make_unique<RT64::Interpreter>();app.interpreter->setup(app.state.get());
    app.workloadQueue=std::make_unique<RT64::WorkloadQueue>();
    RT64::EmulatorConfiguration emulator{};
    auto& state=*app.state;state.ext.workloadQueue=app.workloadQueue.get();
    state.ext.interpreter=app.interpreter.get();state.ext.emulatorConfig=&emulator;
    auto& work=app.workloadQueue->workloads[0];work.addFramebufferPair(0x10000,0,2,320,0x20000);
    // These synthetic guest addresses use the fixture's qualified USA layout.
    // An absent layout intentionally disables guest-dependent production policies.
    jfg::Rt64F3ddkr renderer(app, false, jfg::test::renderer_layout);renderer.install();renderer.begin(guest);
    const auto command=[&](unsigned x,unsigned y){
        RT64::DisplayList dl{};dl.w0=x;dl.w1=y;auto* cursor=&dl;
        app.interpreter->hleGBI->map[x>>24](&state,&cursor);
    };
    auto* matrix=reinterpret_cast<RT64::FixedMatrix*>(guest.data()+0x1000);
    for(unsigned i=0;i<4;++i)matrix->integer[i][i^1]=1;
    command(0x01000040,0x1000);command(0xFF10013F,0x10000);
    state.rdp->colorImage.changed=state.rdp->depthImage.changed=false;
    for(unsigned i=0;i<3;++i)for(unsigned c=6;c<10;++c)byte(0x2000+i*10+c,255);
    command(0x04180000,0x2000);byte(0x3001,0);byte(0x3002,1);byte(0x3003,2);
    byte(0x3101,0);byte(0x3102,1);byte(0x3103,2);
    command(4229043715U,0xFFFFFFF8U);command(0xEF182C0F,0xC8104A50U);
    command(0xF9000000,0x11223344U);
    const auto oldRspMode=state.rsp->otherModeStack[state.rsp->otherModeStackSize-1];
    const auto oldBlend=state.rdp->blendColorStack[state.rdp->blendColorStackSize-1];
    command(0x05010000,0x3100);
    require(work.drawData.faceIndices.size()==3,"Unowned geometry sharing foliage mode must stay a single draw");
    command(0x05010000,0x3000);
    require(renderer.complete()&&work.drawData.faceIndices.size()==9,
            "Owned blended level face must retain colour plus opaque-core depth contribution");
    require(state.rdp->otherMode.H==0x182C0FU&&state.rdp->otherMode.L==0xC8104A50U&&
            state.rsp->otherModeStack[state.rsp->otherModeStackSize-1].L==oldRspMode.L&&
            state.rsp->otherModeStack[state.rsp->otherModeStackSize-1].H==oldRspMode.H,
            "Core pass must restore both RSP and RDP render modes");
    require(state.rdp->blendColorStack[state.rdp->blendColorStackSize-1].w==oldBlend.w,
            "Core pass must restore blend threshold");
    command(0x05010000,0x3100);
    require(work.drawData.faceIndices.size()==12,"Following actor draw must not inherit solid-core policy");
}


void native_screen_effect_copy_case() {
    std::vector<std::uint8_t> rdram(8U*1024U*1024U);std::uint32_t mi=0;
    auto state=std::make_unique<RT64::State>(rdram.data(),&mi,&interrupt);
    auto& rdp=*state->rdp;
    rdp.colorImage.fmt=G_IM_FMT_RGBA;rdp.colorImage.siz=G_IM_SIZ_16b;rdp.colorImage.width=320;
    rdp.texture.fmt=G_IM_FMT_RGBA;rdp.texture.siz=G_IM_SIZ_16b;rdp.texture.address=0x100000;
    rdp.colorCombinerStackSize=1;
    auto& cc=rdp.colorCombinerStack[0];
    cc.L=0xFC11FEE5U;cc.H=0xFFFFFC3EU;rdp.otherMode.H=0x00100C0FU;rdp.otherMode.L=0x03024000U;
    require(!rdp.jfgNativeScreenEffectCopy(),"Screen effects must not invent a missing GPU framebuffer");
    auto& source=state->framebufferManager.get(0x100000,G_IM_SIZ_16b,320,240);
    source.lastWriteType=RT64::Framebuffer::Type::Color;source.lastWriteFmt=G_IM_FMT_RGBA;
    require(rdp.jfgNativeScreenEffectCopy(),"Native nightvision must reuse the high-resolution screen");
    cc.L=0xFC11FE23U;cc.H=0xFFFFFDFEU;rdp.otherMode.H=0x00000C0FU;rdp.otherMode.L=0x0F0A4000U;
    require(rdp.jfgNativeScreenEffectCopy(),"Native damage tint must reuse the high-resolution screen");
    source.lastWriteType=RT64::Framebuffer::Type::Depth;
    require(!rdp.jfgNativeScreenEffectCopy(),"A reused depth allocation must never become a screen texture");
    source.lastWriteType=RT64::Framebuffer::Type::Color;
    source.lastWriteFmt=G_IM_FMT_I;
    require(!rdp.jfgNativeScreenEffectCopy(),"CPU-modified intensity shadows must not opt into GPU screen copies");
    source.lastWriteFmt=G_IM_FMT_RGBA;
    rdp.texture.address=0x300000;
    require(!rdp.jfgNativeScreenEffectCopy(),"Unrelated RAM textures must keep their CPU contents");
    rdp.texture.address=0x100000;rdp.colorImage.width=64;
    require(!rdp.jfgNativeScreenEffectCopy(),"Offscreen mask destinations must retain CPU ownership");
    rdp.colorImage.width=320;cc.H^=1;
    require(!rdp.jfgNativeScreenEffectCopy(),"Other alpha/blend materials must not broaden screen-effect eligibility");
}

int main() {
    native_screen_effect_copy_case();
    menu_icon_alpha_case(false,true);menu_icon_alpha_case(true,true);menu_icon_alpha_case(false,false);
    level_solid_core_draw_case();
    level_solid_core_case();
    enhanced_shadow_collection_case();
    reflection_culling_case(false, 320);
    reflection_culling_case(true, 320);
    reflection_culling_case(true, 64);

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
      {jfg::ActorLodPresentationScope scope(jfg::test::renderer_layout,bytes,0x8000CC64,actor,false);require(!scope.applied()&&bytes==original,"Original LOD changes no guest bytes");}
      {
        jfg::ActorLodPresentationScope scope(jfg::test::renderer_layout,bytes,0x8000CC64,actor,true);
        const jfg::PresentationGuestView ram(bytes);
        require(scope.applied()&&ram.u32(header+0xcc)==0&&ram.u8(0x800A0A20)==0,"High disables distance and global detail reduction");
        require(ram.u8(actor+0x3a)==2&&ram.u32(models+8)==instance,"High preserves authored model variant");
        {jfg::ActorLodPresentationScope nested(jfg::test::renderer_layout,bytes,0x8000CC64,actor,true);}
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
      jfg::PresentationIdentityTracker tracker{jfg::test::renderer_layout};
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
      {jfg::ActorLodPresentationScope scope(jfg::test::renderer_layout,bytes,0x8000CC64,actor,true);require(!scope.applied()&&bytes==wrong,"unknown native selector is untouched");}
      word(0x8000D434,0x00827021);byte(actor+0x3a,4);
      {jfg::ActorLodPresentationScope scope(jfg::test::renderer_layout,bytes,0x8000CC64,actor,true);require(!scope.applied(),"invalid base model fails closed");}
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
    jfg::Rt64F3ddkr renderer(application, false, jfg::test::renderer_layout);
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
