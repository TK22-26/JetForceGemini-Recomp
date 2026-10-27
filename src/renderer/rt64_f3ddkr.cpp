#include "jfg/runtime/cutscene_skip.hpp"
#include "jfg/runtime/cutscene_skip_button.hpp"
#include "jfg/runtime/cutscene_skip_label.hpp"
#include "jfg/renderer/glass_uv_history.hpp"
#include "rt64_f3ddkr.hpp"
#include "rt64_blur_pairing.hpp"
#include "jfg/renderer/blur_source_audit.hpp"
#include "jfg/renderer/native_blur.hpp"
#include "jfg/renderer/native_blur_mode.hpp"
#include "jfg/renderer/fog_settings.hpp"
#include "jfg/renderer/frame_diagnostics_state.hpp"
#include "jfg/renderer/interpolation_bridge.hpp"
#include "jfg/renderer/presentation_identity.hpp"
#include "jfg/renderer/semantic_presentation.hpp"
#include <bit>
#include "jfg/renderer/rt64_f3ddkr_address.hpp"

#include "gbi/rt64_gbi_f3d.h"
#include "gbi/rt64_gbi_rdp.h"
#include "hle/rt64_application.h"

#include <algorithm>
#include <array>
#include <bitset>
#include <chrono>
#include <cmath>
#include <cstdlib>
#include <cstddef>
#include <cstdint>
#include <mutex>
#include <future>
#include "jfg/renderer/floating_environment.hpp"
#include <unordered_map>

namespace jfg {
namespace {

constexpr std::uint8_t kOpDmaMatrix = 0x01U;
constexpr std::uint8_t kOpDmaTextureOffset = 0x02U;
constexpr std::uint8_t kOpDmaVertex = 0x04U;
constexpr std::uint8_t kOpDmaTriangles = 0x05U;
constexpr std::uint8_t kOpDisplayList = 0x06U;
constexpr std::uint8_t kOpDmaDisplayList = 0x07U;
constexpr std::uint8_t kOpSetPerspNorm = 0xB5U;
constexpr std::uint8_t kOpCullDisplayList = 0xBEU;
constexpr std::uint8_t kOpPopMatrix = 0xBDU;
constexpr std::uint8_t kOpMoveWord = 0xBCU;
constexpr std::uint8_t kOpDmaOffsets = 0xBFU;
constexpr std::uint8_t kOpSetTextureImage = 0xFDU;
constexpr std::uint8_t kOpSetDepthImage = 0xFEU;
constexpr std::uint8_t kOpSetColorImage = 0xFFU;
constexpr std::uint8_t kMoveWordBillboard = 0x02U;
constexpr std::uint8_t kMoveWordModelMatrix = 0x0AU;
constexpr std::size_t kMatrixCount = 32U;
constexpr std::size_t kVertexCount = 80U;
constexpr std::uint32_t kRdramBytes = 8U * 1024U * 1024U;
constexpr std::uint32_t kScratchAddress = kRdramBytes - 4096U;
// A guest list that branches to itself would otherwise spin forever on the
// game thread (jump form) or grow RT64's unbounded return stack (call form).
// The largest observed Goldwood task issues a few hundred G_DL edges; the
// budget is generous so only a cycle or a wild pointer can exhaust it.
constexpr std::size_t kMaximumDisplayListBranches = 65536U;
// The RSP microcode's own display-list stack is far shallower than this.
constexpr std::size_t kMaximumReturnStackDepth = 64U;
// F3D G_MOVEMEM payloads are at most 64 bytes (a full light set).
constexpr std::uint32_t kMaximumMoveMemBytes = 64U;

struct SemanticVertexState {
    SemanticPresentationSample sample;
    PresentationMatrix world{};
    std::uint32_t source = 0;
    std::array<std::uint64_t, 4> billboard_key{}, rigid_key{};
    // Points into this task's immutable identities; consumed before begin()
    // replaces that shared snapshot or clears the per-task vertex metadata.
    const RigidPresentationPose* rigid_pose = nullptr;
    const PresentationCameraIdentity* camera_owner = nullptr;
};
struct Context {
    RT64::Application* application = nullptr;
    RT64::GBI gbi{};
    NativeCutscenePrompt cutscene_prompt{};
    DayNightFog daynight_fog{};
    bool cutscene_prompt_drawn = false;
    std::array<hlslpp::float4x4, kMatrixCount> matrices{};
    std::array<std::uint32_t, kMatrixCount> matrix_segmented_addresses{};
    std::array<std::uint32_t, kMatrixCount> matrix_physical_addresses{};
    std::bitset<kMatrixCount> loaded_matrices{};
    std::uint32_t matrix_offset = 0U;
    std::uint32_t vertex_offset = 0U;
    std::uint32_t texture_offset = 0U;
    std::uint32_t texture_shift = 0U;
    std::size_t texture_count = 0U;
    std::size_t vertex_cursor = 0U;
    std::size_t selected_matrix = 0U;
    std::size_t commands = 0U;
    Rt64F3ddkrStats stats{};
    std::bitset<kVertexCount> loaded_vertices{};
    std::span<const std::uint8_t> simulation_rdram{};
    bool interpolate = false;
    std::uint64_t vi_tick = 0U;
    PresentationHistory presentation_history;
    std::optional<NativeBlurPass> blur_pass;
    std::uint32_t blur_list_address = 0;
    struct PendingBlurWorld {
        std::uint64_t serial = 0, tick = 0;
        std::uint32_t source = 0;
        unsigned rate = 0;
    } pending_blur_world;
    std::uint64_t presentation_serial = 0;
    PresentationHistory rigid_baseline_history; // Used only by explicit diagnostics.
    PresentationHistory shared_matrix_baseline_history; // Same-input old-policy diagnostic.
    PresentationHistory camera_shape_baseline_history; // Explicit comparison only.
    SemanticPresentationHistory semantic_history;
    GlassUvHistory glass_uv_history;
    std::shared_ptr<const PresentationSceneIdentity> identities;
    std::array<hlslpp::float4x4,kMatrixCount> model_matrices{}, camera_matrices{};
    std::array<std::uint64_t,kMatrixCount> camera_ids{};
    std::array<const PresentationCameraIdentity*,kMatrixCount> camera_owners{};
    std::array<bool,kMatrixCount> model_finite{};
    bool semantic_target = false;
    std::vector<SemanticVertexState> semantic_vertices;
    // Synchronous interpreter scratch only. Published frames own their data;
    // the semantic worker is joined before any of this storage is reused.
    std::vector<SemanticPresentationSample> semantic_samples;
    std::vector<SemanticPresentationPrevious> semantic_previous;
    std::vector<PresentationMesh> meshes;
    std::vector<std::uint32_t> local_indices;
    std::vector<std::size_t> vertex_counts;
    std::vector<hlslpp::float4x4> inverse_worlds;
    std::vector<bool> inverse_ready;
    bool billboard = false;
    // The game's G_CULL_FRONT bit (see dma_triangles): set by
    // G_SETGEOMETRYMODE, cleared by G_CLEARGEOMETRYMODE, reset per task.
    bool cull_front_switch = false;
    bool failed = false;
};

std::mutex contexts_mutex;
std::unordered_map<RT64::State*, Context*> contexts;
// Bound only during synchronous interpretation by the owning adapter. This
// avoids a global mutex/hash lookup for every command without retaining a
// pointer after the call, across destruction, or on another renderer thread.
thread_local Context* dispatch_context = nullptr;


[[nodiscard]] Context* find_context(RT64::State* state) noexcept {
    if (dispatch_context && dispatch_context->application->state.get() == state)
        return dispatch_context;
    const std::scoped_lock lock(contexts_mutex);
    const auto iterator = contexts.find(state);
    return iterator == contexts.end() ? nullptr : iterator->second;
}

void reject(RT64::State* state, RT64::DisplayList** dl) noexcept {
    if (Context* context = find_context(state); context != nullptr) {
        context->failed = true;
        // A handler that already recorded a specific cause keeps it. Generic
        // rejections (an unsupported opcode reached by running past the end
        // of a list, for example) fall back to the most recent G_DL edge so
        // triage can distinguish a bad pointer from a list that ran on.
        if (context->stats.rejection_reason == 0U &&
            context->stats.rejection_source_address == 0U) {
            context->stats.rejection_source_address =
                context->stats.last_display_list_address;
            context->stats.rejection_detail =
                context->stats.last_display_list_target;
        }
        if (dl != nullptr && *dl != nullptr) {
            context->stats.rejected_command_word0 = (**dl).w0;
            context->stats.rejected_command_word1 = (**dl).w1;
            const std::uintptr_t cursor =
                reinterpret_cast<std::uintptr_t>(*dl);
            const std::array<std::uintptr_t, 2U> bases{
                state == nullptr
                    ? 0U
                    : reinterpret_cast<std::uintptr_t>(state->RDRAM),
                reinterpret_cast<std::uintptr_t>(
                    context->simulation_rdram.data()),
            };
            for (const std::uintptr_t base : bases) {
                if (base != 0U && cursor >= base &&
                    cursor - base <= kRdramBytes - sizeof(**dl)) {
                    context->stats.rejected_command_address =
                        static_cast<std::uint32_t>(cursor - base);
                    break;
                }
            }
        }
    }
    if (dl != nullptr) {
        *dl = nullptr;
    }
}

[[nodiscard]] bool physical_range(
    const std::uint32_t address,
    const std::size_t length) noexcept {
    return address <= kRdramBytes && length <= kRdramBytes - address;
}

[[nodiscard]] std::uint8_t guest_byte(
    const Context& context,
    const RT64::State& state,
    const std::uint32_t address) noexcept {
    if (context.simulation_rdram.size() == kRdramBytes) {
        return context.simulation_rdram[address ^ 3U];
    }
    return state.RDRAM[address ^ 3U];
}

[[nodiscard]] std::int16_t guest_s16(
    const Context& context,
    const RT64::State& state,
    const std::uint32_t address) noexcept {
    const std::uint16_t value =
        (static_cast<std::uint16_t>(guest_byte(context, state, address)) << 8U) |
        guest_byte(context, state, address + 1U);
    return static_cast<std::int16_t>(value);
}

[[nodiscard]] std::uint32_t segmented_physical(
    RT64::State& state,
    const std::uint32_t address) noexcept {
    return detail::resolve_f3ddkr_byte_source(
        state.rsp->fromSegmented(address));
}

void select_matrix(Context& context) noexcept {
    RT64::RSP& rsp = *context.application->state->rsp;
    const std::size_t index = context.selected_matrix;
    rsp.modelMatrixStackSize = 1;
    rsp.modelMatrixStack[0] = context.matrices[index];
    rsp.modelMatrixSegmentedAddressStack[0] =
        context.matrix_segmented_addresses[index];
    rsp.modelMatrixPhysicalAddressStack[0] =
        context.matrix_physical_addresses[index];
    RT64::TransformGroup& group = rsp.extended.modelMatrixIdStack[0];
    group.matrixId = G_EX_ID_IGNORE;
    group.decompose = false;
    group.positionInterpolation = G_EX_COMPONENT_SKIP;
    group.rotationInterpolation = G_EX_COMPONENT_SKIP;
    group.scaleInterpolation = G_EX_COMPONENT_SKIP;
    group.skewInterpolation = G_EX_COMPONENT_SKIP;
    group.perspectiveInterpolation = G_EX_COMPONENT_SKIP;
    group.tileInterpolation = G_EX_COMPONENT_SKIP;
    group.ordering = G_EX_ORDER_LINEAR;
    rsp.extended.modelMatrixIdStackChanged = true;

    const int projection = rsp.projectionMatrixStackSize - 1;
    const hlslpp::float4x4 identity = hlslpp::float4x4::identity();
    rsp.viewMatrixStack[projection] = identity;
    rsp.projMatrixStack[projection] = identity;
    rsp.viewProjMatrixStack[projection] = identity;
    rsp.invViewProjMatrixStack[projection] = identity;
    rsp.projectionMatrixInversed = true;
    rsp.modelViewProjInserted = false;
    rsp.modelViewProjChanged = true;
}

void unsupported(RT64::State* state, RT64::DisplayList** dl) {
    reject(state, dl);
}

void no_op(RT64::State*, RT64::DisplayList**) {
}

PresentationMatrix presentation_matrix(const hlslpp::float4x4& value);

void dma_matrix(RT64::State* state, RT64::DisplayList** dl) {
    Context* context = find_context(state);
    if (context == nullptr) {
        reject(state, dl);
        return;
    }
    ++context->commands;
    ++context->stats.matrix_commands;
    const RT64::DisplayList command = **dl;
    const detail::F3ddkrMatrixCommand decoded_command =
        detail::decode_f3ddkr_matrix_command(command.w0);
    const std::size_t index = decoded_command.index;
    const bool multiply = decoded_command.multiply;
    const std::uint32_t segmented = state->rsp->fromSegmented(command.w1);
    if ((command.w0 & 0xFFFFU) != 64U ||
        index >= context->matrices.size()) {
        reject(state, dl);
        return;
    }
    const std::uint32_t address = detail::resolve_f3ddkr_dma_base(
        segmented, context->matrix_offset);
    if (!physical_range(address, sizeof(RT64::FixedMatrix))) {
        reject(state, dl);
        return;
    }
    const auto* fixed = reinterpret_cast<const RT64::FixedMatrix*>(
        context->simulation_rdram.size() == kRdramBytes
            ? context->simulation_rdram.data() + address
            : state->fromRDRAM(address));
    hlslpp::float4x4 decoded = fixed->toMatrix4x4();
    const auto model_matrix = decoded;
    if (multiply) {
        if (!context->loaded_matrices.test(0U)) {
            reject(state, dl);
            return;
        }
        // JFG's multiply form composes the object matrix with slot zero's
        // already-combined camera MVP. RT64 uses row-vector matrices here.
        decoded = hlslpp::mul(decoded, context->matrices[0U]);
    }
    context->camera_ids[index] = 0U;
    context->camera_owners[index] = nullptr;
    if (multiply && index != 0U && context->interpolate && context->identities) {
        context->model_matrices[index] = model_matrix;
        context->camera_matrices[index] = context->matrices[0U];
        context->camera_ids[index] = context->camera_ids[0U];
        context->camera_owners[index] = context->camera_owners[0U];
        const auto inverse = hlslpp::inverse(model_matrix);
        bool finite = true;
        for(int r=0;r<4;++r) for(int c=0;c<4;++c)
            finite = finite && std::isfinite(float(model_matrix[r][c])) && std::isfinite(float(inverse[r][c]));
        context->model_finite[index] = finite;
    }
    else if (!multiply && index == 0U && context->identities) {
        bool ambiguous=false;
        for (const auto& camera : context->identities->cameras)
            if (camera.matrix == address) {
                if(context->camera_ids[index])ambiguous=true;
                context->camera_ids[index] = camera.identity;
                if(camera.pose_valid && rigid_pose_matches_matrix(camera.pose,presentation_matrix(decoded)))
                    context->camera_owners[index] = &camera;
            }
        if(ambiguous)context->camera_owners[index]=nullptr;
    }
    context->matrices[index] = decoded;
    context->loaded_matrices.set(index);
    context->matrix_segmented_addresses[index] = command.w1;
    context->matrix_physical_addresses[index] = address;
    context->selected_matrix = index;
    select_matrix(*context);
}

void dma_texture_offset(RT64::State* state, RT64::DisplayList** dl) {
    Context* context = find_context(state);
    if (context == nullptr) {
        reject(state, dl);
        return;
    }
    ++context->commands;
    context->texture_offset = segmented_physical(*state, (*dl)->w1) &
        0x00FF'FFF8U;
    context->texture_shift = 0U;
    context->texture_count = 0U;
}

void set_color_image(RT64::State* state, RT64::DisplayList** dl) {
    Context* context = find_context(state);
    if (context == nullptr) {
        reject(state, dl);
        return;
    }
    const std::uint8_t format = static_cast<std::uint8_t>(
        (*dl)->p0(21U, 3U));
    const std::uint8_t size = static_cast<std::uint8_t>(
        (*dl)->p0(19U, 2U));
    const std::uint16_t width = static_cast<std::uint16_t>(
        (*dl)->p0(0U, 12U) + 1U);
    context->semantic_target = format == G_IM_FMT_RGBA && size == G_IM_SIZ_16b && width >= 320U;
    context->stats.color_image_address =
        segmented_physical(*state, (*dl)->w1);
    state->rdp->setColorImage(
        format, size, width, context->stats.color_image_address);
}

void set_depth_image(RT64::State* state, RT64::DisplayList** dl) {
    state->rdp->setDepthImage(segmented_physical(*state, (*dl)->w1));
}

void set_texture_image(RT64::State* state, RT64::DisplayList** dl) {
    Context* context = find_context(state);
    if (context == nullptr) {
        reject(state, dl);
        return;
    }
    const std::uint8_t format = static_cast<std::uint8_t>(
        (*dl)->p0(21U, 3U));
    const std::uint8_t size = static_cast<std::uint8_t>(
        (*dl)->p0(19U, 2U));
    const std::uint16_t width = static_cast<std::uint16_t>(
        (*dl)->p0(0U, 12U) + 1U);
    std::uint32_t address = segmented_physical(*state, (*dl)->w1);
    if (context->texture_offset != 0U) {
        if (format == G_IM_FMT_RGBA) {
            const std::uint32_t shift_address = context->texture_offset +
                static_cast<std::uint32_t>(context->texture_count * 2U);
            if (!physical_range(shift_address, 2U)) {
                reject(state, dl);
                return;
            }
            context->texture_shift = static_cast<std::uint16_t>(
                guest_s16(*context, *state, shift_address));
            address = detail::resolve_f3ddkr_byte_source(
                address + context->texture_shift);
        }
        else {
            context->texture_offset = 0U;
            context->texture_shift = 0U;
            context->texture_count = 0U;
        }
    }
    state->rdp->setTextureImage(format, size, width, address);
}

void load_block(RT64::State* state, RT64::DisplayList** dl) {
    Context* context = find_context(state);
    if (context == nullptr) {
        reject(state, dl);
        return;
    }
    const std::uint16_t lrs = static_cast<std::uint16_t>(
        (*dl)->p1(12U, 12U));
    if (context->texture_offset != 0U) {
        const std::uint32_t block_bytes = ((lrs >> 2U) + 1U) << 3U;
        if (block_bytes != 0U &&
            (context->texture_shift % block_bytes) != 0U) {
            // The shift is a raw guest s16. Undoing a shift larger than the
            // current texture address would wrap to a ~4 GiB address that
            // RT64's loadBlock dereferences unchecked.
            if (context->texture_shift > state->rdp->texture.address) {
                context->stats.rejection_reason = kF3ddkrRejectTextureShiftWrap;
                context->stats.rejection_detail = context->texture_shift;
                reject(state, dl);
                return;
            }
            state->rdp->texture.address -= context->texture_shift;
            context->texture_offset = 0U;
            context->texture_shift = 0U;
            context->texture_count = 0U;
        }
        else {
            ++context->texture_count;
        }
    }
    RT64::GBI_RDP::loadBlock(state, dl);
}

PresentationMatrix presentation_matrix(const hlslpp::float4x4& value) {
    PresentationMatrix result{};
    for(int r=0;r<4;++r) for(int c=0;c<4;++c) result[r*4+c]=value[r][c];
    return result;
}
hlslpp::float4x4 presentation_matrix(const PresentationMatrix& m) {
    return hlslpp::float4x4(m[0],m[1],m[2],m[3],m[4],m[5],m[6],m[7],
            m[8],m[9],m[10],m[11],m[12],m[13],m[14],m[15]);
}
SemanticVertexState semantic_vertex(const Context& context,std::uint32_t source,
                                   const std::array<float,3>& local,
                                   const PresentationRigidIdentity* rigid,
                                   const PresentationBeamIdentity* beam,
                                   const PresentationModelIdentity* bridge,
                                   const PresentationVertexIdentity& identity) {
    SemanticVertexState result;
    result.source = source;
    if(!context.identities || context.billboard) return result;
    const auto slot=context.selected_matrix;
    if (beam && rigid->camera && rigid_pose_matches_matrix(rigid->pose,
            presentation_matrix(context.matrices[slot]))) {
        result.sample.key={beam->lifetime,
            (std::uint64_t(beam->actor)<<32U)|beam->control,
            (std::uint64_t(beam->header)<<16U)|beam->flags,rigid->camera,
            0x4245414dU,(source-beam->vertices)/10U};
        result.world=rigid->pose.world;
        result.sample.camera=presentation_matrix(hlslpp::mul(
            presentation_matrix(rigid->pose.view),presentation_matrix(rigid->pose.projection)));
        const auto world=hlslpp::mul(hlslpp::float4(local[0],local[1],local[2],1.0f),
            presentation_matrix(result.world));
        result.sample.world={world.x,world.y,world.z};
        result.sample.valid=std::isfinite(float(world.w)) &&
            std::abs(float(world.w)-1.0f)<0.001f;
        return result;
    }
    if (bridge && rigid->camera && rigid_pose_matches_matrix(rigid->pose,
            presentation_matrix(context.matrices[slot]))) {
        result.sample.key={bridge->lifetime,
            (std::uint64_t(bridge->actor)<<32U)|bridge->instance,
            bridge->model,rigid->camera,0x42524944U,(source-bridge->vertices)/10U};
        result.world=rigid->pose.world;
        result.sample.camera=presentation_matrix(hlslpp::mul(
            presentation_matrix(rigid->pose.view),presentation_matrix(rigid->pose.projection)));
        const auto world=hlslpp::mul(hlslpp::float4(local[0],local[1],local[2],1.0f),
            presentation_matrix(result.world));
        result.sample.world={world.x,world.y,world.z};
        result.sample.valid=std::isfinite(float(world.w)) &&
            std::abs(float(world.w)-1.0f)<0.001f;
        return result;
    }
    if(context.camera_ids[slot]==0U) return result;
    if (!identity.owner)
        return result;
    const auto &owner = *identity.owner;
    const auto &geometry = identity.geometry ? *identity.geometry : owner;
    result.sample.key = {
        owner.lifetime, (std::uint64_t(owner.actor) << 32U) | geometry.instance,
        geometry.model, context.camera_ids[slot],
        identity.joint, identity.vertex};
    result.world = presentation_matrix(context.model_matrices[slot]);
    result.sample.camera = presentation_matrix(context.camera_matrices[slot]);
    result.camera_owner = context.camera_owners[slot];
    if (!identity.geometry)
        return result;
    const auto world =
        hlslpp::mul(hlslpp::float4(local[0], local[1], local[2], 1.0f),
                    context.model_matrices[slot]);
    result.sample.world = {world.x, world.y, world.z};
    result.sample.valid = context.model_finite[slot] &&
                          std::isfinite(float(world.w)) &&
                          std::abs(float(world.w) - 1.0f) < 0.001f;
    result.sample.point_collapsed = !result.sample.valid && semantic_point_collapse(result.world);
    return result;
}

void dma_vertex(RT64::State* state, RT64::DisplayList** dl) {
    Context* context = find_context(state);
    if (context == nullptr) {
        reject(state, dl);
        return;
    }
    ++context->commands;
    ++context->stats.vertex_batches;
    const RT64::DisplayList command = **dl;
    const std::size_t count = (command.w0 >> 19U) & 0x1FU;
    const std::size_t requested_start = (command.w0 >> 9U) & 0x1FU;
    const bool append = (command.w0 & 0x0001'0000U) != 0U;
    if (append) {
        if (context->billboard) {
            context->vertex_cursor = 1U;
        }
    }
    else {
        context->vertex_cursor = 0U;
    }
    if (requested_start > kVertexCount - context->vertex_cursor) {
        reject(state, dl);
        return;
    }
    const std::size_t first = context->vertex_cursor + requested_start;
    const std::uint32_t segmented = state->rsp->fromSegmented(command.w1);
    if (count == 0U || first > kVertexCount || count > kVertexCount - first) {
        reject(state, dl);
        return;
    }
    const std::uint32_t address = detail::resolve_f3ddkr_vertex_dma_source(
        segmented, context->vertex_offset, command.w0);
    const std::size_t source_bytes = count * 10U;
    if (!physical_range(address, source_bytes)) {
        reject(state, dl);
        return;
    }

    hlslpp::float4x4 unanchored_matrix{};
    bool anchored_billboard = false;
    std::array<std::uint64_t, 4> billboard_key{};
    const auto rigid_key = context->interpolate && context->identities &&
            context->semantic_target && !context->billboard
        ? presentation_rigid_key(*context->identities,
            context->matrix_physical_addresses[context->selected_matrix], address,
            static_cast<std::uint32_t>(count))
        : std::array<std::uint64_t, 4>{};
    const auto* rigid_owner = context->interpolate && context->identities &&
        (rigid_key[0] || !context->identities->beams.empty())
        ? presentation_rigid_owner(*context->identities,
            context->matrix_physical_addresses[context->selected_matrix]) : nullptr;
    const auto* beam = rigid_owner ? presentation_beam_vertex(
        *context->identities,*rigid_owner,address) : nullptr;
    if (beam && count > (80U-(address-beam->vertices))/10U) beam=nullptr;
    static const bool bridge_vertices_enabled=[] {
#ifdef _MSC_VER
        char* value=nullptr;std::size_t length=0U;
        if(_dupenv_s(&value,&length,"JFG_DIAGNOSTIC_BRIDGE_VERTICES")!=0)return false;
        const bool enabled=!value || (length==2U && value[0]=='1');
        std::free(value);return enabled;
#else
        const char* value=std::getenv("JFG_DIAGNOSTIC_BRIDGE_VERTICES");
        return !value || std::strcmp(value,"1")==0;
#endif
    }();
    const auto* bridge=bridge_vertices_enabled && rigid_owner
        ? presentation_bridge_vertices(*context->identities,*rigid_owner,address,
            static_cast<std::uint32_t>(count)) : nullptr;

    if (context->billboard) {
        const int workload_cursor = state->ext.workloadQueue->writeCursor;
        RT64::Workload& workload =
            state->ext.workloadQueue->workloads[workload_cursor];
        const std::uint32_t anchor_index = state->rsp->indices[0U];
        if (anchor_index >= workload.drawData.posTransformed.size()) {
            reject(state, dl);
            return;
        }
        if (context->identities &&
            anchor_index < context->semantic_vertices.size()) {
            const auto source = context->semantic_vertices[anchor_index].source;
            for (const auto &sprite : context->identities->sprites)
                if (sprite.anchor == source) {
                    billboard_key = {sprite.lifetime, sprite.actor,
                                     sprite.sprite, context->camera_ids[0]};
                    break;
                }
        }
        unanchored_matrix = context->matrices[context->selected_matrix];
        context->matrices[context->selected_matrix][3] +=
            workload.drawData.posTransformed[anchor_index];
        anchored_billboard = true;
    }
    select_matrix(*context);
    std::array<std::byte, sizeof(RT64::RSP::Vertex) * 32U> saved{};
    auto* scratch = state->fromRDRAM(kScratchAddress);
    const std::size_t scratch_bytes = count * sizeof(RT64::RSP::Vertex);
    for (std::size_t index = 0U; index < scratch_bytes; ++index) {
        saved[index] = static_cast<std::byte>(scratch[index]);
    }
    auto* vertices = reinterpret_cast<RT64::RSP::Vertex*>(scratch);
    for (std::size_t index = 0U; index < count; ++index) {
        const std::uint32_t source =
            address + static_cast<std::uint32_t>(index * 10U);
        RT64::RSP::Vertex& vertex = vertices[index];
        vertex.x = guest_s16(*context, *state, source);
        vertex.y = guest_s16(*context, *state, source + 2U);
        vertex.z = guest_s16(*context, *state, source + 4U);
        vertex.flag = 0U;
        vertex.s = 0;
        vertex.t = 0;
        vertex.color.r = guest_byte(*context, *state, source + 6U);
        vertex.color.g = guest_byte(*context, *state, source + 7U);
        vertex.color.b = guest_byte(*context, *state, source + 8U);
        vertex.color.a = guest_byte(*context, *state, source + 9U);
    }
    state->rsp->setVertex(
        kScratchAddress,
        static_cast<std::uint32_t>(count),
        static_cast<std::uint32_t>(first));
    {
        const int workload_cursor = state->ext.workloadQueue->writeCursor;
        RT64::Workload& workload =
            state->ext.workloadQueue->workloads[workload_cursor];
        std::array<PresentationVertexIdentity,32> vertex_identities{};
        if(context->interpolate && context->identities && context->semantic_target &&
           !context->billboard && context->camera_ids[context->selected_matrix]!=0U)
            presentation_vertex_identities(*context->identities,
                context->matrix_physical_addresses[context->selected_matrix],address,
                std::span<PresentationVertexIdentity>(vertex_identities).first(count));
        for (std::size_t index = first; index < first + count; ++index) {
            const std::uint32_t global = state->rsp->indices[index];
            if (global >= workload.drawData.posTransformed.size()) {
                continue;
            }
            if(context->interpolate && context->identities && context->semantic_target) {
                context->semantic_vertices.resize(workload.drawData.worldIndices.size());
                const auto& positions=workload.drawData.posFloats;
                context->semantic_vertices[global]=semantic_vertex(*context,
                    address+static_cast<std::uint32_t>((index-first)*10U),
                    {positions[global*3U],positions[global*3U+1U],positions[global*3U+2U]},rigid_owner,beam,bridge,vertex_identities[index-first]);
                context->semantic_vertices[global].billboard_key =
                    billboard_key;
                context->semantic_vertices[global].rigid_key = rigid_key;
                context->semantic_vertices[global].rigid_pose = rigid_owner ? &rigid_owner->pose : nullptr;
            }
            const hlslpp::float4 position =
                workload.drawData.posTransformed[global];
            if (!std::isfinite(position.x) || !std::isfinite(position.y) ||
                !std::isfinite(position.z) || !std::isfinite(position.w)) {
                continue;
            }
            ++context->stats.vertices_finite;
            const float limit = std::abs(position.w) * 2.0F;
            if (position.w != 0.0F && std::abs(position.x) <= limit &&
                std::abs(position.y) <= limit &&
                std::abs(position.z) <= limit) {
                ++context->stats.vertices_in_clip;
            }
        }
    }
    for (std::size_t index = 0U; index < scratch_bytes; ++index) {
        scratch[index] = std::to_integer<std::uint8_t>(saved[index]);
    }
    if (anchored_billboard) {
        context->matrices[context->selected_matrix] = unanchored_matrix;
        select_matrix(*context);
    }
    for (std::size_t index = first; index < first + count; ++index) {
        context->loaded_vertices.set(index);
    }
    context->stats.vertices_loaded += count;
    context->vertex_cursor += count;
}

[[nodiscard]] bool set_vertex_texture_coordinates(
    Context& context, RT64::State& state,
    RT64::RSP& rsp,
    const std::uint8_t vertex,
    const std::uint32_t coordinate, const bool unused_coordinates) {
    const int workload_cursor = state.ext.workloadQueue->writeCursor;
    RT64::Workload& workload =
        state.ext.workloadQueue->workloads[workload_cursor];
    auto& draw = workload.drawData;
    std::uint32_t global = rsp.indices[vertex];
    const auto has_components = [global](const std::size_t size,
                                         const std::size_t stride) {
        return stride != 0U && global <= (SIZE_MAX - (stride - 1U)) / stride &&
            static_cast<std::size_t>(global) * stride + (stride - 1U) < size;
    };
    if (!has_components(draw.posFloats.size(), 3U) ||
        !has_components(draw.velFloats.size(), 3U) ||
        !has_components(draw.normColBytes.size(), 4U) ||
        !has_components(draw.tcFloats.size(), 2U) ||
        !has_components(draw.tcVelFloats.size(), 2U) ||
        global >= draw.viewProjIndices.size() ||
        global >= draw.worldIndices.size() || global >= draw.fogIndices.size() ||
        global >= draw.lightIndices.size() || global >= draw.lightCounts.size() ||
        global >= draw.lookAtIndices.size() ||
        global >= draw.posTransformed.size() || global >= draw.posScreen.size()) {
        return false;
    }

    // The validated I8 mask combiner consumes neither textures nor LOD.
    // Retain the vertex and every triangle; only omit unused UV writes.
    if (unused_coordinates) return true;

    // Repeating an identical UV on an offscreen pass does not modify a
    // previously submitted vertex. Keep scene topology unchanged: its stable
    // per-triangle vertices are also interpolation identities.
    if (!context.semantic_target && draw.lookAtIndices[global] == 0U &&
        draw.tcFloats[global * 2U] ==
            static_cast<float>(static_cast<std::int16_t>(coordinate >> 16U)) / 32.0F &&
        draw.tcFloats[global * 2U + 1U] ==
            static_cast<float>(static_cast<std::int16_t>(coordinate)) / 32.0F)
        return true;

    // RT64's pinned modifyVertex implementation appends directly from its
    // own vectors. A growth reallocation can invalidate the source reference,
    // corrupting positions when F3DDKR clones a shared vertex for per-triangle
    // texture coordinates. Clone through local values so this adapter remains
    // correct without modifying the pinned dependency checkout.
    if (rsp.used[vertex]) {
        const std::uint32_t replacement = draw.vertexCount();
        const float px = draw.posFloats[global * 3U];
        const float py = draw.posFloats[global * 3U + 1U];
        const float pz = draw.posFloats[global * 3U + 2U];
        const float vx = draw.velFloats[global * 3U];
        const float vy = draw.velFloats[global * 3U + 1U];
        const float vz = draw.velFloats[global * 3U + 2U];
        const std::uint8_t red = draw.normColBytes[global * 4U];
        const std::uint8_t green = draw.normColBytes[global * 4U + 1U];
        const std::uint8_t blue = draw.normColBytes[global * 4U + 2U];
        const std::uint8_t alpha = draw.normColBytes[global * 4U + 3U];
        const float texture_s = draw.tcFloats[global * 2U];
        const float texture_t = draw.tcFloats[global * 2U + 1U];
        const float velocity_s = draw.tcVelFloats[global * 2U];
        const float velocity_t = draw.tcVelFloats[global * 2U + 1U];
        const auto view_projection = draw.viewProjIndices[global];
        const auto world = draw.worldIndices[global];
        const auto fog = draw.fogIndices[global];
        const auto light = draw.lightIndices[global];
        const auto light_count = draw.lightCounts[global];
        const auto look_at = draw.lookAtIndices[global];
        const auto transformed = draw.posTransformed[global];
        const auto screen = draw.posScreen[global];

        draw.posFloats.insert(draw.posFloats.end(), {px, py, pz});
        draw.velFloats.insert(draw.velFloats.end(), {vx, vy, vz});
        draw.normColBytes.insert(
            draw.normColBytes.end(), {red, green, blue, alpha});
        draw.tcFloats.insert(draw.tcFloats.end(), {texture_s, texture_t});
        draw.tcVelFloats.insert(
            draw.tcVelFloats.end(), {velocity_s, velocity_t});
        draw.viewProjIndices.emplace_back(view_projection);
        draw.worldIndices.emplace_back(world);
        draw.fogIndices.emplace_back(fog);
        draw.lightIndices.emplace_back(light);
        draw.lightCounts.emplace_back(light_count);
        draw.lookAtIndices.emplace_back(look_at);
        draw.posTransformed.emplace_back(transformed);
        draw.posScreen.emplace_back(screen);
        if(context.interpolate && context.identities && context.semantic_target) {
            const auto semantic=global<context.semantic_vertices.size() ? context.semantic_vertices[global] : SemanticVertexState{};
            context.semantic_vertices.resize(draw.worldIndices.size());
            context.semantic_vertices[replacement]=semantic;
        }
        rsp.indices[vertex] = replacement;
        rsp.used[vertex] = false;
        global = replacement;
    }

    draw.tcFloats[global * 2U] =
        static_cast<float>(static_cast<std::int16_t>(coordinate >> 16U)) /
        32.0F;
    draw.tcFloats[global * 2U + 1U] =
        static_cast<float>(static_cast<std::int16_t>(coordinate)) / 32.0F;
    draw.lookAtIndices[global] = 0U;
    return true;
}

[[nodiscard]] std::uint8_t vertex_clip_code(
    const hlslpp::float4& position) noexcept {
    std::uint8_t clip = 0U;
    if (position.x > position.w)
        clip |= 0x01U;
    if (position.x < -position.w)
        clip |= 0x02U;
    if (position.y > position.w)
        clip |= 0x04U;
    if (position.y < -position.w)
        clip |= 0x08U;
    if (position.w < 0.01F)
        clip |= 0x10U;
    return clip;
}

void capture_loaded_vertices(Context& context) noexcept {
    context.stats.loaded_vertices_low = 0U;
    context.stats.loaded_vertices_high = 0U;
    for (std::size_t index = 0U; index < 64U; ++index) {
        if (context.loaded_vertices.test(index))
            context.stats.loaded_vertices_low |= std::uint64_t{1U} << index;
    }
    for (std::size_t index = 64U;
         index < context.loaded_vertices.size(); ++index) {
        if (context.loaded_vertices.test(index))
            context.stats.loaded_vertices_high |=
                static_cast<std::uint16_t>(1U << (index - 64U));
    }
}

void dma_triangles(RT64::State* state, RT64::DisplayList** dl) {
    Context* context = find_context(state);
    if (context == nullptr) {
        reject(state, dl);
        return;
    }
    ++context->commands;
    ++context->stats.triangle_batches;
    const RT64::DisplayList command = **dl;
    const std::size_t count = ((command.w0 >> 20U) & 0x0FU) + 1U;
    const std::uint8_t texture =
        static_cast<std::uint8_t>((command.w0 >> 16U) & 0x0FU);
    const std::uint32_t address = detail::resolve_f3ddkr_direct_dma_source(
        state->rsp->fromSegmented(command.w1));
    if (!physical_range(address, count * 16U)) {
        context->stats.rejection_reason = 1U;
        context->stats.rejection_detail = address;
        reject(state, dl);
        return;
    }
    // The F3DDKR command changes only gSP.texture.on. RT64 stores the mip
    // count as level + 1, so feeding textureState.levels back through
    // setTexture() would incorrectly increment an unrelated field on every
    // DMA triangle batch.
    state->rsp->textureState.on = texture;
    const auto& color = state->rdp->colorImage;
    const auto& combiner = state->rdp->colorCombinerStack[state->rdp->colorCombinerStackSize - 1];
    const auto mode = state->rsp->otherModeStack[state->rsp->otherModeStackSize - 1];
    bool unused_coordinates = !context->semantic_target && color.width == 64U &&
        color.fmt == G_IM_FMT_I && color.siz == G_IM_SIZ_8b &&
        !combiner.usesTexture(mode, 0U, true) && !combiner.usesTexture(mode, 1U, true);
    for (unsigned cycle = 0; unused_coordinates && cycle < 2; ++cycle)
        for (unsigned input = 0; input < 4; ++input)
            if (combiner.decodeColorInput(input, cycle != 0) == interop::ColorCombiner::C_LOD_FRACTION ||
                combiner.decodeAlphaInput(input, cycle != 0) == interop::ColorCombiner::A_LOD_FRACTION)
                unused_coordinates = false;
    for (std::size_t triangle = 0U; triangle < count; ++triangle) {
        const std::uint32_t source =
            address + static_cast<std::uint32_t>(triangle * 16U);
        const std::uint8_t flags = guest_byte(*context, *state, source);
        const std::array<std::uint8_t, 3U> vertices{
            guest_byte(*context, *state, source + 1U),
            guest_byte(*context, *state, source + 2U),
            guest_byte(*context, *state, source + 3U),
        };
        for (const std::uint8_t vertex : vertices) {
            if (vertex >= context->loaded_vertices.size() ||
                !context->loaded_vertices.test(vertex)) {
                context->stats.rejection_reason = 2U;
                context->stats.rejection_detail = vertex;
                context->stats.rejection_source_address = source;
                context->stats.rejection_triangle =
                    static_cast<std::uint32_t>(triangle);
                capture_loaded_vertices(*context);
                reject(state, dl);
                return;
            }
        }
        const int workload_cursor = state->ext.workloadQueue->writeCursor;
        const RT64::Workload& workload =
            state->ext.workloadQueue->workloads[workload_cursor];
        std::uint8_t common_clip = 0x1FU;
        for (const std::uint8_t vertex : vertices) {
            const std::uint32_t global = state->rsp->indices[vertex];
            if (global >= workload.drawData.posTransformed.size()) {
                context->stats.rejection_reason = 3U;
                context->stats.rejection_detail = global;
                reject(state, dl);
                return;
            }
            common_clip &=
                vertex_clip_code(workload.drawData.posTransformed[global]);
        }
        // The current endpoint may be outside while an intermediate camera
        // still sees this triangle. Clip interpolated scene geometry on the
        // GPU at its presentation pose; keep original/offscreen behavior.
        if (common_clip != 0U &&
            !(context->interpolate && context->semantic_target))
            continue;
        // JFG's microcode (DMA-triangle handler IMEM 0x1754-0x1770, triangle
        // setup 0x1B18-0x1BF8): a triangle without flag 0x40 gets G_CULL_BACK.
        // If the game has set G_CULL_FRONT, that bit turns the test round, so
        // single-sided triangles lose their front faces instead. The game sets
        // it around mirrored floor-reflection draws (overlay 137,
        // realReflectPrint). The GLideN64 DKR rule (front only when the
        // viewport X scale is negative) ignored the game's bit, so mirrored
        // single-sided parts such as faces were culled on the wrong side.
        // A negative viewport scale needs no rule: RT64 culls by screen
        // winding like the RDP.
        const std::uint32_t cull_mode = (flags & 0x40U) != 0U
            ? 0U
            : (context->cull_front_switch
                ? state->rsp->cullFrontMask
                : state->rsp->cullBothMask ^ state->rsp->cullFrontMask);
        state->rsp->modifyGeometryMode(
            ~state->rsp->cullBothMask, cull_mode);
        for (std::size_t corner = 0U; corner < vertices.size(); ++corner) {
            const std::uint32_t coordinate =
                (static_cast<std::uint32_t>(static_cast<std::uint16_t>(
                    guest_s16(*context, *state, source + 4U +
                        static_cast<std::uint32_t>(corner * 4U)))) << 16U) |
                static_cast<std::uint16_t>(guest_s16(
                    *context, *state, source + 6U +
                        static_cast<std::uint32_t>(corner * 4U)));
            if (!set_vertex_texture_coordinates(
                    *context, *state, *state->rsp, vertices[corner], coordinate, unused_coordinates)) {
                context->stats.rejection_reason = 4U;
                context->stats.rejection_detail = vertices[corner];
                reject(state, dl);
                return;
            }
        }
        state->rsp->drawIndexedTri(vertices[0U], vertices[1U], vertices[2U]);
        ++context->stats.triangles_drawn;
    }
    context->vertex_cursor = 0U;
}

void set_perspective_normalization(
    RT64::State* state,
    RT64::DisplayList** dl) {
    if (Context* context = find_context(state); context != nullptr) {
        ++context->commands;
    }
    state->rsp->setPerspNorm((*dl)->p1(16U, 16U));
}

void set_geometry_mode(RT64::State* state, RT64::DisplayList** dl) {
    if (Context* context = find_context(state); context != nullptr &&
        ((*dl)->w1 & state->rsp->cullFrontMask) != 0U) {
        context->cull_front_switch = true;
    }
    RT64::GBI_F3D::setGeometryMode(state, dl);
}

void clear_geometry_mode(RT64::State* state, RT64::DisplayList** dl) {
    if (Context* context = find_context(state); context != nullptr &&
        ((*dl)->w1 & state->rsp->cullFrontMask) != 0U) {
        context->cull_front_switch = false;
    }
    RT64::GBI_F3D::clearGeometryMode(state, dl);
}

void cull_display_list(RT64::State* state, RT64::DisplayList** dl) {
    Context* context = find_context(state);
    if (context == nullptr || dl == nullptr || *dl == nullptr) {
        reject(state, dl);
        return;
    }
    ++context->commands;
    std::size_t first = ((*dl)->w0 & 0x00FF'FFFFU) / 40U;
    if ((*dl)->w1 < 40U) {
        reject(state, dl);
        return;
    }
    std::size_t last = ((*dl)->w1 / 40U) - 1U;
    if (last < first)
        std::swap(first, last);
    if (last >= context->loaded_vertices.size()) {
        reject(state, dl);
        return;
    }

    const int workload_cursor = state->ext.workloadQueue->writeCursor;
    const RT64::Workload& workload =
        state->ext.workloadQueue->workloads[workload_cursor];
    std::uint8_t common_clip = 0x1FU;
    for (std::size_t vertex = first; vertex <= last; ++vertex) {
        if (!context->loaded_vertices.test(vertex)) {
            reject(state, dl);
            return;
        }
        const std::uint32_t global = state->rsp->indices[vertex];
        if (global >= workload.drawData.posTransformed.size()) {
            reject(state, dl);
            return;
        }
        const hlslpp::float4 position =
            workload.drawData.posTransformed[global];
        common_clip &= vertex_clip_code(position);
        if (common_clip == 0U)
            return;
    }
    // As with individual triangles, the endpoint is insufficient to cull
    // an interpolated display list. Loaded-vertex validation still applies.
    if (context->interpolate && context->semantic_target)
        return;
    // A cull at the top level has nothing to return to. RT64 would report
    // that as a clean EndDL and silently terminate the whole task.
    if (state->returnAddressStack.empty()) {
        context->stats.rejection_reason = kF3ddkrRejectReturnStackUnderflow;
        reject(state, dl);
        return;
    }
    *dl = state->popReturnAddress();
}

void move_mem(RT64::State* state, RT64::DisplayList** dl) {
    Context* context = find_context(state);
    if (context == nullptr) {
        reject(state, dl);
        return;
    }
    // Stock F3D moveMem dereferences a 24-bit masked address into RT64's
    // 8 MiB snapshot without a range check. Bound it here before delegating.
    const std::uint32_t address = state->rsp->fromSegmentedMasked((*dl)->w1);
    if (!physical_range(address, kMaximumMoveMemBytes)) {
        context->stats.rejection_reason = kF3ddkrRejectMoveMemRange;
        context->stats.rejection_detail = address;
        reject(state, dl);
        return;
    }
    RT64::GBI_F3D::moveMem(state, dl);
}

void move_word(RT64::State* state, RT64::DisplayList** dl) {
    Context* context = find_context(state);
    if (context == nullptr) {
        reject(state, dl);
        return;
    }
    ++context->commands;
    const std::uint8_t subtype = static_cast<std::uint8_t>((*dl)->w0);
    if (subtype == kMoveWordBillboard) {
        if (((*dl)->w1 & ~1U) != 0U) {
            reject(state, dl);
            return;
        }
        context->billboard = ((*dl)->w1 & 1U) != 0U;
        return;
    }
    if (subtype == kMoveWordModelMatrix) {
        context->selected_matrix = ((*dl)->w1 >> 6U) & 0x03U;
        select_matrix(*context);
        return;
    }
    if ((*dl)->p0(0U,8U) == G_MW_FOG) {
        auto native = (*dl)->w1;
        const auto& refinement = context->daynight_fog;
        if (refinement.valid && native == refinement.native_coefficients) {
            const auto& color = state->rdp->fogColorStack[state->rdp->fogColorStackSize - 1];
            const auto byte = [](float value) {
                return static_cast<std::uint32_t>(value * 255.0f + 0.5f);
            };
            const auto packed_color = (byte(static_cast<float>(color.x)) << 24U) |
                (byte(static_cast<float>(color.y)) << 16U) |
                (byte(static_cast<float>(color.z)) << 8U) | byte(static_cast<float>(color.w));
            native = daynight_fog_command(refinement, native, packed_color);
            if (interpolation_trace_enabled())
                trace_interpolation("daynight-fog-match", context->vi_tick,
                    (*dl)->w1, native, packed_color,
                    packed_color == refinement.color ? 1U : 0U, 0.0f, 0U, 0U);
            if (native != (*dl)->w1 && interpolation_trace_enabled())
                trace_interpolation("daynight-fog", context->vi_tick, (*dl)->w1,
                    native, packed_color, 0U, 0.0f, 0U, 0U);
        }
        const auto coefficients=jfg::fog_coefficients(native,
            jfg::fog_strength_preference().load(std::memory_order_relaxed));
        state->rsp->setFog(static_cast<std::int16_t>(coefficients >> 16U),
                          static_cast<std::int16_t>(coefficients & 0xffffU));
    } else RT64::GBI_F3D::moveWord(state, dl);
}

void dma_offsets(RT64::State* state, RT64::DisplayList** dl) {
    Context* context = find_context(state);
    if (context == nullptr) {
        reject(state, dl);
        return;
    }
    ++context->commands;
    context->matrix_offset = (*dl)->w0 & 0x00FF'FFFFU;
    context->vertex_offset = (*dl)->w1 & 0x00FF'FFFFU;
    // The original BF handler clears the texture-offset enable byte (DMEM
    // 0x1E7). A new model's DMA bases must not retain the prior texture table.
    context->texture_offset = 0U;
    context->texture_shift = 0U;
    context->texture_count = 0U;
}

void run_display_list(RT64::State* state, RT64::DisplayList** dl) {
    Context* context = find_context(state);
    if (context == nullptr || context->simulation_rdram.size() != kRdramBytes) {
        reject(state, dl);
        return;
    }
    ++context->stats.display_list_branches;
    if (context->stats.display_list_branches > kMaximumDisplayListBranches) {
        context->stats.rejection_reason = kF3ddkrRejectBranchBudget;
        context->stats.rejection_detail = static_cast<std::uint32_t>(
            context->stats.display_list_branches);
        reject(state, dl);
        return;
    }
    if ((*dl)->p0(16U, 1U) == 0U) {
        if (state->returnAddressStack.size() >= kMaximumReturnStackDepth) {
            context->stats.rejection_reason = kF3ddkrRejectReturnStackDepth;
            context->stats.rejection_detail = static_cast<std::uint32_t>(
                state->returnAddressStack.size());
            reject(state, dl);
            return;
        }
        state->pushReturnAddress(*dl);
    }
    const std::uint32_t address = detail::resolve_f3ddkr_direct_dma_source(
        state->rsp->fromSegmented((*dl)->w1));
    const std::uintptr_t command_cursor =
        reinterpret_cast<std::uintptr_t>(*dl);
    const std::uintptr_t simulation_base = reinterpret_cast<std::uintptr_t>(
        context->simulation_rdram.data());
    if (command_cursor >= simulation_base &&
        command_cursor - simulation_base <=
            kRdramBytes - sizeof(RT64::DisplayList)) {
        // Remember the most recent direct display-list edge. reject() copies
        // it into the rejection fields only when no handler recorded a more
        // specific cause, so a later successful edge cannot clobber an
        // earlier triangle diagnostic.
        context->stats.last_display_list_address =
            static_cast<std::uint32_t>(command_cursor - simulation_base);
        context->stats.last_display_list_target = address;
    }
    if (!physical_range(address, sizeof(RT64::DisplayList))) {
        reject(state, dl);
        return;
    }
    *dl = reinterpret_cast<RT64::DisplayList*>(
        const_cast<std::uint8_t*>(context->simulation_rdram.data()) +
        address) - 1;
}

bool detailed_function_profile_enabled() {
    static const bool enabled=[] {
#ifdef _MSC_VER
        char* value=nullptr;std::size_t length=0U;
        if(_dupenv_s(&value,&length,"JFG_DIAGNOSTIC_FUNCTION_PROFILE")!=0)return false;
        const bool selected=value && length==2U && (value[0]=='1' || value[0]=='2');
        std::free(value);
        return selected;
#else
        const char* value=std::getenv("JFG_DIAGNOSTIC_FUNCTION_PROFILE");
        return value && (value[0]=='1' || value[0]=='2') && value[1]=='\0';
#endif
    }();
    return enabled;
}

void prepare_interpolation(Context& context, RT64::State& state) {
    if (!context.interpolate) return;
    // Every synchronization consumes the preceding offer, including offscreen
    // or unrecognized work. A later effect cannot revive stale world history.
    const auto previous_world = context.pending_blur_world;
    context.pending_blur_world = {};
    const auto serial = ++context.presentation_serial;
    state.flush();
    auto& workload = state.ext.workloadQueue->workloads[state.ext.workloadQueue->writeCursor];
    auto& data = workload.drawData;
    if (context.blur_pass && native_blur_render_mode() >= 2U) {
        auto frame = std::make_shared<PresentationHistoryFrame>();
        frame->tick = context.vi_tick;
        frame->scene = true;
        frame->blur_source = context.blur_pass->source;
        frame->blur_target = context.blur_pass->target;
        frame->presentation_serial = serial;
        if (previous_world.serial && previous_world.serial + 1U == serial &&
            previous_world.source == context.blur_pass->source &&
            previous_world.tick <= context.vi_tick) {
            frame->blur_parent_serial = previous_world.serial;
            frame->tick = previous_world.tick;
            frame->source_rate = previous_world.rate;
        }
        if (native_blur_render_mode() == 5U)
            record_blur_source_audit({context.vi_tick, serial, 6U,
                previous_world.source, context.blur_pass->source,
                static_cast<unsigned>(previous_world.serial),
                static_cast<unsigned>(frame->blur_parent_serial),
                static_cast<unsigned>(previous_world.tick),
                static_cast<unsigned>(frame->tick),
                frame->blur_parent_serial ? 0U : 1U, previous_world.rate, frame->source_rate});
        frame->transforms.resize(data.worldTransforms.size());
        state.setRefreshRate(static_cast<std::uint16_t>(frame->source_rate));
        publish_presentation_snapshot(&workload, std::move(frame));
        context.semantic_vertices.clear();
        return;
    }
    bool scene = false;
    for (std::uint32_t f = 0; f < workload.fbPairCount; ++f) {
        const auto& pair = workload.fbPairs[f];
        scene = scene || (pair.colorImage.width >= 320U &&
            pair.colorImage.siz == G_IM_SIZ_16b && !pair.drawColorRect.isEmpty());
    }
    // Offscreen masks never enter either scene history. Publish the same
    // unmatched transform metadata without constructing mesh keys, semantic
    // samples, and temporary ownership maps that are discarded by record().
    if (!scene) {
        auto frame = std::make_shared<PresentationHistoryFrame>();
        frame->tick = context.vi_tick;
        frame->transforms.resize(data.worldTransforms.size());
        state.setRefreshRate(0U);
        publish_presentation_snapshot(&workload, std::move(frame));
        context.semantic_vertices.clear();
        return;
    }
    const bool history_profile=interpolation_trace_enabled() || detailed_function_profile_enabled();
    auto history_stage_started=history_profile ? std::chrono::steady_clock::now()
        : std::chrono::steady_clock::time_point{};
    const auto history_stage=[&](unsigned stage) {
        if (!history_profile) return;
        const auto now=std::chrono::steady_clock::now();
        const auto elapsed=static_cast<std::uint64_t>(
            std::chrono::duration_cast<std::chrono::microseconds>(now-history_stage_started).count());
        if(stage>=1U && stage<=context.stats.history_stage_microseconds.size())
            context.stats.history_stage_microseconds[stage-1U]+=elapsed;
        if(interpolation_trace_enabled())
            trace_interpolation("history-stage",context.vi_tick,stage,scene?1U:0U,0U,
                static_cast<unsigned>(data.worldIndices.size()),0.0f,elapsed,
                data.worldTransforms.size());
        history_stage_started=std::chrono::steady_clock::now();
    };
    context.semantic_vertices.resize(data.worldIndices.size());
    auto& semantic_samples=context.semantic_samples;
    semantic_samples.clear();
    semantic_samples.reserve(context.semantic_vertices.size());
    for (const auto& vertex : context.semantic_vertices) {
        auto sample = vertex.sample;
        if (!data.modifyPosUints.empty()) {
            sample.valid = false;
            sample.point_collapsed = false;
        }
        semantic_samples.push_back(sample);
    }
    const auto collapsed_count=exclude_collapsed_semantic_samples(semantic_samples,data.faceIndices);
    if(collapsed_count && interpolation_trace_enabled()) {
        std::map<std::uint32_t,unsigned> actors;
        for(std::size_t v=0;v<semantic_samples.size();++v)
            if(context.semantic_vertices[v].sample.point_collapsed &&
               context.semantic_vertices[v].sample.key[0] && !semantic_samples[v].key[0])
                ++actors[static_cast<unsigned>(context.semantic_vertices[v].sample.key[1]>>32U)];
        for(const auto& [actor,count]:actors)
            trace_interpolation("semantic-collapsed",context.vi_tick,actor,0,0,count,0,0,0);
    }
    SemanticRigidPoses semantic_rigid_poses;
    std::set<std::uint64_t> semantic_pose_conflicts;
    for(const auto& vertex:context.semantic_vertices) {
        if(!vertex.sample.valid || vertex.sample.key[4]!=0x42524944U || !vertex.rigid_pose)continue;
        const auto lifetime=vertex.sample.key[0];
        const auto [it,inserted]=semantic_rigid_poses.emplace(lifetime,*vertex.rigid_pose);
        if(!inserted && it->second!=*vertex.rigid_pose)semantic_pose_conflicts.insert(lifetime);
    }
    for(const auto lifetime:semantic_pose_conflicts)semantic_rigid_poses.erase(lifetime);
    SemanticCameraFrames semantic_cameras;
    std::set<std::uint64_t> semantic_camera_conflicts;
    for(const auto& vertex:context.semantic_vertices) {
        const auto* camera=vertex.camera_owner;
        if(!vertex.sample.valid || !camera || !camera->pose_valid ||
           camera->identity!=vertex.sample.key[3])continue;
        const auto [it,inserted]=semantic_cameras.emplace(camera->identity,
            SemanticCameraFrame{camera->generation,camera->pose,vertex.sample.camera});
        if(!inserted && (it->second.generation!=camera->generation ||
           it->second.pose!=camera->pose || it->second.matrix!=vertex.sample.camera))
            semantic_camera_conflicts.insert(camera->identity);
    }
    for(const auto identity:semantic_camera_conflicts)semantic_cameras.erase(identity);
    const bool semantic_cadence = context.presentation_history.has_continuous_cadence(context.vi_tick, scene);
    std::fenv_t semantic_environment{};
    const bool semantic_parallel = scene && semantic_samples.size() >= 128 &&
        capture_floating_environment(semantic_environment);
    auto semantic_job = std::async(semantic_parallel ? std::launch::async : std::launch::deferred,
        [&context, tick = context.vi_tick, scene,
         semantic_cadence, semantic_parallel, semantic_environment,
         poses=std::move(semantic_rigid_poses),cameras=std::move(semantic_cameras)]() mutable {
            const ScopedFloatingEnvironment environment(
                semantic_parallel ? &semantic_environment : nullptr);
            const auto& values=context.semantic_samples;
            SemanticPresentationDiagnostics reasons;
            const bool audit=blur_source_audit_enabled();
            context.semantic_history.record_into(values, tick, scene, semantic_cadence,
                context.semantic_previous, (interpolation_trace_enabled() || audit)?&reasons:nullptr,&poses,&cameras);
            if(audit) {
                // Private fixed-buffer evidence: distinguish native geometry
                // absence from an all-or-nothing interpolation history rejection.
                struct ActorAudit { unsigned actor=0,model=0,samples=0,matched=0; };
                std::map<std::uint64_t,ActorAudit> actors;
                if(context.identities)for(const auto& model:context.identities->models) {
                    auto& row=actors[model.lifetime];
                    row.actor=model.actor;row.model=model.model;
                }
                for(std::size_t i=0;i<values.size();++i) {
                    const auto& sample=values[i];
                    if(!sample.key[0])continue;
                    auto& row=actors[sample.key[0]];
                    row.actor=static_cast<unsigned>(sample.key[1]>>32U);
                    row.model=static_cast<unsigned>(sample.key[2]);
                    ++row.samples;
                    row.matched+=context.semantic_previous[i].matched;
                }
                for(const auto& [lifetime,row]:actors) {
                    const auto it=reasons.find(lifetime);
                    const std::array<std::uint64_t,7> zero{};
                    const auto& counts=it==reasons.end()?zero:it->second;
                    record_blur_source_audit({tick,lifetime,9U,row.actor,row.model,
                        static_cast<unsigned>(counts[0]),static_cast<unsigned>(counts[1]),
                        static_cast<unsigned>(counts[2]),static_cast<unsigned>(counts[3]),
                        static_cast<unsigned>(counts[4]),row.matched,row.samples});
                    if(counts[6])record_blur_source_audit({tick,lifetime,11U,row.actor,row.model,
                        static_cast<unsigned>(counts[6]),row.matched,row.samples,0U,0U,0U,0U});
                }
                if(context.identities)for(const auto& camera:context.identities->cameras)
                    record_blur_source_audit({tick,camera.identity,10U,camera.matrix,
                        static_cast<unsigned>(camera.generation),
                        std::bit_cast<unsigned>(camera.pose.view[0]),
                        std::bit_cast<unsigned>(camera.pose.view[2]),
                        std::bit_cast<unsigned>(camera.pose.view[12]),
                        std::bit_cast<unsigned>(camera.pose.view[14]),
                        camera.pose_valid?1U:0U,0U,0U});
            }
            if(interpolation_trace_enabled())for(const auto& [lifetime,counts]:reasons) {
                const auto sample=std::find_if(values.begin(),values.end(),[&](const auto& s){
                    return s.key[0]==lifetime;
                });
                const auto actor=sample==values.end()?0U:static_cast<unsigned>(sample->key[1]>>32U);
                trace_interpolation("semantic-reject",tick,actor,
                    static_cast<unsigned>(counts[0]),static_cast<unsigned>(counts[1]),
                    static_cast<unsigned>(counts[2]),0.0f,counts[3],counts[4]);
            }
            return floating_exception_flags();
        });
    auto& meshes=context.meshes;
    meshes.resize(data.worldTransforms.size());
    for(auto& mesh:meshes) {
        mesh.key.clear();mesh.positions.clear();mesh.matrix={};
        mesh.eligible=true;mesh.complete_local_topology=true;
        mesh.rigid_pose.reset();mesh.camera_owner.reset();mesh.camera_pose.reset();
    }
    auto& local_indices=context.local_indices;
    local_indices.assign(data.worldIndices.size(),0U);
    auto& vertex_counts=context.vertex_counts;
    vertex_counts.assign(meshes.size(),0U);
    for (std::size_t v=0;v<data.worldIndices.size();++v)
        if (data.worldIndices[v]<meshes.size() && v*3U+2U<data.posFloats.size())
            ++vertex_counts[data.worldIndices[v]];
    for (std::size_t i = 0; i < meshes.size(); ++i) {
        // UV clones normally contribute one triangle index per position.
        // Reserve headroom once; unusual topology still grows normally.
        meshes[i].positions.reserve(vertex_counts[i]);
        meshes[i].key.reserve(vertex_counts[i]*6U+11U);
        for (std::size_t r = 0; r < 4; ++r)
            for (std::size_t c = 0; c < 4; ++c)
                meshes[i].matrix[r*4+c] = data.worldTransforms[i].m[r][c];
        meshes[i].eligible = data.modifyPosUints.empty();
    }
    for (std::size_t v = 0; v < data.worldIndices.size(); ++v) {
        const auto m = data.worldIndices[v];
        if (m >= meshes.size() || v*3+2 >= data.posFloats.size()) continue;
        auto& mesh = meshes[m];
        local_indices[v] = static_cast<std::uint32_t>(mesh.positions.size());
        std::array<float, 3> point{};
        for (std::size_t c = 0; c < 3; ++c) {
            point[c] = data.posFloats[v*3+c];
            mesh.key.push_back(std::bit_cast<std::uint32_t>(point[c]));
        }
        mesh.positions.push_back(point);
    }
    for (auto& mesh : meshes) {
        mesh.key.push_back(0xFFFFFFFFU);
        mesh.key.push_back(static_cast<std::uint32_t>(mesh.positions.size()));
    }
    std::size_t cross_matrix_triangles=0, equal_matrix_triangles=0;
    for (std::size_t t = 0; t + 2 < data.faceIndices.size(); t += 3) {
        const auto a = data.faceIndices[t], b = data.faceIndices[t+1], c = data.faceIndices[t+2];
        if (a >= data.worldIndices.size() || b >= data.worldIndices.size() ||
            c >= data.worldIndices.size()) continue;
        const auto ma = data.worldIndices[a], mb = data.worldIndices[b], mc = data.worldIndices[c];
        if (ma >= meshes.size() || mb >= meshes.size() || mc >= meshes.size()) continue;
        if (ma != mb || ma != mc) {
            ++cross_matrix_triangles;
            if(allow_shared_matrix_triangle(meshes[ma],meshes[mb],meshes[mc]))
                ++equal_matrix_triangles;
            continue;
        }
        meshes[ma].key.insert(meshes[ma].key.end(),
            {local_indices[a], local_indices[b], local_indices[c]});
    }
    history_stage(1U); // Geometry keys and local indices.
    // Identical sprite quads must not match a different pickup just because
    // their geometry is equal. Stable actor lifetime + asset + camera owns
    // the billboard transform; texture animation keeps its authored cadence.
    std::map<unsigned, std::array<std::uint64_t, 4>> billboard_owners;
    for (std::size_t v = 0;
         v < context.semantic_vertices.size() && v < data.worldIndices.size();
         ++v) {
        const auto &key = context.semantic_vertices[v].billboard_key;
        if (key[0] != 0 && key[3] != 0)
            billboard_owners[data.worldIndices[v]] = key;
    }
    for (const auto &[matrix, key] : billboard_owners)
        if (matrix < meshes.size())
            bind_presentation_billboard(meshes[matrix], key);
    const bool rigid_trace = scene && interpolation_trace_enabled();
    const bool rigid_compare=rigid_trace && interpolation_compare_enabled();
    PresentationHistoryFrame rigid_baseline;
    if (rigid_compare)
        rigid_baseline = context.rigid_baseline_history.record(meshes, context.vi_tick, scene);
    std::map<unsigned, std::array<std::uint64_t, 4>> rigid_owners;
    std::set<unsigned> rigid_conflicts;
    std::map<unsigned, const RigidPresentationPose*> rigid_poses;
    for (std::size_t v = 0; v < context.semantic_vertices.size() && v < data.worldIndices.size(); ++v) {
        const auto &key = context.semantic_vertices[v].rigid_key;
        if (!key[0] || !key[3]) continue;
        const auto matrix = data.worldIndices[v];
        const auto [it, inserted] = rigid_owners.emplace(matrix, key);
        if (!inserted && it->second != key) rigid_conflicts.insert(matrix);
        const auto* pose=context.semantic_vertices[v].rigid_pose;
        if (pose) {
            const auto [previous, fresh]=rigid_poses.emplace(matrix,pose);
            if (!fresh && *previous->second != *pose) rigid_conflicts.insert(matrix);
        }
    }
    for (const auto &[matrix, key] : rigid_owners) if (matrix < meshes.size()) {
        if (rigid_conflicts.contains(matrix)) meshes[matrix].eligible = false;
        else {
            bind_presentation_rigid(meshes[matrix], key);
            const auto pose=rigid_poses.find(matrix);
            if (pose!=rigid_poses.end() && rigid_pose_matches_matrix(*pose->second, meshes[matrix].matrix))
                meshes[matrix].rigid_pose=*pose->second;
            else if (pose!=rigid_poses.end() && rigid_compare && context.vi_tick>=3300U) {
                static unsigned captured=0;
                if(captured<512U) {
                    ++captured;
                    const std::array<float,16>* matrices[]{&pose->second->world,&pose->second->view,
                        &pose->second->projection,&meshes[matrix].matrix};
                    for(unsigned part=0;part<4;++part)for(unsigned row=0;row<4;++row) {
                        const auto& m=*matrices[part];
                        const auto pair=[&](unsigned c) { return
                            (std::uint64_t(std::bit_cast<std::uint32_t>(m[row*4+c]))<<32U)|
                            std::bit_cast<std::uint32_t>(m[row*4+c+1]); };
                        trace_interpolation("rigid-reject",context.vi_tick,static_cast<unsigned>(key[1]>>32U),
                            part,row,captured,0.0f,pair(0),pair(2));
                    }
                }
            }
        }
    }
    PresentationHistoryFrame shared_matrix_baseline;
    if(rigid_compare) {
        auto old_policy=meshes;
        for(auto& mesh:old_policy) if(!mesh.complete_local_topology) mesh.eligible=false;
        shared_matrix_baseline=context.shared_matrix_baseline_history.record(
            old_policy,context.vi_tick,scene);
    }
    PresentationHistoryFrame camera_shape_baseline;
    if(rigid_compare) camera_shape_baseline=context.camera_shape_baseline_history.record(
        meshes,context.vi_tick,scene);
    if(context.identities)for(std::size_t m=0;m<meshes.size() && m<data.worldTransformPhysicalAddresses.size();++m) {
        const PresentationCameraIdentity* owner=nullptr;
        bool ambiguous=false;
        for(const auto& camera:context.identities->cameras)
            if(camera.matrix==data.worldTransformPhysicalAddresses[m] && camera.pose_valid) {
                if(owner)ambiguous=true;
                owner=&camera;
            }
        if(owner && !ambiguous) {
            meshes[m].camera_owner=std::array<std::uint64_t,2>{owner->generation,owner->identity};
            meshes[m].camera_pose=owner->pose;
        }
    }
    auto frame = std::make_shared<PresentationHistoryFrame>(
        context.presentation_history.record(meshes, context.vi_tick, scene, rigid_compare));
    if(rigid_compare) {
        std::size_t gained=0,lost=0,changed=0,owned=0;
        for(std::size_t m=0;m<meshes.size();++m) {
            const auto& old=camera_shape_baseline.transforms[m];
            const auto& current=frame->transforms[m];
            owned+=meshes[m].camera_owner.has_value();
            if(current.matched && !old.matched)gained+=meshes[m].positions.size();
            if(old.matched && !current.matched)lost+=meshes[m].positions.size();
            if(old.matched && current.matched && old.previous!=current.previous)++changed;
        }
        trace_interpolation("camera-identity",context.vi_tick,frame->source_rate,
            static_cast<unsigned>(changed),static_cast<unsigned>(owned),
            static_cast<unsigned>(data.worldIndices.size()),0.0f,gained,lost);
        const auto& camera_debug=frame->debug_cameras;
        trace_interpolation("camera-history",context.vi_tick,frame->source_rate,
            static_cast<unsigned>(camera_debug[0]),static_cast<unsigned>(camera_debug[1]),
            static_cast<unsigned>(camera_debug[2]),frame->debug_projection_delta,
            camera_debug[3],camera_debug[4]);
        for(unsigned owner=0;owner<frame->debug_camera_rejections.size();++owner)
            for(unsigned endpoint=0;endpoint<2;++endpoint)for(unsigned part=0;part<2;++part)
                for(unsigned row=0;row<4;++row) {
                    const auto& pose=frame->debug_camera_rejections[owner][endpoint];
                    const auto& matrix=part?pose.projection:pose.view;
                    const auto pair=[&](unsigned c) {return
                        (std::uint64_t(std::bit_cast<std::uint32_t>(matrix[row*4+c]))<<32U)|
                        std::bit_cast<std::uint32_t>(matrix[row*4+c+1]);};
                    trace_interpolation("camera-operand",context.vi_tick,owner,
                        endpoint,part,row,0.0f,pair(0),pair(2));
                }
    }
    if(rigid_compare) {
        std::size_t gained=0,lost=0,changed=0;
        for(std::size_t m=0;m<meshes.size();++m) {
            const auto& old=shared_matrix_baseline.transforms[m];
            const auto& current=frame->transforms[m];
            if(current.matched && !old.matched)gained+=meshes[m].positions.size();
            if(old.matched && !current.matched)lost+=meshes[m].positions.size();
            if(old.matched && current.matched && old.previous!=current.previous)++changed;
        }
        trace_interpolation("matrix-sharing",context.vi_tick,frame->source_rate,
            static_cast<unsigned>(changed),0U,static_cast<unsigned>(data.worldIndices.size()),
            0.0f,gained,lost);
    }
    history_stage(2U); // Matrix ownership and rigid/shape history.
    if (rigid_trace) {
        std::size_t valid=0;
        for (const auto& mesh:meshes) valid+=mesh.rigid_pose.has_value();
        trace_interpolation("rigid-pose", context.vi_tick, frame->source_rate, 0U, 0U,
            static_cast<unsigned>(rigid_owners.size()), 0.0f, valid, 0U);
    }
    if (rigid_compare) for (const auto &[matrix,key] : rigid_owners)
        if (matrix < frame->transforms.size())
            trace_interpolation("rigid",context.vi_tick,static_cast<unsigned>(key[1]>>32U),
                static_cast<unsigned>(key[1]),static_cast<unsigned>(key[2]),
                static_cast<unsigned>(meshes[matrix].positions.size()),0.0f,
                rigid_baseline.transforms[matrix].matched,frame->transforms[matrix].matched);
    if (rigid_trace) for (const auto &[matrix,key] : rigid_owners)
        if (matrix < frame->transforms.size())
            trace_interpolation("rigid-owned",context.vi_tick,static_cast<unsigned>(key[1]>>32U),
                static_cast<unsigned>(key[1]),static_cast<unsigned>(key[2]),
                static_cast<unsigned>(meshes[matrix].positions.size()),0.0f,
                frame->transforms[matrix].matched,0U);
    const auto semantic_flags = semantic_job.get();
    if (semantic_parallel) merge_floating_exceptions(semantic_flags);
    const auto& samples = context.semantic_samples;
    const auto& history = context.semantic_previous;
    history_stage(3U); // Semantic history and ownership diagnostics.
    std::size_t semantic_count=0,matched_count=0,moving_count=0;
    if (scene && interpolation_trace_enabled()) {
        std::size_t matched = 0;
        for (const auto &[matrix, key] : billboard_owners)
            matched += matrix < frame->transforms.size() &&
                       frame->transforms[matrix].matched;
        trace_interpolation("billboard", context.vi_tick, frame->source_rate, 0,
                            0, static_cast<unsigned>(billboard_owners.size()),
                            0, matched, 0);
    }
    auto& inverse_worlds=context.inverse_worlds;
    inverse_worlds.resize(frame->transforms.size());
    auto& inverse_ready=context.inverse_ready;
    inverse_ready.assign(frame->transforms.size(),false);
    for(std::size_t v=0;v<samples.size();++v) {
        if(samples[v].key[0]==0U) continue;
        ++semantic_count;
        const auto m=data.worldIndices[v];
        if(m>=frame->transforms.size()) continue;
        auto& transform=frame->transforms[m];
        transform.matched=false; // Hold all parts together on an invalid sample.
        if(!history[v].matched) continue;
        const auto& vertex=context.semantic_vertices[v];
        if(!inverse_ready[m]) {
            inverse_worlds[m]=hlslpp::inverse(presentation_matrix(vertex.world));
            inverse_ready[m]=true;
        }
        const auto& inverse=inverse_worlds[m];
        const auto& p=history[v].world;
        const auto old_local=hlslpp::mul(hlslpp::float4(p[0],p[1],p[2],1.0f),inverse);
        const float old[3]={old_local.x,old_local.y,old_local.z};
        for(std::size_t c=0;c<3;++c) data.velFloats[v*3U+c]=data.posFloats[v*3U+c]-old[c];
        transform.matched=true;transform.semantic_vertices=true;
        transform.current_world=vertex.world;
        transform.previous_camera=history[v].camera;
        transform.current_camera=samples[v].camera;
        ++matched_count;
        if(samples[v].world!=history[v].world) ++moving_count;
    }
    // A hidden point has no inverse. Keep its native collapsed endpoint;
    // generic matrix history must not grow it back toward a previous pose.
    if(collapsed_count) for(std::size_t v=0;v<samples.size();++v) {
        const auto& original=context.semantic_vertices[v].sample;
        if(original.point_collapsed && original.key[0] && !samples[v].key[0] &&
           data.worldIndices[v]<frame->transforms.size())
            frame->transforms[data.worldIndices[v]].matched=false;
    }
    // Camera-driven glass reflections must use the same interpolation
    // phase as the pane. Only intact, lifetime-owned quads qualify.
    std::vector<GlassUvSample> glass_uv;
    std::vector<std::size_t> glass_vertices;
    for(std::size_t v=0;v<context.semantic_vertices.size();++v) {
        const auto& vertex=context.semantic_vertices[v];
        const auto& key=vertex.rigid_key;
        if(!key[0] || (key[2]&0xFFFFFFFFU)!=0x474C4153U ||
           v*2U+1U>=data.tcFloats.size() || !context.identities)continue;
        const auto actor=static_cast<std::uint32_t>(key[1]>>32U);
        for(const auto& pane:context.identities->glass) {
            if(pane.actor!=actor || pane.lifetime!=key[0] ||
               pane.control!=static_cast<std::uint32_t>(key[1]))continue;
            glass_uv.push_back({{key[0],key[1],key[2],key[3],vertex.source},
                {data.tcFloats[v*2U],data.tcFloats[v*2U+1U]},pane.texture_period});
            glass_vertices.push_back(v);
            break;
        }
    }
    const auto glass_velocity=context.glass_uv_history.record(glass_uv,context.vi_tick);
    unsigned glass_matched=0,glass_uv_moving=0;
    for(std::size_t i=0;i<glass_vertices.size();++i) {
        const auto v=glass_vertices[i];const auto m=data.worldIndices[v];
        if(m>=frame->transforms.size() || !frame->transforms[m].matched ||
           v*2U+1U>=data.tcVelFloats.size())continue;
        data.tcVelFloats[v*2U]=glass_velocity[i][0];
        data.tcVelFloats[v*2U+1U]=glass_velocity[i][1];
        ++glass_matched;
        glass_uv_moving+=glass_velocity[i][0]!=0.0f || glass_velocity[i][1]!=0.0f;
    }
    if(native_blur_render_mode()==5U && context.identities && !context.identities->glass.empty())
        record_blur_source_audit({context.vi_tick,serial,7U,
            static_cast<unsigned>(context.identities->glass.size()),
            static_cast<unsigned>(glass_vertices.size()),
            glass_matched,glass_uv_moving,0U,0U,0U,0U,0U});
    history_stage(4U); // Previous-world endpoint conversion.
    if(scene) trace_interpolation("semantic",context.vi_tick,frame->source_rate,0U,0U,
        static_cast<unsigned>(semantic_count),0.0f,matched_count,moving_count);
    if (scene && interpolation_trace_enabled()) {
        std::map<std::uint32_t,std::array<unsigned,3>> bridges;
        for (std::size_t v=0;v<samples.size();++v) if(samples[v].key[4]==0x42524944U) {
            auto& count=bridges[static_cast<std::uint32_t>(samples[v].key[1]>>32U)];
            ++count[0];count[1]+=history[v].matched;
            count[2]+=history[v].matched && samples[v].world!=history[v].world;
        }
        for (const auto& [actor,count]:bridges)
            trace_interpolation("bridge-owned",context.vi_tick,actor,0U,0U,
                count[0],0.0f,count[1],count[2]);
        std::map<std::uint32_t,std::array<unsigned,2>> beams;
        for (std::size_t v=0;v<samples.size();++v) if(samples[v].key[4]==0x4245414dU) {
            auto& count=beams[static_cast<std::uint32_t>(samples[v].key[1]>>32U)];
            ++count[0]; count[1]+=history[v].matched;
        }
        for (const auto& [actor,count]:beams)
            trace_interpolation("beam-owned",context.vi_tick,actor,0U,0U,count[0],0.0f,count[1],0U);
    }
    if(scene && interpolation_trace_enabled()) {
        std::set<PresentationMatrix> cameras;
        for(const auto& sample:samples) if(sample.valid) cameras.insert(sample.camera);
        std::size_t camera_vertices=0, camera_matched=0, all_matched=0;
        std::size_t invalid_camera_vertices=0;
        for(std::size_t v=0;v<data.worldIndices.size();++v) {
            const auto m=data.worldIndices[v];
            if(m>=meshes.size()) continue;
            const bool matched=frame->transforms[m].matched;
            all_matched+=matched;
            if(cameras.contains(meshes[m].matrix)) {
                ++camera_vertices;camera_matched+=matched;
                invalid_camera_vertices+=!meshes[m].eligible;
            }
        }
        trace_interpolation("geometry-conflict",context.vi_tick,frame->source_rate,0U,0U,
            static_cast<unsigned>(cross_matrix_triangles),0.0f,equal_matrix_triangles,invalid_camera_vertices);
        if(rigid_compare && context.vi_tick>=3300U) {
            static unsigned captured_camera_holds=0;
            for(std::size_t m=0;m<meshes.size();++m) {
                if(!cameras.contains(meshes[m].matrix) || frame->transforms[m].matched ||
                    meshes[m].positions.empty() || captured_camera_holds>=2048U) continue;
                ++captured_camera_holds;
                trace_interpolation("camera-hold",context.vi_tick,frame->source_rate,
                    static_cast<unsigned>(m),frame->debug_reasons[m],
                    static_cast<unsigned>(meshes[m].positions.size()),0.0f,
                    meshes[m].key.size(),captured_camera_holds);
                for(unsigned part=0;part<2;++part) for(unsigned row=0;row<4;++row) {
                    const auto& matrix=part?meshes[m].matrix:frame->debug_previous[m];
                    const auto pair=[&](unsigned c) {return
                        (std::uint64_t(std::bit_cast<std::uint32_t>(matrix[row*4+c]))<<32U)|
                        std::bit_cast<std::uint32_t>(matrix[row*4+c+1]);};
                    trace_interpolation("camera-matrix",context.vi_tick,static_cast<unsigned>(m),
                        part,row,captured_camera_holds,0.0f,pair(0),pair(2));
                }
            }
        }
        trace_interpolation("coverage",context.vi_tick,frame->source_rate,0U,
            static_cast<unsigned>(camera_vertices),static_cast<unsigned>(data.worldIndices.size()),
            0.0f,camera_matched,all_matched);
    }
    history_stage(5U); // Coverage diagnostics.
    if (scene && !data.worldIndices.empty()) {
        // The pinned native flag requests a blur task after this world task.
        // Keep its geometry/history, but let the completed composite own output.
        if (native_blur_render_mode() >= 2U && context.simulation_rdram.size() > 0xfeca5U) {
            const auto word=[&](unsigned address) {
                std::uint32_t value;std::memcpy(&value,context.simulation_rdram.data()+address,4);return value;
            };
            frame->defer_to_blur = context.simulation_rdram[0xfeca5U ^ 3U] != 0U &&
                word(0x551f8U)==0x3c028010U && word(0x551fcU)==0x8042eca5U &&
                word(0x55200U)==0x03e00008U && word(0x55204U)==0U;
        }
    }
    frame->presentation_serial = serial;
    if (frame->defer_to_blur) {
        const auto source = blur_world_source(workload);
        if (source)
            context.pending_blur_world = {serial, context.vi_tick, source, frame->source_rate};
        if (native_blur_render_mode() == 5U) {
            for (std::uint32_t f = 0; f < workload.fbPairCount; ++f) {
                const auto& pair = workload.fbPairs[f];
                record_blur_source_audit({context.vi_tick, serial, 5U,
                    pair.colorImage.address, pair.depthImage.address,
                    pair.colorImage.width, pair.colorImage.siz, pair.colorImage.fmt,
                    pair.gameCallCount, (pair.fillRectOnly ? 1U : 0U) |
                    (pair.fastPaths.clearDepthOnly ? 2U : 0U) |
                    (pair.drawColorRect.isEmpty() ? 4U : 0U) |
                    (source && source == pair.colorImage.address ? 8U : 0U),
                    frame->source_rate, 0U});
            }
        }
    }
    state.setRefreshRate(static_cast<std::uint16_t>(frame->defer_to_blur ? 0U : frame->source_rate));
    publish_presentation_snapshot(&workload, std::move(frame));
    context.semantic_vertices.clear();
}

bool native_blur_color_command(Context* context, RT64::State* state,
                               RT64::DisplayList** dl, std::size_t index) {
    if (!context || !context->blur_pass || !dl || !*dl) return false;
    const auto address = context->blur_list_address + index * sizeof(RT64::DisplayList);
    const auto cursor = reinterpret_cast<std::uintptr_t>(*dl);
    return cursor == reinterpret_cast<std::uintptr_t>(context->simulation_rdram.data()) + address ||
           cursor == reinterpret_cast<std::uintptr_t>(state->RDRAM) + address;
}
void set_blur_blend_color(RT64::State* state, RT64::DisplayList** dl) {
    auto color = (**dl).w1;
    auto* context = find_context(state);
    if (native_blur_color_command(context, state, dl, 11U)) {
        const auto original = color;
        color = configured_blur_color(color);
        if (blur_source_audit_enabled())
            record_blur_source_audit({context->vi_tick, 0U, 8U, 11U,
                static_cast<unsigned>(native_blur_preference().load(std::memory_order_relaxed)),
                original & 255U, color & 255U, 0U, 0U, diagnostic_blur_mode()});
    }
    state->rdp->setBlendColor(color);
}
void set_blur_env_color(RT64::State* state, RT64::DisplayList** dl) {
    auto color = (**dl).w1;
    auto* context = find_context(state);
    if (native_blur_color_command(context, state, dl, 13U)) {
        const auto original = color;
        color = configured_blur_color(color);
        if (blur_source_audit_enabled())
            record_blur_source_audit({context->vi_tick, 0U, 8U, 13U,
                static_cast<unsigned>(native_blur_preference().load(std::memory_order_relaxed)),
                original & 255U, color & 255U, 0U, 0U, diagnostic_blur_mode()});
    }
    state->rdp->setEnvColor(color);
}



// The generated button is a small native RGBA16 texture. Upload through RT64's
// ordinary TMEM decoder, while preserving game TMEM and guest memory. Only the
// explicitly added HUD rectangle receives this texture; no host overlay exists.
void draw_native_skip_texture(RT64::State* state, const NativeCutscenePrompt& prompt,
    std::span<const std::uint16_t> pixels, unsigned texture_width, unsigned texture_height,
    int left, int top, int display_width, int display_height,
    std::uint8_t format=G_IM_FMT_RGBA, std::uint8_t size=G_IM_SIZ_16b) {
    auto& rdp=*state->rdp;
    auto& workload=state->ext.workloadQueue->workloads[state->ext.workloadQueue->writeCursor];
    state->flush(); // Complete the preceding game's draw before changing tile state.
    constexpr unsigned tile_index=7;
    const auto old_tile=rdp.tiles[tile_index];
    const auto old_hash=rdp.tileReplacementHashes[tile_index];
    const auto old_texture_on=state->drawCall.textureOn;
    const auto old_texture_tile=state->drawCall.textureTile;
    const auto old_texture_levels=state->drawCall.textureLevels;
    rdp.setTile(tile_index,format,size,static_cast<std::uint16_t>((texture_width<<size)/16),0,0,
                G_TX_CLAMP,G_TX_CLAMP,0,0,0,0);
    rdp.setTileSize(tile_index,0,0,static_cast<std::uint16_t>((texture_width-1)*4),
        static_cast<std::uint16_t>((texture_height-1)*4));
    std::array<std::uint64_t,RDP_TMEM_WORDS> saved_tmem{};
    std::copy(std::begin(rdp.TMEM),std::end(rdp.TMEM),saved_tmem.begin());
    std::array<std::uint8_t,RDP_TMEM_BYTES> native_pixels{};
    for(unsigned i=0;i<pixels.size();++i) {
        native_pixels[(2U*i)^3U]=static_cast<std::uint8_t>(pixels[i]>>8U);
        native_pixels[(2U*i+1U)^3U]=static_cast<std::uint8_t>(pixels[i]);
    }
    auto source=rdp.texture;
    source.address=0;source.fmt=format;source.siz=size;source.width=static_cast<std::uint16_t>(texture_width);
    auto* game_rdram=state->RDRAM;
    state->RDRAM=native_pixels.data();
    // This immediate half of the native load only copies bytes into TMEM.
    // It schedules no deferred read from the temporary source buffer.
    rdp.loadTileOperation(rdp.tiles[tile_index],source,false);
    state->RDRAM=game_rdram;
    const auto hash=state->textureManager.uploadTexture(state,rdp.tiles[tile_index],
        state->ext.textureCache,workload.submissionFrame,
        static_cast<std::uint16_t>(texture_width),static_cast<std::uint16_t>(texture_height),0);
    std::copy(saved_tmem.begin(),saved_tmem.end(),std::begin(rdp.TMEM));
    rdp.setTileReplacementHash(tile_index,hash);
    // G_CC_DECALRGBA, one-cycle bilerp, standard translucent surface blending.
    // RT64 stores the native command low word in the upper uint32.
    rdp.setCombine(0xFFFCF27900FFFFFFULL);
    rdp.setOtherMode(0x000020F0U,0x00504240U);
    rdp.setScissor(0,0,0,prompt.width*4U,prompt.height*4U,RT64::ExtendedAlignment{});
    const auto before=workload.drawData.callTiles.size();
    // RDP rectangles rasterize on whole pixels. Fractional top coordinates
    // also trigger the native one-row T adjustment; using them directly made
    // the small button shift upward relative to its integer-aligned ring.
    // Cover the intended subpixel rectangle with whole-pixel bounds and carry
    // the fractional origin in S/T instead, identically on both axes.
    const auto ds=static_cast<std::int16_t>(texture_width*4096/display_width);
    const auto dt=static_cast<std::int16_t>(texture_height*4096/display_height);
    const int x0=left&~3,y0=top&~3;
    const int x1=(left+display_width+3)&~3,y1=(top+display_height+3)&~3;
    const auto s0=static_cast<std::int16_t>(-((left-x0)*ds)/128);
    const auto t0=static_cast<std::int16_t>(-((top-y0)*dt)/128);
    rdp.drawTexRect(x0,y0,x1,y1,tile_index,s0,t0,ds,dt,
        false,RT64::ExtendedAlignment{});
    state->flush();
    // The HUD has its own texture, never an overlapping game framebuffer copy.
    // Correct only descriptors created for this one native rectangle.
    for(auto i=before;i<workload.drawData.callTiles.size();++i) {
        auto& tile=workload.drawData.callTiles[i];
        tile.tmemHashOrID=hash;tile.tileCopyUsed=false;tile.rawTMEM=false;
        tile.reinterpretTile=false;tile.syncRequired=false;
    }
    rdp.tiles[tile_index]=old_tile;
    rdp.setTileReplacementHash(tile_index,old_hash);
    state->drawCall.textureOn=old_texture_on;
    state->drawCall.textureTile=old_texture_tile;
    state->drawCall.textureLevels=old_texture_levels;
    state->updateDrawStatusAttribute(RT64::DrawAttribute::Texture);
}

// IA8 gives the ring 16 alpha levels at 64x64 while fitting native 4 KiB TMEM.
// Its rectangle shares the button center, avoiding integer-fill half-pixel bias.
std::array<std::uint16_t,2048> native_skip_ring(float progress) {
    std::array<std::uint16_t,2048> packed{};
    if(progress<=0.0f)return packed;
    constexpr float pi=3.14159265358979323846f, radius=28.0f;
    const float sweep=std::clamp(progress,0.0f,1.0f)*2.0f*pi;
    const float ex=std::sin(sweep)*radius,ey=-std::cos(sweep)*radius;
    for(unsigned y=0;y<64;++y)for(unsigned x=0;x<64;++x) {
        const float dx=static_cast<float>(x)+0.5f-32.0f;
        const float dy=static_cast<float>(y)+0.5f-32.0f;
        float angle=std::atan2(dx,-dy);if(angle<0.0f)angle+=2.0f*pi;
        float distance=std::abs(std::hypot(dx,dy)-radius);
        if(angle>sweep)distance=std::min(std::hypot(dx,dy+radius),std::hypot(dx-ex,dy-ey));
        const auto alpha=static_cast<unsigned>(std::lround(std::clamp(2.5f-distance,0.0f,1.0f)*15.0f));
        const auto value=static_cast<std::uint16_t>(0xF0U|alpha);
        const unsigned i=y*64+x;
        packed[i/2]|=static_cast<std::uint16_t>(value<<((i&1U)?0U:8U));
    }
    return packed;
}

// This is an extra native N64 HUD display list, decoded through the same GBI
// functions as the game. It allocates no guest RAM and is never a host overlay.
void draw_cutscene_prompt(Context& context, RT64::State* state) {
    const auto& prompt=context.cutscene_prompt;
    auto& rdp=*state->rdp;
    if((!prompt.visible && !prompt.transition) || context.cutscene_prompt_drawn ||
       rdp.colorImage.fmt!=G_IM_FMT_RGBA || rdp.colorImage.siz!=G_IM_SIZ_16b ||
       rdp.colorImage.width!=prompt.width ||
       rdp.fillColorStackSize>=RDP_EXTENDED_STACK_SIZE-1 ||
         rdp.primColorStackSize>=RDP_EXTENDED_STACK_SIZE-1 ||
         rdp.colorCombinerStackSize>=RDP_EXTENDED_STACK_SIZE-1 ||
       rdp.scissorStackSize>=RDP_EXTENDED_STACK_SIZE-1)return;
    const auto commands=prompt.transition ? cutscene_transition_gbi(prompt.width,prompt.height)
          : cutscene_skip_gbi(prompt.width,prompt.height,0.0f,true);
    if(commands.empty())return;
    const auto modes=rdp.otherMode;
    rdp.pushFillColor();rdp.pushScissor();rdp.pushPrimColor();rdp.pushCombine();
    if(!prompt.transition) {
        const int scale=prompt.width>=512?2:1;
        const int cx=(static_cast<int>(prompt.width)-49*scale)*4;
        const int cy=(static_cast<int>(prompt.height)-14*scale)*4;
        const int diameter=36*scale;
        if(prompt.progress>0.0f) {
            const auto ring=native_skip_ring(prompt.progress);
            draw_native_skip_texture(state,prompt,ring,64,64,
                cx-24*scale,cy-24*scale,48*scale,48*scale,G_IM_FMT_IA,G_IM_SIZ_8b);
        }
        draw_native_skip_texture(state,prompt,cutscene_skip_button_rgba16,32,32,
            cx-diameter/2,cy-diameter/2,diameter,diameter);
        draw_native_skip_texture(state,prompt,cutscene_skip_label_rgba16,64,24,
            cx+33*scale,cy-15*scale,90*scale,30*scale);
    }
    for(const auto words:commands) {
        RT64::DisplayList command{};
        command.w0=words.w0;command.w1=words.w1;
        auto* current=&command;
        const auto function=context.gbi.map[words.w0>>24U];
        if(function)function(state,&current);
    }
    rdp.popCombine();rdp.popPrimColor();rdp.popScissor();rdp.popFillColor();
    rdp.setOtherMode(modes.H,modes.L);
    context.cutscene_prompt_drawn=true;
}

void full_sync(RT64::State* state, RT64::DisplayList** dl) {
    Context* context = find_context(state);
    const auto start = std::chrono::steady_clock::now();
    const bool detailed=detailed_function_profile_enabled();
    if(context)draw_cutscene_prompt(*context,state);
    auto rdp_started=std::chrono::steady_clock::time_point{};
    if (context != nullptr) {
        const auto& workload = state->ext.workloadQueue->workloads[state->ext.workloadQueue->writeCursor];
        bool scene = false;
        for (std::uint32_t f = 0; f < workload.fbPairCount; ++f) {
            const auto& pair = workload.fbPairs[f];
            scene = scene || (pair.colorImage.width >= 320U && pair.colorImage.siz == G_IM_SIZ_16b);
        }
        if (scene) frame_diagnostic_state().scene(context->vi_tick);
        const auto history_start=std::chrono::steady_clock::now();
        prepare_interpolation(*context, *state);
        if(scene && interpolation_trace_enabled()) trace_interpolation("history-cost",context->vi_tick,
            0U,0U,0U,0U,0.0f,std::chrono::duration_cast<std::chrono::microseconds>(
                std::chrono::steady_clock::now()-history_start).count(),0U);
        if(detailed) {
            rdp_started=std::chrono::steady_clock::now();
            context->stats.history_prepare_microseconds+=static_cast<std::uint64_t>(
                std::chrono::duration_cast<std::chrono::microseconds>(rdp_started-history_start).count());
        }
    }
    RT64::GBI_RDP::fullSync(state, dl);
    if (context != nullptr) {
        const auto end=std::chrono::steady_clock::now();
        context->stats.full_sync_microseconds+=static_cast<std::uint64_t>(
            std::chrono::duration_cast<std::chrono::microseconds>(end-start).count());
        if(detailed)context->stats.rdp_sync_microseconds+=static_cast<std::uint64_t>(
            std::chrono::duration_cast<std::chrono::microseconds>(end-rdp_started).count());
    }
}

void dispatch_nested(RT64::State* state, RT64::DisplayList*& command) {
    Context* context = find_context(state);
    if (context == nullptr || command == nullptr) {
        return;
    }
    const std::uint8_t opcode = static_cast<std::uint8_t>(command->w0 >> 24U);
    if ((opcode & 0xC0U) != 0xC0U) {
        // F3DDKR's counted DMA-list handler dispatches only RDP commands;
        // low opcodes inside the fixed-size block are data words, not
        // commands. Count them so a block that draws nothing is visible in
        // diagnostics without rejecting valid guest data.
        ++context->stats.nested_data_words;
        return;
    }
    const RT64::GBIFunction function = context->gbi.map[opcode];
    if (function == nullptr) {
        reject(state, &command);
        return;
    }
    function(state, &command);
}

void dma_display_list(RT64::State* state, RT64::DisplayList** dl) {
    Context* context = find_context(state);
    if (context == nullptr) {
        reject(state, dl);
        return;
    }
    ++context->commands;
    ++context->stats.dma_display_lists;
    const RT64::DisplayList outer = **dl;
    const std::size_t count = (outer.w0 >> 16U) & 0xFFU;
    const std::size_t encoded_bytes = outer.w0 & 0xFFFFU;
    const std::uint32_t address = detail::resolve_f3ddkr_direct_dma_source(
        state->rsp->fromSegmented(outer.w1));
    if (count == 0U || encoded_bytes != count * sizeof(RT64::DisplayList) ||
        !physical_range(address, encoded_bytes)) {
        reject(state, dl);
        return;
    }
    RT64::DisplayList* nested = reinterpret_cast<RT64::DisplayList*>(
        context->simulation_rdram.size() == kRdramBytes
            ? const_cast<std::uint8_t*>(context->simulation_rdram.data()) +
                address
            : state->fromRDRAM(address));
    RT64::DisplayList* const end = nested + count;
    while (nested != nullptr && nested < end && !context->failed) {
        RT64::DisplayList* current = nested;
        dispatch_nested(state, nested);
        if (nested == nullptr) {
            // EndDL is valid only as the final encoded word of a counted
            // list. It must not silently truncate the block.
            if (current + 1 != end) {
                reject(state, dl);
            }
            break;
        }
        RT64::DisplayList* const next = nested + 1;
        if (next <= current || next > end) {
            // Handlers such as TextureRectangle advance over continuation
            // words themselves. Count those words, and reject control flow
            // that escapes the explicitly bounded block.
            reject(state, dl);
            return;
        }
        nested = next;
    }
}

void reset(RT64::State* state) {
    RT64::GBI_F3D::reset(state);
    if (Context* context = find_context(state); context != nullptr) {
        context->matrix_offset = 0U;
        context->vertex_offset = 0U;
        context->texture_offset = 0U;
        context->texture_shift = 0U;
        context->texture_count = 0U;
        context->vertex_cursor = 0U;
        context->loaded_vertices.reset();
        context->selected_matrix = 0U;
        context->matrix_segmented_addresses.fill(0U);
        context->matrix_physical_addresses.fill(0U);
        context->loaded_matrices.reset();
        context->camera_ids.fill(0U);
        context->camera_owners.fill(nullptr);
        context->model_finite.fill(false);
        context->semantic_target=false;
        context->billboard = false;
        context->cull_front_switch = false;
    }
}

}  // namespace

struct Rt64F3ddkr::Impl {
    explicit Impl(RT64::Application& app) {
        context.application = &app;
    }
    Context context;
};

Rt64F3ddkr::Rt64F3ddkr(RT64::Application& application, const bool interpolate)
    : impl_(std::make_unique<Impl>(application)) {
    impl_->context.interpolate = interpolate;
    const std::scoped_lock lock(contexts_mutex);
    contexts.emplace(application.state.get(), &impl_->context);
}

Rt64F3ddkr::~Rt64F3ddkr() {
    if (impl_ != nullptr && impl_->context.application != nullptr &&
        impl_->context.application->state != nullptr) {
        const std::scoped_lock lock(contexts_mutex);
        contexts.erase(impl_->context.application->state.get());
        if (impl_->context.application->workloadQueue != nullptr)
            for (auto& workload : impl_->context.application->workloadQueue->workloads)
                publish_presentation_snapshot(&workload, nullptr);
    }
}

void Rt64F3ddkr::begin(
    const std::span<const std::uint8_t> simulation_rdram, const std::uint64_t vi_tick,
    std::shared_ptr<const PresentationSceneIdentity> identities, NativeCutscenePrompt prompt,
    DayNightFog daynight_fog) noexcept {
    impl_->context.daynight_fog = daynight_fog;
    impl_->context.cutscene_prompt=prompt;
    impl_->context.cutscene_prompt_drawn=false;
    impl_->context.identities=std::move(identities);
    impl_->context.semantic_vertices.clear();
    impl_->context.vi_tick = vi_tick;
    impl_->context.simulation_rdram = simulation_rdram;
    impl_->context.commands = 0U;
    impl_->context.stats = {};
    impl_->context.failed = false;
    reset(impl_->context.application->state.get());
}

void Rt64F3ddkr::process_display_list(std::uint32_t address) {
    auto& context=impl_->context;
    context.blur_list_address = address & 0x00ffffffU;
    context.blur_pass = native_blur_render_mode() >= 2U
        ? native_blur_pass(context.simulation_rdram,address) : std::nullopt;
    struct RestoreBinding {
        Context* previous;
        ~RestoreBinding() { dispatch_context=previous; }
    } restore{dispatch_context};
    dispatch_context=&context;
    context.application->processDisplayLists(
        const_cast<std::uint8_t*>(context.simulation_rdram.data()),address,0U,true);
}

void Rt64F3ddkr::install() noexcept {
    Context& context = impl_->context;
    context.gbi = {};
    context.gbi.ucode = RT64::GBIUCode::F3D;
    RT64::GBI_RDP::setup(&context.gbi, true);
    RT64::GBI_F3D::setup(&context.gbi);
    for (RT64::GBIFunction& function : context.gbi.map) {
        if (function == nullptr) {
            function = &unsupported;
        }
    }
    context.gbi.map[kOpDmaMatrix] = &dma_matrix;
    context.gbi.map[kOpDmaTextureOffset] = &dma_texture_offset;
    context.gbi.map[kOpDmaVertex] = &dma_vertex;
    context.gbi.map[kOpDmaTriangles] = &dma_triangles;
    context.gbi.map[kOpDisplayList] = &run_display_list;
    context.gbi.map[kOpDmaDisplayList] = &dma_display_list;
    context.gbi.map[G_RDPFULLSYNC] = &full_sync;
    context.gbi.map[G_SETBLENDCOLOR] = &set_blur_blend_color;
    context.gbi.map[G_SETENVCOLOR] = &set_blur_env_color;
    context.gbi.map[kOpSetPerspNorm] = &set_perspective_normalization;
    context.gbi.map[kOpCullDisplayList] = &cull_display_list;
    context.gbi.map[kOpPopMatrix] = &no_op;
    context.gbi.map[kOpMoveWord] = &move_word;
    context.gbi.map[kOpDmaOffsets] = &dma_offsets;
    context.gbi.map[kOpSetTextureImage] = &set_texture_image;
    context.gbi.map[kOpSetDepthImage] = &set_depth_image;
    context.gbi.map[kOpSetColorImage] = &set_color_image;
    context.gbi.map[G_LOADBLOCK] = &load_block;
    context.gbi.map[F3D_G_MOVEMEM] = &move_mem;
    context.gbi.map[F3D_G_SETGEOMETRYMODE] = &set_geometry_mode;
    context.gbi.map[F3D_G_CLEARGEOMETRYMODE] = &clear_geometry_mode;
    // F3DDKR has no sprite microcode; stock F3D would interpret 0x09 as a
    // Sprite2D base pointer and dereference it unchecked.
    context.gbi.map[F3D_G_SPRITE2D_BASE] = &unsupported;
    context.gbi.resetFromTask = &reset;
    RT64::Application& application = *context.application;
    application.interpreter->hleGBI = &context.gbi;
    application.state->rsp->setGBI(&context.gbi);
}

bool Rt64F3ddkr::complete() const noexcept {
    // A valid setup list may contain only stock RDP/GBI commands (for
    // example FullSync followed by EndDL), so custom-command count is a
    // diagnostic rather than an acceptance requirement.
    return impl_ != nullptr && !impl_->context.failed;
}

std::size_t Rt64F3ddkr::command_count() const noexcept {
    return impl_ == nullptr ? 0U : impl_->context.commands;
}

Rt64F3ddkrStats Rt64F3ddkr::stats() const noexcept {
    return impl_ == nullptr ? Rt64F3ddkrStats{} : impl_->context.stats;
}

}  // namespace jfg
