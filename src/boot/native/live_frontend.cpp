#include "runtime_services.hpp"
#include "gameplay_scopes.hpp"
namespace jfg::boot::native::detail {
#if defined(_WIN32) && defined(JFG_PHASE8_LIVE_RUNTIME)
bool service_host_audio(State &state, const bool pace) {
  const DiagnosticHostStage host_stage(state,"host-profile-audio");
  if (state.mmio_trace == nullptr || state.rdram == nullptr ||
      state.mmio_trace->ai_submission_overflows != 0U)
    return false;
  while (state.mmio_trace->ai_submission_read <
         state.mmio_trace->ai_submission_write) {
    const std::size_t slot = static_cast<std::size_t>(
        state.mmio_trace->ai_submission_read %
        MmioTrace::kAiSubmissionCapacity);
    const MmioTrace::AiSubmission submission =
        state.mmio_trace->ai_submissions[slot];
    if (state.mmio_trace->trace_audio_payloads) {
      state.gameplay_trace.event("audio-payload", {state.mmio_trace->ai_submission_read,
          submission.address,submission.length,submission.submitted_count,state.cpu_count,
          submission.payload_hash,state.mmio_trace->audio_payload_hash(submission.address,submission.length)});
    }
    if (!state.host_audio.queue(state.rdram, submission.address,
                                submission.length,
                                submission.dac_rate,hardware_clocks().video_hz))
      return false;
    ++state.mmio_trace->ai_submission_read;
  }
  // Interactive mode is already paced by the VI/window clock.  Waiting on
  // the SDL queue as well creates a second, drifting clock and visible frame
  // hitches whenever a graphics frame arrives late.  Headless probes have no
  // window clock, so retain audio throttling there unless a diagnostic replay
  // explicitly uses the same VI clock as interactive playback.
  state.host_audio.service(
      pace?(initial_tv_mode()==0U?50U:60U):0U, pace && !state.play_mode && !state.fast_replay &&
                !state.realtime_replay &&
                !(state.original_os_host_pacing && state.original_os_host_anchor_ready));
  // Only native interactive audio uses recovery. Original timing, null sinks,
  // startup/resume anchors, loading and cutscene completion remain excluded.
  hle::GuestMemory audio_memory({state.rdram,kRdramSize},
      hle::GuestMemory::Layout::native_word_big_endian);
  std::uint32_t audio_mode = UINT32_MAX, loading = UINT32_MAX;
  const bool recoverable = state.play_mode && !state.fast_replay &&
      state.diagnostic_host_clock && state.native_audio_playback &&
      state.original_os_host_anchor_ready && !state.cutscene_prompt.transition &&
      !state.cutscene_chain && audio_memory.read_u32(game_data("globals.audioQueueMode"),audio_mode) &&
      audio_mode == 0U && audio_memory.read_u32(game_data("globals.levelLoading"),loading) && loading == 0U;
  if (!state.host_audio.recover_latency(recoverable)) return false;
  state.audio_device_initialized = state.host_audio.initialized();
  state.audio_device_started = state.host_audio.started();
  state.audio_device_frequency = state.host_audio.frequency();
  state.audio_device_buffers = state.host_audio.submitted_buffers();
  state.audio_device_queued_bytes = state.host_audio.queued_bytes();
  state.audio_device_consumed_bytes = state.host_audio.consumed_bytes();
  state.audio_device_consumed_ms =
      state.host_audio.consumed_milliseconds();
  state.audio_device_underruns = state.host_audio.underruns();
  state.audio_device_overruns = state.host_audio.overruns();
  state.mmio_trace->ai_emulated_remaining_length =
      state.host_audio.current_buffer_remaining();
  return true;
}

void service_navigation_inventory_requests(State &state, bool publish);

void service_live_window(State &state) {
  const DiagnosticHostStage host_stage(state,"host-profile-window");
  {
    const auto input=state.window_input.consume_frame(state.host_keys,state.host_key_presses,state.exit_requested,false);
    state.menu_pointer_frame=input.pointer;
    if(input.focus_lost){state.menu_pointer.reset();for(auto &effect:state.pc_rumble_effects)effect.clear();state.pc_mouse.clear();state.pc_wheel.clear();state.pc_input_blocked=true;(void)state.controller_input_gate.blocked(true,state.controller_ports.samples);}
    if(state.pc_mouse_captured.load()) {
      state.pc_mouse.add(input.x,input.y);
      if(input.x || input.y)state.mouse_diagnostics.increment(jfg::MouseCount::mailbox_nonzero);
    }
    state.pc_wheel.add(input.wheel);
  }
  const SlowHostWork window_service_timing(state,"host-window-service");
  const auto frame_start = std::chrono::steady_clock::now();
  if (state.host_frame_start_initialized) {
    const auto interval = static_cast<std::uint64_t>(
        std::chrono::duration_cast<std::chrono::microseconds>(
            frame_start - state.host_frame_start)
            .count());
    state.host_frame_interval_max_us =
        (std::max)(state.host_frame_interval_max_us, interval);
    state.host_frames_over_25ms += interval > 25000U ? 1U : 0U;
    state.host_frames_over_50ms += interval > 50000U ? 1U : 0U;
    state.host_frames_over_100ms += interval > 100000U ? 1U : 0U;
    if (state.timing_trace) {
      state.timing_trace << "frame\t" << state.vi_frames << '\t'
                         << state.vi_retraces << '\t' << interval << '\t'
                         << state.presented_frames << '\t'
                         << state.pending_graphics_tasks.size() << '\n';
    }
  }
  state.host_frame_start = frame_start;
  state.host_frame_start_initialized = true;
  const auto presentation = jfg::vi_presentation_size(
      state.vi_mode_horizontal_start, state.rt64_vi.vertical_start, state.rt64_vi.vertical_sync);
  // Pointer coordinates follow the actual displayed VI, including widescreen.
  // The launcher canvas follows the selected video mode instead: a temporary
  // cinematic crop must not resize the canvas and zoom away its black bars.
  if(presentation.valid())state.window_presentation=presentation;
  NativeGameMemory video_memory({state.rdram,kRdramSize});
  // Read the user's saved screen preference, not the temporary cinematic VI
  // mode. frontGetScreenMode uses this same options bit in the supported ROM.
  const auto canvas=jfg::game_display_canvas(game_view(video_memory).u32(game_data_ref("globals.frontendDisplayFlags")));
  const bool widescreen=canvas.height==180U;
  if(state.native_window && widescreen!=state.window_widescreen) {
    state.window_widescreen=widescreen;
    PostMessageW(static_cast<HWND>(state.native_window),LiveRt64Window::kAspectMessage,
      320U,widescreen?180:240);
    state.gameplay_trace.event("display-canvas",{state.vi_retraces,320U,widescreen?180U:240U});
  }
  const auto frontend = state.native_window ? GetAncestor(static_cast<HWND>(state.native_window), GA_ROOT) : nullptr;
  bool frontend_paused = false;
  while (!state.exit_requested && frontend && IsWindow(frontend) &&
         GetPropW(frontend, L"JfgFrontendPause") != nullptr) {
    if (!frontend_paused) {
      if (state.diagnostic_host_clock &&
          !state.host_count_clock.pause(std::chrono::steady_clock::now()))
        fail_closed_dispatch(state,"native-clock","pause",0U);
      state.gameplay_trace.event("host-pause", {state.vi_retraces,
          state.diagnostic_host_clock ?
              state.host_count_clock.sample(std::chrono::steady_clock::now()).value_or(UINT64_MAX) : state.cpu_count});
      state.host_audio.frontend_pause(true);
      SetPropW(frontend,L"JfgFrontendPaused",reinterpret_cast<HANDLE>(1));
      frontend_paused = true;
    }
    {
    const auto input=state.window_input.consume_frame(state.host_keys,state.host_key_presses,state.exit_requested);
    state.menu_pointer.reset();state.menu_pointer_frame={};
    if(input.focus_lost){state.menu_pointer.reset();for(auto &effect:state.pc_rumble_effects)effect.clear();state.pc_mouse.clear();state.pc_wheel.clear();state.pc_input_blocked=true;(void)state.controller_input_gate.blocked(true,state.controller_ports.samples);}
    if(state.pc_mouse_captured.load()) {
      state.pc_mouse.add(input.x,input.y);
      if(input.x || input.y)state.mouse_diagnostics.increment(jfg::MouseCount::mailbox_nonzero);
    }
    state.pc_wheel.add(input.wheel);
  }
    service_navigation_inventory_requests(state,true);
    std::this_thread::sleep_for(std::chrono::milliseconds(10));
  }
  if (frontend_paused) {
    RemovePropW(frontend,L"JfgFrontendPaused");
    if (state.diagnostic_host_clock &&
        !state.host_count_clock.resume(std::chrono::steady_clock::now()))
      fail_closed_dispatch(state,"native-clock","resume",0U);
    state.gameplay_trace.event("host-resume", {state.vi_retraces,
        state.diagnostic_host_clock ?
            state.host_count_clock.sample(std::chrono::steady_clock::now()).value_or(UINT64_MAX) : state.cpu_count});
    state.host_audio.frontend_pause(false);
    state.host_frame_deadline_initialized = false;
    state.host_frame_start_initialized = false;
    state.original_os_host_anchor_ready = false;
  }
  if (state.original_os_host_pacing) return;
  if (!state.host_frame_deadline_initialized) {
    state.host_frame_deadline = std::chrono::steady_clock::now();
    state.host_frame_deadline_initialized = true;
  }
  state.host_frame_deadline += std::chrono::microseconds(16667);
  const auto deadline_now = std::chrono::steady_clock::now();
  if (state.host_frame_deadline > deadline_now) {
    std::this_thread::sleep_until(state.host_frame_deadline);
  } else if (deadline_now - state.host_frame_deadline >
             std::chrono::microseconds(66668)) {
    // Do not run an unbounded catch-up burst after shader compilation, window
    // movement, or another long host stall.  Resume from the current VI edge.
    state.host_frame_deadline = deadline_now;
  }
}

bool write_live_frame_capture(State &state) {
  // Diagnostic images stay bounded in memory during playback. Flush only on
  // shutdown, beside the session's private RDRAM capture.
  if(!state.cutscene_capture.empty() && !state.rdram_capture_path.empty()) {
    const auto folder=std::filesystem::path(state.rdram_capture_path).parent_path();
    for(const auto& saved:state.cutscene_capture) {
      const auto path=folder/("transition-"+std::to_string(saved.vi)+".ppm");
      std::ofstream out(path,std::ios::binary);
      out<<"P6\n"<<saved.width<<' '<<saved.height<<"\n255\n";
      out.write(saved.rgb.data(),static_cast<std::streamsize>(saved.rgb.size()));
      if(!out){state.gameplay_trace.event("cinematic-image-write-failed",{saved.vi});break;}
    }
    state.cutscene_capture.clear();
  }
  if (state.frame_capture_path.empty())
    return true;
  if (state.rt64_shell == nullptr)
    return false;
  auto frame = state.rt64_shell->last_presented_frame();
  if (!frame.valid() && !state.play_mode && state.presented_frames != 0U) {
    // A bounded probe can end more than two VIs after its last presentation.
    // Read back the already selected display buffer at the stop boundary;
    // do not run more guest instructions merely to obtain a diagnostic image.
    state.last_rt64_error = state.rt64_shell->present(true);
    if (state.last_rt64_error != jfg::Rt64ShellError::none)
      return false;
    frame = state.rt64_shell->last_presented_frame();
    state.gameplay_trace.event("final-frame-capture", {state.vi_retraces,
        state.controller_samples, state.presented_frames});
  }
  if (!frame.valid())
    return false;
  std::ofstream stream(state.frame_capture_path, std::ios::binary);
  if (!stream)
    return false;
  stream << "P6\n" << frame.width << ' ' << frame.height << "\n255\n";
  for (std::size_t y = 0U; y < frame.height; ++y) {
    const std::size_t row = y * frame.row_pitch_bytes;
    for (std::size_t x = 0U; x < frame.width; ++x) {
      const std::size_t pixel = row + x * 4U;
      const std::array<char, 3U> rgb = {
          static_cast<char>(
              std::to_integer<unsigned char>(frame.bgra8[pixel + 2U])),
          static_cast<char>(
              std::to_integer<unsigned char>(frame.bgra8[pixel + 1U])),
          static_cast<char>(
              std::to_integer<unsigned char>(frame.bgra8[pixel]))};
      stream.write(rgb.data(), static_cast<std::streamsize>(rgb.size()));
    }
  }
  state.frame_captured = static_cast<bool>(stream);
  return state.frame_captured;
}

bool write_logical_rdram_capture(const State &state,
                                 const std::filesystem::path &path) {
  std::ofstream stream(path, std::ios::binary);
  if (!stream)
    return false;
  std::array<char, 4096U> logical_bytes{};
  for (std::size_t base = 0U; base < kRdramSize;
       base += logical_bytes.size()) {
    for (std::size_t index = 0U; index < logical_bytes.size(); ++index) {
      logical_bytes[index] =
          static_cast<char>(state.rdram[(base + index) ^ 3U]);
    }
    stream.write(logical_bytes.data(),
                 static_cast<std::streamsize>(logical_bytes.size()));
  }
  return static_cast<bool>(stream);
}

bool write_private_rdram_capture(const State &state) {
  if (state.rdram_capture_path.empty())
    return true;
  return write_logical_rdram_capture(state, state.rdram_capture_path);
}

bool write_private_rt64_snapshot(
    const State &state, const std::span<const std::byte> snapshot) {
  if (state.rdram_capture_path.empty())
    return true;
  std::ofstream stream(state.rdram_capture_path + ".rt64",
                       std::ios::binary);
  if (!stream || snapshot.empty() || snapshot.size() % 4U != 0U)
    return false;
  std::array<char, 4096U> logical_bytes{};
  for (std::size_t base = 0U; base < snapshot.size();
       base += logical_bytes.size()) {
    const std::size_t chunk =
        (std::min)(logical_bytes.size(), snapshot.size() - base);
    for (std::size_t index = 0U; index < chunk; ++index) {
      logical_bytes[index] = static_cast<char>(
          std::to_integer<std::uint8_t>(snapshot[(base + index) ^ 3U]));
    }
    stream.write(logical_bytes.data(), static_cast<std::streamsize>(chunk));
  }
  return static_cast<bool>(stream);
}

#if defined(_WIN32) && defined(JFG_PHASE8_LIVE_RUNTIME)
bool write_mod_export(State &state, const std::filesystem::path &path, const std::string &text) {
  const auto copy = std::make_shared<const std::string>(text);
  if (path.filename() == L"mesh.json") {
    state.navigation_mesh_export = copy;
    return true;
  }
  jfg::AsyncSnapshots::Batch files;
  if (state.navigation_mesh_export)
    files.push_back({state.navigation_output/L"mesh.json",state.navigation_mesh_export});
  files.push_back({path,copy});
  return state.snapshot_writer.submit(1U,std::move(files));
}


// Process explicit inventory commands on the game thread, including while its
// simulation is paused by the Mods dialog. This does not tick AI, move actors,
// clear enemies, restore health, advance time, or initiate room transitions.
void service_navigation_inventory_requests(State &state, bool publish) {
  auto &mod=state.navigation_mod;
  if(!mod.observing())return;
  const auto config=state.navigation_config_files.latest();
  if(!config || config->size()!=5U)return;
  const auto fresh=[&](std::size_t index,const std::string &previous) {
    return config->at(index).status==jfg::ConfigFileValue::Status::ready &&
           config->at(index).text!=previous;
  };
  const bool weapons=fresh(3U,state.navigation_last_weapons_request);
  const bool floyd=fresh(4U,state.navigation_last_floyd_request);
  if(!weapons && !floyd)return;
  NativeGameMemory memory({state.rdram,kRdramSize});
  try {
    const auto list=jfg::mod::actors(memory);
    const auto now=std::chrono::duration_cast<std::chrono::milliseconds>(
        std::chrono::system_clock::now().time_since_epoch()).count();
    const auto old_weapons_nonce=mod.weapons_nonce,old_floyd_nonce=mod.floyd_nonce;
    if(weapons) {
      state.navigation_last_weapons_request=config->at(3U).text;
      std::istringstream request(state.navigation_last_weapons_request);
      if(mod.give_weapons(request,memory,list,now))
        state.gameplay_trace.event("mod-give-weapons",
            {state.vi_retraces,mod.generation,mod.weapons_nonce,mod.player,mod.weapon_grants});
    }
    if(floyd) {
      state.navigation_last_floyd_request=config->at(4U).text;
      std::istringstream request(state.navigation_last_floyd_request);
      if(mod.give_floyd(request,memory,list,now))
        state.gameplay_trace.event("mod-give-floyd",
            {state.vi_retraces,mod.generation,mod.floyd_nonce,mod.player,mod.floyd_grants});
    }
    if(publish && (old_weapons_nonce!=mod.weapons_nonce || old_floyd_nonce!=mod.floyd_nonce)) {
      const auto level=game_view(memory).u32(game_data_ref("globals.currentLevel"));
      const bool mesh_ready=state.navigation_mesh_export && mod.player!=0U &&
          game_view(memory).u32(game_data_ref("globals.currentTrack"))==mod.last_track && level==mod.last_level;
      std::ostringstream output;mod.write_state(output,memory,list,level,mesh_ready);
      if(!write_mod_export(state,state.navigation_output/L"live.json",output.str()))++mod.invalid;
    }
  } catch(const std::runtime_error &) {++mod.invalid;}
}

void update_navigation_mod(State &state) {
  if(!state.navigation_mod.observing())return;
  const DiagnosticHostStage total_cost(state,"host-profile-navigation");
  auto &mod=state.navigation_mod;
  mod.dialogue=navigation_dialogue(state);
  NativeGameMemory memory({state.rdram,kRdramSize});
  try {
    const auto list=jfg::mod::actors(memory);
    // File I/O is isolated on a worker; commands still pass their original
    // parser, nonce, generation, actor and five-second freshness checks here.
    const auto config=state.navigation_config_files.latest();
    if (mod.updates % 6U == 0U && config && config->size()==5U) {
      const DiagnosticHostStage read_cost(state,"host-profile-navigation-read");
      if (config->at(0).status==jfg::ConfigFileValue::Status::ready) {
        std::istringstream settings(config->at(0).text);
        (void)mod.configure_mods(settings);
      }
      service_navigation_inventory_requests(state,false);
      if (config->at(1).status==jfg::ConfigFileValue::Status::ready) {
        std::istringstream warp(config->at(1).text);
        const auto stamp=std::chrono::duration_cast<std::chrono::milliseconds>(std::chrono::system_clock::now().time_since_epoch()).count();
        if(mod.warp_to_exit(warp,memory,list,stamp) && state.gameplay_trace)
          state.gameplay_trace.event("exit-warp",{state.vi_retraces,mod.generation,
            mod.warp_nonce,game_view(memory).u32(game_data_ref("globals.currentLevel")),mod.player,
            memory.u32(memory.u32(mod.player+game_member("layout.actor.control"))+game_member("layout.playerControl.exitContact"))});
      }
    }
    if(state.diagnostic_ichor_warp_vi!=0U && !state.diagnostic_ichor_warp_done &&
       state.vi_retraces>=state.diagnostic_ichor_warp_vi) {
      state.diagnostic_ichor_warp_done=true;
      std::uint32_t chosen=0U;unsigned matches=0U;
      if(game_view(memory).u32(game_data_ref("globals.currentLevel"))==19U)
        for(const auto& exit:jfg::mod::exits(memory,list))
          // Native transition code 0xFFB5 resolves to Ichor (level 181).
          if(exit.condition==23 && exit.destination==0xFFB5U){chosen=exit.address;++matches;}
      if(matches!=1U)
        fail_closed_dispatch(state,"image-fixture","ichor-exit-not-unique",0U);
      const auto stamp=std::chrono::duration_cast<std::chrono::milliseconds>(
          std::chrono::system_clock::now().time_since_epoch()).count();
      std::ostringstream command;
      command<<"JFGWARP1 19 "<<mod.generation<<' '<<(mod.warp_nonce+1U)<<' '
             <<stamp<<' '<<chosen<<'\n';
      std::istringstream input(command.str());
      if(!mod.warp_to_exit(input,memory,list,stamp))
        fail_closed_dispatch(state,"image-fixture","ichor-warp-rejected",0U);
      state.gameplay_trace.event("fixture-exit-warp",{state.vi_retraces,mod.generation,
          chosen,mod.player});
    }
    bool player_present=false;
    for(const auto &actor:list) {
      if(actor.address==mod.player)player_present=true;
      (void)mod.clear_enemy(memory,actor.address);
    }
    if(!player_present)mod.player=0;
    else (void)mod.full_health(memory,mod.player);
    ++mod.updates;
    const auto now = std::chrono::duration_cast<std::chrono::milliseconds>(std::chrono::system_clock::now().time_since_epoch()).count();
    const auto ai_level = game_view(memory).u32(game_data_ref("globals.currentLevel"));
    if (mod.enabled && mod.updates % 6U == 0U && config && config->size()==5U &&
        config->at(2).status==jfg::ConfigFileValue::Status::ready) {
      std::istringstream command(config->at(2).text);
      (void)mod.pilot.command(command,ai_level,mod.generation,now);
    }
    if (mod.enabled && mod.player != 0U) {
      const auto p = jfg::mod::position(memory, mod.player);
      const auto camera = jfg::mod::control_camera(memory);
      mod.pilot.camera_heading(camera.known, camera.yaw);
      mod.pilot.tick({p.x,p.y,p.z}, jfg::mod::gameplay_active(memory,mod.player),ai_level,mod.generation,now);
      const auto movement=jfg::mod::player_motion(memory,mod.player);
      if(movement.known && (movement.state==6U||movement.state==12U) &&
         mod.pilot.active() && std::string_view(mod.pilot.state).starts_with("jump_"))
        mod.pilot.stop("jump_unexpected_grab_state");
      // Diagnostic rows are immutable copies; the bounded worker never reads
      // guest memory. Slow storage must not stall simulation or audio.
      if(jfg::mod::gameplay_active(memory,mod.player)) {
        std::ostringstream trace;
        trace<<mod.updates<<','<<now<<','<<ai_level<<','<<p.x<<','<<p.y<<','<<p.z
             <<','<<movement.known<<','<<movement.state<<','<<movement.animation
             <<','<<movement.animation_frame<<','<<game_view(memory).u32(game_data_ref("globals.controlButtons"))<<'\n';
        (void)state.movement_trace.append(trace.str());
      }
      if(std::string_view(mod.pilot.state).starts_with("jump_") && mod.pilot.active()) {
        std::ostringstream trace;const auto input=mod.pilot.observed_input();
        trace<<mod.updates<<','<<now<<','<<ai_level<<','<<p.x<<','<<p.y<<','<<p.z
             <<','<<input.x<<','<<input.y<<','<<input.buttons<<','<<mod.pilot.state
             <<','<<camera.yaw<<','<<memory.s16(mod.player)<<'\n';
        (void)state.jump_trace.append(trace.str());
      }
    } else mod.pilot.stop("player_unavailable");
    if(mod.updates%6U!=0U)return;
    const auto track=game_view(memory).u32(game_data_ref("globals.currentTrack")), level=game_view(memory).u32(game_data_ref("globals.currentLevel"));
    bool mesh_ready=mod.player!=0U && track==mod.last_track && level==mod.last_level;
    if(mod.player!=0U && !mesh_ready) {
      try {
        const DiagnosticHostStage mesh_cost(state,"host-profile-navigation-mesh");
        const auto mesh=[&] {
          const DiagnosticHostStage decode_cost(state,"host-profile-navigation-decode");
          return jfg::mod::decode_mesh(memory,track);
        }();
        std::ostringstream output;
        {
          const DiagnosticHostStage serialize_cost(state,"host-profile-navigation-json");
          jfg::mod::write_mesh(output,mesh,level,mod.generation);
        }
        mesh_ready=write_mod_export(state, state.navigation_output/L"mesh.json",output.str());
        if(mesh_ready){mod.last_track=track;mod.last_level=level;}
      }catch(const std::runtime_error &){++mod.invalid;}
    }
    const DiagnosticHostStage state_cost(state,"host-profile-navigation-state");
    std::ostringstream output;mod.write_state(output,memory,list,level,mesh_ready);
    if(!write_mod_export(state, state.navigation_output/L"live.json",output.str()))++mod.invalid;
  }catch(const std::runtime_error &){++mod.invalid;}
}
#endif


#if defined(_WIN32) && defined(JFG_PHASE8_LIVE_RUNTIME)
// Capture when the native fog getter returns, before the controller advances.
// No global renderer preference or wall clock is involved, and no guest state
// is changed. Competing fog controllers keep their original rendering.

#endif
#endif
} // namespace jfg::boot::native::detail
