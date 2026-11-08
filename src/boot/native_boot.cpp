#include "native/runtime_services.hpp"
#include "native/process_supervisor.hpp"
#if defined(JFG_NATIVE_BUILD_HEADER)
#include JFG_NATIVE_BUILD_HEADER
#endif
extern "C" { JfgOriginalTimingFast* jfg_original_timing_state = nullptr; }
namespace jfg::boot::native {
using namespace detail;
int describe() {
  constexpr const auto& d = jfg::game::linked::descriptor;
  const auto& b = jfg::game::linked::bindings;
  if (jfg::game::validate(d) != jfg::game::DescriptorError::none ||
      jfg::game::validate(d,b) != jfg::game::BindingError::none) return 2;
  const auto& revision = jfg::roms::known_revision(d.revision);
  std::printf("{\"schema_version\":2,\"kind\":\"jfg-native-program-identity\","
      "\"revision_id\":\"%.*s\",\"rom_sha1\":\"%.*s\",\"rom_size\":%llu,"
      "\"descriptor_abi\":%u,\"binding_abi\":%u,\"program_model_sha256\":\"%.*s\","
      "\"generation_input_sha256\":\"%.*s\",\"initial_tv_mode\":%u,"
      "\"qualification\":\"candidate\",\"build_identity\":\"%s\",\"build\":{",
      static_cast<int>(d.revision.size()),d.revision.data(),
      static_cast<int>(d.rom_sha1.size()),d.rom_sha1.data(),
      static_cast<unsigned long long>(revision.size),d.abi,b.abi,
      static_cast<int>(d.model_sha256.size()),d.model_sha256.data(),
      static_cast<int>(d.input_sha256.size()),d.input_sha256.data(),
      static_cast<unsigned>(d.initial_tv_mode),JFG_PHASE6_BUILD_IDENTITY);
  using namespace jfg::game::build;
  constexpr std::pair<std::string_view,std::string_view> fields[] = {
    {"source_sha256",kSourceSha256},{"generated_sources_sha256",kGeneratedSourcesSha256},
    {"descriptor_sha256",kDescriptorSha256},{"bindings_sha256",kBindingsSha256},
    {"generator_sha256",kGeneratorSha256},{"audio_sha256",kAudioSha256},
    {"dependencies_sha256",kDependenciesSha256},{"configuration_sha256",kConfigurationSha256},
    {"build_sha256",kBuildSha256}};
  bool separator = false;
  for (const auto& [name,value] : fields) {
    std::printf("%s\"%.*s\":\"%.*s\"", separator ? "," : "",
        static_cast<int>(name.size()), name.data(), static_cast<int>(value.size()), value.data());
    separator = true;
  }
  std::fputs("}}\n",stdout);

  return 0;
}
struct DispatchBinding {
  State &state;
  bool bound = false;
  bool cpu_bound = false;
  ~DispatchBinding() {
    if (cpu_bound)
      (void)jfg_minimal_runtime_unbind_cpu(native_cpu_operation, &state);
    if (bound)
      (void)jfg_minimal_runtime_unbind_dispatch(dispatch, &state);
  }
};
void invoke_generated(const jfg::GeneratedOverlayFunctionHandle &function,
                      std::uint8_t *rdram, recomp_context *context,
                      State &state, std::uint32_t transfer_target) {
  if (function.invoke(rdram, context) != jfg::GeneratedOverlayError::none) {
    ledger(state, "generated", "invoke-failed", transfer_target);
  }
}

int run_child(const char *path, const unsigned retrace_target,
              const unsigned poll_target, const bool play_mode) {
  std::vector<std::uint8_t> rom;
  if (!read_supported_rom(path, rom))
    return 2;
#if defined(JFG_PHASE8_LIVE_RUNTIME)
  if (!validate_persistent_profile_paths(play_mode)) return 3;
#endif
  if constexpr (std::endian::native != std::endian::little) {
    std::fputs("native boot setup failed: unsupported host endianness\n",
               stderr);
    return 3;
  }
  std::vector<std::uint8_t> bytes(kRdramSize);
  GuestBacking backing;
  if (!backing.create() || !backing.load_overlay_images(rom)) {
    std::fputs("native boot setup failed: guest address space\n", stderr);
    return 3;
  }
  const std::span<std::uint8_t> rdram = backing.bytes();
  if (!load_static_sections(rom, bytes)) {
    std::fputs("native boot setup failed: static section validation\n", stderr);
    return 3;
  }
  const auto handoff = interpret_reset_handoff(
      bytes, initial_entrypoint(), kRdramSize / sizeof(std::uint32_t) + 4096U);
  if (!handoff.ok()) {
    const char *reason =
        handoff.error == ResetHandoffError::unsupported_instruction
            ? "unsupported-instruction"
        : handoff.error == ResetHandoffError::budget_exhausted    ? "budget"
        : handoff.error == ResetHandoffError::unaligned_access    ? "unaligned"
        : handoff.error == ResetHandoffError::arithmetic_overflow ? "overflow"
                                                                  : "memory";
    std::fprintf(stderr, "native boot setup failed: reset handoff %s\n",
                 reason);
    return 3;
  }
  if (!initialize_ipl_state(bytes, rom)) {
    std::fputs("native boot setup failed: IPL state\n", stderr);
    return 3;
  }
  for (std::size_t index = 0U; index < rdram.size(); index += 4U) {
    rdram[index] = bytes[index + 3U];
    rdram[index + 1U] = bytes[index + 2U];
    rdram[index + 2U] = bytes[index + 1U];
    rdram[index + 3U] = bytes[index];
  }
  jfg::GeneratedOverlayRuntime runtime(std::as_writable_bytes(rdram));
  State state{};
  // Controller setup can inspect gameplay context before the renderer starts.
  state.rdram = rdram.data();
#if defined(_WIN32) && defined(JFG_PHASE8_LIVE_RUNTIME)
  char mod_flag[2]{};
  if (GetEnvironmentVariableA("JFG_NAVIGATION_MOD",mod_flag,2U)==1U && mod_flag[0]=='1') {
    wchar_t output[32768]{};
    const DWORD length=GetEnvironmentVariableW(L"JFG_MOD_OUTPUT",output,32768U);
    if(length==0U || length>=32768U) {
      std::fputs("navigation mod requires JFG_MOD_OUTPUT\n",stderr);return 2;
    }
    state.navigation_output=std::filesystem::path(output);
    std::error_code error;std::filesystem::create_directories(state.navigation_output,error);
    if(error)return 2;
    state.navigation_mod.enabled=true;
    // File open/flush stays on the diagnostic worker, never the guest thread.
    (void)state.movement_trace.start(state.navigation_output/L"movement-samples.csv", 4U*1024U*1024U);
    (void)state.jump_trace.start(state.navigation_output/L"jump-samples.csv", 4U*1024U*1024U);
    jfg::support_event("mod=navigation-enabled");
    char speed_flag[2]{};
    state.navigation_mod.juno_double_run =
        GetEnvironmentVariableA("JFG_MOD_JUNO_DOUBLE_RUN", speed_flag, 2U) == 1U &&
        speed_flag[0] == '1';
    if (state.navigation_mod.juno_double_run)
      jfg::support_event("mod=juno-run-speed-2x-enabled");
  }
  // Live tools observe by default; map Mods explicitly opt into individual changes.
  if (!state.navigation_mod.enabled) {
    wchar_t output[32768]{};
    const DWORD length=GetEnvironmentVariableW(L"JFG_LIVE_OUTPUT",output,32768U);
    if (length != 0U && length < 32768U) {
      state.navigation_output=std::filesystem::path(output);
      std::error_code error;std::filesystem::create_directories(state.navigation_output,error);
      if (!error) state.navigation_mod.telemetry_enabled=true;
    }
  }
  if (state.navigation_mod.observing()) {
    state.navigation_config_files.start({
        {state.navigation_output/L"mods.txt",128U},
        {state.navigation_output/L"warp-exit.txt",256U},
        {state.navigation_output/L"ai-command.txt",32768U},
        {state.navigation_output/L"give-weapons.txt",128U},
        {state.navigation_output/L"give-floyd.txt",128U}});
  }
  char memory_trace_flag[2]{};
  const auto memory_trace_length=GetEnvironmentVariableA("JFG_GAMEPLAY_TRACE_MEMORY",memory_trace_flag,2U);
  if(memory_trace_length!=0U && (memory_trace_length!=1U || memory_trace_flag[0]!='1'))return 3;
  wchar_t gameplay_trace_path[32768]{};
  const DWORD trace_path_length = GetEnvironmentVariableW(L"JFG_GAMEPLAY_TRACE", gameplay_trace_path, 32768U);
  if (trace_path_length != 0U && (trace_path_length >= 32768U ||
      !state.gameplay_trace.open(std::filesystem::path(gameplay_trace_path),256ULL*1024ULL*1024ULL,memory_trace_length==1U))) {
    std::fputs("native boot setup failed: gameplay trace path\n", stderr);
    return 3;
  }
  if (state.gameplay_trace)
    state.gameplay_trace.event("clock-origin", {state.gameplay_trace.steady_origin_us()});
  char trace_actors[2]{};
  const auto trace_actors_length = GetEnvironmentVariableA("JFG_GAMEPLAY_TRACE_ACTORS", trace_actors, 2U);
  if (trace_actors_length != 0U && (trace_actors_length != 1U ||
      (trace_actors[0] != '0' && trace_actors[0] != '1'))) {
    std::fputs("native boot setup failed: gameplay trace actors\n", stderr);
    return 3;
  }
  state.gameplay_trace_actors = trace_actors_length != 1U || trace_actors[0] != '0';
  state.host_audio.set_gameplay_trace(&state.gameplay_trace);
  state.host_audio.set_vi_counter(&state.vi_retraces);
  g_active_child_state = &state;
  jfg_original_timing_state = &state;
  initialize_original_timing_cache(state);
  jfg::support_event("native=rom-ready");
  wchar_t mapping_path[32768]{};
  const DWORD mapping_length = GetEnvironmentVariableW(L"JFG_CONTROLLER_CONFIG", mapping_path, 32768U);
  if (mapping_length != 0U) {
    state.controller_config_path=std::filesystem::path(mapping_path);
    std::ifstream mapping_file(std::filesystem::path(mapping_path), std::ios::binary | std::ios::ate);
    if (mapping_length >= 32768U || !mapping_file || mapping_file.tellg() > 4096 || mapping_file.tellg() <= 0) {
      jfg::support_event("native=controller-invalid");
      return 2;
    }
    mapping_file.seekg(0);
    const std::string mapping_text{std::istreambuf_iterator<char>(mapping_file), std::istreambuf_iterator<char>()};
    if (!jfg::parse_controller_mapping(mapping_text, state.controller_mapping)) {
      jfg::support_event("native=controller-invalid");
      return 2;
    }
  }
  if (!state.controller_config_path.empty()) {
    std::vector<jfg::ConfigFileRequest> requests;
    for (std::size_t p=0;p<4U;++p) {
      const auto parent=state.controller_config_path.parent_path();
      requests.push_back({parent/(p==0 ? "modern-controls.ini" : "modern-controls-"+std::to_string(p+1)+".ini"),8192U});
      requests.push_back({parent/(p==0 ? "pc-input.ini" : "pc-input-"+std::to_string(p+1)+".ini"),4096U});
      requests.push_back({p==0 ? state.controller_config_path : parent/("controller-"+std::to_string(p+1)+".ini"),4096U});
    }
    const auto automatic_path=state.controller_config_path.parent_path()/"controller-auto.ini";
    requests.push_back({automatic_path,8192U});
    // Apply saved removal intent before the very first device sample. Later
    // changes use the existing asynchronous settings reader.
    std::ifstream automatic_file(automatic_path,std::ios::binary|std::ios::ate);
    if(automatic_file && automatic_file.tellg()>0 && automatic_file.tellg()<=8192) {
      automatic_file.seekg(0);
      const std::string automatic_text{std::istreambuf_iterator<char>(automatic_file),{}};
      (void)jfg::parse_controller_auto_assignment(automatic_text,state.controller_ports.auto_assignment);
    }
    state.controller_config_files.start(std::move(requests));
  }
  state.controller_ports.configure(0,state.controller_mapping);
  sample_controller_ports(state,false);
  // One opt-in runtime mode owns CPU, OS, device clocks and host pacing.
  // Diagnostic traces and the travel fixture are independent and optional.
  char timing_fixture_flag[2]{};
  state.timing_fixture = GetEnvironmentVariableA("JFG_TIMING_TEST_FIXTURE",timing_fixture_flag,2U)==1U &&
      timing_fixture_flag[0]=='1';
  char original_timing_flag[2]{};
  const auto timing_override = GetEnvironmentVariableA("JFG_ORIGINAL_TIMING", original_timing_flag, 2U);
  const bool original_timing_mode = timing_override == 1U ? original_timing_flag[0] == '1' :
      JFG_ORIGINAL_TIMING_GENERATION == 1;
  if (original_timing_mode && JFG_ORIGINAL_TIMING_GENERATION != 1 && timing_override != 1U)
    return 3;
  char writeback_flag[2]{};
  state.renderer_writeback_probe = original_timing_mode || (
      GetEnvironmentVariableA("JFG_PHASE9_RENDERER_WRITEBACK_PROBE", writeback_flag, 2U) == 1U &&
      writeback_flag[0] == '1');
  char leaf_flag[2]{};
  state.guest_leaf_probe = original_timing_mode || (
      GetEnvironmentVariableA("JFG_PHASE9_GUEST_LEAF_PROBE", leaf_flag, 2U) == 1U &&
      leaf_flag[0] == '1');
  char os_flag[2]{};
  state.guest_os_probe = original_timing_mode || (
      GetEnvironmentVariableA("JFG_PHASE9_GUEST_OS_PROBE", os_flag, 2U) == 1U && os_flag[0] == '1');
  char original_pacing_flag[2]{};
  state.original_os_host_pacing = original_timing_mode || (
      GetEnvironmentVariableA("JFG_DIAGNOSTIC_OS_VI_PACING", original_pacing_flag, 2U) == 1U &&
      original_pacing_flag[0] == '1');
  if (state.original_os_host_pacing && !state.guest_os_probe) return 3;
  if (state.guest_os_probe && !state.guest_leaf_probe) {
    std::fputs("native boot setup failed: guest OS probe requires the guest CPU root\n", stderr);
    return 3;
  }
  if (state.guest_leaf_probe)
    state.tlb_registers = jfg::boot::TlbRegisters32::observed_mupen_boot();
  (void)SetUnhandledExceptionFilter(child_exception_filter);
#endif
  state.retrace_target =
      play_mode || poll_target != 0U
          ? (std::numeric_limits<std::uint32_t>::max)()
          : retrace_target;
  state.poll_target = poll_target;
#if defined(JFG_PHASE8_LIVE_RUNTIME)
  state.play_mode = play_mode;
#if defined(_WIN32)
  char *fast_replay = nullptr;
  std::size_t fast_replay_size = 0U;
  if (_dupenv_s(&fast_replay, &fast_replay_size,
                "JFG_PHASE9_FAST_REPLAY") != 0) {
    std::fputs("native boot setup failed: fast replay environment\n",
               stderr);
    return 3;
  }
  if (fast_replay != nullptr && *fast_replay != '\0') {
    if (std::strcmp(fast_replay, "1") != 0) {
      std::free(fast_replay);
      std::fputs("native boot setup failed: fast replay value\n", stderr);
      return 3;
    }
    state.fast_replay = true;
  }
  std::free(fast_replay);
  char *capture = nullptr;
  std::size_t capture_size = 0U;
  if (_dupenv_s(&capture, &capture_size, "JFG_PHASE8_FRAME_CAPTURE") != 0) {
    std::fputs("native boot setup failed: frame capture environment\n",
               stderr);
    return 3;
  }
  if (capture != nullptr && *capture != '\0') {
    if (capture_size > 32768U) {
      std::free(capture);
      std::fputs("native boot setup failed: frame capture path\n", stderr);
      return 3;
    }
    state.frame_capture_path = capture;
  }
  std::free(capture);
  char *pcm_capture = nullptr;
  std::size_t pcm_capture_size = 0U;
  if (_dupenv_s(&pcm_capture, &pcm_capture_size,
                "JFG_PHASE8_PCM_CAPTURE") != 0) {
    std::fputs("native boot setup failed: PCM capture environment\n",
               stderr);
    return 3;
  }
  if (pcm_capture != nullptr && *pcm_capture != '\0' &&
      (pcm_capture_size > 32768U ||
       !state.host_audio.configure_capture(pcm_capture))) {
    std::free(pcm_capture);
    std::fputs("native boot setup failed: PCM capture path\n", stderr);
    return 3;
  }
  std::free(pcm_capture);
  char *rdram_capture = nullptr;
  std::size_t rdram_capture_size = 0U;
  if (_dupenv_s(&rdram_capture, &rdram_capture_size,
                "JFG_PHASE8_RDRAM_CAPTURE") != 0) {
    std::fputs("native boot setup failed: RDRAM capture environment\n",
               stderr);
    return 3;
  }
  if (rdram_capture != nullptr && *rdram_capture != '\0') {
    if (rdram_capture_size > 32768U) {
      std::free(rdram_capture);
      std::fputs("native boot setup failed: RDRAM capture path\n", stderr);
      return 3;
    }
    state.rdram_capture_path = rdram_capture;
  }
  std::free(rdram_capture);
  char *progress = nullptr;
  std::size_t progress_size = 0U;
  if (_dupenv_s(&progress, &progress_size, "JFG_PHASE8_PROGRESS") != 0) {
    std::fputs("native boot setup failed: progress environment\n", stderr);
    return 3;
  }
  if (progress != nullptr && *progress != '\0') {
    if (progress_size > 32768U) {
      std::free(progress);
      std::fputs("native boot setup failed: progress path\n", stderr);
      return 3;
    }
    state.progress_path = progress;
  }
  std::free(progress);
  char *record_path = nullptr;
  std::size_t record_path_size = 0U;
  if (_dupenv_s(&record_path, &record_path_size,
                "JFG_PHASE9_INPUT_RECORD") != 0) {
    std::fputs("native boot setup failed: input record environment\n", stderr);
    return 3;
  }
  if (record_path != nullptr && *record_path != '\0') {
    if (record_path_size > 32768U) {
      std::free(record_path);
      std::fputs("native boot setup failed: input record path\n", stderr);
      return 3;
    }
    state.input_record_path = record_path;
  }
  std::free(record_path);
  char *actor_trace = nullptr;
  std::size_t actor_trace_size = 0U;
  if (_dupenv_s(&actor_trace, &actor_trace_size,
                "JFG_PHASE9_ACTOR_TRACE") != 0) {
    std::fputs("native boot setup failed: actor trace environment\n", stderr);
    return 3;
  }
  if (actor_trace != nullptr && *actor_trace != '\0') {
    if (std::strcmp(actor_trace, "1") != 0) {
      std::free(actor_trace);
      std::fputs("native boot setup failed: actor trace value\n", stderr);
      return 3;
    }
    state.actor_timing_trace = true;
  }
  std::free(actor_trace);
  char *retrace_hash = nullptr;
  std::size_t retrace_hash_size = 0U;
  if (_dupenv_s(&retrace_hash, &retrace_hash_size,
                "JFG_PHASE9_RETRACE_HASH") != 0) {
    std::fputs("native boot setup failed: retrace hash environment\n",
               stderr);
    return 3;
  }
  if (retrace_hash != nullptr && *retrace_hash != '\0') {
    if (retrace_hash_size > 32768U) {
      std::free(retrace_hash);
      std::fputs("native boot setup failed: retrace hash path\n", stderr);
      return 3;
    }
    state.retrace_hash_path = retrace_hash;
  }
  std::free(retrace_hash);
  char *replay_by_poll = nullptr;
  std::size_t replay_by_poll_size = 0U;
  if (_dupenv_s(&replay_by_poll, &replay_by_poll_size,
                "JFG_PHASE9_REPLAY_BY_POLL") != 0) {
    std::fputs("native boot setup failed: replay poll environment\n", stderr);
    return 3;
  }
  if (replay_by_poll != nullptr && *replay_by_poll != '\0') {
    if (std::strcmp(replay_by_poll, "1") != 0) {
      std::free(replay_by_poll);
      std::fputs("native boot setup failed: replay poll value\n", stderr);
      return 3;
    }
    state.input_replay_by_poll = true;
  }
  std::free(replay_by_poll);
  char *replay_path = nullptr;
  std::size_t replay_path_size = 0U;
  if (_dupenv_s(&replay_path, &replay_path_size,
                "JFG_PHASE8_INPUT_REPLAY") != 0) {
    std::fputs("native boot setup failed: input replay environment\n",
               stderr);
    return 3;
  }
  if (replay_path != nullptr && *replay_path != '\0') {
    if (replay_path_size > 32768U ||
        jfg::DeterministicInputReplay::load(replay_path,
                                             state.input_replay, state.input_replay_by_poll
                  ? jfg::InputReplayOrder::recorded_poll
                  : jfg::InputReplayOrder::retrace) !=
            jfg::InputReplayError::none) {
      std::free(replay_path);
      std::fputs("native boot setup failed: input replay\n", stderr);
      return 3;
    }
    state.input_replay_loaded = true;
    state.input_replay_event_count = state.input_replay.events().size();
  }
  std::free(replay_path);
  // Bounded replay fixture for the same input-suspension path used by focus
  // loss. It never changes desktop focus and is rejected in interactive Play.
  char suspend_interval[48]{};
  const auto suspend_length=GetEnvironmentVariableA("JFG_DIAGNOSTIC_INPUT_SUSPEND_VI",suspend_interval,48U);
  if(suspend_length!=0U) {
    if(suspend_length>=48U || !state.input_replay_loaded || state.play_mode)return 3;
    const std::string_view spec(suspend_interval,suspend_length);
    const auto colon=spec.find(':');
    if(colon==std::string_view::npos)return 3;
    auto first=std::from_chars(spec.data(),spec.data()+colon,state.diagnostic_input_suspend_begin);
    auto last=std::from_chars(spec.data()+colon+1U,spec.data()+spec.size(),state.diagnostic_input_suspend_end);
    if(first.ec!=std::errc{} || first.ptr!=spec.data()+colon || last.ec!=std::errc{} ||
       last.ptr!=spec.data()+spec.size() || state.diagnostic_input_suspend_begin<3U ||
       state.diagnostic_input_suspend_begin>=state.diagnostic_input_suspend_end ||
       state.diagnostic_input_suspend_end>1000000U)return 3;
  }
  char *pointer_script=nullptr;std::size_t pointer_script_size=0;
  if(_dupenv_s(&pointer_script,&pointer_script_size,"JFG_PHASE9_MENU_POINTER_REPLAY")!=0)return 3;
  if(pointer_script && *pointer_script) {
    std::ifstream script(pointer_script);
    if(state.play_mode || !state.input_replay_loaded || !script || !state.menu_pointer_replay.load(script)) {
      std::free(pointer_script);
      std::fputs("native boot setup failed: menu pointer probe requires bounded input replay\n",stderr);
      return 3;
    }
  }
  std::free(pointer_script);
  if (state.input_replay_by_poll && !state.input_replay_loaded) {
    std::fputs("native boot setup failed: replay poll requires input replay\n", stderr);
    return 3;
  }
  // A bounded, hidden replay can exercise the interactive VI/audio cadence
  // without opening another game window or consuming live controller input.
  char *realtime_replay = nullptr;
  std::size_t realtime_replay_size = 0U;
  if (_dupenv_s(&realtime_replay, &realtime_replay_size,
                "JFG_PHASE9_REALTIME_REPLAY") != 0) {
    std::fputs("native boot setup failed: realtime replay environment\n", stderr);
    return 3;
  }
  if (realtime_replay != nullptr && *realtime_replay != '\0') {
    if (std::strcmp(realtime_replay, "1") != 0 ||
        !state.input_replay_loaded || state.play_mode || state.fast_replay ||
        (state.guest_leaf_probe && !state.original_os_host_pacing)) {
      std::free(realtime_replay);
      std::fputs("native boot setup failed: realtime replay value\n", stderr);
      return 3;
    }
    // The unified guest OS already owns its clock. service_live_window returns
    // before the cooperative frame pacer in this mode, so hidden replay can
    // exercise frontend pause without adding a second VI pacing policy.
    state.realtime_replay = true;
    jfg::support_event("replay=hidden-realtime-vi-clock");
  }
  std::free(realtime_replay);
  if (state.poll_target != 0U &&
      (!state.input_replay_loaded || !state.input_replay_by_poll)) {
    std::fputs("native boot setup failed: poll target requires replay-by-poll\n",
               stderr);
    return 3;
  }
  char *save_path = nullptr;
  std::size_t save_path_size = 0U;
  if (_dupenv_s(&save_path, &save_path_size, "JFG_PHASE8_SAVE_PATH") != 0) {
    std::fputs("native boot setup failed: save environment\n", stderr);
    return 3;
  }
  if (save_path != nullptr && *save_path != '\0' &&
      (save_path_size > 32768U || !configure_flash_path(state, save_path))) {
    std::free(save_path);
    std::fputs("native boot setup failed: save path\n", stderr);
    return 3;
  }
  std::free(save_path);
  char *controller_pak_path = nullptr;
  std::size_t controller_pak_path_size = 0U;
  if (_dupenv_s(&controller_pak_path, &controller_pak_path_size,
                "JFG_PHASE8_CONTROLLER_PAK_PATH") != 0) {
    std::fputs("native boot setup failed: controller pak environment\n",
               stderr);
    return 3;
  }
  if (controller_pak_path != nullptr && *controller_pak_path != '\0' &&
      (controller_pak_path_size > 32768U ||
       !configure_controller_pak_path(state, controller_pak_path))) {
    std::free(controller_pak_path);
    std::fputs("native boot setup failed: controller pak path\n", stderr);
    return 3;
  }
  std::free(controller_pak_path);
#else
  if (const char *fast_replay = std::getenv("JFG_PHASE9_FAST_REPLAY");
      fast_replay != nullptr && *fast_replay != '\0') {
    if (std::strcmp(fast_replay, "1") != 0) {
      std::fputs("native boot setup failed: fast replay value\n", stderr);
      return 3;
    }
    state.fast_replay = true;
  }
  if (const char *capture = std::getenv("JFG_PHASE8_FRAME_CAPTURE");
      capture != nullptr && *capture != '\0') {
    if (std::strlen(capture) > 32767U) {
      std::fputs("native boot setup failed: frame capture path\n", stderr);
      return 3;
    }
    state.frame_capture_path = capture;
  }
  if (const char *rdram_capture = std::getenv("JFG_PHASE8_RDRAM_CAPTURE");
      rdram_capture != nullptr && *rdram_capture != '\0') {
    if (std::strlen(rdram_capture) > 32767U) {
      std::fputs("native boot setup failed: RDRAM capture path\n", stderr);
      return 3;
    }
    state.rdram_capture_path = rdram_capture;
  }
  if (const char *progress = std::getenv("JFG_PHASE8_PROGRESS");
      progress != nullptr && *progress != '\0') {
    if (std::strlen(progress) > 32767U) {
      std::fputs("native boot setup failed: progress path\n", stderr);
      return 3;
    }
    state.progress_path = progress;
  }
  if (const char *retrace_hash = std::getenv("JFG_PHASE9_RETRACE_HASH");
      retrace_hash != nullptr && *retrace_hash != '\0') {
    if (std::strlen(retrace_hash) > 32767U) {
      std::fputs("native boot setup failed: retrace hash path\n", stderr);
      return 3;
    }
    state.retrace_hash_path = retrace_hash;
  }
  if (const char *replay_path = std::getenv("JFG_PHASE8_INPUT_REPLAY");
      replay_path != nullptr && *replay_path != '\0') {
    if (std::strlen(replay_path) > 32767U ||
        jfg::DeterministicInputReplay::load(replay_path,
                                             state.input_replay) !=
            jfg::InputReplayError::none) {
      std::fputs("native boot setup failed: input replay\n", stderr);
      return 3;
    }
    state.input_replay_loaded = true;
    state.input_replay_event_count = state.input_replay.events().size();
  }
  if (const char *save_path = std::getenv("JFG_PHASE8_SAVE_PATH");
      save_path != nullptr && *save_path != '\0' &&
      (std::strlen(save_path) > 32767U ||
       !configure_flash_path(state, save_path))) {
    std::fputs("native boot setup failed: save path\n", stderr);
    return 3;
  }
  if (const char *controller_pak_path =
          std::getenv("JFG_PHASE8_CONTROLLER_PAK_PATH");
      controller_pak_path != nullptr && *controller_pak_path != '\0' &&
      (std::strlen(controller_pak_path) > 32767U ||
       !configure_controller_pak_path(state, controller_pak_path))) {
    std::fputs("native boot setup failed: controller pak path\n", stderr);
    return 3;
  }
#endif
  if (!state.progress_path.empty()) {
    state.timing_trace.open(state.progress_path + ".timing.tsv",
                            std::ios::out | std::ios::trunc);
    if (!state.timing_trace) {
      std::fputs("native boot setup failed: timing trace path\n", stderr);
      return 3;
    }
    state.timing_trace
        << "kind\tvi_frame\tvi_retrace\tduration_us\tdetail_a\tdetail_b"
           "\tdetail_c\tdetail_d\n";
  }
  if (!state.input_record_path.empty()) {
    state.input_record.open(state.input_record_path, std::ios::trunc);
    if (!state.input_record) {
      std::fputs("native boot setup failed: input record open\n", stderr);
      return 3;
    }
#if defined(_WIN32)
    reload_controller_ports(state);
    state.pc_record_extended=state.modern_controls_active;
#endif
    state.input_record << (state.pc_record_extended?jfg::kInputReplayHeaderV8:jfg::kInputReplayHeader) << '\n';
  }
  if (!state.retrace_hash_path.empty()) {
    state.retrace_hash_trace.open(state.retrace_hash_path,
                                  std::ios::out | std::ios::trunc);
    if (!state.retrace_hash_trace) {
      std::fputs("native boot setup failed: retrace hash open\n", stderr);
      return 3;
    }
    state.retrace_hash_trace
        << "{\"kind\":\"jfg-phase9-retrace-hash-header\","
           "\"schema\":1}\n";
    char *updates = nullptr;
    std::size_t updates_size = 0U;
    if (_dupenv_s(&updates, &updates_size, "JFG_PHASE9_UPDATE_HASHES") != 0) {
      std::fputs("native boot setup failed: update hash environment\n", stderr);
      return 3;
    }
    const bool update_hash_enabled = updates != nullptr && std::strcmp(updates, "1") == 0;
    const bool update_hash_invalid = updates != nullptr && *updates != '\0' && !update_hash_enabled;
    std::free(updates);
    if (update_hash_invalid) {
      std::fputs("native boot setup failed: update hash value\n", stderr);
      return 3;
    }
    if (update_hash_enabled) {
      state.update_hash_trace.open(state.retrace_hash_path + ".updates.jsonl",
                                   std::ios::out | std::ios::trunc);
      if (!state.update_hash_trace) {
        std::fputs("native boot setup failed: update hash open\n", stderr);
        return 3;
      }
      state.update_hash_trace
          << "{\"kind\":\"jfg-phase9-update-hash-header\",\"schema\":1}\n";
      char *focus = nullptr;
      std::size_t focus_size = 0U;
      if (_dupenv_s(&focus, &focus_size, "JFG_PHASE9_FOCUS_UPDATES") != 0) {
        std::fputs("native boot setup failed: focus environment\n", stderr);
        return 3;
      }
      if (focus != nullptr && *focus != '\0') {
        const std::string_view specification(focus);
        const auto colon = specification.find(':');
        std::uint64_t first = 0U, last = 0U;
        bool valid = colon != std::string_view::npos && colon != 0U &&
                     colon + 1U < specification.size();
        if (valid) {
          const auto first_number = std::from_chars(
              specification.data(), specification.data() + colon, first);
          const auto last_number = std::from_chars(
              specification.data() + colon + 1U,
              specification.data() + specification.size(), last);
          valid = first_number.ec == std::errc{} &&
                  first_number.ptr == specification.data() + colon &&
                  last_number.ec == std::errc{} &&
                  last_number.ptr == specification.data() + specification.size();
        }
        std::free(focus);
        if (!valid || first < 1U || last < first || last - first > 15U) {
          std::fputs("native boot setup failed: focus update range\n", stderr);
          return 3;
        }
        state.focus_update_start = first;
        state.focus_update_end = last;
      } else {
        std::free(focus);
      }
    }
  }
  char *update_word = nullptr;
  std::size_t update_word_size = 0U;
  if (_dupenv_s(&update_word, &update_word_size,
                "JFG_PHASE9_UPDATE_WORD") != 0) {
    std::fputs("native boot setup failed: update word environment\n", stderr);
    return 3;
  }
  if (update_word != nullptr && *update_word != '\0') {
    const std::string_view specification(update_word);
    std::uint32_t address = 0U;
    bool valid = specification.size() == 10U &&
                 specification.substr(0U, 2U) == "0x";
    if (valid) {
      const auto parsed = std::from_chars(specification.data() + 2U,
                                          specification.data() + 10U,
                                          address, 16);
      valid = parsed.ec == std::errc{} &&
              parsed.ptr == specification.data() + 10U;
    }
    std::free(update_word);
    if (!valid || address < 0x80000000U || address > 0x803FFFFCU ||
        (address & 3U) != 0U || !state.update_hash_trace.is_open()) {
      std::fputs("native boot setup failed: update word range\n", stderr);
      return 3;
    }
    state.update_word_address = address;
    const auto update_word_path = std::filesystem::path(state.retrace_hash_path).parent_path() /
        "update-word.tsv";
    state.update_word_trace.open(update_word_path, std::ios::out | std::ios::trunc);
    if (!state.update_word_trace) {
      std::fputs("native boot setup failed: update word trace\n", stderr);
      return 3;
    }
    state.update_word_trace <<
        "update\tcontroller_polls\tvi\tframe\taddress\tvalue\n";
  } else {
    std::free(update_word);
  }
  char *watch = nullptr;
  std::size_t watch_size = 0U;
  if (_dupenv_s(&watch, &watch_size, "JFG_PHASE9_WATCH_WORD") != 0) {
    std::fputs("native boot setup failed: watch environment\n", stderr);
    return 3;
  }
  if (watch != nullptr && *watch != '\0') {
    const std::string_view specification(watch);
    std::uint32_t address = 0U;
    bool valid = specification.size() == 10U &&
                 specification.substr(0U, 2U) == "0x";
    if (valid) {
      const auto parsed = std::from_chars(specification.data() + 2U,
                                          specification.data() + 10U,
                                          address, 16);
      valid = parsed.ec == std::errc{} &&
              parsed.ptr == specification.data() + 10U;
    }
    std::free(watch);
    if (!valid || address < 0x80000000U || address > 0x803FFFFCU ||
        (address & 3U) != 0U || state.focus_update_start == 0U ||
        !state.update_hash_trace.is_open()) {
      std::fputs("native boot setup failed: watch word range\n", stderr);
      return 3;
    }
    state.watch_word_address = address;
    const auto watch_path = std::filesystem::path(state.retrace_hash_path).parent_path() /
        "watch-word.tsv";
    state.watch_word_trace.open(watch_path, std::ios::out | std::ios::trunc);
    if (!state.watch_word_trace) {
      std::fputs("native boot setup failed: watch word trace\n", stderr);
      return 3;
    }
    state.watch_word_trace <<
        "update_candidate\tvi_retraces\tcontroller_polls\tdepth\t"
        "dispatch_target\treturn_address\tbefore\tafter\n";
  } else {
    std::free(watch);
  }
  char *entry = nullptr;
  std::size_t entry_size = 0U;
  if (_dupenv_s(&entry, &entry_size, "JFG_PHASE9_ENTRY_TARGET") != 0) {
    std::fputs("native boot setup failed: entry environment\n", stderr);
    return 3;
  }
  if (entry != nullptr && *entry != '\0') {
    const std::string_view specification(entry);
    std::uint32_t target = 0U;
    bool valid = specification.size() == 10U &&
                 specification.substr(0U, 2U) == "0x";
    if (valid) {
      const auto parsed = std::from_chars(specification.data() + 2U,
                                          specification.data() + 10U,
                                          target, 16);
      valid = parsed.ec == std::errc{} &&
              parsed.ptr == specification.data() + 10U;
    }
    std::free(entry);
    if (!valid || target == 0U || (target & 3U) != 0U ||
        state.focus_update_start == 0U || !state.update_hash_trace.is_open()) {
      std::fputs("native boot setup failed: entry target range\n", stderr);
      return 3;
    }
    state.entry_probe_target = target;
    const auto entry_path =
        std::filesystem::path(state.retrace_hash_path).parent_path() /
        "entry-args.tsv";
    state.entry_probe_trace.open(entry_path, std::ios::out | std::ios::trunc);
    if (!state.entry_probe_trace) {
      std::fputs("native boot setup failed: entry trace\n", stderr);
      return 3;
    }
    state.entry_probe_trace <<
        "update_candidate\tvi_retraces\tcontroller_polls\ttarget\t"
        "a0\ta1\ta2\ta3\n";
  } else {
    std::free(entry);
  }
  char *entry_fpu = nullptr;
  std::size_t entry_fpu_size = 0U;
  if (_dupenv_s(&entry_fpu, &entry_fpu_size, "JFG_PHASE9_ENTRY_FPU") != 0) {
    std::fputs("native boot setup failed: entry FPU environment\n", stderr);
    return 3;
  }
  const bool trace_entry_fpu = entry_fpu != nullptr &&
      std::string_view(entry_fpu) == "1";
  const bool invalid_entry_fpu = entry_fpu != nullptr &&
      *entry_fpu != '\0' && !trace_entry_fpu;
  std::free(entry_fpu);
  if (invalid_entry_fpu || (trace_entry_fpu && state.entry_probe_target == 0U)) {
    std::fputs("native boot setup failed: entry FPU requires entry probe\n", stderr);
    return 3;
  }
  if (trace_entry_fpu) {
    const auto fpu_path =
        std::filesystem::path(state.retrace_hash_path).parent_path() /
        "entry-fpu.tsv";
    state.entry_fpu_trace.open(fpu_path, std::ios::out | std::ios::trunc);
    if (!state.entry_fpu_trace) {
      std::fputs("native boot setup failed: entry FPU trace\n", stderr);
      return 3;
    }
    state.entry_fpu_trace <<
        "update_candidate\tvi_retraces\tcontroller_polls\ttarget";
    for (std::size_t index = 0U; index < 32U; ++index)
      state.entry_fpu_trace << "\tf" << index << "_lo\tf" << index << "_hi";
    state.entry_fpu_trace << '\n';
  }
  char *entry_memory = nullptr;
  std::size_t entry_memory_size = 0U;
  if (_dupenv_s(&entry_memory, &entry_memory_size,
                "JFG_PHASE9_ENTRY_MEMORY") != 0) {
    std::fputs("native boot setup failed: entry memory environment\n", stderr);
    return 3;
  }
  const bool trace_entry_memory = entry_memory != nullptr &&
      std::string_view(entry_memory) == "1";
  const bool invalid_entry_memory = entry_memory != nullptr &&
      *entry_memory != '\0' && !trace_entry_memory;
  std::free(entry_memory);
  if (invalid_entry_memory ||
      (trace_entry_memory && state.entry_probe_target == 0U)) {
    std::fputs("native boot setup failed: entry memory requires entry probe\n",
               stderr);
    return 3;
  }
  if (trace_entry_memory) {
    const auto memory_path =
        std::filesystem::path(state.retrace_hash_path).parent_path() /
        "entry-memory.tsv";
    state.entry_memory_trace.open(memory_path, std::ios::out | std::ios::trunc);
    if (!state.entry_memory_trace) {
      std::fputs("native boot setup failed: entry memory trace\n", stderr);
      return 3;
    }
    state.entry_memory_trace <<
        "update_candidate\tvi_retraces\tcontroller_polls\ttarget\t"
        "a1_256\ta2_256\ta3_256\n";
  }
  char *entry_gpr = nullptr;
  std::size_t entry_gpr_size = 0U;
  if (_dupenv_s(&entry_gpr, &entry_gpr_size, "JFG_PHASE9_ENTRY_GPR") != 0) {
    std::fputs("native boot setup failed: entry GPR environment\n", stderr);
    return 3;
  }
  const bool trace_entry_gpr = entry_gpr != nullptr &&
      std::string_view(entry_gpr) == "1";
  const bool invalid_entry_gpr = entry_gpr != nullptr &&
      *entry_gpr != '\0' && !trace_entry_gpr;
  std::free(entry_gpr);
  if (invalid_entry_gpr || (trace_entry_gpr && state.entry_probe_target == 0U)) {
    std::fputs("native boot setup failed: entry GPR requires entry probe\n", stderr);
    return 3;
  }
  if (trace_entry_gpr) {
    const auto gpr_path =
        std::filesystem::path(state.retrace_hash_path).parent_path() /
        "entry-gpr.tsv";
    state.entry_gpr_trace.open(gpr_path, std::ios::out | std::ios::trunc);
    if (!state.entry_gpr_trace) {
      std::fputs("native boot setup failed: entry GPR trace\n", stderr);
      return 3;
    }
    state.entry_gpr_trace <<
        "update_candidate\tvi_retraces\tcontroller_polls\ttarget";
    for (std::size_t index = 0U; index < 32U; ++index)
      state.entry_gpr_trace << "\tr" << index << "_lo\tr" << index << "_hi";
    state.entry_gpr_trace << '\n';
  }
  char *instruction_probe = nullptr;
  const auto point_addresses = [](const char* name) {
    char* raw = nullptr;
    std::size_t size = 0;
    if (_dupenv_s(&raw, &size, name) != 0)
      return std::optional<std::vector<std::uint32_t>>{};
    const auto parsed = point_probe_addresses(raw == nullptr ? "" : raw);
    std::free(raw);
    return parsed;
  };
  const auto point_pcs = point_addresses("JFG_PHASE9_POINT_PCS");
  const auto point_words = point_addresses("JFG_PHASE9_POINT_WORDS");
  if (!point_pcs || !point_words ||
      (point_pcs->empty() && !point_words->empty()) ||
      (!point_pcs->empty() && (!state.guest_os_probe || state.focus_update_start == 0U ||
                              !state.update_hash_trace.is_open()))) {
    std::fputs("native boot setup failed: point probe requires original OS and focused updates\n", stderr);
    return 3;
  }
  state.point_probe_pcs = *point_pcs;
  state.point_probe_words = *point_words;
  char* device_events = nullptr;
  std::size_t device_events_size = 0U;
  if (_dupenv_s(&device_events, &device_events_size, "JFG_PHASE9_DEVICE_EVENTS") != 0) return 3;
  const bool trace_device_events = device_events != nullptr && std::string_view(device_events) == "1";
  const bool invalid_device_events = device_events != nullptr && !trace_device_events;
  std::free(device_events);
  if (invalid_device_events || (trace_device_events && point_pcs->empty())) {
    std::fputs("native boot setup failed: device events require focused original-OS point capture\n", stderr);
    return 3;
  }
  if (trace_device_events) {
    const auto device_event_path = std::filesystem::path(state.retrace_hash_path).parent_path() / "device-events.tsv";
    FILE* device_event_output = nullptr;
    if (_wfopen_s(&device_event_output, device_event_path.c_str(), L"wb") != 0 || device_event_output == nullptr) return 3;
    state.device_event_stream.reset(device_event_output);
    const auto event_first = static_cast<std::uint32_t>((std::max)(std::uint64_t{1}, state.focus_update_start - 1U));
    const auto event_last = static_cast<std::uint32_t>(state.focus_update_end + 1U);
    if (!jfg_device_event_open(&state.device_event_probe, device_event_output, event_first, event_last, JFG_EVENT_NATIVE_PRE_INSTRUCTION)) return 3;
  }
  char* eret_transfers = nullptr;
  std::size_t eret_transfers_size = 0U;
  if (_dupenv_s(&eret_transfers, &eret_transfers_size, "JFG_PHASE9_ERET_TRANSFERS") != 0) return 3;
  const bool trace_eret_transfers = eret_transfers != nullptr && std::string_view(eret_transfers) == "1";
  const bool invalid_eret_transfers = eret_transfers != nullptr && !trace_eret_transfers;
  std::free(eret_transfers);
  if (invalid_eret_transfers || (trace_eret_transfers && !trace_device_events)) return 3;
  if (trace_eret_transfers) {
    state.eret_transfer_stream.open(std::filesystem::path(state.retrace_hash_path).parent_path() / "eret-transfers.tsv");
    if (!state.eret_transfer_stream || !state.eret_transfer_probe.open(state.eret_transfer_stream,
        state.device_event_probe.first, state.device_event_probe.last)) return 3;
  }
  char* instruction_effects = nullptr;
  std::size_t instruction_effects_size = 0U;
  if (_dupenv_s(&instruction_effects, &instruction_effects_size, "JFG_PHASE9_INSTRUCTION_EFFECT_UPDATE") != 0) return 3;
  if (instruction_effects != nullptr) {
    const std::string_view value(instruction_effects);
    const auto parsed = std::from_chars(value.data(), value.data() + value.size(), state.instruction_effect_update);
    const bool valid = parsed.ec == std::errc{} && parsed.ptr == value.data() + value.size() &&
        state.guest_os_probe && trace_eret_transfers && trace_device_events &&
        state.instruction_effect_update >= state.device_event_probe.first &&
        state.instruction_effect_update <= state.device_event_probe.last;
    std::free(instruction_effects);
    if (!valid) return 3;
    state.instruction_effect_stream.open(std::filesystem::path(state.retrace_hash_path).parent_path() /
                                        "instruction-effects.bin", std::ios::binary);
    if (!state.instruction_effect_stream || !state.instruction_effect_trace.open(
          state.instruction_effect_stream, state.instruction_effect_update)) return 3;
  }
  if (!point_pcs->empty()) {
    state.point_probe_trace.open(std::filesystem::path(state.retrace_hash_path).parent_path() /
                                "point-probe.tsv", std::ios::out | std::ios::trunc);
    if (!state.point_probe_trace) return 3;
    state.point_probe_trace << "update_candidate\tvi_retraces\tcontroller_polls\tpc\topcode";
    for (unsigned index = 0; index < 32; ++index)
      state.point_probe_trace << "\tr" << index << "_lo\tr" << index << "_hi";
    for (const auto address : state.point_probe_words)
      state.point_probe_trace << "\tm" << std::hex << std::setw(8) << std::setfill('0') << address;
    state.point_probe_trace << std::dec << std::setfill(' ') << '\n';
  }
  std::size_t instruction_probe_size = 0U;
  if (_dupenv_s(&instruction_probe, &instruction_probe_size,
                "JFG_PHASE9_INSTRUCTION_PROBE") != 0) {
    std::fputs("native boot setup failed: instruction probe environment\n", stderr);
    return 3;
  }
  const bool trace_instruction = instruction_probe != nullptr &&
      std::string_view(instruction_probe) == "1";
  const bool invalid_instruction = instruction_probe != nullptr &&
      *instruction_probe != '\0' && !trace_instruction;
  std::free(instruction_probe);
  if (invalid_instruction ||
      (trace_instruction && (state.focus_update_start == 0U ||
                             !state.update_hash_trace.is_open()))) {
    std::fputs("native boot setup failed: instruction probe requires focused updates\n",
               stderr);
    return 3;
  }
  if (trace_instruction) {
    const auto instruction_path =
        std::filesystem::path(state.retrace_hash_path).parent_path() /
        "instruction-probe.tsv";
    state.instruction_probe_trace.open(instruction_path,
                                       std::ios::out | std::ios::trunc);
    if (!state.instruction_probe_trace) {
      std::fputs("native boot setup failed: instruction probe trace\n", stderr);
      return 3;
    }
    state.instruction_probe_trace <<
        "update_candidate\tvi_retraces\tcontroller_polls\tpc\t"
        "r4\tr5\tr6\tr7\tr10\tr15\tr19\tr20\tr21\tr23\tr25\t"
        "f4_lo\tf22_lo\tf23_odd_lo\thost_fe_round\n";
  }
#else
  if (play_mode)
    return 3;
#endif
  state.runtime = &runtime;
  state.rdram = rdram.data();
  state.rom = rom.data();
  state.rom_size = rom.size();
  if (state.navigation_mod.observing() && !state.navigation_mod.npc_rewards.load_rom(rom,kRomAssetDirectory,jfg::game::linked::descriptor.revision))
    std::fputs("navigation mod: NPC reward catalog unavailable; rewards remain unknown\n", stderr);
#if defined(JFG_PHASE8_LIVE_RUNTIME)
  char *poll_path = nullptr;
  std::size_t poll_path_size = 0U;
  if (_dupenv_s(&poll_path, &poll_path_size,
                "JFG_PHASE95_NATIVE_POLL_TRACE") != 0) {
    std::fputs("native boot setup failed: poll trace environment\n", stderr);
    return 3;
  }
  if (poll_path != nullptr && *poll_path != '\0') {
    if (poll_path_size > 32768U) {
      std::free(poll_path);
      std::fputs("native boot setup failed: poll trace path\n", stderr);
      return 3;
    }
    state.phase95_poll_trace.open(poll_path, std::ios::out | std::ios::trunc);
    if (!state.phase95_poll_trace) {
      std::free(poll_path);
      std::fputs("native boot setup failed: poll trace open\n", stderr);
      return 3;
    }
    state.phase95_poll_trace
        << "poll\tvi_retrace\tvi_frame\tfront_mode\tlevel_word"
           "\trng_seed\tbuttons\tx\ty\n";
  }
  std::free(poll_path);
  char *poll_hashes = nullptr;
  std::size_t poll_hashes_size = 0U;
  if (_dupenv_s(&poll_hashes, &poll_hashes_size,
                "JFG_PHASE9_POLL_HASHES") != 0) {
    std::fputs("native boot setup failed: poll hash environment\n", stderr);
    return 3;
  }
  const bool poll_hash_enabled = poll_hashes != nullptr &&
      std::strcmp(poll_hashes, "1") == 0;
  const bool poll_hash_invalid = poll_hashes != nullptr &&
      *poll_hashes != '\0' && !poll_hash_enabled;
  std::free(poll_hashes);
  if (poll_hash_invalid || (poll_hash_enabled &&
      (!state.input_replay_by_poll || state.retrace_hash_path.empty()))) {
    std::fputs("native boot setup failed: poll hash requires replay-by-poll\n", stderr);
    return 3;
  }
  if (poll_hash_enabled) {
    state.poll_hash_trace.open(state.retrace_hash_path + ".polls.jsonl",
                               std::ios::out | std::ios::trunc);
    if (!state.poll_hash_trace) {
      std::fputs("native boot setup failed: poll hash open\n", stderr);
      return 3;
    }
    state.poll_hash_trace <<
        "{\"kind\":\"jfg-phase9-poll-hash-header\",\"schema\":1,"
        "\"boundary\":\"pre-controller-input\"}\n";
  }
  char *event_range = nullptr;
  std::size_t event_range_size = 0U;
  if (_dupenv_s(&event_range, &event_range_size,
                "JFG_PHASE9_EVENT_TRACE_RANGE") != 0) {
    std::fputs("native boot setup failed: event trace environment\n", stderr);
    return 3;
  }
  if (event_range != nullptr && *event_range != '\0') {
    const std::string_view specification(event_range);
    bool valid = poll_hash_enabled && state.update_hash_trace.is_open() &&
                 specification.size() <= 64U;
    std::size_t cursor = 0U;
    while (valid && cursor < specification.size()) {
      if (state.event_range_count == state.event_ranges.size()) {
        valid = false;
        break;
      }
      const auto comma = specification.find(',', cursor);
      const auto end = comma == std::string_view::npos
                           ? specification.size() : comma;
      const auto colon = specification.find(':', cursor);
      std::uint64_t first = 0U, last = 0U;
      valid = colon != std::string_view::npos && colon > cursor &&
              colon + 1U < end && colon < end;
      if (valid) {
        const auto left = std::from_chars(
            specification.data() + cursor, specification.data() + colon,
            first);
        const auto right = std::from_chars(
            specification.data() + colon + 1U, specification.data() + end,
            last);
        valid = left.ec == std::errc{} &&
                left.ptr == specification.data() + colon &&
                right.ec == std::errc{} &&
                right.ptr == specification.data() + end &&
                last >= first && last - first <= 31U && last <= 1000000U &&
                (state.event_range_count == 0U ||
                 first > state.event_ranges[state.event_range_count - 1U].second);
      }
      if (valid)
        state.event_ranges[state.event_range_count++] = {first, last};
      if (comma == std::string_view::npos)
        break;
      cursor = comma + 1U;
      valid = valid && cursor < specification.size();
    }
    if (!valid || state.event_range_count == 0U) {
      std::free(event_range);
      std::fputs("native boot setup failed: event trace range\n", stderr);
      return 3;
    }
    state.event_trace.open(state.retrace_hash_path + ".events.tsv",
                           std::ios::out | std::ios::trunc);
    if (!state.event_trace) {
      std::free(event_range);
      std::fputs("native boot setup failed: event trace open\n", stderr);
      return 3;
    }
    state.event_trace << "sequence\tevent\tpoll\tcompleted_updates\tframe"
                         "\tvi\tstart_calls\tget_calls\tconnected\tbuttons"
                         "\tstick_x\tstick_y\n";
  }
  std::free(event_range);
  char *controller_return = nullptr;
  std::size_t controller_return_size = 0U;
  if (_dupenv_s(&controller_return, &controller_return_size,
                "JFG_PHASE9_CONTROLLER_RETURN") != 0) {
    std::fputs("native boot setup failed: controller return environment\n", stderr);
    return 3;
  }
  if (controller_return != nullptr && *controller_return != '\0') {
    const bool valid = std::strcmp(controller_return, "1") == 0 &&
                       state.event_range_count != 0U;
    std::free(controller_return);
    if (!valid) {
      std::fputs("native boot setup failed: controller return range\n", stderr);
      return 3;
    }
    state.controller_return_trace.open(
        state.retrace_hash_path + ".controller-return.tsv",
        std::ios::out | std::ios::trunc);
    if (!state.controller_return_trace) {
      std::fputs("native boot setup failed: controller return trace\n", stderr);
      return 3;
    }
    state.controller_return_trace <<
        "sequence\tpoll\tcompleted_updates\tvi\tframe\taddress\tdata\n";
  } else {
    std::free(controller_return);
  }
  std::uint32_t graphics_shadow_cursor =
      static_cast<std::uint32_t>(kRdramSize);
  for (std::uint32_t section = 0U;
       section < jfg_generated_section_count(); ++section) {
    JfgGeneratedSectionMetadata metadata{};
    if (jfg_generated_section_metadata(section, &metadata) == 0) {
      std::fputs("native boot setup failed: graphics overlay index\n",
                 stderr);
      return 3;
    }
    if (metadata.is_overlay == 0U)
      continue;
    const std::uint64_t extent = std::uint64_t{metadata.text_size} +
                                 metadata.data_size + metadata.bss_size;
    graphics_shadow_cursor = (graphics_shadow_cursor + 15U) & ~15U;
    if (extent == 0U || extent > UINT32_MAX - graphics_shadow_cursor ||
        graphics_shadow_cursor + extent > jfg::kRt64RequiredRdramBytes) {
      std::fputs("native boot setup failed: graphics overlay index\n",
                 stderr);
      return 3;
    }
    state.graphics_overlay_shadows.push_back(
        {section, metadata.linked_vram, static_cast<std::uint32_t>(extent),
         graphics_shadow_cursor});
    graphics_shadow_cursor += static_cast<std::uint32_t>(extent);
  }
#endif
  for (std::uint32_t source = 0U;
       source < jfg_generated_section_count(); ++source) {
    const JfgGeneratedR32Descriptor *descriptors = nullptr;
    std::size_t count = 0U;
    if (jfg_generated_relocation_descriptors(source, &descriptors, &count) ==
            0 ||
        (count != 0U && descriptors == nullptr)) {
      std::fputs("native boot setup failed: relocation target index\n",
                 stderr);
      return 3;
    }
    for (std::size_t index = 0U; index < count; ++index) {
      JfgGeneratedSectionMetadata target_metadata{};
      if (jfg_generated_section_metadata(descriptors[index].target_section,
                                         &target_metadata) == 0 ||
          descriptors[index].target_offset >
              UINT32_MAX - target_metadata.linked_vram) {
        std::fputs("native boot setup failed: relocation target index\n",
                   stderr);
        return 3;
      }
      state.generated_relocation_targets.insert(
          target_metadata.linked_vram + descriptors[index].target_offset);
    }
  }
#if defined(_WIN32) && defined(JFG_PHASE8_LIVE_RUNTIME)
  char hidden_validation[2]{};
  const bool diagnostic_hidden_window =
      GetEnvironmentVariableA("JFG_DIAGNOSTIC_HIDDEN_WINDOW",hidden_validation,2U)==1U &&
      hidden_validation[0]=='1';
  LiveRt64Window live_window(state.window_input, state.pc_mouse_captured, state.pc_mouse_requested,
      state.mouse_diagnostics, play_mode && !diagnostic_hidden_window);
  state.native_window = live_window.get();
  state.pc_raw_available = live_window.raw_available();
  if (!initialize_live_renderer(state, live_window)) {
    std::fputs("native boot setup failed: RT64 renderer\n", stderr);
    return 3;
  }
#endif
  jfg::support_event("native=renderer-ready");
  state.mmio_trace = &backing.mmio_trace();
  if (!state.mmio_trace->ai_dma.configure_clocks(hardware_clocks())) return 3;
#if defined(_WIN32) && defined(JFG_PHASE8_LIVE_RUNTIME)
  state.mmio_trace->trace_audio_payloads = state.host_audio.capturing_pcm();
#endif
  state.io_revision = &state.mmio_trace->execution_io_revision;
  state.io_guest_count = &state.mmio_trace->guest_count;
#if defined(_WIN32) && defined(JFG_PHASE8_LIVE_RUNTIME)
  if (state.guest_os_probe) {
    // Read-only, ROM-pinned corrected-Mupen IPL hardware observation. This
    // initializes platform registers only, not game actors, RNG or save RAM.
    // The reset interpreter contributes its actual executed instructions.
    // Startup phase and progressive scanlines passed the independent phase
    // microtest; no game-parity acceptance follows from this profile.
    state.cpu_count = 14421016U + 2U * handoff.instructions;
    state.mmio_trace->guest_execution = true;
    state.mmio_trace->device_rdram = {state.rdram, kRdramSize};
    state.mmio_trace->device_rom = {state.rom, state.rom_size};
    // IPL3 programs cartridge-domain timing from the ROM header before boot.
    // Recover that platform state because this private entry skips IPL3.
    if (state.rom_size < 4U) return 3;
    const auto cartridge_timing = (std::uint32_t(state.rom[0]) << 24U) |
        (std::uint32_t(state.rom[1]) << 16U) |
        (std::uint32_t(state.rom[2]) << 8U) | std::uint32_t(state.rom[3]);
    const std::array<std::uint32_t, 4> pi_boot_timing{
        cartridge_timing & 255U, (cartridge_timing >> 8U) & 255U,
        (cartridge_timing >> 16U) & 15U, (cartridge_timing >> 20U) & 3U};
    for (std::size_t index = 0U; index < pi_boot_timing.size(); ++index) {
      if (!state.mmio_trace->pi_dma.write(0x14U + static_cast<std::uint32_t>(index) * 4U,
              pi_boot_timing[index], state.cpu_count, state.mmio_trace->device_rdram,
              state.mmio_trace->device_rom)) return 3;
    }

    if (!state.mmio_trace->flash_bus.bind(state.flashram,jfg::boot::FlashModel::mx29l1100,hardware_clocks().count_hz,state.cpu_count)) return 3;
    state.mmio_trace->guest_count = state.cpu_count;
    state.mmio_trace->mi_pending = 8U;
    if (!state.mmio_trace->vi_clock.initialize(hardware_clocks(),state.cpu_count,true)) return 3;
    state.mmio_trace->vi_next = UINT64_MAX;
    char* guest_trace_path = nullptr;
    std::size_t guest_trace_path_size = 0U;
    if (_dupenv_s(&guest_trace_path, &guest_trace_path_size, "JFG_PHASE9_GUEST_OS_CLOCK_TRACE") != 0)
      return 3;
    if (guest_trace_path != nullptr && *guest_trace_path != '\0') {
      state.guest_clock_trace.open(guest_trace_path, std::ios::binary | std::ios::trunc);
      std::free(guest_trace_path);
      if (!state.guest_clock_trace) return 3;
      state.guest_clock_trace << "boot\t" << state.cpu_count << '\t' << handoff.instructions << '\n';
      state.guest_clock_trace << "pi-boot\t" << cartridge_timing;
      for (auto value : pi_boot_timing) state.guest_clock_trace << '\t' << value;
      state.guest_clock_trace << '\n';
    } else {
      std::free(guest_trace_path);
      if (!original_timing_mode) {
        std::fputs("native boot setup failed: guest OS diagnostic trace required\n", stderr);
        return 3;
      }
    }

  }
#endif
  if (state.guest_leaf_probe) {
    // Explicitly observed reference boot state, not a hardware-reset claim.
    if (!state.mmio_trace->mi_mask.initialize(0U)) return 3;
    state.mmio_trace->guest_mi_mask = true;
    // The HLE task engine is initially stopped, with no outstanding task.
    // This explicit owned-device state is not a general hardware reset model.
    if (!state.mmio_trace->sp_status.initialize(1U, false)) return 3;
    state.mmio_trace->guest_sp_status = true;
    state.mmio_trace->sp_rdram = {state.rdram, kRdramSize};
    state.mmio_trace->guest_pif_boot = true;
  }
  if (!backing.arm_mmio_monitor(state.journal)) {
    std::fputs("native boot setup failed: MMIO monitor\n", stderr);
    return 3;
  }
  state.scheduler = std::make_unique<ThreadScheduler>(hle::GuestMemory(
      {rdram.data(), rdram.size()},
      hle::GuestMemory::Layout::native_word_big_endian));
  if (state.guest_leaf_probe && !state.scheduler->set_baton_hook(
      [&state](int thread, bool entering) {
        const auto index = static_cast<std::size_t>(thread);
        if (thread < 0 || index >= state.saved_rcp_masks.size())
          fail_closed_dispatch(state, "guest-leaf", "thread-mask-owner", 0U);
        // The independent thread fixture qualifies the ordinary unrestricted
        // OS global policy. Restricted global policies need their own saved
        // versus effective-mask qualification; do not silently approximate.
        std::uint32_t global = 0U;
        if (!state.scheduler->memory().read_u32(game_data("os.globalInterruptMask"), global) ||
            global != 0x003fff01U)
          fail_closed_dispatch(state, "guest-leaf", "thread-mask-global-policy", global);
        if (entering) {
          if (!state.mmio_trace->mi_mask.initialize(state.saved_rcp_masks[index]))
            fail_closed_dispatch(state, "guest-leaf", "thread-mask-restore", 0U);
        } else {
          state.saved_rcp_masks[index] = state.mmio_trace->mi_mask.read();
        }
      })) return 3;
  if (jfg_minimal_runtime_initialize() == 0 ||
      !runtime.install_table(std::make_unique<GeneratedOverlayTableAdapter>()).ok() ||
      jfg_minimal_runtime_bind_dispatch(dispatch, &state) == 0) {
    std::fputs("native boot setup failed: generated runtime\n", stderr);
    return 3;
  }
#if defined(_WIN32) && defined(JFG_PHASE8_LIVE_RUNTIME)
  // Clock policy is fixed for play. A bounded replay may request one measured
  // policy boundary so two clocks can begin from identical guest memory.
  // Avoid inspecting stream/vector internals at every guest instruction.
  char recorded_time_flag[2]{};
  const auto recorded_time_length = GetEnvironmentVariableA("JFG_PHASE9_REPLAY_RECORDED_TIME",recorded_time_flag,2U);
  if (recorded_time_length != 0U && (recorded_time_length != 1U || recorded_time_flag[0] != '1' ||
      !state.input_replay_loaded || !state.input_replay_by_poll)) return 3;
  state.input_replay_recorded_time = recorded_time_length == 1U;
  char gameplay_time_flag[2]{};
  const auto gameplay_time_length = GetEnvironmentVariableA("JFG_PHASE9_REPLAY_GAMEPLAY_TIME",gameplay_time_flag,2U);
  if (gameplay_time_length != 0U && (gameplay_time_length != 1U || gameplay_time_flag[0] != '1' ||
      !state.input_replay_loaded || !state.input_replay_by_poll || state.input_replay_recorded_time)) return 3;
  state.input_replay_gameplay_time = gameplay_time_length == 1U;
  if (state.input_replay_gameplay_time) {
    const auto& events = state.input_replay.events();
    const auto first = std::find_if(events.begin(),events.end(),[](const auto& event) { return event.sample.pc_mode == 3U; });
    if (first == events.end()) return 3;
    state.replay_gameplay_first_poll = static_cast<std::size_t>(first-events.begin());
  }
  char native_clock_flag[2]{};
  const auto native_clock_length = GetEnvironmentVariableA("JFG_DIAGNOSTIC_HOST_CLOCK",native_clock_flag,2U);
  if (native_clock_length != 0U && (native_clock_length != 1U || native_clock_flag[0] != '1')) return 3;
  // Private qualification path: exercise the existing instruction-timed
  // CPU/OS/device model through ordinary Play, including live input and audio.
  // This is not a hardware-parity claim and never changes the default policy.
  char reference_play_flag[2]{};
  const auto reference_play_length = GetEnvironmentVariableA(
      "JFG_DIAGNOSTIC_REFERENCE_PLAY_CLOCK", reference_play_flag, 2U);
  if (reference_play_length != 0U && (reference_play_length != 1U ||
      reference_play_flag[0] != '1' || !state.play_mode ||
      !original_timing_mode || native_clock_length != 0U)) return 3;
  const bool reference_play_clock = reference_play_length == 1U;
  bool native_preview_play = false;
#if defined(JFG_EXPERIMENTAL_NATIVE_PLAY_TIMING)
  native_preview_play = state.play_mode && !reference_play_clock;
#endif
  if (reference_play_clock)
    jfg::support_event("timing=instruction-model/diagnostic-play");
  state.diagnostic_host_clock_requested = native_clock_length == 1U || native_preview_play;
  // Copied-save causal experiments only; absent flags retain current behavior.
  char recovery_flag[2]{}, flight_adapter_flag[2]{};
  const auto recovery_length=GetEnvironmentVariableA(
      "JFG_DIAGNOSTIC_NATIVE_RECOVERY",recovery_flag,2U);
  const auto flight_adapter_length=GetEnvironmentVariableA(
      "JFG_DIAGNOSTIC_FLIGHT_ADAPTER",flight_adapter_flag,2U);
  if ((recovery_length && (recovery_length!=1U || recovery_flag[0]!='0')) ||
      (flight_adapter_length && (flight_adapter_length!=1U || flight_adapter_flag[0]!='0')) ||
      ((recovery_length || flight_adapter_length) && !state.diagnostic_host_clock_requested)) return 3;
  state.diagnostic_native_recovery_enabled=recovery_length==0U;
  state.flying_motion_adapter_enabled=flight_adapter_length==0U;

  char native_span_flag[2]{};
  const auto native_span_length = GetEnvironmentVariableA("JFG_DIAGNOSTIC_NATIVE_SPANS",native_span_flag,2U);
  if (native_span_length != 0U && (native_span_length != 1U || native_span_flag[0] != '1' ||
      !state.diagnostic_host_clock_requested || JFG_NATIVE_TIMING_SPAN_GENERATION != 1 ||
      state.instruction_effect_stream.is_open())) return 3;
  state.native_spans_enabled = native_span_length == 1U || native_preview_play;
  char cache_all_flag[2]{};
  const auto cache_all_length=GetEnvironmentVariableA("JFG_DIAGNOSTIC_NATIVE_CACHE_ALL",cache_all_flag,2U);
  if(cache_all_length && (cache_all_length!=1U || (cache_all_flag[0]!='0' && cache_all_flag[0]!='1') ||
      (cache_all_flag[0]=='1' && !state.native_spans_enabled)))return 3;
  state.native_cache_all_enabled=cache_all_length==1U && cache_all_flag[0]=='1';
  char shadow_filter_flag[2]{};
  const auto shadow_filter_length=GetEnvironmentVariableA("JFG_DIAGNOSTIC_NATIVE_SHADOW_FILTER",shadow_filter_flag,2U);
  if(shadow_filter_length && (shadow_filter_length!=1U ||
      (shadow_filter_flag[0]!='0' && shadow_filter_flag[0]!='1') ||
      (shadow_filter_flag[0]=='1' && !state.native_spans_enabled)))return 3;
  state.native_shadow_filter_enabled=shadow_filter_length==1U && shadow_filter_flag[0]=='1';
  char direct_sp_flag[2]{};
  const auto direct_sp_length=GetEnvironmentVariableA("JFG_DIAGNOSTIC_DIRECT_SP_ACCESS",direct_sp_flag,2U);
  if(direct_sp_length && (direct_sp_length!=1U || (direct_sp_flag[0]!='0' && direct_sp_flag[0]!='1')))return 3;
  state.mmio_trace->direct_sp_access=direct_sp_length==1U && direct_sp_flag[0]=='1';
  char direct_mi_flag[2]{};
  const auto direct_mi_length=GetEnvironmentVariableA("JFG_DIAGNOSTIC_DIRECT_MI_MASK_ACCESS",direct_mi_flag,2U);
  if(direct_mi_length && (direct_mi_length!=1U || (direct_mi_flag[0]!='0' && direct_mi_flag[0]!='1')))return 3;
  state.mmio_trace->direct_mi_mask_access=direct_mi_length==1U && direct_mi_flag[0]=='1';
  if(state.mmio_trace->direct_mi_mask_access && !state.mmio_trace->direct_sp_access)return 3;


  char pure_math[2]{};
  const auto pure_length=GetEnvironmentVariableA("JFG_DIAGNOSTIC_RESIDENT_MATH",pure_math,2U);
  if(pure_length && (pure_length!=1U || (pure_math[0]!='0' && pure_math[0]!='1') || (pure_math[0]=='1' && !state.native_spans_enabled)))return 3;
  state.resident_math_enabled=pure_length==1U ? pure_math[0]=='1' : native_preview_play;
  char bsp_flag[2]{};
  const auto bsp_length=GetEnvironmentVariableA("JFG_DIAGNOSTIC_BSP_NATIVE",bsp_flag,2U);
  if(bsp_length && (bsp_length!=1U || (bsp_flag[0]!='0' && bsp_flag[0]!='1')))return 3;
  if(bsp_length==1U && bsp_flag[0]=='1' && !jfg::boot::native_collision_available())return 3;
  state.diagnostic_bsp_enabled=jfg::boot::native_collision_available() &&
      (bsp_length==1U ? bsp_flag[0]=='1' : native_preview_play);


  if (native_preview_play) {
    jfg::support_event("timing=native-elapsed/experimental-preview");
    jfg::support_event("timing=native-spans-enabled");
  }
  wchar_t cutscene_review_path[32768]{};
  const auto cutscene_review_length=GetEnvironmentVariableW(
      L"JFG_DIAGNOSTIC_CUTSCENE_REQUEST",cutscene_review_path,32768U);
  if(cutscene_review_length) {
    if(cutscene_review_length>=32768U || !state.play_mode || !state.gameplay_trace)return 3;
    const auto review_request_path=std::filesystem::path(cutscene_review_path);
    if(!review_request_path.is_absolute())return 3;
    state.cutscene_review_session_started=std::chrono::duration_cast<std::chrono::milliseconds>(
        std::chrono::system_clock::now().time_since_epoch()).count();
    state.cutscene_review_files.start({{review_request_path,192U}});
    state.diagnostic_cutscene_review=true;
    jfg::support_event("diagnostic=cutscene-review/copied-profile-only");
  }
  char fixture_warp_vi[32]{};
  const auto fixture_warp_length=GetEnvironmentVariableA(
      "JFG_DIAGNOSTIC_ICHOR_WARP_AT_VI",fixture_warp_vi,32U);
  if(fixture_warp_length!=0U) {
    if(fixture_warp_length>=32U || state.play_mode || !state.guest_os_probe ||
       !state.input_replay_loaded || !state.gameplay_trace)return 3;
    const auto parsed=std::from_chars(fixture_warp_vi,fixture_warp_vi+fixture_warp_length,
        state.diagnostic_ichor_warp_vi);
    if(parsed.ec!=std::errc{} || parsed.ptr!=fixture_warp_vi+fixture_warp_length ||
       state.diagnostic_ichor_warp_vi<1500U || state.diagnostic_ichor_warp_vi>10000U)return 3;
  }
  char function_profile_flag[2]{};
  const auto function_profile_length=GetEnvironmentVariableA("JFG_DIAGNOSTIC_FUNCTION_PROFILE",function_profile_flag,2U);
  if(function_profile_length!=0U && (function_profile_length!=1U ||
      (function_profile_flag[0]!='1' && function_profile_flag[0]!='2' && function_profile_flag[0]!='3') ||
      !state.gameplay_trace || memory_trace_length!=1U))return 3;
  state.diagnostic_function_profile=function_profile_length==1U?unsigned(function_profile_flag[0]-'0'):0U;
  for(const auto& item:std::array<std::pair<const char*,std::uint64_t*>,2>{{
      {"JFG_DIAGNOSTIC_PROFILE_FIRST_VI",&state.diagnostic_profile_first_vi},
      {"JFG_DIAGNOSTIC_PROFILE_LAST_VI",&state.diagnostic_profile_last_vi}}}) {
    char text[32]{};const auto length=GetEnvironmentVariableA(item.first,text,32U);
    if(length==0U)continue;
    if(length>=32U || !state.diagnostic_function_profile)return 3;
    const auto parsed=std::from_chars(text,text+length,*item.second);
    if(parsed.ec!=std::errc{} || parsed.ptr!=text+length)return 3;
  }
  if(state.diagnostic_profile_last_vi<=state.diagnostic_profile_first_vi ||
     state.diagnostic_profile_last_vi-state.diagnostic_profile_first_vi>3600U)return 3;
  char update_cycles_flag[2]{};
  const auto update_cycles_length = GetEnvironmentVariableA(
      "JFG_DIAGNOSTIC_UPDATE_CYCLES", update_cycles_flag, 2U);
  if (update_cycles_length != 0U && (update_cycles_length != 1U ||
      update_cycles_flag[0] != '1' || !state.gameplay_trace)) return 3;
  state.diagnostic_update_cycles = update_cycles_length == 1U;
  char host_stage_flag[2]{};
  const auto host_stage_length=GetEnvironmentVariableA("JFG_DIAGNOSTIC_HOST_STAGES",host_stage_flag,2U);
  if(host_stage_length && (host_stage_length!=1U || host_stage_flag[0]!='1' ||
      !state.gameplay_trace || !state.input_replay_loaded))return 3;
  state.diagnostic_host_stages=host_stage_length==1U;
  char mmio_profile_flag[2]{};
  const auto mmio_profile_length=GetEnvironmentVariableA("JFG_DIAGNOSTIC_MMIO_PROFILE",mmio_profile_flag,2U);
  if(mmio_profile_length!=0U && (mmio_profile_length!=1U || mmio_profile_flag[0]!='1' ||
      !state.mmio_trace || !state.gameplay_trace || !state.input_replay_loaded))return 3;
  if(mmio_profile_length==1U) {
    if(!QueryPerformanceFrequency(&state.mmio_trace->fault_frequency) ||
        state.mmio_trace->fault_frequency.QuadPart<=0)return 3;
    state.mmio_trace->profile_faults=true;
    state.gameplay_trace.event("mmio-profile-meta",{
      static_cast<std::uint64_t>(state.mmio_trace->fault_frequency.QuadPart),kMmioHostOffsets.size()});
  }
  char cost_flag[2]{};
  const auto cost_length = GetEnvironmentVariableA("JFG_DIAGNOSTIC_CPU_COSTS", cost_flag, 2U);
  if (cost_length != 0U && (cost_length != 1U || cost_flag[0] != '1' ||
      state.play_mode || !state.gameplay_trace || !state.input_replay_loaded)) return 3;
  state.diagnostic_cpu_costs = cost_length == 1U;
  char gpu_cost_flag[2]{};
  const auto gpu_cost_length=GetEnvironmentVariableA("JFG_DIAGNOSTIC_GPU_COSTS",gpu_cost_flag,2U);
  if(gpu_cost_length!=0U && (gpu_cost_length!=1U || gpu_cost_flag[0]!='1' ||
      !state.diagnostic_function_profile))return 3;
  state.diagnostic_gpu_costs=gpu_cost_length==1U;
  if ((state.diagnostic_cpu_costs || state.diagnostic_gpu_costs) && (!state.rt64_shell ||
      !state.rt64_shell->enable_framebuffer_gpu_timing())) return 3;
  char boundary_text[32]{};
  const auto boundary_length = GetEnvironmentVariableA("JFG_DIAGNOSTIC_CLOCK_BOUNDARY_VI",boundary_text,32U);
  if (boundary_length != 0U) {
    if (boundary_length >= 32U || state.play_mode || !state.gameplay_trace ||
        !state.input_replay_loaded || !state.input_replay_by_poll) return 3;
    const auto parsed = std::from_chars(boundary_text,boundary_text+boundary_length,state.diagnostic_clock_boundary_vi);
    if (parsed.ec != std::errc{} || parsed.ptr != boundary_text+boundary_length ||
        state.diagnostic_clock_boundary_vi == 0U) return 3;
    if (state.input_replay_gameplay_time)
      state.replay_gameplay_first_poll = (std::numeric_limits<std::size_t>::max)();
  }
  char stall_text[16]{};
  auto stall_length = GetEnvironmentVariableA("JFG_DIAGNOSTIC_CLOCK_STALL_MS",stall_text,16U);
  if (stall_length == 0U)
    stall_length = GetEnvironmentVariableA("JFG_DIAGNOSTIC_BOUNDARY_STALL_MS",stall_text,16U);
  if (stall_length != 0U) {
    if (stall_length >= 16U || state.play_mode || !state.diagnostic_host_clock_requested ||
        state.diagnostic_clock_boundary_vi == 0U) return 3;
    const auto parsed = std::from_chars(stall_text,stall_text+stall_length,state.diagnostic_boundary_stall_ms);
    if (parsed.ec != std::errc{} || parsed.ptr != stall_text+stall_length ||
        state.diagnostic_boundary_stall_ms == 0U || state.diagnostic_boundary_stall_ms > 2000U) return 3;
  }
  state.diagnostic_host_clock = state.diagnostic_host_clock_requested && state.diagnostic_clock_boundary_vi == 0U;
  char audio_source_flag[2]{};
  const auto audio_source_length=GetEnvironmentVariableA("JFG_DIAGNOSTIC_NATIVE_AUDIO_SOURCE",audio_source_flag,2U);
  if(audio_source_length!=0U && (audio_source_length!=1U || audio_source_flag[0]!='1' ||
      !state.diagnostic_host_clock_requested)) return 3;
  // Chosen at startup, before even the instruction-clock prefix builds audio.
  // Switching providers over outstanding DMA descriptors is not supported.
  state.native_audio_source=audio_source_length==1U || native_preview_play;
  if(state.native_audio_source) jfg::support_event("audio=synchronous-rom-sample-cache");
  char audio_playback_flag[2]{};
  const auto audio_playback_length=GetEnvironmentVariableA("JFG_DIAGNOSTIC_NATIVE_AUDIO_PLAYBACK",audio_playback_flag,2U);
  if(audio_playback_length!=0U && (audio_playback_length!=1U ||
      (audio_playback_flag[0]!='0' && audio_playback_flag[0]!='1') ||
      !state.diagnostic_host_clock_requested)) return 3;
  state.native_audio_playback=audio_playback_length ? audio_playback_flag[0]=='1' : native_preview_play;
  if(state.native_audio_playback)jfg::support_event("audio=native-demand-playback");

  std::string clock_record_path,clock_replay_path;
  const auto clock_path = [](const char* name,std::string& destination) {
    char* value=nullptr;std::size_t size=0;
    if (_dupenv_s(&value,&size,name)!=0) return false;
    const bool valid=size<=32768U;
    if (valid && value) destination=value;
    std::free(value);return valid;
  };
  if (!clock_path("JFG_DIAGNOSTIC_CLOCK_RECORD",clock_record_path) ||
      !clock_path("JFG_DIAGNOSTIC_CLOCK_REPLAY",clock_replay_path)) return 3;
  char clock_limit_text[32]{};
  const auto clock_limit_length=GetEnvironmentVariableA(
      "JFG_DIAGNOSTIC_CLOCK_SAMPLE_LIMIT",clock_limit_text,32U);
  if (clock_limit_length!=0U) {
    if (clock_limit_length>=32U || state.play_mode ||
        (clock_record_path.empty() && clock_replay_path.empty())) return 3;
    std::uint64_t clock_sample_limit=0U;
    const auto parsed_limit=std::from_chars(clock_limit_text,
        clock_limit_text+clock_limit_length,clock_sample_limit);
    if (parsed_limit.ec!=std::errc{} ||
        parsed_limit.ptr!=clock_limit_text+clock_limit_length ||
        !state.native_clock_samples.set_sample_limit(clock_sample_limit)) return 3;
  }
  if (!clock_record_path.empty() || !clock_replay_path.empty()) {
    if (state.play_mode || !state.input_replay_loaded || !state.diagnostic_host_clock_requested ||
        state.diagnostic_clock_boundary_vi==0U || state.diagnostic_boundary_stall_ms!=0U ||
        (!clock_record_path.empty() && !clock_replay_path.empty())) return 3;
    state.native_clock_sample_buffer.resize(65536U);
    if (!clock_record_path.empty()) {
      state.native_clock_sample_output.rdbuf()->pubsetbuf(state.native_clock_sample_buffer.data(),65536);
      state.native_clock_sample_output.open(clock_record_path,std::ios::binary|std::ios::trunc);
      if (!state.native_clock_samples.record(state.native_clock_sample_output)) return 3;
    } else {
      state.native_clock_sample_input.rdbuf()->pubsetbuf(state.native_clock_sample_buffer.data(),65536);
      state.native_clock_sample_input.open(clock_replay_path,std::ios::binary);
      if (!state.native_clock_samples.replay(state.native_clock_sample_input)) return 3;
    }
  }
  char release_text[32]{};
  const auto release_length=GetEnvironmentVariableA("JFG_DIAGNOSTIC_CLOCK_RELEASE_VI",release_text,32U);
  if (release_length != 0U) {
    if (release_length>=32U || state.play_mode || !state.gameplay_trace ||
        !state.input_replay_by_poll || !state.native_clock_samples.replaying()) return 3;
    const auto parsed=std::from_chars(release_text,release_text+release_length,state.diagnostic_clock_release_vi);
    if (parsed.ec!=std::errc{} || parsed.ptr!=release_text+release_length ||
        state.diagnostic_clock_release_vi<=state.diagnostic_clock_boundary_vi ||
        state.diagnostic_clock_release_vi>=state.retrace_target) return 3;
  }
  char rom_completion_flag[2]{};
  const auto rom_completion_length=GetEnvironmentVariableA(
      "JFG_DIAGNOSTIC_NATIVE_ROM_COMPLETION",rom_completion_flag,2U);
  if(rom_completion_length && (rom_completion_length!=1U ||
      (rom_completion_flag[0]!='0' && rom_completion_flag[0]!='1') ||
      (rom_completion_flag[0]=='1' && !state.diagnostic_host_clock_requested)))return 3;
  const bool native_rom_requested=rom_completion_length ? rom_completion_flag[0]=='1' : native_preview_play;
  if (state.mmio_trace) {
    state.mmio_trace->native_elapsed_time = state.diagnostic_host_clock;
    // Recorded clock and instruction observers retain the reference bus model.
    // Ordinary input replay and the function-cost profiler remain eligible.
    state.mmio_trace->native_rom_completion=native_rom_requested &&
        !state.native_clock_sample_input.is_open() && !state.native_clock_sample_output.is_open() &&
        state.focus_update_start==0U && !state.guest_clock_trace.is_open() &&
        state.point_probe_pcs.empty() && !state.device_event_stream &&
        !state.eret_transfer_stream.is_open() && !state.instruction_effect_stream.is_open();
    if(state.mmio_trace->native_rom_completion)
      jfg::support_event("assets=native-rom-completion");
  }
  char rom_api_flag[2]{};
  const auto rom_api_length=GetEnvironmentVariableA("JFG_DIAGNOSTIC_NATIVE_ROM_API",rom_api_flag,2U);
  if(rom_api_length && (rom_api_length!=1U || (rom_api_flag[0]!='0' && rom_api_flag[0]!='1') ||
      (rom_api_flag[0]=='1' && !state.diagnostic_host_clock_requested)))return 3;
  // Qualified immutable-ROM SDK completion in ordinary native Play. Recorded
  // clocks and instruction observers retain the original PI/OS execution path.
  const bool native_rom_api_requested=rom_api_length ? rom_api_flag[0]=='1' : native_preview_play;
  state.native_rom_api=native_rom_api_requested && state.mmio_trace &&
      state.mmio_trace->native_rom_completion;
  if(state.native_rom_api)jfg::support_event("assets=native-rom-api-enabled");
  if(state.diagnostic_host_clock && state.native_audio_playback && state.mmio_trace &&
      !state.mmio_trace->ai_dma.native_queue_capacity(4U))
    fail_closed_dispatch(state,"audio","native-queue-capacity",0U);

  if (state.diagnostic_host_clock_requested && (!state.guest_os_probe || !state.original_os_host_pacing ||
      !state.point_probe_pcs.empty() || state.device_event_stream || state.eret_transfer_stream.is_open())) return 3;
  char* model_watch_value = nullptr;
  std::size_t model_watch_size = 0U;
  if (_dupenv_s(&model_watch_value,&model_watch_size,"JFG_DIAGNOSTIC_MODEL_POINTER_WATCH") != 0)
    return 3;
  const bool model_watch_requested = model_watch_value != nullptr;
  const bool model_watch_hardware = model_watch_requested && std::string_view(model_watch_value) == "hardware";
  const bool model_watch_pages = model_watch_requested && std::string_view(model_watch_value) == "pages";
  const bool model_watch_valid = !model_watch_requested || model_watch_hardware || model_watch_pages ||
      std::string_view(model_watch_value) == "1";
  std::free(model_watch_value);
  if (!model_watch_valid || (model_watch_requested &&
      (state.rdram_capture_path.empty() || !state.guest_os_probe))) return 3;
  char abort_capture_flag[2]{};
  const bool abort_capture_requested=GetEnvironmentVariableA(
      "JFG_DIAGNOSTIC_ABORT_CAPTURE",abort_capture_flag,2U)==1U && abort_capture_flag[0]=='1';
  if(abort_capture_requested && state.rdram_capture_path.empty())return 3;
  if ((model_watch_requested || abort_capture_requested ||
       (state.gameplay_trace && !state.rdram_capture_path.empty())) &&
      std::signal(SIGABRT,private_abort_capture)==SIG_ERR)
    return 3;
  state.private_model_pointer_watch = model_watch_requested;
  state.private_model_hardware_watch = model_watch_hardware;
  state.private_model_page_watch = model_watch_pages;
  if ((model_watch_hardware || model_watch_pages) &&
      AddVectoredExceptionHandler(1U,model_watch_pages ? private_page_write_observer
                                                     : private_model_write_observer)==nullptr)
    return 3;

  state.execution_fast_profile_ready = !state.diagnostic_host_clock && state.guest_os_probe &&
      state.mmio_trace != nullptr && state.point_probe_pcs.empty() &&
      !state.device_event_stream && !state.eret_transfer_stream.is_open();
#endif
  jfg::support_event("native=running");
  DispatchBinding binding{state, true};
  if (state.guest_leaf_probe) {
    if (jfg_minimal_runtime_bind_cpu(native_cpu_operation, &state) == 0) {
      std::fputs("native boot setup failed: CPU operation owner\n", stderr);
      return 3;
    }
    binding.cpu_bound = true;
  }
  const auto function =
      runtime.lookup_function_by_guest_address(handoff.transfer_target);
  if (!function.ok())
    ledger(state, "generated", "reset-transfer-unresolved",
           handoff.transfer_target);
  else {
    recomp_context context{};
    constexpr std::array<gpr recomp_context::*, 32> kGprMembers = {
        &recomp_context::r0,  &recomp_context::r1,  &recomp_context::r2,
        &recomp_context::r3,  &recomp_context::r4,  &recomp_context::r5,
        &recomp_context::r6,  &recomp_context::r7,  &recomp_context::r8,
        &recomp_context::r9,  &recomp_context::r10, &recomp_context::r11,
        &recomp_context::r12, &recomp_context::r13, &recomp_context::r14,
        &recomp_context::r15, &recomp_context::r16, &recomp_context::r17,
        &recomp_context::r18, &recomp_context::r19, &recomp_context::r20,
        &recomp_context::r21, &recomp_context::r22, &recomp_context::r23,
        &recomp_context::r24, &recomp_context::r25, &recomp_context::r26,
        &recomp_context::r27, &recomp_context::r28, &recomp_context::r29,
        &recomp_context::r30, &recomp_context::r31,
    };
    for (std::size_t index = 0U; index < handoff.gpr.size(); ++index)
      context.*kGprMembers[index] =
          static_cast<gpr>(sign_extend_mips32(handoff.gpr[index]));
    context.f_odd = &context.f0.u32h;
    context.status_reg = 0U;
    context.mips3_float_mode = 0U;
    if (state.guest_leaf_probe)
      cop0_status_write(&context, 0x34000000U); // observed reference cold boot
    if (state.guest_os_probe) {
      state.guest_transport = std::make_unique<GuestThreadTransport<recomp_context>>(
          [&state](std::uint32_t entry, recomp_context& cpu) {
            const auto body = state.runtime->lookup_function_by_guest_address(entry);
            if (!body.ok()) fail_closed_dispatch(state, "guest-os", "thread-entry-unavailable", entry);
            invoke_generated(body.function, state.rdram, &cpu, state, entry);
          }, [](recomp_context& cpu) {
            cpu.f_odd = cpu.mips3_float_mode ? &cpu.f1.u32l : &cpu.f0.u32h;
            set_cop1_cs(cpu.fcr31);
          }, [&state](const GuestThreadTransport<recomp_context>::EretBoundary& edge,
                      const recomp_context& cpu) {
#if defined(_WIN32) && defined(JFG_PHASE8_LIVE_RUNTIME)
            if (!state.eret_transfer_stream.is_open() && !state.instruction_effect_stream.is_open()) return;
            if (!state.guest_eret_boundary || state.guest_epc != edge.target_pc)
              fail_closed_dispatch(state, "eret-transfer-probe", "uncommitted-return", state.guest_last_pc);
            emit_instruction_effect(state, cpu, 2U, state.instruction_effect_section,
                state.guest_last_pc, state.guest_last_word, edge.target_pc, edge.to_thread);
            if (!state.eret_transfer_stream.is_open()) return;
            const EretTransferRow row{
              static_cast<std::uint32_t>(state.completed_game_updates + 1U),
              state.guest_last_pc, state.guest_last_word, edge.from_thread, edge.to_thread,
              edge.target_pc, cpu.status_reg, static_cast<std::uint32_t>(state.cpu_count),
              {0, cpu.r1, cpu.r2, cpu.r3, cpu.r4, cpu.r5, cpu.r6, cpu.r7,
               cpu.r8, cpu.r9, cpu.r10, cpu.r11, cpu.r12, cpu.r13, cpu.r14, cpu.r15,
               cpu.r16, cpu.r17, cpu.r18, cpu.r19, cpu.r20, cpu.r21, cpu.r22, cpu.r23,
               cpu.r24, cpu.r25, cpu.r26, cpu.r27, cpu.r28, cpu.r29, cpu.r30, cpu.r31}};
            if (!state.eret_transfer_probe.emit(row))
              fail_closed_dispatch(state, "eret-transfer-probe", "output-or-boundary", state.guest_last_pc);
#else
            (void)state; (void)edge; (void)cpu;
#endif
          });
#if defined(_WIN32) && defined(JFG_PHASE8_LIVE_RUNTIME)
      state.guest_transport->enable_timing(state.diagnostic_cpu_costs || state.diagnostic_function_profile!=0U || state.diagnostic_update_cycles);
      char fiber_flag[2]{};
      if (GetEnvironmentVariableA("JFG_DIAGNOSTIC_FIBER_TRANSPORT",fiber_flag,2U)==1U && fiber_flag[0]=='1') {
        state.guest_transport->set_fiber_mode(true);
        jfg::support_event("transport=windows-fibers");
        jfg::support_event("profiling=per-fiber-cycles-high-bit-participant");
      }
      char baton_spin_flag[2]{};
      if (GetEnvironmentVariableA("JFG_DIAGNOSTIC_BATON_SPIN",baton_spin_flag,2U)==1U && baton_spin_flag[0]=='1') {
        state.guest_transport->set_spin_budget(50U);
        jfg::support_event("transport=bounded-spin-50us");
      }

#endif
      try {
        state.guest_transport->run(handoff.transfer_target, context,
            state.play_mode ? UINT64_MAX : 1000000U);
      } catch (const std::exception& error) {
        std::fprintf(stderr, "guest OS transport failure: %s\n", error.what());
        fail_closed_dispatch(state, "guest-os", "transport-contract", state.guest_last_pc);
      }
    } else {
      invoke_generated(function.function, rdram.data(), &context, state,
                       handoff.transfer_target);
    }
  }
  if (!state.ledgered)
    ledger(state, "generated", "returned", handoff.transfer_target);
  return 4;
}

bool reset_transfer_target(const std::vector<std::uint8_t> &rom,
                           std::uint32_t &target) {
  std::vector<std::uint8_t> bytes(kRdramSize);
  if (!load_static_sections(rom, bytes))
    return false;
  const auto handoff = interpret_reset_handoff(
      bytes, initial_entrypoint(), kRdramSize / sizeof(std::uint32_t) + 4096U);
  if (!handoff.ok())
    return false;
  target = handoff.transfer_target;
  return true;
}

int run(const char *executable_path, const char *rom_path, unsigned timeout_ms,
        bool child_mode, const char *child_token, const char *marker_handle,
        unsigned retrace_target, unsigned poll_target, bool play_mode) {
  jfg::support_event("native=boot");
  if (child_mode) {
#if defined(_WIN32)
    if (!validate_child_capability(child_token, marker_handle))
      return 3;
#else
    return 3;
#endif
    return run_child(rom_path, retrace_target, poll_target, play_mode);
  }
#if defined(_WIN32)
  return run_parent(executable_path, rom_path, timeout_ms, retrace_target,
                    poll_target, play_mode);
#else
  (void)executable_path;
  (void)timeout_ms;
  (void)child_token;
  (void)marker_handle;
  std::fputs(
      "native boot setup failed: process isolation unavailable on this host\n",
      stderr);
  return 3;
#endif
}
} // namespace jfg::boot::native
