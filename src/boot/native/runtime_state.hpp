#pragma once
// Private shared simulation state. Ownership stays with run_child.
#include "jfg/renderer/enhanced_shadow_footprint.hpp"
#include "jfg/renderer/door_indicator_presentation.hpp"
#include "jfg/renderer/camera_helper_presentation.hpp"
#include "jfg/renderer/camera_trig_precision.hpp"
#include "jfg/renderer/native_blur_mode.hpp"
#include "jfg/renderer/rain_fade.hpp"
#include "jfg/renderer/fog_settings.hpp"
#include "jfg/runtime/execution_local.hpp"
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
#include "jfg/boot/sync_print_sink.hpp"
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
#include "jfg/boot/reference_flash_bus.hpp"
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
constexpr std::uint32_t kRunlinkModuleTablePointer = 0x800FEAA0U;
constexpr std::size_t kRunlinkOverlaySlotCount = 157U;
constexpr std::uint32_t kHintTextOverlaySection = 7U;
constexpr std::uint64_t kCountTicksPerViFrame = 781250U;
constexpr std::uint64_t kCountTicksPerDispatch = 64U;
// A guest may wait for asynchronous hardware by polling an empty libultra
// queue without blocking. Bound only that repeated poll pattern so ordinary
// generated execution keeps its established cooperative timing.
constexpr std::uint32_t kEmptyReceivePollTimeslice = 2048U;
constexpr std::array<std::uint8_t, 20U> kSupportedRomSha1 = {
    0x49U, 0x3cU, 0xedU, 0x90U, 0x08U, 0xdbU, 0xe9U, 0x32U, 0xd6U, 0xe9U,
    0x11U, 0x79U, 0xb6U, 0x8eU, 0x86U, 0x30U, 0xcfU, 0x23U, 0xa0U, 0x23U,
};
struct Mapping {
  std::uint32_t vram;
  const char *name;
};
constexpr Mapping kMappings[] = {
#include JFG_PHASE6_DISPATCH_TABLE_INC
};
constexpr std::size_t kMappingCount = sizeof(kMappings) / sizeof(kMappings[0]);
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
  jfg::PresentationIdentityTracker presentation_identities;
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
  std::uint64_t sync_print_sink_calls = 0U;
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
  std::uint32_t private_model_write_offset = 0xf5b0cU;

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
  std::array<std::uint32_t, 8U> matrix_watch_addresses{
      0x801FDA80U, 0x801FDAC0U, 0x802239A0U, 0x802239E0U,
      0x800FAAF0U, 0x800FAF7CU};
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
