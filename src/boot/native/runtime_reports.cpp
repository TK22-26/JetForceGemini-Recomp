#include "runtime_services.hpp"
namespace jfg::boot::native::detail {
#if defined(_WIN32) && defined(JFG_PHASE8_LIVE_RUNTIME)
#if defined(_WIN32) && defined(JFG_PHASE8_LIVE_RUNTIME)
jfg::DayNightFog capture_daynight_fog(State &state) {
  if (!state.rdram || !section_addresses ||
      !state.active_overlay_sections.contains(game_module(OriginalModule::day_night)) ||
      state.active_overlay_sections.contains(game_module(OriginalModule::mantis_lighting)) ||
      state.active_overlay_sections.contains(game_module(OriginalModule::vela_magic))) return {};
  NativeGameMemory ram({state.rdram, kRdramSize});
  const auto base = static_cast<std::uint32_t>(section_addresses[game_module(OriginalModule::day_night)]);
  const auto read = [&](const auto &memory) -> jfg::DayNightFog {
    const auto phase = memory.u32(base + game_overlay_data("renderer.day.phase",OriginalModule::day_night));
    if (phase >= 12U) return {};
    const auto current = base + game_overlay_data("renderer.day.phases",OriginalModule::day_night) + phase * 20U;
    const auto next = base + game_overlay_data("renderer.day.phases",OriginalModule::day_night) + ((phase + 1U) % 12U) * 20U;
    const auto red = memory.u32(base + game_overlay_data("renderer.day.red",OriginalModule::day_night));
    const auto green = memory.u32(base + game_overlay_data("renderer.day.green",OriginalModule::day_night));
    const auto blue = memory.u32(base + game_overlay_data("renderer.day.blue",OriginalModule::day_night));
    if (red > 255U || green > 255U || blue > 255U) return {};
    return jfg::make_daynight_fog(memory.u32(base + game_overlay_data("renderer.day.elapsed",OriginalModule::day_night)),
        memory.u32(base + game_overlay_data("renderer.day.duration",OriginalModule::day_night)), memory.u16(current + 6U),
        memory.u16(current + 8U), memory.u16(next + 6U), memory.u16(next + 8U),
        static_cast<int>(memory.u32(base + game_overlay_data("renderer.day.near",OriginalModule::day_night))),
        static_cast<int>(memory.u32(base + game_overlay_data("renderer.day.far",OriginalModule::day_night))),
        (red << 24U) | (green << 16U) | (blue << 8U) | 255U);
  };
  if (ram.valid(base, game_overlay_extent(OriginalModule::day_night))) return read(ram);
  JfgGeneratedSectionMetadata metadata{};
  if (!jfg_generated_section_metadata(game_module(OriginalModule::day_night), &metadata) ||
      metadata.is_overlay != 1U || base != metadata.linked_vram || (base & 3U)) return {};
  const std::uint64_t extent = std::uint64_t(metadata.text_size) +
      metadata.data_size + metadata.bss_size;
  const std::uint32_t offset = base - kKseg0;
  if (extent < game_overlay_extent(OriginalModule::day_night) || extent > 0x10000U || offset > kGuestAddressSpan ||
      extent > kGuestAddressSpan - offset || (extent & 3U)) return {};
  const jfg::mod::DialogueMemory memory(ram, base,
      std::span<const std::uint8_t>(state.rdram + offset, static_cast<std::size_t>(extent)));
  return read(memory);
}

// Diagnostic only: follow the day/night controller's canonical relocated
// globals and the values returned to its fog/geometry colour consumers.
// The original code/data image in physical RDRAM can hold stale BSS copies.
void trace_daynight_atmosphere(State &state, std::uint32_t target,
                              const std::array<std::uint32_t, 5> &outputs) {
  if (!state.gameplay_trace || !state.gameplay_trace_actors ||
      !state.rdram || !section_addresses ||
      !state.active_overlay_sections.contains(game_module(OriginalModule::day_night))) return;
  NativeGameMemory ram({state.rdram, kRdramSize});
  const auto base = static_cast<std::uint32_t>(section_addresses[game_module(OriginalModule::day_night)]);
  std::array<std::uint64_t, 27> row{};
  row[0] = state.vi_retraces; row[1] = state.gameplay_trace_updates;
  row[2] = target; row[3] = game_view(ram).u32(game_data_ref("globals.currentLevel")); row[4] = base;
  for (std::size_t i = 0; i < outputs.size(); ++i) {
    auto &value = row[22U + i];
    value = UINT32_MAX;
    if (target == game_overlay_token("overlay.day.track_fade") && i < 3U && ram.valid(outputs[i], 4U))
      value = ram.u32(outputs[i]);
    else if (target == game_overlay_token("overlay.day.fog") && ram.valid(outputs[i], i < 2U ? 2U : 1U))
      value = i < 2U ? ram.u16(outputs[i]) : ram.u8(outputs[i]);
  }
  const auto emit = [&](const auto &memory) {
    for (std::uint32_t i = 0; i < 4U; ++i)
      row[5U + i] = memory.u32(base + game_overlay_data("renderer.day.observation",OriginalModule::day_night) + i * 4U);
    for (std::uint32_t i = 0; i < 13U; ++i)
      row[9U + i] = memory.u32(base + game_overlay_data("renderer.day.observationBss",OriginalModule::day_night) + i * 4U);
    state.gameplay_trace.event("daynight-atmosphere", row);
  };
  if (ram.valid(base, game_overlay_extent(OriginalModule::day_night))) { emit(ram); return; }
  JfgGeneratedSectionMetadata metadata{};
  if (!jfg_generated_section_metadata(game_module(OriginalModule::day_night), &metadata) ||
      metadata.is_overlay != 1U || base != metadata.linked_vram || (base & 3U)) return;
  const std::uint64_t extent = std::uint64_t(metadata.text_size) +
      metadata.data_size + metadata.bss_size;
  const std::uint32_t offset = base - kKseg0;
  if (extent < game_overlay_extent(OriginalModule::day_night) || extent > 0x10000U || offset > kGuestAddressSpan ||
      extent > kGuestAddressSpan - offset || (extent & 3U)) return;
  const jfg::mod::DialogueMemory memory(ram, base,
      std::span<const std::uint8_t>(state.rdram + offset, static_cast<std::size_t>(extent)));
  emit(memory);
}
#endif

void trace_gameplay_state(State &state, bool update) {
  if (!state.gameplay_trace || state.rdram == nullptr) return;
  if (!update && state.gameplay_trace_vi == state.vi_retraces) return;
  if (update) ++state.gameplay_trace_updates;
  else state.gameplay_trace_vi = state.vi_retraces;
  hle::GuestMemory memory({state.rdram, kRdramSize},
                          hle::GuestMemory::Layout::native_word_big_endian);
  std::uint32_t level = 0, actors = 0, count = 0;
  (void)memory.read_u32(game_data("globals.currentLevel"), level);
  (void)memory.read_u32(game_data("globals.objectList"), actors);
  (void)memory.read_u32(game_data("globals.objectCount"), count);
  state.gameplay_trace.event(update ? "update" : "tick", {
      state.vi_retraces, state.controller_samples, state.gameplay_trace_updates,
      state.rdram[(game_data("globals.frontendMode")&0x1FFFFFFFU) ^ 3U], level, count, state.presented_frames,
      state.graphics_tasks, state.pending_graphics_tasks.size(), state.dispatch_calls,
      state.audio_device_queued_bytes, state.audio_device_consumed_bytes,
      state.audio_device_underruns, state.audio_device_overruns});
  if (!update || !state.gameplay_trace_actors) return;
  if (count > 256U) {
    state.gameplay_trace.event("actor-table-invalid", {state.vi_retraces, actors, count});
    return;
  }
  for (std::uint32_t index = 0; index < 256U; ++index) {
    std::uint32_t actor = 0, header = 0;
    if (index >= count || !memory.read_u32(actors + index * 4U, actor) || actor == 0U) {
      if (state.gameplay_actor_seen[index])
        state.gameplay_trace.event("actor-removed", {state.vi_retraces, state.gameplay_trace_updates, index});
      state.gameplay_actor_seen[index] = false;
      continue;
    }
    // All actor types, sampled after the game update, only when state changes.
    // Payload: identity/name, actor[0..0x7f], properties[0..0x1f], control[0..0x1f].
    std::array<std::uint64_t, 56> row{};
    row[0] = state.vi_retraces; row[1] = state.gameplay_trace_updates;
    row[2] = index; row[3] = actor;
    (void)memory.read_u32(actor + game_member("layout.actor.header"), header);
    for (std::uint32_t n = 0; n < 4U; ++n) {
      std::uint32_t word = 0;
      row[4U + n] = memory.read_u32(header + 4U + n * 4U, word) ? word : UINT32_MAX;
    }
    for (std::uint32_t n = 0; n < 32U; ++n) {
      std::uint32_t word = 0;
      row[8U + n] = memory.read_u32(actor + n * 4U, word) ? word : UINT32_MAX;
    }
    for (std::uint32_t block = 0; block < 2U; ++block) {
      std::uint32_t pointer = 0;
      (void)memory.read_u32(actor + (block == 0U ? game_member("layout.actor.properties") : game_member("layout.actor.control")), pointer);
      for (std::uint32_t n = 0; n < 8U; ++n) {
        std::uint32_t word = 0;
        row[40U + block * 8U + n] = pointer != 0U && memory.read_u32(pointer + n * 4U, word) ? word : UINT32_MAX;
      }
    }
    const auto &previous = state.gameplay_actor_previous[index];
    if (!state.gameplay_actor_seen[index] ||
        !std::equal(row.begin() + 2, row.end(), previous.begin() + 2)) {
      state.gameplay_trace.event("actor", row);
      state.gameplay_actor_previous[index] = row;
      state.gameplay_actor_seen[index] = true;
    }
  }
}

void write_actor_timing_trace(State &state) {
  if (!state.actor_timing_trace || !state.timing_trace.is_open() ||
      state.rdram == nullptr ||
      state.last_actor_trace_retrace == state.vi_retraces)
    return;
  state.last_actor_trace_retrace = state.vi_retraces;
  hle::GuestMemory actor_memory(
      {state.rdram, kRdramSize},
      hle::GuestMemory::Layout::native_word_big_endian);
  std::uint32_t actor_list = 0U;
  std::uint32_t actor_count = 0U;
  if (!actor_memory.read_u32(game_data("globals.objectList"), actor_list) ||
      !actor_memory.read_u32(game_data("globals.objectCount"), actor_count) || actor_count > 256U)
    return;
  for (std::uint32_t index = 0U; index < actor_count; ++index) {
    std::uint32_t actor = 0U;
    std::uint32_t header = 0U;
    std::uint32_t name0 = 0U;
    std::uint32_t name1 = 0U;
    if (!actor_memory.read_u32(actor_list + index * 4U, actor) ||
        actor == 0U || !actor_memory.read_u32(actor + game_member("layout.actor.header"), header) ||
        header == 0U || !actor_memory.read_u32(header + 4U, name0) ||
        !actor_memory.read_u32(header + 8U, name1) ||
        name0 != 0x616E696DU || name1 != 0x426C7565U)
      continue;
    state.timing_trace << "actor\t" << state.vi_frames << '\t'
                       << state.vi_retraces << "\t0\t" << std::hex
                       << actor << '\t' << name0 << name1 << "\t0\t";
    for (std::uint32_t offset = 0U; offset < 0x200U; offset += 4U) {
      std::uint32_t word = 0U;
      if (offset != 0U)
        state.timing_trace << ':';
      if (actor_memory.read_u32(actor + offset, word))
        state.timing_trace << word;
      else
        state.timing_trace << "invalid";
    }
    state.timing_trace << std::dec << '\n';
  }
}

std::optional<std::string> hash_logical_rdram_region(
    const State &state, const std::uint32_t guest_address,
    const std::size_t length) {
  if (state.rdram == nullptr)
    return std::nullopt;
  const std::uint64_t physical = guest_address & 0x1FFFFFFFU;
  if (physical > kRdramSize || length > kRdramSize - physical)
    return std::nullopt;
  jfg::testkernel::Sha256 hasher;
  std::array<std::uint8_t, 1024U> logical{};
  std::size_t consumed = 0U;
  while (consumed < length) {
    const std::size_t chunk =
        (std::min)(logical.size(), length - consumed);
    for (std::size_t index = 0U; index < chunk; ++index)
      logical[index] = state.rdram[
          (static_cast<std::size_t>(physical) + consumed + index) ^ 3U];
    hasher.update_bytes(logical.data(), chunk);
    consumed += chunk;
  }
  return jfg::testkernel::hex_digest(hasher.finish());
}

void write_retrace_semantic_hash(State &state, std::ostream *update_output,
                                std::ostream *poll_output) {
  if ((update_output != nullptr && poll_output != nullptr) ||
      (update_output == nullptr && poll_output == nullptr &&
       !state.retrace_hash_trace.is_open()) ||
      state.rdram == nullptr)
    return;
  hle::GuestMemory memory({state.rdram, kRdramSize},
                          hle::GuestMemory::Layout::native_word_big_endian);
  constexpr std::uint32_t kObjectListAddress = game_data("globals.objectList");
  constexpr std::uint32_t kObjectCountAddress = game_data("globals.objectCount");
  constexpr std::uint32_t kRngSeedAddress = game_data("diagnostic.rngState");
  constexpr std::uint32_t kFrontModeAddress = game_data("globals.frontendMode");
  constexpr std::uint32_t kGameGlobalsAddress = game_data("diagnostic.gameGlobals");
  constexpr std::size_t kGameGlobalsBytes = 0x90U;
  constexpr std::uint32_t kCameraStateAddress = game_data("diagnostic.cameraState");
  constexpr std::size_t kCameraStateBytes = 0x158U;
  constexpr std::size_t kActorStateBytes = 0x200U;
  constexpr std::uint32_t kMaximumActors = 256U;

  std::uint32_t actor_list = 0U;
  std::uint32_t actor_count = 0U;
  std::uint32_t rng_seed = 0U;
  (void)memory.read_u32(kObjectListAddress, actor_list);
  (void)memory.read_u32(kObjectCountAddress, actor_count);
  (void)memory.read_u32(kRngSeedAddress, rng_seed);
  const unsigned front_mode = state.rdram[(kFrontModeAddress - kKseg0) ^ 3U];
  const bool actor_table_valid = actor_count <= kMaximumActors &&
      (actor_count == 0U ||
       hash_logical_rdram_region(state, actor_list,
                                 actor_count * sizeof(std::uint32_t))
           .has_value());
  const auto actor_table_hash = actor_table_valid
      ? hash_logical_rdram_region(state, actor_list,
                                  actor_count * sizeof(std::uint32_t))
      : std::nullopt;
  const auto player_hash = state.phase9_player_actor == 0U
      ? std::nullopt
      : hash_logical_rdram_region(state, state.phase9_player_actor,
                                  kActorStateBytes);
  const auto globals_hash = hash_logical_rdram_region(
      state, kGameGlobalsAddress, kGameGlobalsBytes);
  const auto camera_hash = hash_logical_rdram_region(
      state, kCameraStateAddress, kCameraStateBytes);

  auto &stream = poll_output != nullptr ? *poll_output
      : update_output != nullptr ? *update_output : state.retrace_hash_trace;
  stream << "{\"kind\":\""
         << (poll_output != nullptr ? "jfg-phase9-poll-hash"
             : update_output == nullptr ? "jfg-phase9-retrace-hash"
                                        : "jfg-phase9-update-hash")
         << "\",\"schema\":1,\""
         << (poll_output != nullptr ? "poll"
             : update_output == nullptr ? "retrace" : "update") << "\":"
         << (poll_output != nullptr ? state.controller_samples - 1U
             : update_output == nullptr ? state.vi_retraces
                                        : state.completed_game_updates)
         << ",\"front_mode\":" << front_mode
         << ",\"rng_seed\":\"0x" << std::hex << std::setw(8)
         << std::setfill('0') << rng_seed
         << "\",\"player_actor\":\"0x" << std::setw(8)
         << state.phase9_player_actor << "\"" << std::dec
         << ",\"player_sha256\":";
  if (player_hash.has_value())
    stream << '"' << *player_hash << '"';
  else
    stream << "null";
  stream << ",\"actor_list\":\"0x" << std::hex << std::setw(8)
         << std::setfill('0') << actor_list << "\"" << std::dec
         << ",\"actor_count\":" << actor_count
         << ",\"actor_table_sha256\":";
  if (actor_table_hash.has_value())
    stream << '"' << *actor_table_hash << '"';
  else
    stream << "null";
  stream << ",\"globals_sha256\":";
  if (globals_hash.has_value())
    stream << '"' << *globals_hash << '"';
  else
    stream << "null";
  stream << ",\"camera_sha256\":";
  if (camera_hash.has_value())
    stream << '"' << *camera_hash << '"';
  else
    stream << "null";
  stream << ",\"actors\":[";
  bool first = true;
  if (actor_table_valid) {
    for (std::uint32_t index = 0U; index < actor_count; ++index) {
      std::uint32_t actor = 0U;
      (void)memory.read_u32(actor_list + index * sizeof(std::uint32_t), actor);
      const auto digest = actor == 0U
          ? std::nullopt
          : hash_logical_rdram_region(state, actor, kActorStateBytes);
      if (!first)
        stream << ',';
      first = false;
      stream << "{\"index\":" << index << ",\"address\":\"0x"
             << std::hex << std::setw(8) << std::setfill('0') << actor
             << "\",\"sha256\":" << std::dec;
      if (digest.has_value())
        stream << '"' << *digest << '"';
      else
        stream << "null";
      stream << '}';
    }
  }
  stream << ']';
  if (poll_output != nullptr) {
    std::uint32_t level_word = 0U;
    (void)memory.read_u32(game_data("globals.currentLevel"), level_word);
    stream << ",\"level_word\":" << level_word
           << ",\"connected\":" << (state.latched_controller_connected ? 1 : 0)
           << ",\"buttons\":" << state.latched_controller_buttons
           << ",\"stick_x\":" << static_cast<int>(state.latched_controller_stick_x)
           << ",\"stick_y\":" << static_cast<int>(state.latched_controller_stick_y)
           << ",\"update_counter_valid\":"
           << (state.update_hash_trace.is_open() ? "true" : "false")
           << ",\"completed_updates\":";
    if (state.update_hash_trace.is_open())
      stream << state.completed_game_updates;
    else
      stream << "null";
    stream << ",\"vi_retraces\":" << state.vi_retraces
           << ",\"controller_read_start_calls\":"
           << state.controller_read_start_calls
           << ",\"controller_get_data_calls\":"
           << state.controller_get_data_calls;
  } else if (update_output != nullptr)
    stream << ",\"controller_polls\":" << state.controller_samples
           << ",\"vi_retraces\":" << state.vi_retraces;
  stream << "}\n";
}

void write_private_progress(State &state,
                            const char *stage) {
  constexpr std::uint64_t kProgressIntervalRetraces = 30U;
  // Actor motion needs per-retrace sampling to expose short freeze/jump
  // patterns. Deduplication keeps the many progress call sites from writing
  // the same actor state more than once in a retrace.
  trace_gameplay_state(state, false);
  write_actor_timing_trace(state);
  // This diagnostic contains sizeable rolling renderer traces.  Rewriting it
  // at every begin/end marker can turn optional observability into several
  // synchronous filesystem writes per video frame and make an otherwise
  // smooth build hitch.  One atomic snapshot per half-second is sufficient
  // for watchdog diagnosis and keeps instrumentation off the critical path.
  if (state.progress_path.empty() ||
      state.vi_retraces % kProgressIntervalRetraces != 0U ||
      state.last_progress_retrace == state.vi_retraces)
    return;
  state.last_progress_retrace = state.vi_retraces;
  std::ostringstream stream;
  const unsigned front_mode = state.rdram[(game_data("globals.frontendMode")&0x1FFFFFFFU) ^ 3U];
  const std::uint32_t last_dispatch =
      state.recent_dispatch_position == 0U
          ? 0U
          : state.recent_dispatches[(state.recent_dispatch_position - 1U) %
                                    state.recent_dispatches.size()];
  stream << "{\"stage\":\"" << stage << "\""
         << ",\"vi_retraces\":" << state.vi_retraces
         << ",\"front_mode\":" << front_mode
         << ",\"dispatches\":" << state.dispatch_calls
         << ",\"last_dispatch\":\"0x" << std::hex << last_dispatch
         << std::dec << '"'
         << ",\"generated_calls\":" << state.generated_calls
         << ",\"sound_queue_recoveries\":" << state.sound_queue_recoveries
         << ",\"timing_game_updates\":" << state.timing_game_updates
         << ",\"audio_device_underruns\":" << state.audio_device_underruns
         << ",\"audio_device_overruns\":" << state.audio_device_overruns
         << ",\"mapped_calls\":" << state.mapped_calls
         << ",\"interrupt_timeslices\":" << state.interrupt_timeslices
         << ",\"receive_successes\":" << state.receive_successes
         << ",\"receive_empties\":" << state.receive_empties
         << ",\"receive_blocks\":" << state.receive_blocks
         << ",\"last_receive_queue\":\"0x" << std::hex
         << state.last_receive_queue << "\""
         << ",\"last_receive_block\":" << std::dec
         << state.last_receive_block
         << ",\"last_receive_result\":" << state.last_receive_result
         << ",\"graphics_tasks\":" << state.graphics_tasks
         << ",\"presented_frames\":" << state.presented_frames
         << ",\"vi_current_framebuffer\":\"0x" << std::hex
         << state.vi_current_framebuffer
         << "\",\"vi_next_framebuffer\":\"0x"
         << state.vi_next_framebuffer
         << "\",\"graphics_color_image\":\"0x"
         << state.graphics_color_image
         << "\",\"recent_graphics_targets\":\"";
  const std::size_t graphics_recent_count =
      (std::min)(state.recent_graphics_position,
                 state.recent_graphics_color_images.size());
  for (std::size_t index = 0U; index < graphics_recent_count; ++index) {
    const std::size_t distance = graphics_recent_count - index;
    const std::size_t slot =
        (state.recent_graphics_position - distance) %
        state.recent_graphics_color_images.size();
    if (index != 0U)
      stream << ',';
    stream << state.recent_graphics_command_addresses[slot] << ':'
           << state.recent_graphics_color_images[slot] << ':'
           << state.recent_graphics_vi_selections[slot] << ':'
           << state.recent_graphics_matrix_commands[slot] << ':'
           << state.recent_graphics_vertices_loaded[slot] << ':'
           << state.recent_graphics_vertices_in_clip[slot] << ':'
           << state.recent_graphics_triangles[slot];
  }
  stream << "\"" << std::dec
         << ",\"decoded_audio_tasks\":" << state.decoded_audio_tasks
         << ",\"controller_samples\":" << state.controller_samples
         << ",\"non_neutral_controller_samples\":"
         << state.non_neutral_controller_samples
         << ",\"non_neutral_controller_writes\":"
         << state.non_neutral_controller_writes
         << ",\"game_pressed_observations\":"
         << state.game_pressed_observations
         << ",\"game_stick_observations\":"
         << state.game_stick_observations
         << ",\"last_game_stick_x\":"
         << static_cast<int>(state.last_game_stick_x)
         << ",\"last_game_stick_y\":"
         << static_cast<int>(state.last_game_stick_y)
         << ",\"menu_stick_observations\":"
         << state.menu_stick_observations
         << ",\"last_menu_stick_x\":"
         << static_cast<int>(state.last_menu_stick_x)
         << ",\"last_menu_stick_y\":"
         << static_cast<int>(state.last_menu_stick_y)
         << ",\"ai_register_writes\":"
         << (state.mmio_trace == nullptr
                 ? 0U
                 : state.mmio_trace->ai_register_writes)
         << ",\"ai_buffer_submissions\":"
         << (state.mmio_trace == nullptr
                 ? 0U
                 : state.mmio_trace->ai_buffer_submissions)
         << ",\"ai_dram_address\":\"0x" << std::hex
         << (state.mmio_trace == nullptr
                 ? 0U
                 : state.mmio_trace->ai_dram_address)
         << "\",\"ai_length\":" << std::dec
         << (state.mmio_trace == nullptr ? 0U
                                         : state.mmio_trace->ai_length)
         << ",\"ai_control\":"
         << (state.mmio_trace == nullptr ? 0U
                                         : state.mmio_trace->ai_control)
         << ",\"ai_dac_rate\":"
         << (state.mmio_trace == nullptr ? 0U
                                         : state.mmio_trace->ai_dac_rate)
         << ",\"ai_bit_rate\":"
         << (state.mmio_trace == nullptr ? 0U
                                         : state.mmio_trace->ai_bit_rate)
         << ",\"audio_task_us\":" << state.audio_task_microseconds
         << ",\"graphics_prepare_us\":"
         << state.graphics_prepare_microseconds
         << ",\"graphics_submit_us\":"
         << state.graphics_submit_microseconds
         << ",\"graphics_present_us\":"
         << state.graphics_present_microseconds
         << ",\"host_frame_interval_max_us\":"
         << state.host_frame_interval_max_us
         << ",\"present_interval_max_us\":"
         << state.present_interval_max_us
         << ",\"graphics_prepare_max_us\":"
         << state.graphics_prepare_max_us
         << ",\"graphics_submit_max_us\":"
         << state.graphics_submit_max_us
         << ",\"graphics_present_max_us\":"
         << state.graphics_present_max_us
         << ",\"host_frames_over_25ms\":"
         << state.host_frames_over_25ms
         << ",\"host_frames_over_50ms\":"
         << state.host_frames_over_50ms
         << ",\"host_frames_over_100ms\":"
         << state.host_frames_over_100ms
         << ",\"recent_matrix_conversions\":\"" << std::hex;
  const std::size_t matrix_recent_count =
      (std::min)(state.recent_matrix_conversion_position,
                 state.recent_matrix_conversion_sources.size());
  for (std::size_t index = 0U; index < matrix_recent_count; ++index) {
    const std::size_t distance = matrix_recent_count - index;
    const std::size_t slot =
        (state.recent_matrix_conversion_position - distance) %
        state.recent_matrix_conversion_sources.size();
    if (index != 0U)
      stream << ',';
    stream << state.recent_matrix_conversion_sources[slot] << ':'
           << state.recent_matrix_conversion_destinations[slot];
    for (const std::uint32_t word :
         state.recent_matrix_conversion_first_rows[slot])
      stream << ':' << word;
    for (const std::uint32_t word :
         state.recent_matrix_conversion_output_words[slot])
      stream << ':' << word;
  }
  stream << '"' << std::dec
         << ",\"recent_matrix_cats\":\"" << std::hex;
  const std::size_t matrix_cat_recent_count =
      (std::min)(state.recent_matrix_cat_position,
                 state.recent_matrix_cat_args.size());
  for (std::size_t index = 0U; index < matrix_cat_recent_count; ++index) {
    const std::size_t distance = matrix_cat_recent_count - index;
    const std::size_t slot =
        (state.recent_matrix_cat_position - distance) %
        state.recent_matrix_cat_args.size();
    if (index != 0U)
      stream << ',';
    for (const std::uint32_t argument : state.recent_matrix_cat_args[slot])
      stream << argument << ':';
    for (std::size_t word = 0U;
         word < state.recent_matrix_cat_words[slot].size(); ++word) {
      if (word != 0U)
        stream << ':';
      stream << state.recent_matrix_cat_words[slot][word];
    }
  }
  stream << '"' << std::dec
         << ",\"recent_matrix_watch\":\"" << std::hex;
  const std::size_t watch_recent_count =
      (std::min)(state.recent_matrix_watch_position,
                 state.recent_matrix_watch_addresses.size());
  for (std::size_t index = 0U; index < watch_recent_count; ++index) {
    const std::size_t distance = watch_recent_count - index;
    const std::size_t slot =
        (state.recent_matrix_watch_position - distance) %
        state.recent_matrix_watch_addresses.size();
    if (index != 0U)
      stream << ',';
    stream << state.recent_matrix_watch_addresses[slot] << ':'
           << state.recent_matrix_watch_before[slot] << ':'
           << state.recent_matrix_watch_after[slot] << ':'
           << state.recent_matrix_watch_targets[slot] << ':'
           << state.recent_matrix_watch_callers[slot] << ':'
           << state.recent_matrix_watch_current_targets[slot] << ':'
           << state.recent_matrix_watch_return_addresses[slot];
  }
  stream << '"' << std::dec
         << ",\"poison_matrix_watch\":\"" << std::hex;
  for (std::size_t index = 0U; index < state.poison_matrix_watch.size();
       ++index) {
    if (index != 0U)
      stream << ':';
    stream << state.poison_matrix_watch[index];
  }
  stream << '"' << std::dec
         << ",\"poison_dispatch_history\":\"" << std::hex;
  for (std::size_t index = 0U; index < state.poison_dispatch_history.size();
       ++index) {
    if (index != 0U)
      stream << ',';
    stream << state.poison_dispatch_history[index];
  }
  stream << '"' << std::dec
         << ",\"materialize_reject_reason\":"
         << state.materialize_reject_reason
         << ",\"materialize_reject_address\":\"0x" << std::hex
         << state.materialize_reject_address << "\""
         << ",\"materialize_reject_word0\":\"0x"
         << state.materialize_reject_word0 << "\""
         << ",\"materialize_reject_word1\":\"0x"
         << state.materialize_reject_word1 << "\"" << std::dec
         << ",\"materialize_parent_address\":\"0x" << std::hex
         << state.materialize_parent_address << "\""
         << ",\"materialize_parent_word0\":\"0x"
         << state.materialize_parent_word0 << "\""
         << ",\"materialize_parent_word1\":\"0x"
         << state.materialize_parent_word1 << "\"" << std::dec
         << ",\"materialize_block_address\":\"0x" << std::hex
         << state.materialize_block_address << "\""
         << ",\"materialize_parent_segment_base\":\"0x"
         << state.materialize_parent_segment_base << "\"" << std::dec
         << ",\"recent_dispatches\":\"";
  const std::size_t recent_count =
      (std::min)(state.recent_dispatch_position,
                 state.recent_dispatches.size());
  for (std::size_t index = 0U; index < recent_count; ++index) {
    const std::size_t distance = recent_count - index;
    if (index != 0U)
      stream << ',';
    stream << std::hex
           << state.recent_dispatches[(state.recent_dispatch_position -
                                       distance) %
                                      state.recent_dispatches.size()];
  }
  stream << std::dec << "\"}\n";
  (void)state.snapshot_writer.submit(0U,{{state.progress_path,
      std::make_shared<const std::string>(stream.str())}});
  // Keep the replay and timing streams recoverable even if the host console
  // or launcher disappears without giving the runtime a normal shutdown.
  // This runs on the existing half-second progress cadence, off the
  // per-frame hot path used by the renderer diagnostics.
  if (state.input_record.is_open())
    state.input_record.flush();
  if (state.native_clock_sample_output.is_open())
    state.native_clock_sample_output.flush();
  if (state.timing_trace.is_open())
    state.timing_trace.flush();
  state.gameplay_trace.flush();
  if (state.retrace_hash_trace.is_open())
    state.retrace_hash_trace.flush();
  if (state.update_hash_trace.is_open())
    state.update_hash_trace.flush();
  if (state.update_word_trace.is_open())
    state.update_word_trace.flush();
  if (state.controller_return_trace.is_open())
    state.controller_return_trace.flush();
  if (state.poll_hash_trace.is_open())
    state.poll_hash_trace.flush();
  if (state.event_trace.is_open())
    state.event_trace.flush();
}
#endif

#if defined(JFG_PHASE8_LIVE_RUNTIME)

#endif
} // namespace jfg::boot::native::detail
