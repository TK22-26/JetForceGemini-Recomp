#pragma once
#include "runtime_state.hpp"
namespace jfg::boot::native::detail {
enum class SyntheticOverlayPublication : std::uint8_t {
  ensure_active,
  reload,
};
void stop_pc_rumble(State& state) noexcept;
#if defined(JFG_PHASE8_LIVE_RUNTIME)
bool validate_persistent_profile_paths(bool play_mode);
#endif

#if defined(_WIN32) && defined(JFG_PHASE8_LIVE_RUNTIME)
void support_mouse_snapshot(State& state) noexcept;
bool host_key_down(const State &state, const int virtual_key) noexcept;
void trace_phase9_event(State &state, const char *event,
                        const std::uint64_t poll);
bool read_xinput_device(int device,
                        jfg::StandardControllerSample &sample) noexcept;
bool pc_rumble_eligible(const State& state,const NativeGameMemory& ram,std::size_t port);
void sync_pc_rumble(State& state);
void request_pc_rumble(State& state,std::uint32_t target,const recomp_context& context);
bool modern_controls_selected(const State &state,std::size_t port);
unsigned modern_actor_port(const State& state,std::uint32_t actor);
jfg::PcInputConfig active_pc_input(const State &state,std::size_t port);
void trace_modern_view_reset(State& state, std::size_t port, unsigned reason);
bool modern_shoulder_current(const State &state,std::size_t port,std::uint32_t actor);
bool modern_free_movement_current(const State& state,std::size_t port);
bool modern_landing_view_current(const State& state,std::uint32_t actor);
bool modern_ledge_view_current(const State& state,std::uint32_t actor);
bool modern_swimming_view_current(const State& state,std::uint32_t actor);
bool modern_shoulder_camera_current(const State& state,std::size_t port,std::uint32_t actor);
bool modern_air_aim_active(const State &state,std::uint32_t actor,std::uint32_t control);
void modern_air_aim_update(State &state,std::uint32_t actor,std::uint32_t control,
                           const recomp_context &context);
void modern_shoulder_physics(State &state,std::uint32_t target,const recomp_context &context);
unsigned modern_animation_family(State &state,unsigned character,unsigned requested);
void modern_shoulder_aim_camera(State &state,std::uint32_t target,
                                std::uint32_t actor,std::uint32_t control);
bool diagnostic_weather();
bool diagnostic_reticle_lines();
void reload_controller_ports(State &state);
jfg::ControllerPortSample sample_keyboard_port(const State &state,std::size_t port);
void sample_controller_ports(State &state,bool discover_sdl=true);
jfg::mod::DialogueState navigation_dialogue(State &state);
jfg::GuestMenuState read_pause_menu(State &state);
jfg::GuestMenuState read_guest_menu(State &state) noexcept;
bool select_guest_menu(State& state, jfg::GuestMenuKind kind, int target) noexcept;
void sample_live_controller(State &state) noexcept;
bool service_host_audio(State &state, const bool pace);
void service_live_window(State &state);
bool write_live_frame_capture(State &state);
bool write_logical_rdram_capture(const State &state,
                                 const std::filesystem::path &path);
bool write_private_rdram_capture(const State &state);
bool write_private_rt64_snapshot(
    const State &state, const std::span<const std::byte> snapshot);
bool write_mod_export(State &state, const std::filesystem::path &path, const std::string &text);
void service_navigation_inventory_requests(State &state, bool publish);
void update_navigation_mod(State &state);
jfg::DayNightFog capture_daynight_fog(State &state);
void trace_daynight_atmosphere(State &state, std::uint32_t target,
                              const std::array<std::uint32_t, 5> &outputs);
void trace_gameplay_state(State &state, bool update);
void write_actor_timing_trace(State &state);
std::optional<std::string> hash_logical_rdram_region(
    const State &state, const std::uint32_t guest_address,
    const std::size_t length);
void write_retrace_semantic_hash(State &state, std::ostream *update_output = nullptr,
                                std::ostream *poll_output = nullptr);
void write_private_progress(State &state,
                            const char *stage = "retrace");
#endif

#if defined(JFG_PHASE8_LIVE_RUNTIME)
bool configure_live_vi_mode(State &state, hle::GuestMemory &memory,
                            const std::uint32_t address);
bool apply_live_vi_field(State &state, const std::uint32_t framebuffer);
bool configure_flash_path(State &state, const char *path);
bool configure_controller_pak_path(State &state, const char *path);
bool persist_controller_pak(State &state);
bool mirror_synthetic_overlay_in_runlink(
    State &state, const JfgGeneratedSectionMetadata &metadata);
bool note_guest_cold_overlay_load(State &state, const std::uint32_t slot);
bool ensure_guest_overlay_allocation(
    State &state, const JfgGeneratedSectionMetadata &metadata,
    recomp_context &caller_context);
bool publish_synthetic_overlay(
    State &state, const std::uint32_t section,
    const JfgGeneratedSectionMetadata &metadata,
    SyntheticOverlayPublication publication =
        SyntheticOverlayPublication::ensure_active);
#endif


bool resolve_bzero_host_offset(const State &state, const std::uint32_t address,
                               const std::uint32_t length,
                               std::size_t &host_offset);

#if defined(JFG_PHASE8_LIVE_RUNTIME)
bool guest_task_blob(const State &state, const std::uint32_t address,
                     const std::size_t size,
                     std::vector<std::byte> &output);
std::uint32_t translate_live_graphics_address(
    const State &state, const std::uint32_t address) noexcept;
bool materialize_live_graphics_overlays(
    State &state, std::vector<std::byte> &snapshot,
    const std::uint32_t command_address,
    const std::uint32_t command_count,
    std::vector<jfg::Rt64RdramRange>* changed,
    bool overlays_initialized, std::span<const jfg::Rt64RdramRange> prior_dirty,
    std::vector<jfg::Rt64RdramRange>& overlay_dirty);
bool execute_live_audio_task(State &state, hle::GuestMemory &memory);
#if defined(_WIN32)
bool initialize_live_renderer(State &state, LiveRt64Window &window);
bool execute_live_graphics_task(State &state, hle::GuestMemory &memory);
#endif

#endif


void hash_u32(jfg::testkernel::Sha256 &hasher, const std::uint32_t value);

void hash_u64(jfg::testkernel::Sha256 &hasher, const std::uint64_t value);

std::string journal_hash(const State &state);

std::string mmio_trace_text(const State &state);

std::string state_hash(const State &state);

void ledger(State &state, std::string_view category, std::string_view operation,
            std::uint32_t guest_target);

#if defined(_WIN32) && defined(JFG_PHASE8_LIVE_RUNTIME)
void private_abort_capture(int signal_number);
bool arm_private_memory_pages(State& state);
LONG CALLBACK private_page_write_observer(EXCEPTION_POINTERS* exception);
bool arm_private_model_write_watch(State& state);
LONG CALLBACK private_model_write_observer(EXCEPTION_POINTERS* exception);
LONG WINAPI child_exception_filter(EXCEPTION_POINTERS *exception);
#endif


[[noreturn]] void fail_closed_dispatch(State &state, std::string_view category,
                                       std::string_view operation,
                                       std::uint32_t guest_target);

[[noreturn]] void stable_vi_gate(State &state);

#if defined(JFG_PHASE8_LIVE_RUNTIME)
[[noreturn]] void probe_target_gate(State &state);
#endif

#if defined(_WIN32) && defined(JFG_PHASE8_LIVE_RUNTIME)
[[noreturn]] void play_exit(State &state);
#endif


[[noreturn]] void retrace_gate(State &state);

#if defined(_WIN32) && defined(JFG_PHASE8_LIVE_RUNTIME)
void complete_guest_sp_status(State &state, const std::uint32_t target);
void complete_pending_live_graphics_tasks(
    State &state, const std::uint32_t target,
    const bool require_offscreen_target = false);
#endif


void set_result(recomp_context *context, std::int32_t result);

#if defined(JFG_PHASE8_LIVE_RUNTIME)
bool complete_flash_operation(State &state);
#endif


bool guest_byte_offset(const std::uint32_t address, std::size_t &offset);

bool write_guest_byte(State &state, const std::uint32_t address,
                      const std::uint8_t value);

[[noreturn]] void fail_closed_overlay_publication(State &state,
                                                 const std::uint32_t target);

void trace_si_timing(State &state, const char *event, std::uint32_t queue,
                     std::uint32_t caller, std::int32_t result);

void service_si_deadline(State &state, const std::uint32_t target);

void schedule_si_deadline(State &state, const std::uint32_t target);

void service_timers(State &state, const std::uint32_t target);

void trace_guest_clock(State &state, const char *event, std::uint32_t address);

void advance_legacy_vi_clock(State &state, const std::uint32_t target);

void present_completed_video(State &state, const std::uint32_t target);

void latch_next_vi_framebuffer(State &state, const std::uint32_t target);

void deliver_legacy_si_completion(State &state, const std::uint32_t target);

void deliver_vi_interrupt(State &state, const std::uint32_t target);

void service_vi_frame(State &state, const std::uint32_t target);

[[maybe_unused]] void note_hints_control_call(State &state, const std::uint32_t target,
                             const recomp_context &context);

#if defined(_WIN32) && defined(JFG_PHASE8_LIVE_RUNTIME)
std::array<std::uint64_t,6> sample_model_thread(State& state,std::uint32_t query,
    std::uint32_t next=UINT32_MAX);
bool cutscene_actors_reviewed(const NativeGameMemory& ram);
bool update_cutscene_review(State& state,recomp_context& context);
std::uint8_t* cutscene_credits_memory(State& state,const NativeGameMemory& ram);
void update_cutscene_completion(State& state,recomp_context& context);
#endif


int dispatch(void *opaque, std::int32_t address, std::uint8_t *rdram,
             recomp_context *context);

bool read_supported_rom(const char *path, std::vector<std::uint8_t> &rom);

#if defined(_WIN32) && defined(JFG_PHASE8_LIVE_RUNTIME)
void emit_instruction_effect(State& state, const recomp_context& cpu,
    unsigned phase, unsigned section, unsigned pc, unsigned word,
    std::uint32_t target = 0U, std::uint32_t selected_owner = 0U);
extern State* g_active_child_state;
extern thread_local volatile bool private_model_watch_armed;
#endif

void initialize_original_timing_cache(State& state) noexcept;
int native_cpu_operation(void* opaque, void* guest_context, std::uint32_t operation,
    std::uint32_t selector, std::uint64_t* value);
bool range(std::uint64_t,std::uint64_t,std::size_t);
bool write_boot_word(std::vector<std::uint8_t>&,std::uint32_t,std::uint32_t);
bool initialize_ipl_state(std::vector<std::uint8_t>&,std::span<const std::uint8_t>);
bool load_static_sections(const std::vector<std::uint8_t>&,std::vector<std::uint8_t>&);
std::array<std::uint8_t,20U> sha1(std::span<const std::uint8_t>);
constexpr bool is_immediate_offscreen_task_candidate(
    const std::uint32_t command_size) noexcept {
  // Both observed tiny actor passes finish within the same VI in BizHawk.
  // The renderer still verifies that their color target is not displayed.
  return command_size == 0x1BU || command_size == 0x1FU;
}
} // namespace jfg::boot::native::detail
