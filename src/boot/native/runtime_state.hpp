#pragma once
#include "jfg/renderer/game_layout.hpp"
// Private shared simulation state. Ownership stays with run_child.
#include "jfg/renderer/enhanced_shadow_footprint.hpp"
#include "jfg/renderer/door_indicator_presentation.hpp"
#include "jfg/renderer/camera_helper_presentation.hpp"
#include "jfg/renderer/camera_trig_precision.hpp"
#include "jfg/renderer/native_blur_mode.hpp"
#include "jfg/renderer/rain_fade.hpp"
#include "jfg/renderer/fog_settings.hpp"
#include "jfg/runtime/execution_local.hpp"
#include "jfg/game/rom_catalog.hpp"
#include "jfg/game/original_modules.hpp"
#include "jfg/game/resident_memory.hpp"
#include "jfg/game/overlay_memory.hpp"
#ifndef JFG_NATIVE_GAME_HEADER
#error "Native runtime requires a linked regional descriptor and bindings"
#endif
#include JFG_NATIVE_GAME_HEADER
#include "jfg/runtime/flying_motion.hpp"
#include "jfg/boot/native_cache_all.hpp"
#ifndef NOMINMAX
#define NOMINMAX
#endif
#include "jfg/runtime/snapshot_copy.hpp"
#include "funcs.h"
#if __has_include("jfg_original_timing.h")
#include "jfg_original_timing.h"
#else
#define JFG_ORIGINAL_TIMING_GENERATION 0
#include "jfg/boot/original_timing_fast.h"
#endif
#ifndef JFG_NATIVE_TIMING_SPAN_GENERATION
#define JFG_NATIVE_TIMING_SPAN_GENERATION 0
#endif
#if defined(JFG_EXPERIMENTAL_NATIVE_PLAY_TIMING) && JFG_NATIVE_TIMING_SPAN_GENERATION != 1
#error Native timing preview requires a qualified generated span root
#endif
#include "jfg/boot/hle.hpp"
#include "jfg/boot/native_audio_source.hpp"
#include "jfg/boot/sound_queue_recovery.hpp"
#include "jfg/boot/reset_handoff.hpp"
#include "jfg/boot/ipl_handoff.hpp"
#include "jfg/boot/gameplay_trace.hpp"
#include "jfg/boot/function_profile.hpp"
#include "jfg/renderer/submission_profile.hpp"
#include "jfg/boot/native_resident_math.h"
#include "jfg/boot/native_collision.hpp"
#include "jfg/boot/native_shadow_filter.hpp"
#include "jfg/boot/direct_sp_access.hpp"
#include "jfg/boot/direct_mi_mask_access.hpp"
#include "jfg/renderer/interpolation_bridge.hpp"
#include "jfg/renderer/blur_source_audit.hpp"
#include "jfg/renderer/frame_diagnostics_state.hpp"
#include "jfg/boot/host_count_clock.hpp"
#include "jfg/boot/native_frame_recovery.hpp"
#include "jfg/boot/count_sample_tape.hpp"
#include "jfg/boot/recorded_input_timeline.hpp"
#include "jfg/mod/navigation_mod.hpp"
#include "jfg/runtime/async_bounded_trace.hpp"
#include "jfg/runtime/async_snapshots.hpp"
#include "jfg/runtime/async_diagnostic_file.hpp"
#include "jfg/runtime/async_volume_file.hpp"
#include "jfg/runtime/async_config_files.hpp"
#include "jfg/audio/master_volume.hpp"
#include "jfg/audio/playback_buffer.hpp"
#include "jfg/audio/latency_recovery.hpp"
#include "jfg/audio/vi_playback_clock.hpp"
#include "jfg/runtime/window_input_mailbox.hpp"
#include "jfg/runtime/mouse_input_diagnostics.hpp"
#include <set>
#include <utility>
#include <future>
#include <atomic>
#include "jfg/boot/runlink_module_table.hpp"
#include "jfg/boot/runlink_native_identity.hpp"
#include "jfg/boot/thread_scheduler.hpp"
#include "jfg/boot/guest_thread_transport.hpp"
#include "jfg/boot/tlb.hpp"
#include "jfg/boot/reference_cache.hpp"
#include "jfg/boot/cpu_status.hpp"
#include "jfg/boot/mi_interrupt_mask.hpp"
#include "jfg/boot/sp_status.hpp"
#include "jfg/boot/reference_sp_dma.hpp"
#include "jfg/boot/reference_pif_boot.hpp"
#include "jfg/boot/original_timing_pi_dma.hpp"
#include "jfg/boot/reference_compare.hpp"
#include "jfg/boot/reference_si_dma.hpp"
#include "jfg/boot/reference_event_commit.hpp"
#include "jfg/boot/native_event_batch.hpp"
#include "generated_lookup_entry.h"
#include "jfg/boot/native_periodic_deadline.hpp"
#include "jfg/boot/native_audio_playback.hpp"
#include "jfg/boot/flash_device.hpp"
#include "jfg/boot/original_timing_ai_dma.hpp"
#include "jfg/boot/point_probe.hpp"
#include "jfg/boot/device_event_probe.h"
#include "jfg/boot/eret_transfer_probe.hpp"
#include "jfg/boot/instruction_effect_trace.hpp"
#include "jfg/runtime/cpu_operation_bridge.h"
#include "jfg/boot/timers.hpp"
#include "jfg/boot/si_deadline.hpp"
#include "jfg/runtime/generated_overlay_runtime.hpp"
#include "jfg/runtime/input_stick.hpp"
#include "jfg/runtime/controller_mapping.hpp"
#include "jfg/runtime/controller_ports.hpp"
#if defined(_WIN32) && defined(JFG_PHASE8_LIVE_RUNTIME)
#include "jfg/runtime/sdl_controller_backend.hpp"
#endif
#include "jfg/runtime/pc_input.hpp"
#include "jfg/runtime/modern_controls.hpp"
#include "jfg/runtime/modern_roll.hpp"
#include "jfg/runtime/cutscene_skip.hpp"
#include "jfg/runtime/cutscene_script.hpp"
#include "jfg/runtime/cutscene_completion.hpp"
#include "jfg/runtime/cutscene_review.hpp"
#include "jfg/runtime/cutscene_audio.hpp"
#include "jfg/runtime/flight_transition_music.hpp"
#include "jfg/runtime/pc_rumble.hpp"
#include "jfg/runtime/pc_rumble_output.hpp"
#include "jfg/runtime/pc_camera_visibility.hpp"
#include "jfg/runtime/support_log.hpp"
#include "jfg/runtime/support_snapshot.hpp"
#include <iterator>
#include "jfg/runtime/rt64_overlay_address.hpp"
#include "jfg/renderer/rt64_f3ddkr_address.hpp"
#include "jfg/runtime/cic_nus_6105.hpp"
#include "jfg/testkernel/sha256.hpp"
#if defined(JFG_PHASE8_LIVE_RUNTIME)
#include "jfg/evidence/g2_private_task_adapter.hpp"
#include "jfg/renderer/rt64_shell.hpp"
#include "jfg/renderer/video_settings.hpp"
#include "jfg/renderer/presentation_identity.hpp"
#include "jfg/renderer/actor_lod_presentation.hpp"
#include "jfg/renderer/shadow_settings.hpp"
#include "jfg/renderer/interpolation_history.hpp"
#include "jfg/renderer/vi_presentation.hpp"
#include "jfg/runtime/audio_task_bridge.hpp"
#include "jfg/runtime/input_replay.hpp"
#include "jfg/runtime/save_device_runtime.hpp"
#endif

#include <algorithm>
#include "jfg/runtime/controller_status_query.hpp"
#include <array>
#include <bit>
#include <chrono>
#include <charconv>
#include <cfenv>
#include <cstdint>
#include <cstdio>
#include <csignal>
#include <cstdlib>
#include <cstring>
#include <deque>
#include <fstream>
#include <filesystem>
#include <iomanip>
#include <limits>
#include <memory>
#include <optional>
#include <unordered_map>
#include <unordered_set>
#include <regex>
#include <span>
#include <string>
#include <string_view>
#include <system_error>
#include <thread>
#include <vector>

#if defined(_WIN32)
#include <windows.h>
#include <Xinput.h>
#include <fcntl.h>
#include <io.h>
#if defined(JFG_PHASE8_LIVE_RUNTIME)
#include <SDL.h>
#endif
extern "C" BOOLEAN WINAPI SystemFunction036(PVOID, ULONG);
#endif

#include "jfg/boot/host_deadline_wait.hpp"

#if !defined(JFG_PHASE6_BUILD_IDENTITY)
#error "JFG_PHASE6_BUILD_IDENTITY must bind the native runner build"
#endif
#if !defined(JFG_PHASE6_SANITIZER_ID)
#error "JFG_PHASE6_SANITIZER_ID must bind the native runner instrumentation"
#endif

#include "runtime_constants.hpp"
#include "guest_memory.hpp"
#include "host_audio_device.hpp"
#include "generated_overlay_table.hpp"
#include "live_window.hpp"

extern "C" { extern JfgOriginalTimingFast* jfg_original_timing_state; }

namespace jfg::boot::native {
namespace detail {
constexpr std::uint32_t kKseg0 = 0x80000000U;
constexpr jfg::boot::NativeAudioSourceLayout kAudioSourceLayout{
  jfg::game::linked::code_address("audio.source_callback"),
  jfg::game::linked::data_address("audio.cache_control"),
  jfg::game::linked::data_address("audio.cache_nodes"),
  jfg::game::linked::data_address("audio.cache_frame"),
  jfg::game::linked::data_address("audio.pending_dma")};
constexpr std::uint32_t kOsCurrentThread = jfg::game::linked::data_address("os.current_thread");
constexpr std::uint32_t kOsFlashHandle = jfg::game::linked::data_address("os.flash_handle");
constexpr std::uint32_t kOsExceptionPreamble = jfg::game::linked::code_address("os.exception_preamble");
constexpr std::uint32_t kOsViWorker = jfg::game::linked::code_address("os.vi_worker");
constexpr std::uint32_t kOsSchedulerPark = jfg::game::linked::code_address("os.scheduler_park");
constexpr std::uint32_t kOsInitialize = jfg::game::linked::code_address("sdk.osInitialize");
constexpr std::uint32_t kOsVirtualToPhysical = jfg::game::linked::code_address("sdk.osVirtualToPhysical");
constexpr std::uint32_t kOsSetIntMask = jfg::game::linked::code_address("sdk.osSetIntMask");
constexpr std::uint32_t kViInitializeSite = jfg::game::linked::instruction_address("vi.initialize");
constexpr std::uint32_t kViManagerIdleSite = jfg::game::linked::instruction_address("vi.manager_idle");
constexpr std::uint32_t kRunlinkModuleTablePointer = jfg::game::linked::data_address("runlink.module_table_pointer");
constexpr std::uint32_t kRunlinkSuspendedModules = jfg::game::linked::data_address("runlink.suspended_modules");
constexpr std::uint32_t kRunlinkColdLoad = jfg::game::linked::code_address("runlink.cold_load");
constexpr std::uint32_t kRunlinkResume = jfg::game::linked::code_address("runlink.resume");
constexpr std::size_t kRunlinkOverlaySlotCount = jfg::game::linked::bindings.overlay_slot_count;
constexpr std::size_t kRunlinkSuspendedCount = jfg::game::linked::bindings.suspended_record_count;
constexpr std::uint32_t initial_entrypoint() {
  const auto& d = jfg::game::linked::descriptor;
  return d.sections[d.entry.section].linked_address + d.entry.offset;
}
constexpr std::uint32_t initial_tv_mode() { return static_cast<std::uint32_t>(jfg::game::linked::descriptor.initial_tv_mode); }
using OriginalModule = jfg::game::OriginalModule;
consteval std::uint32_t game_module(OriginalModule module) {
  const auto section=jfg::game::original_module_section(jfg::game::linked::descriptor,module);
  if(!section)throw "Required original module has no unique generated owner";
  return *section;
}
constexpr std::uint32_t kHintTextOverlaySection = game_module(OriginalModule::hint_text);
constexpr DeviceClocks hardware_clocks() {
  return initial_tv_mode()==0U ? kPalDeviceClocks : kNtscDeviceClocks;
}
// The old cooperative HLE profile uses nominal retraces. Original OS execution
// uses the register-driven VI owner and never this approximation.
constexpr std::uint64_t kCountTicksPerViFrame = hardware_clocks().count_hz / (initial_tv_mode()==0U?50U:60U);
constexpr std::uint64_t kCountTicksPerDispatch = 64U;
// A guest may wait for asynchronous hardware by polling an empty libultra
// queue without blocking. Bound only that repeated poll pattern so ordinary
// generated execution keeps its established cooperative timing.
constexpr std::uint32_t kEmptyReceivePollTimeslice = 2048U;
constexpr auto kSupportedRomSha1 = jfg::roms::known_revision(jfg::game::linked::descriptor.revision).sha1_bytes;
using Mapping = jfg::game::SdkMapping;
constexpr const auto& kMappings = jfg::game::linked::sdk_mappings;
constexpr std::size_t kMappingCount = kMappings.size();
inline const jfg::game::MemoryContext& game_memory_context() {
  static const jfg::game::MemoryContext context(jfg::game::linked::descriptor,jfg::game::linked::bindings);
  return context;
}
class NativeGameMemory : public jfg::mod::Memory {
public:
  explicit NativeGameMemory(std::span<std::uint8_t> bytes,bool native_words=true)
      :jfg::mod::Memory(bytes,game_memory_context(),native_words) {}
};
template<class Memory> auto game_view(Memory& memory) {
  return jfg::game::ResidentMemory<Memory>(jfg::game::linked::descriptor,memory);
}
consteval jfg::game::DataRef game_data_ref(std::string_view name) {
  return jfg::game::linked::data_reference(name);
}
constexpr jfg::CutsceneSoundBindings kCutsceneSoundBindings{
  game_data_ref("globals.currentLevel"),game_data_ref("globals.levelHeader"),
  game_data_ref("globals.cutsceneGroup"),game_data_ref("globals.cutsceneScriptStart"),
  game_data_ref("globals.cutsceneSoundHandles"),
  jfg::game::linked::code_reference("game.amSndPlay"),jfg::game::linked::code_reference("game.amSndPlayXYZ"),
  jfg::game::linked::instruction_reference("cutscene.sound_fire_and_forget"),
  jfg::game::linked::instruction_reference("cutscene.sound_handle"),
  jfg::game::linked::instruction_reference("cutscene.sound_positioned"),
  jfg::game::linked::member_offset("layout.levelHeader.kind"),
  jfg::game::linked::member_offset("layout.cutsceneActor.soundHandle")};
consteval std::uint32_t game_data(std::string_view name) {
  return jfg::game::linked::data_address(name);
}

consteval std::uint32_t game_instruction_word(std::string_view name) {
  return jfg::game::linked::instruction_word(name);
}
consteval std::uint32_t game_overlay_site(std::string_view name,OriginalModule module) {
  const auto ref=jfg::game::linked::instruction_reference(name);
  if(ref.revision!=jfg::game::linked::descriptor.revision || ref.section!=game_module(module))throw "Overlay instruction owner mismatch";
  return ref.offset;
}

consteval std::uint32_t game_member(std::string_view name) {
  return jfg::game::linked::member_offset(name);
}

consteval std::uint32_t game_instruction(std::string_view name) {
  return jfg::game::linked::instruction_address(name);
}

consteval std::uint32_t game_code(std::string_view name) {
  return jfg::game::linked::code_address(name);
}

// Compare linked identities only. Do not use these tokens for RAM access or
// bypass the generated overlay runtime's execution lease.
consteval std::uint32_t game_overlay_token(std::string_view name) {
  return jfg::game::linked::overlay_dispatch_token(name);
}

consteval std::uint32_t game_overlay_data(std::string_view name, OriginalModule module) {
  return jfg::game::linked::overlay_data_offset(name,game_module(module));
}
consteval std::uint32_t game_overlay_extent(OriginalModule module) {
  const auto& section=jfg::game::linked::sections[game_module(module)];
  return section.text_size+section.data_size+section.bss_size;
}


inline constexpr jfg::game::RomAssetDirectory kRomAssetDirectory{
 jfg::game::linked::descriptor.revision,
 jfg::game::rom_address_operand(game_instruction_word("rom.assets.table_hi"),game_instruction_word("rom.assets.table_lo")),
 jfg::game::rom_address_operand(game_instruction_word("rom.assets.data_hi"),game_instruction_word("rom.assets.data_lo"))};

inline constexpr JfgNativeMathLayout kNativeMathLayout{
 game_data("math.sineTable"),game_data("math.atanTable"),
 game_instruction("math.angle_direct_return"),game_instruction("math.angle_return"),
 game_code("game.mathDiffAngle"),game_instruction("math.diff_return"),
 game_instruction("math.diff_subtract_return"),game_instruction("math.diff_add_return"),
 game_code("game.Cosf"),game_code("game.Sinf"),game_instruction("math.trig_return")};
inline constexpr jfg::boot::SoundQueueLayout kSoundQueueLayout{
 game_data("audio.soundPlayer"),game_code("audio.sound_callback"),
 game_instruction_word("audio.sound_callback.entry0"),game_instruction_word("audio.sound_callback.entry4")};

inline constexpr jfg::RendererGameLayout kRendererGameLayout{
  jfg::game::linked::descriptor.revision,
  initial_tv_mode()==0U?50U:60U,
  game_data("globals.currentLevel"),
  game_data("globals.objectList"),
  game_data("globals.objectCount"),
  game_data("diagnostic.cameraViewport0"),
  game_data("diagnostic.cameraViewport1"),
  game_data("renderer.worldMatrix"),
  game_data("diagnostic.cameraViewState"),
  game_data("diagnostic.cameraMatrixInput"),
  game_data("diagnostic.shadowClipState"),
  game_data("renderer.shadowPolygons"),
  game_data("diagnostic.shadowVertexStart"),
  game_data("diagnostic.shadowBatchStart"),
  game_data("renderer.shadowUnclippedPoints"),
  game_data("renderer.shadowClippedPoints"),
  game_data("renderer.skyActor"),
  game_data("renderer.matrixQueueCount"),
  game_data("renderer.matrixQueue"),
  game_data("globals.currentTrack"),
  game_data("diagnostic.doorRenderMode"),
  game_data("renderer.cameraTransform"),
  game_data("renderer.cameraInverseMatrix"),
  game_code("game.objPrintModelObject"),
  game_code("game.objPrintObject"),
  game_code("game.shadowBoundingBox"),
  game_code("game.Cosf"),
  game_code("game.Sinf"),
  game_instruction("native.query_capture_return"),
  {game_instruction("render.lod.entry"),game_instruction_word("render.lod.entry")},
  {game_instruction("render.lod.detail"),game_instruction_word("render.lod.detail")},
  {game_instruction("render.lod.threshold"),game_instruction_word("render.lod.threshold")},
  {game_instruction("render.lod.selector"),game_instruction_word("render.lod.selector")},
  {game_instruction("render.camera.entry"),game_instruction_word("render.camera.entry")},
  {game_instruction("render.camera.flags"),game_instruction_word("render.camera.flags")},
  {game_instruction("render.camera.mask"),game_instruction_word("render.camera.mask")},
  {game_instruction("render.camera.rpy0"),game_instruction("render.camera.rpy2"),game_instruction("render.camera.rpy4")},
  {game_instruction("render.camera.rpy1"),game_instruction("render.camera.rpy3"),game_instruction("render.camera.rpy5")},
  {game_instruction("render.camera.ypr0"),game_instruction("render.camera.ypr2"),game_instruction("render.camera.ypr4")},
  {game_instruction("render.camera.ypr1"),game_instruction("render.camera.ypr3"),game_instruction("render.camera.ypr5")},
  game_data("globals.sResolutionIndex"),
  game_data("renderer.resolutionModes"),
  game_data("diagnostic.cutsceneState"),
  game_data("renderer.fadeMode"),
  game_data("renderer.fadeEnabled"),
  game_data("diagnostic.cutsceneByte3"),
  game_data("diagnostic.cutsceneByte0"),
  game_data("diagnostic.cutsceneByte1"),
  game_data("diagnostic.cutsceneByte2"),
  game_data("renderer.fadeVertexBanks"),
  game_data("renderer.fadeTriangleBanks"),
  game_data("renderer.fadeBankIndex"),
  game_data("renderer.fadeDisplayList"),
  game_data("renderer.viewports"),
  game_data("renderer.spSetupDisplayList"),
  game_data("renderer.setupDisplayList"),
  game_data("renderer.fontDisplayList"),
  game_data("globals.debugPrintEnd"),
  game_data("renderer.debugPrintBuffer"),
  game_data("renderer.gameSceneMode"),
  game_data("renderer.displayListCursor"),
  game_data("renderer.displayListBanks"),
  game_data("renderer.displayListBankIndex"),
  game_data("renderer.renderFramebuffer"),
  game_data("renderer.blurEnabled"),
  game_instruction("render.rain.submit_return"),
  game_instruction("render.rain.segment_return"),
  game_instruction("render.rain.debug_return"),
  game_instruction("render.rain.fade_return"),
  game_instruction("render.rain.simple_return"),
  game_instruction("render.rain.spatial_return"),
  {game_instruction("render.rain.fade_call"),game_instruction_word("render.rain.fade_call")},
  {game_instruction("render.rain.segment_call"),game_instruction_word("render.rain.segment_call")},
  {game_instruction("render.rain.effects_call"),game_instruction_word("render.rain.effects_call")},
  {{{game_instruction("render.blur.getter0"),game_instruction_word("render.blur.getter0")},{game_instruction("render.blur.getter1"),game_instruction_word("render.blur.getter1")},{game_instruction("render.blur.getter2"),game_instruction_word("render.blur.getter2")},{game_instruction("render.blur.getter3"),game_instruction_word("render.blur.getter3")}}},
  {game_code("game.mainUpdate"),game_code("game.setupClearScreen"),game_code("game.segSetBase"),game_code("game.diPrintfAll"),game_code("game.fxDrawFadeGeometry"),game_code("game.drawClearScreen"),game_code("game.fxDrawFade"),game_code("game.mainCPUeffects"),game_code("game.rainFastDraw"),game_code("game.cpuLine"),game_code("game.rcpFast3d"),game_code("game.fxFadeOn"),game_overlay_token("render.auxiliary.shadows"),game_overlay_token("render.auxiliary.refraction"),game_overlay_token("render.auxiliary.blur")},
  game_member("layout.actor.control"),
  game_member("layout.actor.type"),
  game_member("layout.actor.properties"),
  game_member("layout.actor.objectData"),
  game_member("layout.actor.animation"),
  game_member("layout.actor.animationFrame"),
  game_member("layout.actor.header"),
  game_member("layout.actor.models"),
  game_member("layout.actor.variant"),
  game_member("layout.actor.flags"),
  game_member("layout.actor.scale"),
  game_member("layout.actor.x"),
  game_member("layout.actor.y"),
  game_member("layout.actor.z"),
  game_member("layout.actor.physics"),
  game_member("layout.actor.deleted"),
  game_member("layout.actor.customBank"),
  game_member("layout.actor.alpha"),
  game_member("layout.objectHeader.renderKind"),
  game_member("layout.objectHeader.modelCount"),
  game_member("layout.objectHeader.lodThreshold"),
  game_member("layout.model.skinned"),
  game_member("layout.actor.state"),
  game_member("layout.objectHeader.assets"),
  game_member("layout.model.vertexCount"),
  game_member("layout.model.boneCount"),
  game_member("layout.model.batchCount"),
  game_member("layout.model.faces"),
  game_member("layout.model.batches"),
  game_member("layout.model.collision"),
  game_member("layout.instance.model"),
  game_member("layout.instance.vertices"),
  game_member("layout.instance.collision"),
  game_member("layout.instance.palette0"),
  game_member("layout.instance.palette1"),
  game_member("layout.doorIndicator.linkedDoor"),
  game_member("layout.doorIndicator.state"),
  game_member("layout.doorIndicator.condition"),
  game_member("layout.objectHeader.collisionVariant"),
  game_member("layout.actor.viewVisibility"),
  game_member("layout.regionControl.active"),
  game_member("layout.limbControl.vertices"),
  game_member("layout.limbControl.opaqueCommands"),
  game_member("layout.limbControl.transparentCommands"),
  game_member("layout.shockwaveControl.texture"),
  game_member("layout.shockwaveControl.bank"),
  game_member("layout.beamControl.active"),
  game_member("layout.beamControl.bank"),
  game_member("layout.beamControl.flags"),
  game_member("layout.glassActor.health"),
  game_member("layout.glassControl.texture"),
  game_member("layout.glassControl.vertices"),
  game_member("layout.glassControl.commands0"),
  game_member("layout.glassControl.commands1"),
  game_member("layout.shadowControl.flags"),
  game_member("layout.shadowControl.scale"),
  game_data("globals.frontendMode"),
  game_data("renderer.keyboardKeyActor"),
};

consteval std::uint32_t original_os_entry(std::string_view name) {
  for (const auto& mapping : kMappings)
    if (mapping.name == name) return mapping.vram;
  throw "Unknown original OS observer";
}

constexpr bool mappings_are_strictly_sorted() noexcept {
  for (std::size_t index = 1U; index < kMappingCount; ++index) {
    if (kMappings[index - 1U].vram >= kMappings[index].vram)
      return false;
  }
  return true;
}
static_assert(mappings_are_strictly_sorted(),
              "native HLE dispatch table must be sorted by guest address");

#if defined(JFG_PHASE8_LIVE_RUNTIME)
struct PendingLiveGraphicsTask final {
  jfg::Rt64GraphicsTask task{};
  std::array<std::uint32_t, 6U> descriptor{};
  std::vector<std::byte> rdram;
  bool skipped = false;
  std::uint64_t base_renderer_generation = 0U;
  std::vector<jfg::Rt64RdramRange> changed;
  std::vector<jfg::Rt64RdramRange> overlay_dirty;
  bool overlays_initialized = false;
};
struct GraphicsSnapshotCache final {
  std::vector<std::byte> rdram;
  std::uint64_t renderer_generation = 0U;
  std::vector<jfg::Rt64RdramRange> overlay_dirty;
  bool overlays_initialized = false;
};

struct LiveGraphicsOverlayShadow final {
  std::uint32_t section = 0U;
  std::uint32_t linked_base = 0U;
  std::uint32_t extent = 0U;
  std::uint32_t physical_base = 0U;
};

struct LiveViFieldRegisters final {
  std::uint32_t origin = 640U;
  std::uint32_t y_scale = 0x00000400U;
  std::uint32_t vertical_start = 0x002501FFU;
  std::uint32_t vertical_burst = 0x000E0204U;
  std::uint32_t intr = 2U;
};
#endif

struct State : JfgOriginalTimingFast {
  State() : JfgOriginalTimingFast{} { execution_fast_revision = UINT64_MAX; }
  bool ledgered = false;
#if defined(JFG_PHASE8_LIVE_RUNTIME)
  bool presentation_identity_enabled = false;
  std::uint32_t presentation_keyboard_key = UINT32_MAX;
  jfg::PresentationIdentityTracker presentation_identities{kRendererGameLayout};
  struct CameraFade { std::uint32_t actor=0,control=0,header=0; std::uint64_t tick=0, update=0; unsigned alpha=255; };
  std::array<CameraFade,4> pc_camera_fades{};
  std::uint64_t camera_fade_updates=0;
  jfg::rain::Runtime rain_fade;
#endif
  bool os_initialized = false;
  jfg::GeneratedOverlayRuntime *runtime = nullptr;
  const std::uint8_t *rom = nullptr;
  std::size_t rom_size = 0U;
  std::unique_ptr<ThreadScheduler> scheduler;
  std::unordered_map<std::uint32_t, int> threads;
  std::vector<std::pair<std::uint32_t, int>> thread_order;
  std::vector<std::uint32_t> thread_entries;
  std::unordered_set<std::uint32_t> queues;
  std::unordered_set<std::uint32_t> active_overlay_sections;
  // Linked section metadata is immutable for this generated root. Dynamic
  // allocation/publication checks still run for every dispatched call.
  std::unordered_map<std::uint32_t,
      std::pair<std::uint32_t, JfgGeneratedSectionMetadata>> generated_section_cache;
  std::unordered_set<std::uint32_t> guest_overlay_loads_in_progress;
  // Fresh guest loads recreate DATA/BSS before their init callback. Suspended
  // modules resume the existing state and must never enter this set.
  std::unordered_set<std::uint32_t> pending_cold_overlay_images;
  jfg::ControllerMapping controller_mapping{};
  jfg::ControllerPorts controller_ports;
#if defined(_WIN32) && defined(JFG_PHASE8_LIVE_RUNTIME)
  jfg::ControllerCatalog controller_catalog;
  jfg::SdlControllerBackend sdl_controllers;
#endif
  jfg::ControllerInputGate controller_input_gate;
  std::filesystem::path controller_config_path;
  jfg::AsyncConfigFiles controller_config_files;
  jfg::AsyncConfigFiles navigation_config_files;
  std::string navigation_last_weapons_request, navigation_last_floyd_request;
  jfg::AsyncConfigFiles cutscene_review_files;
  bool diagnostic_cutscene_review=false;
  std::uint64_t cutscene_review_nonce=0;
  jfg::CutsceneReviewMode cutscene_review_mode;
  std::int64_t cutscene_review_session_started=0;
  std::chrono::steady_clock::time_point controller_config_check{};
  std::uint32_t executing_generated_section = UINT32_MAX;
  bool executing_generated_overlay = false;
  const char *last_overlay_publication_failure = "none";
  std::unordered_set<std::uint32_t> generated_relocation_targets;
  jfg::boot::NativeRunlinkIdentityIndex native_overlay_identity_index;
  std::unordered_map<std::uint32_t, std::pair<std::uint32_t, std::uint32_t>>
      events;
  std::uint32_t pi_command_queue = 0U;
  bool vi_manager_thread_created = false;
  std::uint32_t vi_mode = 0U;
  std::uint32_t vi_queue = 0U;
  std::uint32_t vi_message = 0U;
  std::uint32_t vi_retrace_interval = 0U;
  std::uint32_t vi_current_framebuffer = 0U;
  std::uint32_t vi_next_framebuffer = 0U;
  std::uint32_t vi_special_features = 0U;
  bool vi_blacked = true;
  std::uint64_t vi_retraces = 0U;
  std::uint64_t vi_frames = 0U;
  std::uint64_t vi_interrupts = 0U;
  std::uint64_t vi_messages_delivered = 0U;
  std::uint32_t retrace_target = 3U;
  std::uint32_t poll_target = 0U;
  std::uint32_t vi_internal_queue = 0U;
  std::uint32_t vi_internal_message = 0U;
  EventJournal journal;
  MmioTrace *mmio_trace = nullptr;
  bool scheduler_running = false;
  std::uint32_t root_priority = 0U;
  std::uint32_t interrupt_mask = 0U;
  Timers timers;
  std::uint64_t os_time_base = 0U;
  std::uint64_t os_time_count_origin = 0U;
  std::uint32_t last_pi_rom = 0U;
  std::uint32_t last_pi_dram = 0U;
  std::uint32_t last_pi_size = 0U;
  bool controller_initialized = false;
  bool controller_guest_init_probe = false;
  std::uint32_t pending_si_completions = 0U;
  SiDeadline si_deadline;
  // Private generator-hook observer. This does not feed Count or deadlines.
  bool si_count_probe = false;
  bool renderer_writeback_probe = false;
  bool guest_leaf_probe = false;
  bool guest_initializing = false;
  bool guest_os_probe = false;
  std::uint64_t diagnostic_input_suspend_begin=0,diagnostic_input_suspend_end=0;
  bool native_audio_source = false;
  bool native_audio_playback = false;
  std::uint64_t native_audio_source_requests = 0;
  bool timing_fixture = false;
  bool original_os_host_pacing = false;
  std::uint64_t original_window_pump_vi = UINT64_MAX;
  bool original_os_host_anchor_ready = false;
  jfg::audio::ViPlaybackClock original_os_host_clock;

  std::unique_ptr<GuestThreadTransport<recomp_context>> guest_transport;
  std::uint32_t guest_epc = 0U, guest_cause = 0U;
  jfg::boot::ReferenceCompare guest_timer;
  std::uint32_t guest_active_rsp_task = 0U, guest_active_rsp_type = 0U;
  std::uint64_t guest_exceptions = 0U;
  jfg::AsyncDiagnosticFile guest_clock_trace;
  struct FileCloser { void operator()(FILE* file) const noexcept { std::fclose(file); } };
  std::unique_ptr<FILE, FileCloser> device_event_stream;
  jfg_device_event_probe device_event_probe{};
  std::ofstream eret_transfer_stream;
  EretTransferProbe eret_transfer_probe;
  std::ofstream instruction_effect_stream;
  InstructionEffectTrace instruction_effect_trace;
  std::uint32_t instruction_effect_update = 0U, instruction_effect_section = 0U;
  std::uint32_t device_event_previous_pc = 0U, device_event_previous_word = 0U;
  std::uint32_t device_event_previous_thread = 0U;
  bool device_event_successor = false;
  jfg::boot::TlbRegisters32 tlb_registers;
  std::vector<std::uint32_t> saved_rcp_masks;
  std::array<std::uint8_t, jfg::kPifRamBytes> pif_ram{};
  bool cic_response_pending = false;
  std::uint64_t generated_calls = 0U;
  std::uint64_t mapped_calls = 0U;
  std::uint64_t dispatch_calls = 0U;
  std::uint64_t sound_queue_recoveries = 0U;
  std::uint64_t phase9_player_control_calls = 0U;
  std::uint64_t phase9_weapon_update_calls = 0U;
  std::uint64_t phase9_weapon_fire_held_updates = 0U;
  std::uint64_t phase9_weapon_fire_pressed_updates = 0U;
  std::uint64_t phase9_weapon_dummy_fire_calls = 0U;
  std::uint64_t phase9_weapon_fire_calls = 0U;
  std::uint64_t phase9_weapon_shot_calls = 0U;
  std::uint64_t phase9_weapon_hit_calls = 0U;
  std::uint64_t phase9_enemy_kill_calls = 0U;
  std::uint64_t phase9_collision_calls = 0U;
  std::uint64_t phase9_particle_update_calls = 0U;
  std::uint64_t phase9_cutscene_active_calls = 0U;
  std::uint64_t phase9_cutscene_camera_calls = 0U;
  std::uint64_t phase9_level_change_calls = 0U;
  std::uint64_t phase9_death_restart_calls = 0U;
  std::uint64_t health_overlay_death_reload_generation = 0U;
  std::uint64_t phase9_player_hit_check_calls = 0U;
  std::uint32_t phase9_player_actor = 0U;
  jfg::mod::NavigationMod navigation_mod;
  std::filesystem::path navigation_output;
  jfg::AsyncBoundedTrace movement_trace, jump_trace;
  jfg::AsyncSnapshots snapshot_writer;
  std::shared_ptr<const std::string> navigation_mesh_export;
  std::uint64_t phase9_hints_control_calls = 0U;
  std::uint64_t phase9_hints_talk_calls = 0U;
  std::uint32_t phase9_hints_actor = 0U;
  std::uint64_t phase9_king_bear_control_calls = 0U;
  std::uint32_t phase9_king_bear_actor = 0U;
  std::uint32_t phase9_king_bear_callback = 0U;
  std::uint64_t phase9_hinttext_start_calls = 0U;
  std::uint64_t phase9_hinttext_stop_calls = 0U;
  std::uint64_t phase9_hinttext_active_calls = 0U;
  std::uint64_t phase9_hinttext_active_zero_returns = 0U;
  std::uint64_t phase9_hinttext_active_nonzero_returns = 0U;
  std::uint64_t phase9_hinttext_update_calls = 0U;
  std::uint64_t phase9_hinttext_advance_calls = 0U;
  std::uint64_t phase9_hinttext_accept_calls = 0U;
  std::uint32_t phase9_hinttext_active_last_return = 0U;
  std::uint64_t interrupt_timeslices = 0U;
  std::uint64_t rsp_yield_requests = 0U, rsp_yield_queries = 0U;
  std::unordered_map<std::uint32_t, std::uint32_t> empty_receive_polls;
  std::uint64_t receive_successes = 0U;
  std::uint64_t receive_empties = 0U;
  std::uint64_t receive_blocks = 0U;
  std::uint32_t last_receive_queue = 0U;
  std::uint32_t last_receive_block = 0U;
  std::int32_t last_receive_result = 0;
  std::uint64_t queue_create_calls = 0U;
  std::uint64_t queue_send_calls = 0U;
  std::uint64_t queue_recv_calls = 0U;
  std::uint64_t sp_task_load_calls = 0U;
  std::uint64_t sp_task_start_calls = 0U;
  std::uint64_t controller_read_start_calls = 0U;
  std::uint64_t controller_get_data_calls = 0U;
  std::uint64_t vi_swap_calls = 0U;
  std::uint64_t graphics_tasks = 0U;
  std::uint64_t graphics_commands = 0U;
  std::uint64_t graphics_triangles = 0U;
  std::uint64_t presented_frames = 0U;
  bool frame_captured = false;
  std::uint64_t controller_samples = 0U;
  std::uint64_t non_neutral_controller_samples = 0U;
  std::uint64_t non_neutral_controller_writes = 0U;
  std::uint64_t controller_disconnects = 0U;
  std::uint64_t controller_reconnects = 0U;
  std::uint64_t game_pressed_observations = 0U;
  std::uint16_t last_game_pressed_buttons = 0U;
  std::uint64_t game_stick_observations = 0U;
  std::int8_t last_game_stick_x = 0;
  std::int8_t last_game_stick_y = 0;
  std::uint64_t menu_stick_observations = 0U;
  std::int8_t last_menu_stick_x = 0;
  std::int8_t last_menu_stick_y = 0;
  std::size_t input_replay_event_count = 0U;
  std::uint64_t flash_persist_count = 0U;
  bool flash_image_loaded = false;
  bool flash_image_created = false;
  std::uint32_t active_bzero_address = 0U;
  std::uint32_t active_bzero_length = 0U;
#if defined(JFG_PHASE8_LIVE_RUNTIME)
  jfg::FlashRamStore flashram;
  bool fast_replay = false;
  bool realtime_replay = false;
  bool exit_requested = false;
  bool modern_controls_active = false;
  // Input intent belongs to this native player update, never the last observed actor.
  struct ModernRollUpdate {
    std::uint32_t actor=0,control=0;
    std::uint8_t flags=0,mode=0;
    bool connected=false;
  };
  ModernRollUpdate modern_roll_update{};
  jfg::CutsceneSkipHold cutscene_skip_hold;
  std::atomic<std::uint64_t> cutscene_skip_scene{0}, cutscene_skip_request{0};
  std::atomic<unsigned> cutscene_skip_gesture{0};
  bool cutscene_skip_release=false;
  std::array<std::uint64_t,4> cutscene_input_observation{};
  std::uint32_t cutscene_physical_actions=0;
  std::uint16_t cutscene_mapped_buttons=0;
  std::uint64_t cutscene_trace_until_vi=0;
  struct CutsceneCapture {std::uint64_t vi=0;unsigned width=0,height=0;std::vector<char> rgb;};
  std::vector<CutsceneCapture> cutscene_capture;
  bool cutscene_capture_armed=false,cutscene_capture_started=false;
  std::uint64_t cutscene_capture_until_vi=0;
  bool diagnostic_cutscene_capture=[] {
#if defined(_WIN32)
    char flag[2]{};
    return GetEnvironmentVariableA("JFG_DIAGNOSTIC_CUTSCENE_FLASH_CAPTURE",flag,2U)==1U && flag[0]=='1';
#else
    return false;
#endif
  }();
  std::uint64_t cutscene_cached_scene=0;
  jfg::CutsceneScriptInspection cutscene_script;
  bool cutscene_chain=false;
  std::uint64_t cutscene_transition_started=0;
  unsigned cutscene_chain_level=0,cutscene_chain_group=0,cutscene_chain_count=0;

  jfg::DayNightFogFrames daynight_fog_frames;
  jfg::NativeCutscenePrompt cutscene_prompt{};
  std::unordered_map<std::uint32_t,jfg::NativeCutscenePrompt> cutscene_prompt_submissions;

  std::array<jfg::PcInputConfig,4> pc_input{};
  std::array<jfg::ModernControlsConfig,4> modern_controls{};
  std::array<jfg::ModernAimLatch,4> modern_aim_latch{};
  std::array<jfg::ModernScopeZoom,4> modern_scope_zoom{};
  std::array<std::uint8_t,4> modern_live_flags{};
  std::array<bool,4> modern_physical_neutral{true,true,true,true};
  std::array<jfg::ControllerReplaySample,4> pc_frames{};
  std::array<bool,4> pc_mouse_used{};
  bool pc_record_extended = false;
  std::array<jfg::PcOrbit,4> pc_orbits{};
  std::array<jfg::PcShoulder,4> pc_shoulders{};
  std::array<jfg::ModernMovementLatch,4> modern_movement_latch{};
  std::uint32_t pc_shoulder_actor=0;
  std::uint32_t pc_animation_actor=0;
  float pc_camera_ticks=0;
  bool pc_camera_resolved_valid=false;
  jfg::PcOrbitPoint pc_camera_resolved{};
  std::uint32_t pc_camera_actor=0,pc_camera_control=0,pc_camera_stack=0;
  jfg::PcLookDelta pc_camera_look{};
  std::uint64_t pc_aim_calls = 0, pc_direct_aim_calls = 0;
  std::array<jfg::PcLookDelta,4> pc_aim{};
  std::array<jfg::PcStickMotion,4> pc_stick_motion{};
  std::array<jfg::PcFloydLook,4> pc_floyd_look{};
  std::array<jfg::PcScopeMotion,4> pc_scope_motion{};
  std::array<jfg::PcBossAimMotion,4> pc_boss_aim_motion{};
  std::array<unsigned,4> pc_boss_aim_modes{};
  std::array<std::uint32_t,4> pc_boss_aim_controls{};
  std::array<jfg::ModernScopeSensitivity,4> modern_scope_sensitivity{};
  std::array<jfg::PcDeviceReleaseGate,4> pc_device_release{};
  std::array<int,4> pc_devices{-2,-2,-2,-2};
  std::array<jfg::PcRumbleEffect,4> pc_rumble_effects{};
  std::array<std::uint16_t,4> pc_rumble_levels{};
  std::array<int,4> pc_rumble_devices{-2,-2,-2,-2};
  std::array<bool,4> pc_device_ready{};
  std::unique_ptr<jfg::PcRumbleOutput> pc_rumble_output;
  jfg::PcWheelPulses pc_wheel;
  jfg::PcMouseMotion pc_mouse;
  jfg::MouseInputDiagnostics mouse_diagnostics;
  jfg::MouseSupportHistory mouse_support_history;
  std::array<std::array<std::uint16_t,13>,4> mouse_support_players{};
  std::uint64_t mouse_support_last=0,mouse_support_origin=0;
  int pc_wheel_key = 0;
  std::atomic<bool> pc_mouse_captured{false};
  bool pc_input_blocked = true, pc_raw_available = false;
  jfg::WindowInputMailbox window_input;
  jfg::MenuPointerFrame menu_pointer_frame{};
  jfg::GuestMenuState guest_menu{};
  jfg::GuestMenuPointer menu_pointer;
  std::array<jfg::GuestMenuConfirm,4> menu_confirm;
  std::optional<jfg::GuestMenuState> menu_selection_feedback;
  jfg::MenuPointerReplay menu_pointer_replay;

  std::array<bool, 256U> host_keys{};
  std::array<bool, 256U> host_key_presses{};
  std::uint16_t latched_controller_buttons = 0U;
  std::int8_t latched_controller_stick_x = 0;
  std::int8_t latched_controller_stick_y = 0;
  bool latched_controller_connected = true;
  jfg::DeterministicInputReplay input_replay;
  bool input_replay_loaded = false;
  bool input_replay_by_poll = false;
  bool input_replay_recorded_time = false;
  bool input_replay_gameplay_time = false, replay_gameplay_clock_ready = false;
  std::size_t replay_gameplay_first_poll = 0;
  std::uint64_t replay_gameplay_origin_vi = 0;
  RecordedInputTimeline recorded_input_timeline;
  std::string frame_capture_path;
  std::string rdram_capture_path;
  const recomp_context* private_fault_cpu = nullptr; // Explicit RAM-capture sessions only.
  bool private_model_pointer_watch = false;
  bool private_model_hardware_watch = false;
  bool private_model_page_watch = false;
  bool private_model_pages_ready = false;
  std::uintptr_t private_memory_writer_pc = 0U;
  bool private_model_write_trap = false;
  std::uint32_t private_model_write_offset = (game_data("diagnostic.currentModel")&0x1FFFFFFFU);

  std::uint32_t private_model_pointer = 0U;
  std::array<std::uint32_t,64> private_model_probe_pcs{};
  std::uint64_t private_model_probe_position = 0U;

  std::string progress_path;
  std::string input_record_path;
  std::string retrace_hash_path;
  jfg::AsyncDiagnosticFile input_record;
  std::ofstream phase95_poll_trace;
  std::ofstream retrace_hash_trace;
  std::ofstream update_hash_trace;
  std::ofstream update_word_trace;
  std::uint32_t update_word_address = 0U;
  std::ofstream controller_return_trace;
  std::uint32_t controller_return_rows = 0U;
  std::ofstream poll_hash_trace;
  std::ofstream event_trace;
  std::array<std::pair<std::uint64_t, std::uint64_t>, 2U> event_ranges{};
  std::size_t event_range_count = 0U;
  std::uint64_t event_trace_rows = 0U;
  std::uint64_t completed_game_updates = 0U;
  std::uint64_t timing_game_updates = 0U;
  std::uint64_t focus_update_start = 0U;
  std::uint64_t focus_update_end = 0U;
  std::uint32_t watch_word_address = 0U;
  std::ofstream watch_word_trace;
  std::uint32_t watch_dispatch_depth = 0U;
  std::uint32_t watch_dispatch_changes = 0U;
  std::uint32_t entry_probe_target = 0U;
  std::ofstream entry_probe_trace;
  std::uint32_t entry_probe_hits = 0U;
  std::ofstream entry_fpu_trace;
  std::ofstream entry_memory_trace;
  std::ofstream entry_gpr_trace;
  std::ofstream instruction_probe_trace;
  std::uint32_t instruction_probe_hits = 0U;
  std::vector<std::uint32_t> point_probe_pcs;
  std::vector<std::uint32_t> point_probe_words;
  std::ofstream point_probe_trace;
  std::uint32_t point_probe_hits = 0U;
  jfg::AsyncDiagnosticFile timing_trace;
  jfg::AsyncBoundedTrace reticle_trace;
  bool reticle_trace_started = false, reticle_trace_active = false, reticle_trace_enabled = false;
  std::uint32_t reticle_actor = 0U, reticle_control = 0U;
  GameplayTrace gameplay_trace;
  // Explicit copied-save fixture; never accepted in normal Play.
  std::uint64_t diagnostic_ichor_warp_vi = 0;
  bool diagnostic_ichor_warp_done = false;

  // Optional timing diagnostics; never modify the guest clock or memory.
  bool gameplay_trace_actors = true;
  // Internal qualification only. No launcher/profile switch selects this policy.
  bool diagnostic_host_clock_requested = false;
  bool diagnostic_native_recovery_enabled = true;
  bool flying_motion_adapter_enabled = true;
  jfg::flight::ReferenceCadence flying_motion_reference =
      jfg::flight::reference_for(jfg::game::linked::descriptor.revision);
  std::uint64_t diagnostic_clock_boundary_vi = 0;
  bool diagnostic_clock_boundary_seen = false;
  unsigned diagnostic_boundary_stall_ms = 0;
  // IO/exception boundaries force the full handler; ordinary instructions
  // share a bounded host-clock sampling quantum without modeled time charges.
  static constexpr unsigned kHostClockPollInstructions = 128U;
  HostCountClock host_count_clock;
  CountSampleTape native_clock_samples;
  std::uint64_t diagnostic_clock_release_vi = 0;
  bool diagnostic_clock_released = false;
  std::vector<char> native_clock_sample_buffer;
  std::ofstream native_clock_sample_output;
  std::ifstream native_clock_sample_input;
  HostDeadlineWait host_deadline_wait;
  std::uint64_t profile_host_wait_us = 0U;
  std::uint64_t profile_idle_count_ticks = 0U;
  bool diagnostic_cpu_costs = false;
  bool resident_math_enabled=false;
  bool diagnostic_bsp_enabled=false;
  std::uint64_t bsp_native_calls=0,bsp_clock_refreshes=0;
  std::uint64_t pure_angle_calls=0,pure_diff_calls=0,pure_trig_calls=0;
  bool diagnostic_update_cycles = false;
  bool native_cache_all_enabled=false;
  std::uint64_t native_cache_all_calls=0;
  bool native_shadow_filter_enabled = false;
  std::uint64_t native_shadow_filter_calls = 0U;
  unsigned diagnostic_function_profile=0;
  bool diagnostic_gpu_costs=false;
  bool diagnostic_host_stages=false;
  std::uint64_t diagnostic_profile_first_vi=3300,diagnostic_profile_last_vi=4500;
  struct FunctionCost { std::uint64_t self_ns=0, inclusive_ns=0, calls=0; };
  std::unordered_map<std::uint32_t, FunctionCost> profile_function_costs;
  std::uint64_t profile_function_self_ns = 0;
  std::uint64_t profile_out_of_line_instructions = 0U;
  struct ModelThreadCost {std::uint32_t id=0;std::array<std::uint64_t,6> value{};};
  std::array<ModelThreadCost,32> profile_model_threads{};
  std::array<std::uint64_t,6> profile_model_last{};
  std::uint32_t profile_model_owner=0;

  std::uint64_t profile_full_execution_probes = 0U;
  std::uint64_t profile_native_handler_ns = 0U;
  std::uint64_t profile_dispatch_prefix_ns = 0U, profile_dispatch_prefix_calls = 0U;
  std::uint64_t profile_overlay_inventory_ns = 0U, profile_overlay_inventory_calls = 0U;
  std::uint64_t profile_relocation_ns = 0U, profile_relocation_calls = 0U, profile_relocation_probes = 0U;
  std::uint64_t gameplay_trace_vi = UINT64_MAX;
  std::uint64_t gameplay_trace_updates = 0U;
  std::array<std::array<std::uint64_t, 56>, 256> gameplay_actor_previous{};
  std::array<bool, 256> gameplay_actor_seen{};
  bool actor_timing_trace = false;
  std::uint64_t last_actor_trace_retrace =
      (std::numeric_limits<std::uint64_t>::max)();
  bool host_frame_start_initialized = false;
  std::chrono::steady_clock::time_point host_frame_start{};
  bool present_time_initialized = false;
  std::chrono::steady_clock::time_point present_time{};
  std::uint64_t host_frame_interval_max_us = 0U;
  std::uint64_t present_interval_max_us = 0U;
  std::uint64_t graphics_prepare_max_us = 0U;
  std::uint64_t graphics_submit_max_us = 0U;
  std::uint64_t graphics_present_max_us = 0U;
  std::uint64_t host_frames_over_25ms = 0U;
  std::uint64_t host_frames_over_50ms = 0U;
  std::uint64_t host_frames_over_100ms = 0U;
  std::uint64_t last_progress_retrace =
      (std::numeric_limits<std::uint64_t>::max)();
  std::filesystem::path flash_path;
  std::filesystem::path controller_pak_path;
  std::unique_ptr<jfg::ControllerAccessoryBus> controller_accessory_bus;
  jfg::ControllerPakSession controller_pak_session;
  bool controller_pak_loaded = false;
  bool controller_pak_created = false;
  std::array<LiveViFieldRegisters, 2U> vi_fields{};
  std::uint32_t vi_mode_horizontal_start = 0x006C02ECU;
  bool vi_mode_configured = false;
  bool host_frame_deadline_initialized = false;
  std::chrono::steady_clock::time_point host_frame_deadline{};
  jfg::Rt64ViRegisters rt64_vi;
  std::uint32_t vi_mode_control = 0U;
  void *native_window = nullptr;
  jfg::ViPresentationSize window_presentation{320U, 240U};
  bool window_widescreen=false;
  std::unique_ptr<jfg::Rt64Shell> rt64_shell;
  std::vector<std::byte> rt64_rdram;
  std::uint32_t graphics_color_image = 0U;
  bool graphics_frame_ready = false;
  std::array<std::uint32_t, 64U> recent_graphics_color_images{};
  std::array<std::uint32_t, 64U> recent_graphics_command_addresses{};
  std::array<std::uint32_t, 64U> recent_graphics_vi_selections{};
  std::array<std::uint32_t, 64U> recent_graphics_matrix_commands{};
  std::array<std::uint32_t, 64U> recent_graphics_vertices_loaded{};
  std::array<std::uint32_t, 64U> recent_graphics_vertices_in_clip{};
  std::array<std::uint32_t, 64U> recent_graphics_triangles{};
  std::size_t recent_graphics_position = 0U;
  std::vector<PendingLiveGraphicsTask> pending_graphics_tasks;
  std::vector<LiveGraphicsOverlayShadow> graphics_overlay_shadows;
  // Immutable ROM-derived overlay shadows. Restore these bytes for each task;
  // display-list traversal still patches that task's private snapshot.
  std::vector<std::byte> graphics_overlay_initial_data;
  std::vector<GraphicsSnapshotCache> graphics_snapshot_pool;
  HostAudioDevice host_audio;
  std::uint64_t audio_task_microseconds = 0U;
  std::uint64_t graphics_prepare_microseconds = 0U;
  std::uint64_t graphics_submit_microseconds = 0U;
  std::uint64_t graphics_present_microseconds = 0U;
  std::array<std::uint32_t, 64U> recent_matrix_conversion_sources{};
  std::array<std::uint32_t, 64U> recent_matrix_conversion_destinations{};
  std::array<std::array<std::uint32_t, 4U>, 64U>
      recent_matrix_conversion_first_rows{};
  std::array<std::array<std::uint32_t, 4U>, 64U>
      recent_matrix_conversion_output_words{};
  std::size_t recent_matrix_conversion_position = 0U;
  std::array<std::array<std::uint32_t, 3U>, 64U> recent_matrix_cat_args{};
  std::array<std::array<std::uint32_t, 9U>, 64U>
      recent_matrix_cat_words{};
  std::size_t recent_matrix_cat_position = 0U;
  // Resident owners are bound; heap matrix addresses are acquired from the
  // actual matrix destination below. Historical US heap addresses are not
  // stable across sessions or revisions and must not seed this observer.
  std::array<std::uint32_t, 8U> matrix_watch_addresses{
      game_data("diagnostic.cameraMatrixSource"), (game_data("diagnostic.cameraViewState")+4U)};
  std::array<std::uint32_t, 8U> matrix_watch_words{};
  std::array<std::uint32_t, 64U> recent_matrix_watch_addresses{};
  std::array<std::uint32_t, 64U> recent_matrix_watch_before{};
  std::array<std::uint32_t, 64U> recent_matrix_watch_after{};
  std::array<std::uint32_t, 64U> recent_matrix_watch_targets{};
  std::array<std::uint32_t, 64U> recent_matrix_watch_callers{};
  std::array<std::uint32_t, 64U> recent_matrix_watch_current_targets{};
  std::array<std::uint32_t, 64U> recent_matrix_watch_return_addresses{};
  std::size_t recent_matrix_watch_position = 0U;
  std::array<std::uint32_t, 6U> poison_matrix_watch{};
  std::array<std::uint32_t, 16U> poison_dispatch_history{};
  jfg::Rt64ShellError last_rt64_error = jfg::Rt64ShellError::none;
  std::array<std::uint32_t, 6U> last_graphics_descriptor{};
  std::uint32_t last_graphics_command_address = 0U;
  std::uint32_t last_graphics_command_word = 0U;
  std::uint32_t materialize_reject_reason = 0U;
  std::uint32_t materialize_reject_address = 0U;
  std::uint32_t materialize_reject_word0 = 0U;
  std::uint32_t materialize_reject_word1 = 0U;
  std::uint32_t materialize_parent_address = 0U;
  std::uint32_t materialize_parent_word0 = 0U;
  std::uint32_t materialize_parent_word1 = 0U;
  std::uint32_t materialize_block_address = 0U;
  std::uint32_t materialize_parent_segment_base = 0U;
#endif
  std::array<std::uint64_t, kMappingCount> mapped_call_counts{};
  std::uint32_t loaded_rsp_task = 0U;
  std::uint32_t loaded_rsp_task_type = 0U;
  std::uint64_t decoded_audio_tasks = 0U;
  bool audio_device_initialized = false;
  bool audio_device_started = false;
  std::uint32_t audio_device_frequency = 0U;
  std::uint64_t audio_device_buffers = 0U;
  std::uint64_t audio_device_queued_bytes = 0U;
  std::uint64_t audio_device_consumed_bytes = 0U;
  std::uint64_t audio_device_consumed_ms = 0U;
  std::uint64_t audio_device_underruns = 0U;
  std::uint64_t audio_device_overruns = 0U;
  int controller_read_thread = -1;
  std::uint64_t si_receive_calls = 0U;
  std::uint32_t last_si_receive_return = 0U;
  std::uint32_t last_si_receive_block = 0U;
  std::array<std::uint32_t, 32U> recent_dispatches{};
  std::size_t recent_dispatch_position = 0U;
  std::array<std::uint32_t, 16U> last_si_dispatch_trace{};
};
} // namespace detail
} // namespace jfg::boot::native
