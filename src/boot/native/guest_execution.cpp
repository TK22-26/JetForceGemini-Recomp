#include "runtime_services.hpp"
#include "gameplay_scopes.hpp"
#include "jfg/renderer/keyboard_presentation.hpp"
namespace jfg::boot::native::detail {
#if defined(_WIN32) && defined(JFG_PHASE8_LIVE_RUNTIME)
#include "../flying_motion.inl"
#endif
extern "C" {
#include "jfg/boot/original_timing_cache.h"
}
void initialize_original_timing_cache(State& state) noexcept {
  static constexpr auto slots=[]() consteval {
    std::array<std::uint8_t,kRunlinkOverlaySlotCount+1U> valid{};
    for(const auto& section:jfg::game::linked::descriptor.sections) {
      if(section.kind!=jfg::game::SectionKind::overlay)continue;
      if(section.overlay_slot==0U || section.overlay_slot>=valid.size() ||
          valid[section.overlay_slot])throw "Invalid timing overlay slot identity";
      valid[section.overlay_slot]=1U;
    }
    return valid;
  }();
  static_assert(kRunlinkModuleTablePointer>=0x80000000U &&
      kRunlinkModuleTablePointer-0x80000000U<=kRdramSize-4U);
  state.timing_rdram_size=kRdramSize;
  state.timing_table_pointer=kRunlinkModuleTablePointer-0x80000000U;
  state.timing_slot_count=static_cast<std::uint32_t>(slots.size());
  state.timing_record_size=jfg::game::linked::bindings.runlink_record_size;
  state.timing_valid_slots=slots.data();
  cache_address_state=&state;
  state.instruction_cache = ic; state.data_cache = dc; state.cache_counters = cache_stats;
}
#if defined(_WIN32) && defined(JFG_PHASE8_LIVE_RUNTIME)
void complete_guest_sp_status(State &state, const std::uint32_t target) {
  if (!state.guest_leaf_probe) return;
  if (state.mmio_trace == nullptr || !state.mmio_trace->guest_sp_status ||
      !state.mmio_trace->sp_status.complete_task())
    fail_closed_dispatch(state, "rsp", "completion-status", target);
  // The current HLE interrupt service acknowledges before posting its OS
  // message. It still has no guest interrupt-handler execution/timing.
  state.mmio_trace->sp_status.acknowledge_interrupt();
}


#endif

#if defined(_WIN32) && defined(JFG_PHASE8_LIVE_RUNTIME)

#endif

void set_result(recomp_context *context, std::int32_t result) {
  context->r2 = static_cast<std::uint64_t>(static_cast<std::int64_t>(result));
}

#if defined(JFG_PHASE8_LIVE_RUNTIME)
bool complete_flash_operation(State &state) {
  const jfg::FlashRamResult result =
      state.flash_path.empty()
          ? state.flashram.complete()
          : state.flashram.complete_and_persist(state.flash_path);
  if (result.ok() && !state.flash_path.empty())
    ++state.flash_persist_count;
  return result.ok();
}
#endif

bool guest_byte_offset(const std::uint32_t address, std::size_t &offset) {
  const std::uint32_t segment = address & 0xE0000000U;
  const std::uint32_t physical = address & 0x1FFFFFFFU;
  if ((segment != 0x80000000U && segment != 0xA0000000U) ||
      physical >= kRdramSize)
    return false;
  offset = static_cast<std::size_t>(physical) ^ 3U;
  return true;
}
bool write_guest_byte(State &state, const std::uint32_t address,
                      const std::uint8_t value) {
  std::size_t offset = 0U;
  if (!guest_byte_offset(address, offset))
    return false;
  state.rdram[offset] = value;
  return true;
}
// Every path that publishes a synthetic overlay reports a failure the same
// way: the publisher's recorded reason, under the generated category.
[[noreturn]] void fail_closed_overlay_publication(State &state,
                                                 const std::uint32_t target) {
  std::array<char, 96U> operation{};
  (void)std::snprintf(operation.data(), operation.size(),
                      "overlay-publication-%s",
                      state.last_overlay_publication_failure);
  fail_closed_dispatch(state, "generated", operation.data(), target);
}

// One VI frame of host service while the scheduler is quiescent: frame
// budget, journal, window/audio service, presentation of the completed
// workload, pending graphics-task completion, VI field selection, SI and VI
// message delivery. Extracted from the osStartThread handler so the
// scheduler loop reads as a loop; behavior is unchanged.
// Read-only SI timing evidence. Result is a queue return code, not a claim
// about hardware interrupt latency. Enabled only by focused update capture.
void trace_si_timing(State &state, const char *event, std::uint32_t queue,
                     std::uint32_t caller, std::int32_t result) {
#if defined(_WIN32) && defined(JFG_PHASE8_LIVE_RUNTIME)
  const auto si = state.events.find(5U);
  if (si == state.events.end() || queue != si->second.first ||
      state.focus_update_start == 0U || !state.timing_trace.is_open() ||
      state.completed_game_updates + 1U < state.focus_update_start ||
      state.completed_game_updates + 1U > state.focus_update_end + 1U) return;
  state.timing_trace << "si-timing\t" << state.vi_frames << '\t'
      << state.vi_retraces << '\t' << state.controller_samples << '\t'
      << state.completed_game_updates << '\t' << event << '\t'
      << std::hex << queue << '\t' << caller << std::dec << '\t'
      << result << '\t' << state.cpu_count << '\n';
#else
  (void)state; (void)event; (void)queue; (void)caller; (void)result;
#endif
}

void service_si_deadline(State &state, const std::uint32_t target) {
  const auto completion = state.si_deadline.take(state.cpu_count);
  if (!completion) return;
  if (state.scheduler == nullptr || state.pending_si_completions != 1U)
    fail_closed_dispatch(state, "si", "deadline-ownership", target);
  state.pending_si_completions = 0U;
  const auto result = state.scheduler->send(completion->queue, completion->message, false);
  trace_si_timing(state, "deadline-deliver", completion->queue, 0U, result);
  state.journal.append(NativeEventKind::kController, 4U, completion->queue,
                       result == hle::kOsSuccess ? 1U : 0U);
  if (result == hle::kOsSuccess && state.scheduler_running &&
      state.scheduler->current_thread_id() >= 0)
    state.scheduler->yield_current();
}

void schedule_si_deadline(State &state, const std::uint32_t target) {
  const auto event = state.events.find(5U);
  // Measured oracle DMA-return-to-ack interval for the pinned early case.
  // This is an opt-in causal experiment, NOT an N64 hardware latency claim.
  constexpr std::uint64_t observed_ack_ticks = 2568U;
  if (event == state.events.end() || state.pending_si_completions != 1U ||
      !state.si_deadline.start(state.cpu_count, observed_ack_ticks,
                               event->second.first, event->second.second))
    fail_closed_dispatch(state, "si", "deadline-submission", target);
}

void service_timers(State &state, const std::uint32_t target) {
  if (!state.timers.next().has_value()) return;
  if (state.scheduler == nullptr)
    fail_closed_dispatch(state, "timer", "missing-scheduler", target);
  hle::GuestMemory memory({state.rdram, kRdramSize},
                          hle::GuestMemory::Layout::native_word_big_endian);
  bool delivered = false;
  if (!state.timers.service(memory, state.cpu_count,
      [&](std::uint32_t queue, std::uint32_t message) {
        delivered |= state.scheduler->send(queue, message, false) == hle::kOsSuccess;
      }))
    fail_closed_dispatch(state, "timer", "invalid-timer-state", target);
  if (delivered && state.scheduler_running &&
      state.scheduler->current_thread_id() >= 0)
    state.scheduler->yield_current();
}

// Diagnostic only: the dispatch-based Count is not hardware CPU timing.
void trace_guest_clock(State &state, const char *event, std::uint32_t address) {
#if defined(_WIN32) && defined(JFG_PHASE8_LIVE_RUNTIME)
  if (state.focus_update_start == 0U || !state.timing_trace.is_open() ||
      state.completed_game_updates + 1U < state.focus_update_start - 1U ||
      state.completed_game_updates + 1U > state.focus_update_end + 1U) return;
  state.timing_trace << "guest-clock\t" << state.completed_game_updates << '\t'
      << state.controller_samples << '\t' << state.vi_retraces << '\t'
      << event << '\t' << std::hex << address << std::dec << '\t'
      << state.cpu_count << '\n';
  state.timing_trace << "execution-work\t" << state.completed_game_updates << '\t'
      << state.controller_samples << '\t' << state.vi_retraces << '\t'
      << event << '\t' << std::hex << address << std::dec << '\t'
      << state.observed_guest_instructions << '\n';
  if (state.observed_guest_instructions != 0U) {
    state.timing_trace << "execution-hle\t" << state.completed_game_updates << '\t'
        << event << '\t' << std::hex << address << std::dec;
    for (std::size_t index = 0U; index < kMappingCount; ++index) {
      if (state.mapped_call_counts[index] != 0U)
        state.timing_trace << '\t' << kMappings[index].name << '='
            << state.mapped_call_counts[index];
    }
    state.timing_trace << '\n';
    state.timing_trace << "execution-dispatches\t" << state.completed_game_updates
        << '\t' << event << '\t' << std::hex << address;
    const auto count = (std::min)(state.recent_dispatch_position, state.recent_dispatches.size());
    for (std::size_t offset = 0U; offset < count; ++offset)
      state.timing_trace << '\t' << state.recent_dispatches[
          (state.recent_dispatch_position - count + offset) % state.recent_dispatches.size()];
    state.timing_trace << std::dec << '\n';
  }
#else
  (void)state; (void)event; (void)address;
#endif
}

// Legacy cooperative clock only. Keep this out of the device/presentation
// operations below so an execution-driven dispatcher can call those at
// independent deadlines without adding a frame of time a second time.
void advance_legacy_vi_clock(State &state, const std::uint32_t target) {
  trace_guest_clock(state, "vi-service-entry", target);
  const std::uint64_t frame_budget =
      static_cast<std::uint64_t>(state.retrace_target) * 20U;
  if (++state.vi_frames > frame_budget) {
    fail_closed_dispatch(state, "vi", "frame-budget", target);
  }
  const auto frame_end = state.cpu_count + kCountTicksPerViFrame;
  // A blocked receiver can resume at a timer deadline between VI events.
  // Do not round the controller power-on wait to whole video frames.
  while (true) {
    auto deadline = state.timers.next();
    const auto si_deadline = state.si_deadline.next();
    if (si_deadline && (!deadline || *si_deadline < *deadline)) deadline = si_deadline;
    if (!deadline) break;
    if (*deadline > frame_end) break;
    state.cpu_count = (std::max)(state.cpu_count, *deadline);
    service_si_deadline(state, target);
    service_timers(state, target);
    const auto outcome = state.scheduler->run(1'000'000U);
    if (outcome == ScheduleOutcome::kUnbounded)
      fail_closed_dispatch(state, "timer", "scheduler-step-budget", target);
    if (state.cpu_count >= frame_end) break;
  }
  state.cpu_count = (std::max)(state.cpu_count, frame_end);
  trace_guest_clock(state, "vi-deadline", target);
}

// Presentation consumes already completed work. It does not complete a
// graphics task, advance Count, or deliver a guest interrupt.
void present_completed_video(State &state, const std::uint32_t target) {
#if defined(_WIN32) && defined(JFG_PHASE8_LIVE_RUNTIME)
  const DiagnosticHostStage host_stage(state,"host-profile-video");
  if (state.play_mode || state.realtime_replay) {
    service_live_window(state);
    if (state.exit_requested)
      play_exit(state);
  }
  if (!service_host_audio(state, true))
    fail_closed_dispatch(state, "audio", "host-device", target);
  const std::uint32_t selected_vi_framebuffer =
      (state.vi_next_framebuffer != 0U
           ? state.vi_next_framebuffer
           : state.vi_current_framebuffer) &
      0x00FFFFFFU;
  // The task completed during this scheduler slice targets JFG's
  // off-screen buffer. Present the previously completed workload before
  // submitting that new task, so the normal double-buffer pipeline needs
  // one RT64 submission per displayed frame instead of two.
  if (state.rt64_shell != nullptr && state.graphics_frame_ready &&
      selected_vi_framebuffer != 0U) {
    // Effects can submit more than eight off-screen targets between VI
    // presentations. Ask RT64 whether the selected color target exists instead
    // of letting an unrelated snapshot-cache eviction suppress the frame.
    const bool presentation_ready =
        state.rt64_shell->has_color_framebuffer(selected_vi_framebuffer);
    if (!presentation_ready) {
      state.gameplay_trace.event("present-skip", {state.vi_retraces,
          state.controller_samples, state.gameplay_trace_updates,
          selected_vi_framebuffer, state.graphics_color_image});
    }
    if (presentation_ready) {
      state.rt64_vi.current_line =
          state.rt64_vi.current_line == 0U ? 2U : 0U;
      if (!apply_live_vi_field(state, selected_vi_framebuffer))
        fail_closed_dispatch(state, "renderer", "vi-field", target);
      // Import only the current VI consumer range; the shell tracks those
      // bytes so a later same-value CPU edit cannot leave stale private RAM.
      write_private_progress(state, "graphics-present-begin");
      const auto present_start = std::chrono::steady_clock::now();
      bool transition_capture=false;
      if(state.diagnostic_cutscene_capture && !state.rdram_capture_path.empty()) {
        const NativeGameMemory ram({state.rdram,kRdramSize});
        const auto level=game_view(ram).u32(game_data_ref("globals.currentLevel"));
        if(level==341U)state.cutscene_capture_armed=true;
        const bool departing=level==341U && game_view(ram).u8(game_data_ref("globals.transitionCountdown"))!=0;
        if((level==127U || departing) && state.cutscene_capture_armed && !state.cutscene_capture_started) {
          state.cutscene_capture_started=true;state.cutscene_capture_until_vi=state.vi_retraces+180U;
          state.gameplay_trace.event("cinematic-image-window",{state.vi_retraces,level,64U});
        }
        transition_capture=state.cutscene_capture_started && (level==341U || level==127U) &&
          state.vi_retraces<=state.cutscene_capture_until_vi && state.cutscene_capture.size()<64U;
      }
      const bool capture_frame = transition_capture || (!state.frame_capture_path.empty() &&
          (state.play_mode
               ? (state.presented_frames + 1U) % 60U == 0U
               : state.vi_retraces + 2U >= state.retrace_target));
      state.last_rt64_error =
          state.rt64_shell->present(capture_frame,
              std::as_bytes(std::span(state.rdram,kRdramSize)));
      if(transition_capture && state.last_rt64_error==jfg::Rt64ShellError::none) {
        const auto frame=state.rt64_shell->last_presented_frame();
        if(frame.valid() && frame.width<=8192U && frame.height<=8192U) {
          const auto stride=static_cast<unsigned>((frame.width+319U)/320U);
          State::CutsceneCapture saved;saved.vi=state.vi_retraces;
          saved.width=static_cast<unsigned>((frame.width+stride-1U)/stride);
          saved.height=static_cast<unsigned>((frame.height+stride-1U)/stride);
          saved.rgb.reserve(std::size_t(saved.width)*saved.height*3U);
          unsigned white=0;
          for(unsigned y=0;y<frame.height;y+=stride)
            for(unsigned x=0;x<frame.width;x+=stride) {
              const auto at=std::size_t(y)*frame.row_pitch_bytes+std::size_t(x)*4U;
              const auto red=std::to_integer<unsigned char>(frame.bgra8[at+2U]);
              const auto green=std::to_integer<unsigned char>(frame.bgra8[at+1U]);
              const auto blue=std::to_integer<unsigned char>(frame.bgra8[at]);
              saved.rgb.push_back(static_cast<char>(red));saved.rgb.push_back(static_cast<char>(green));
              saved.rgb.push_back(static_cast<char>(blue));white+=red>=240U&&green>=240U&&blue>=240U;
            }
          state.gameplay_trace.event("cinematic-image",{saved.vi,saved.width,saved.height,white});
          state.cutscene_capture.push_back(std::move(saved));
        }
      }
      const auto present_end = std::chrono::steady_clock::now();
      const auto present_us = static_cast<std::uint64_t>(
          std::chrono::duration_cast<std::chrono::microseconds>(
              present_end - present_start)
              .count());
      state.graphics_present_microseconds += present_us;
      state.graphics_present_max_us =
          (std::max)(state.graphics_present_max_us, present_us);
      std::uint64_t present_interval_us = 0U;
      if (state.present_time_initialized) {
        present_interval_us = static_cast<std::uint64_t>(
            std::chrono::duration_cast<std::chrono::microseconds>(
                present_end - state.present_time)
                .count());
        state.present_interval_max_us =
            (std::max)(state.present_interval_max_us,
                       present_interval_us);
      }
      state.gameplay_trace.event("present", {state.vi_retraces, state.controller_samples,
          state.gameplay_trace_updates, present_us, present_interval_us, selected_vi_framebuffer});
      if(state.gameplay_trace && state.cutscene_trace_until_vi &&
         state.vi_retraces<=state.cutscene_trace_until_vi) {
        const NativeGameMemory ram({state.rdram,kRdramSize});
        state.gameplay_trace.event("cinematic-present-state",{state.vi_retraces,
          game_view(ram).u32(game_data_ref("globals.currentLevel")),selected_vi_framebuffer,state.graphics_color_image,
          state.rt64_vi.origin,state.rt64_vi.status,state.rt64_vi.width,
          state.rt64_vi.horizontal_start,state.rt64_vi.vertical_start,
          state.rt64_vi.x_scale,state.rt64_vi.y_scale,state.vi_blacked?1U:0U,
          state.cutscene_prompt.transition?1U:0U});
      }
      state.present_time = present_end;
      state.present_time_initialized = true;
      if (state.timing_trace) state.timing_trace << "present-qpc\t"
          << state.vi_frames << '\t' << state.vi_retraces << '\t'
          << std::chrono::duration_cast<std::chrono::microseconds>(
                 present_end.time_since_epoch()).count() << '\n';
      if (state.timing_trace) {
        state.timing_trace << "present\t" << state.vi_frames << '\t'
                           << state.vi_retraces << '\t' << present_us
                           << '\t' << present_interval_us << '\t'
                           << std::hex << selected_vi_framebuffer
                           << std::dec << '\n';
      }
      write_private_progress(state, "graphics-present-end");
      if (state.last_rt64_error != jfg::Rt64ShellError::none) {
        std::array<char, 96U> operation{};
        (void)std::snprintf(
            operation.data(), operation.size(),
            "present-%u-%08x-%08x-%08x",
            static_cast<unsigned>(state.last_rt64_error),
            state.rt64_vi.origin, state.graphics_color_image,
            state.rt64_vi.width);
        fail_closed_dispatch(state, "renderer", operation.data(),
                             target);
      }
      ++state.presented_frames;
      state.graphics_frame_ready = false;
    }
  }
#else
  (void)state; (void)target;
#endif
}

void latch_next_vi_framebuffer(State &state, const std::uint32_t target) {
#if defined(_WIN32) && defined(JFG_PHASE8_LIVE_RUNTIME)
  if (state.vi_next_framebuffer != 0U) {
    state.vi_current_framebuffer = state.vi_next_framebuffer;
    if (!apply_live_vi_field(state, state.vi_current_framebuffer))
      fail_closed_dispatch(state, "renderer", "vi-field", target);
  }
#else
  (void)state; (void)target;
#endif
}

void deliver_legacy_si_completion(State &state, const std::uint32_t target) {
  if (!state.si_count_probe && state.pending_si_completions != 0U) {
    const auto si = state.events.find(5U);
    if (si == state.events.end()) {
      fail_closed_dispatch(state, "controller", "si-delivery", target);
    }
    const std::int32_t delivery = state.scheduler->send(
        si->second.first, si->second.second, false);
    if (delivery != hle::kOsSuccess && delivery != hle::kOsFull)
      fail_closed_dispatch(state, "controller", "si-delivery", target);
    --state.pending_si_completions;
    trace_si_timing(state, "deliver", si->second.first, 0U, delivery);
    state.journal.append(NativeEventKind::kController, 4U,
                         si->second.first,
                         delivery == hle::kOsSuccess ? 1U : 0U);
  }
}

void deliver_vi_interrupt(State &state, const std::uint32_t target) {
  if (state.vi_frames % state.vi_retrace_interval == 0U) {
    if (state.scheduler->send(state.vi_internal_queue,
                              state.vi_internal_message, false) !=
        hle::kOsSuccess) {
      fail_closed_dispatch(state, "vi", "interrupt-delivery", target);
    }
    ++state.vi_interrupts;
    state.journal.append(NativeEventKind::kViInterruptRaised,
                         state.vi_internal_queue,
                         state.vi_internal_message,
                         static_cast<std::uint32_t>(
                             state.vi_interrupts));
  }
}

// Preserve the cooperative profile's exact order as a control. Device
// completion is explicitly separate from VI service; this wrapper still
// schedules them together and does NOT claim execution-driven timing.
void service_vi_frame(State &state, const std::uint32_t target) {
  advance_legacy_vi_clock(state, target);
  state.empty_receive_polls.clear();
  state.journal.append(NativeEventKind::kViFrame,
                       static_cast<std::uint32_t>(state.vi_frames));
  present_completed_video(state, target);
#if defined(_WIN32) && defined(JFG_PHASE8_LIVE_RUNTIME)
  complete_pending_live_graphics_tasks(state, target);
#endif
  latch_next_vi_framebuffer(state, target);
  deliver_legacy_si_completion(state, target);
  deliver_vi_interrupt(state, target);
}

// Overlay 32's mrhintsControl entry (text offset 0x2E8) doubles as the King
// Bear hint callback. Three dispatch paths reach it (direct, generated
// overlay lookup, runlink-resolved lookup) and must record identical route
// diagnostics.
[[maybe_unused]] void note_hints_control_call(State &state, const std::uint32_t target,
                             const recomp_context &context) {
  ++state.phase9_hints_control_calls;
  state.phase9_hints_actor = static_cast<std::uint32_t>(context.r4);
  ++state.phase9_king_bear_control_calls;
  state.phase9_king_bear_actor = static_cast<std::uint32_t>(context.r4);
  state.phase9_king_bear_callback = target;
}

#if defined(_WIN32) && defined(JFG_PHASE8_LIVE_RUNTIME)
// Private modeled-time accounting. Charge a dispatch/interrupt-return segment
// to its prior guest owner, then switch to __osRunningThread at ERET. This
// separates other active threads from inclusive function durations.
std::array<std::uint64_t,6> sample_model_thread(State& state,std::uint32_t query,
    std::uint32_t next) {
  std::array<std::uint64_t,12> cache{};jfg_full_cache_snapshot(cache.data());
  std::array<std::uint64_t,6> now{state.cpu_count*2U,cache[1],cache[2],cache[5],cache[6],cache[7]};
  auto slot=[&](std::uint32_t id)->State::ModelThreadCost& {
    for(auto& row:state.profile_model_threads)if(row.id==id)return row;
    for(std::size_t i=1;i<state.profile_model_threads.size();++i) {auto& row=state.profile_model_threads[i];if(row.id==0U){row.id=id;return row;}}
    std::abort();
  };
  auto& owner=slot(state.profile_model_owner);
  for(std::size_t i=0;i<now.size();++i) {
    if(now[i]<state.profile_model_last[i])std::abort();
    owner.value[i]+=now[i]-state.profile_model_last[i];
  }
  state.profile_model_last=now;
  if(next!=UINT32_MAX)state.profile_model_owner=next;
  return slot(query).value;
}
class FunctionProfileScope {
  using Profile=jfg::boot::FunctionProfile;
  struct ThreadData {
    Profile profile;
    std::uint64_t start_vi=0,start_poll=0;
    std::uint32_t thread=0;
    ULONG64 process_cycles=0;
    bool process_valid=false;
    std::uint64_t handoffs=0;
    BatonExecutor::Timing transport{};
  };
  State* state_=nullptr;
  ThreadData* data_=nullptr;
  std::uint32_t model_target_=0;
  std::uint32_t model_a0_=0,model_thread_=0;
  std::array<std::uint64_t,6> model_thread_begin_{};
  std::array<std::uint64_t,12> model_cache_begin_{};
  std::uint64_t model_start_vi_=0,model_start_count_=0,model_start_instructions_=0,model_start_idle_=0;
  static Profile::Sample sample(State& state) {
    const auto cpu=state.guest_transport?state.guest_transport->execution_cycles():BatonExecutor::host_cycles();
    const auto wall=static_cast<std::uint64_t>(std::chrono::duration_cast<std::chrono::nanoseconds>(
      std::chrono::steady_clock::now().time_since_epoch()).count());
    return {wall,cpu.cycles,state.profile_host_wait_us,state.observed_guest_instructions,
      cpu.participant,cpu.valid};
  }
public:
  FunctionProfileScope(State& state,std::uint32_t target,const recomp_context& context) {
    if(!state.diagnostic_function_profile)return;
    struct ProfileLocalTag;
    auto& local=jfg::runtime::execution_local<ThreadData,ProfileLocalTag>();
    const bool root=(target==game_code("game.mainUpdate") || target==game_code("game.amHandleFrameMsg") || target==game_code("game.amHandleDoneMsg")) && !local.profile.active();
    if(root) {
      if(state.vi_retraces<state.diagnostic_profile_first_vi ||
         state.vi_retraces>=state.diagnostic_profile_last_vi)return;
      local.profile.reset();local.start_vi=state.vi_retraces;
      local.start_poll=state.controller_samples;local.thread=sample(state).thread;
      local.process_valid=QueryProcessCycleTime(GetCurrentProcess(),&local.process_cycles)!=0;
      local.handoffs=state.guest_transport?state.guest_transport->handoffs():0U;
      local.transport=state.guest_transport?state.guest_transport->timing():BatonExecutor::Timing{};
    } else if(!local.profile.active())return;
    const bool stage=target==game_code("game.mainUpdate") || target==game_code("game.objObjectsTick") ||
      target==game_overlay_token("overlay.collision.squaddie_control") || target==game_overlay_token("overlay.smart_mover.control") || target==game_code("game.modGenAnimMatrices") ||
      target==game_code("game.trackDraw") || target==game_code("game.rcpFast3d") || target==game_code("game.rcpWaitDP") ||
      target==game_code("game.shadowGenerate") || target==game_overlay_token("overlay.shadows.filter") || target==game_code("game.lightSingleLight") ||
      target==game_code("game.cpuLine") || target==game_code("game.rainFastDraw") || target==game_code("game.diRcpTraceReset") ||
      target==game_code("game.objPrintModelObject") || target==game_code("game.amHandleFrameMsg") || target==game_code("game.n_alAudioFrame") || target==game_code("game.amHandleDoneMsg");
    if(state.diagnostic_function_profile==1U && !stage)return;
    state_=&state;data_=&local;local.profile.enter(target,sample(state));
    if(stage && !state.diagnostic_host_clock) {
      model_target_=target;model_start_vi_=state.vi_retraces;
      model_start_count_=state.cpu_count;model_start_instructions_=state.observed_guest_instructions;
      model_start_idle_=state.profile_idle_count_ticks;
      model_a0_=static_cast<std::uint32_t>(context.r4);
      jfg_full_cache_snapshot(model_cache_begin_.data());
      model_thread_=NativeGameMemory({state.rdram,kRdramSize}).u32(kOsCurrentThread);
      model_thread_begin_=sample_model_thread(state,model_thread_);
      if(target==game_code("game.n_alAudioFrame")) {
        NativeGameMemory audio_ram({state.rdram,kRdramSize});
        state.gameplay_trace.event("audio-frame-call", {state.vi_retraces,state.cpu_count,
          game_view(audio_ram).u32(game_data_ref("globals.currentLevel")),static_cast<std::uint32_t>(context.r4),
          static_cast<std::uint32_t>(context.r5),static_cast<std::uint32_t>(context.r6),
          static_cast<std::uint32_t>(context.r7),audio_ram.u32(game_data("audio.frame_count")),
          state.mmio_trace->ai_dma.read(4U,state.cpu_count).value_or(UINT32_MAX),
          state.mmio_trace->ai_dma.read(12U,state.cpu_count).value_or(UINT32_MAX),
          state.mmio_trace->ai_dma.read(16U,state.cpu_count).value_or(UINT32_MAX)});
      }
    }
  }
  ~FunctionProfileScope() {
    if(!state_)return;
    // Private instruction-clock observer: inclusive guest time can include
    // another guest thread while this call waits; it is not host self CPU cost.
    if(model_target_)state_->gameplay_trace.event("function-stage-model", {
      state_->vi_retraces,state_->cpu_count,model_target_,model_start_vi_,
      model_start_count_,model_start_instructions_,state_->observed_guest_instructions,
      NativeGameMemory({state_->rdram,kRdramSize}).u32(game_data("globals.currentLevel")),
      model_start_idle_,state_->profile_idle_count_ticks});
    if(model_target_) {
      auto own=sample_model_thread(*state_,model_thread_);
      for(std::size_t i=0;i<own.size();++i)own[i]-=model_thread_begin_[i];
      state_->gameplay_trace.event("function-stage-thread", {
        state_->vi_retraces,model_target_,model_a0_,model_thread_,model_start_vi_,
        own[0],own[1],own[2],own[3],own[4],own[5]});
      std::array<std::uint64_t,12> end{};jfg_full_cache_snapshot(end.data());
      for(std::size_t i=0;i<end.size();++i)end[i]-=model_cache_begin_[i];
      state_->gameplay_trace.event("function-stage-cache", {
        state_->vi_retraces,model_target_,model_a0_,model_start_vi_,
        state_->profile_idle_count_ticks-model_start_idle_,
        end[0],end[1],end[2],end[3],end[4],end[5],end[6],end[7],end[8],end[9],end[10],end[11]});
    }
    if(!data_->profile.leave(sample(*state_)))return;
    const auto emit_started=sample(*state_);
    ULONG64 process_cycles=0;
    const bool process_valid=data_->process_valid &&
      QueryProcessCycleTime(GetCurrentProcess(),&process_cycles) &&
      process_cycles>=data_->process_cycles;
    const auto handoffs=state_->guest_transport?state_->guest_transport->handoffs():0U;
    const auto transport=state_->guest_transport?state_->guest_transport->timing():BatonExecutor::Timing{};
    auto& trace=state_->gameplay_trace;
    trace.event("function-profile-host",{state_->vi_retraces,state_->controller_samples,
      data_->start_vi,data_->start_poll,data_->thread,process_valid,
      process_valid?process_cycles-data_->process_cycles:0U,
      handoffs-data_->handoffs,transport.wakes-data_->transport.wakes,
      transport.wake_ns-data_->transport.wake_ns});
    std::uint64_t used=0;
    for(const auto& row:data_->profile.rows()) {
      if(!row.calls)continue;
      ++used;
      trace.event("function-profile",{state_->vi_retraces,state_->controller_samples,
        data_->start_vi,data_->start_poll,data_->thread,row.target,row.parent,row.calls,
        row.wall,row.self_wall,row.cycles,row.self_cycles,row.wait,row.instructions,
        row.max_wall,row.max_cycles,row.valid});
    }
    trace.event("function-profile-end",{state_->vi_retraces,state_->controller_samples,
      data_->start_vi,data_->start_poll,data_->thread,state_->diagnostic_function_profile,
      data_->profile.valid(),data_->profile.calls(),used,data_->profile.overflow()});
    const auto emit_finished=sample(*state_);
    const bool emit_valid=emit_started.valid && emit_finished.valid &&
      emit_started.thread==emit_finished.thread && emit_finished.cycles>=emit_started.cycles &&
      emit_finished.wall>=emit_started.wall;
    trace.event("function-profile-emission",{state_->vi_retraces,state_->controller_samples,
      data_->start_vi,data_->start_poll,data_->thread,emit_valid,
      emit_valid?emit_finished.wall-emit_started.wall:0U,
      emit_valid?emit_finished.cycles-emit_started.cycles:0U});
  }
};
#endif


#if defined(_WIN32) && defined(JFG_PHASE8_LIVE_RUNTIME)
bool cutscene_actors_reviewed(const NativeGameMemory& ram) {
  const auto count=game_view(ram).u32(game_data_ref("globals.objectCount")),list=game_view(ram).u32(game_data_ref("globals.objectList"));
  if(!count||count>1024U||!ram.valid(list,std::uint64_t{count}*4U))return false;
  for(unsigned i=0;i<count;++i) {
    const auto actor=ram.u32(list+4U*i);
    if(!actor)continue;
    if(!ram.valid(actor,0x80U))return false;
    const auto type=ram.u16(actor+game_member("layout.actor.type"));
    const auto data=ram.u32(actor+game_member("layout.actor.header"));
    if(!ram.valid(data,0xD8U) || ram.u32(data+game_member("layout.objectHeader.animationEvents"))!=0)return false;
    if(type==1U || type==59U) {
      // Type 1 has no ordinary objControl case; cinematic copies are not
      // gameplay players. Type 59's overlay 02B00014 first calls objGetPlayerNo
      // (8000E4D0); with zero players it only removes itself and returns before
      // any flag, inventory, hint or collision side effects.
      if(game_view(ram).u32(game_data_ref("globals.playerCount"))!=0 || ram.u32(actor+game_member("layout.actor.physics"))!=0)return false;
    } else if(type==8U) {
      // 8002561C reads flags, then gates every player camera/hint write on
      // hitPlayer (8007E150). Its player-list getter (8000E464) reads
      // 800F2D10; with no gameplay players this trigger has no side effects.
      if(game_view(ram).u32(game_data_ref("globals.playerCount"))!=0 || ram.u32(actor+game_member("layout.actor.physics"))!=0 ||
         !ram.valid(ram.u32(actor+game_member("layout.actor.control")),0x18U))return false;
    } else if(type==145U || type==147U) {
      // Type 147 uses animdroidControl (800270EC) for local texture animation.
      // Type 145 is FireWork (05A002B4): local motion, light intensity,
      // particle emission, RNG and self-removal/reinitialization. Its
      // partUpdateTriggers call updates visual emitters, not gameplay events.
      // These effects can end with the scene; event/movement callbacks are
      // independently excluded. Do not require zero particle triggers:
      // the original FireWork definition has one.
      if(ram.u32(actor+game_member("layout.actor.physics"))!=0 ||
         !ram.valid(ram.u32(actor+game_member("layout.actor.control")),0xCU))return false;
    } else if(type==9U) {
      // 8001C0D8 changes only per-view fog interpolation, not progression.
      // Tawfret's cinematic fog trigger has no gameplay player or callback.
      if(game_view(ram).u32(game_data_ref("globals.playerCount"))!=0 || ram.u32(actor+game_member("layout.actor.physics"))!=0)return false;
    } else if(type==61U || type==66U) {
      // Health/ammo demo objects have no persistent effects without players:
      // both native controls put collection and inventory writes behind
      // hitPlayer (8007E150), whose player count comes from 800F2D10.
      // Health's +7C is its collision/physics state, not a script callback.
      // Keep the ordinary gameplay case excluded; never collect skipped items.
      if(game_view(ram).u32(game_data_ref("globals.playerCount"))!=0)return false;
      const auto physics=ram.u32(actor+game_member("layout.actor.physics"));
      if(type==61U) {
        if(physics && !ram.valid(physics,0x28U))return false;
      } else if(physics!=0)return false;
    } else if((type!=7U && !jfg::cutscene_actor_control_reviewed(type)) ||
              ram.u32(actor+game_member("layout.actor.physics"))!=0)return false;
    // Cinematic doors also enter the native hit/interaction dispatch list.
    // 80025A08 only updates door/animation state, positional sound and hints
    // (00601284/006012B0); it reads progression flags but never writes them.
    // Keep gameplay players and custom event/movement callbacks excluded.
    if(type==7U && game_view(ram).u32(game_data_ref("globals.playerCount"))!=0)return false;
    // Doors, rescue NPCs, landing-room bridges and type132 actors qualify
    // only with ordinary control disabled by the native cinematic animation.
    // Type132 dispatches to07C00678 and can write a game flag when active.
    if(type==7U || type==49U || type==55U || type==132U) {
      const auto anim=ram.u32(actor+game_member("layout.actor.properties"));
      if(!ram.valid(anim,10U)||(ram.u8(anim+9U)&8U)==0)return false;
    }
  }
  return true;
}
bool update_cutscene_review(State& state,recomp_context& context) {
  if(!state.diagnostic_cutscene_review)return false;
  const auto config=state.cutscene_review_files.latest();
  if(!config || config->size()!=1U ||
     config->at(0).status!=jfg::ConfigFileValue::Status::ready)return false;
  const auto now=std::chrono::duration_cast<std::chrono::milliseconds>(
      std::chrono::system_clock::now().time_since_epoch()).count();
  const auto request=jfg::parse_cutscene_review(config->at(0).text,
      state.cutscene_review_nonce,now,state.cutscene_review_session_started);
  if(!request)return false;
  NativeGameMemory ram({state.rdram,kRdramSize});
  const auto header=game_view(ram).u32(game_data_ref("globals.levelHeader")),table=game_view(ram).u32(game_data_ref("globals.assetTable"));
  const auto current_level=game_view(ram).u32(game_data_ref("globals.currentLevel"));
  if(current_level==0U || current_level==1U || current_level==73U ||
     current_level==79U || current_level==161U ||
     (current_level==127U && !state.cutscene_review_mode.review_mode))return false;
  if(!ram.valid(header,0xEAU)||!ram.valid(table,69U*4U)||
     game_view(ram).u8(game_data_ref("globals.transitionCountdown"))!=0 || game_view(ram).u8(game_data_ref("globals.pauseActive"))!=0)return false;
  const auto section=[&](unsigned index)->std::span<const std::uint8_t> {
    const std::uint64_t a=0xB1880ULL+ram.u32(table+(index+1U)*4U);
    const std::uint64_t b=0xB1880ULL+ram.u32(table+(index+2U)*4U);
    if(a>b||b>state.rom_size)return {};
    return {state.rom+static_cast<std::size_t>(a),static_cast<std::size_t>(b-a)};
  };
  state.cutscene_review_nonce=request->nonce;
  if(!jfg::cutscene_review_entry_valid(section(30),section(31),section(65),section(66),*request)) {
    state.gameplay_trace.event("cutscene-review-rejected",{state.vi_retraces,
      request->level,request->group,request->character});return false;
  }
  const auto stack=static_cast<std::uint32_t>(context.r29)-0x80U;
  if(!ram.valid(stack-0x1000U,0x1080U) ||
     !ram.instruction_matches("guard.game.mainChangeLevel.entry0") ||
     !jfg_generated_lookup_function(static_cast<std::int32_t>(game_code("game.mainChangeLevel"))) ||
     !jfg_generated_lookup_function(static_cast<std::int32_t>(game_code("game.mainSetAnimGroup"))) ||
     !jfg_generated_lookup_function(static_cast<std::int32_t>(game_code("game.frontGetMode"))) ||
     !jfg_generated_lookup_function(static_cast<std::int32_t>(game_code("game.mainGetGameFlag"))) ||
     !jfg_generated_lookup_function(static_cast<std::int32_t>(game_code("game.mainSetGameFlag"))))return false;
  hle::GuestMemory memory({state.rdram,kRdramSize},hle::GuestMemory::Layout::native_word_big_endian);
  const auto call=[&](std::uint32_t fn,std::uint32_t a,std::uint32_t b=0,
                     std::uint32_t c=0,std::uint32_t d=0) {
    auto cpu=context;cpu.f_odd=cpu.mips3_float_mode?&cpu.f1.u32l:&cpu.f0.u32h;
    cpu.r29=static_cast<std::int32_t>(stack);cpu.r4=a;cpu.r5=b;cpu.r6=c;cpu.r7=d;
    (void)memory.write_u32(stack+0x10U,1U);(void)memory.write_u32(stack+0x14U,0U);
    if(!dispatch(&state,static_cast<std::int32_t>(fn),state.rdram,&cpu))
      jfg_generated_lookup_function(static_cast<std::int32_t>(fn))(state.rdram,&cpu);
    set_cop1_cs(context.fcr31);
    return static_cast<std::uint32_t>(cpu.r2);
  };
  const auto source=game_view(ram).u32(game_data_ref("globals.currentLevel"));
  state.cutscene_chain=false;state.cutscene_skip_scene=0;
  state.cutscene_skip_request=0;state.cutscene_skip_gesture=0;
  state.cutscene_cached_scene=0;state.cutscene_prompt={};
  const auto current_mode=call(game_code("game.frontGetMode"),0);
  const auto mode=state.cutscene_review_mode.destination(request->level,current_mode);
  if(!mode) {
    state.gameplay_trace.event("cutscene-review-mode-rejected",
      {state.vi_retraces,source,request->level,current_mode});
    return false;
  }
  if(jfg::cutscene_review_needs_character_unlocks(request->level,request->group)) {
    unsigned added=0;
    for(unsigned flag=0;flag<3U;++flag)if(!call(game_code("game.mainGetGameFlag"),flag)) {
      call(game_code("game.mainSetGameFlag"),flag,1U);added|=1U<<flag;
    }
    state.gameplay_trace.event("cutscene-review-context-prepared",
      {state.vi_retraces,request->level,request->group,added});
  }
  call(game_code("game.mainChangeLevel"),request->level,request->character,0,*mode);
  call(game_code("game.mainSetAnimGroup"),request->group);
  state.gameplay_trace.event("cutscene-review-entry",{state.vi_retraces,source,
    request->level,request->group,request->character,request->nonce});
  // The outgoing scene must not execute another script command after selection.
  return true;
}

// Resolve the actual active credits module. Its completion halfword is
// separate from the looping scene script, and must be set before native exit.
std::uint8_t* cutscene_credits_memory(State& state,const NativeGameMemory& ram) {
  constexpr unsigned section=game_module(OriginalModule::credits);
  if(game_view(ram).u8(game_data_ref("globals.frontendMode"))!=23U || !section_addresses ||
     !state.active_overlay_sections.contains(section))return nullptr;
  JfgGeneratedSectionMetadata metadata{};
  if(!jfg_generated_section_metadata(section,&metadata) || metadata.is_overlay!=1U)
    return nullptr;
  const auto base=static_cast<std::uint32_t>(section_addresses[section]);
  const std::uint64_t extent=std::uint64_t(metadata.text_size)+metadata.data_size+metadata.bss_size;
  if(extent<game_overlay_data("cutscene.credits.end",OriginalModule::credits)+2U || extent>0x10000U || (base&3U) || (extent&3U))return nullptr;
  std::uint32_t offset=0;
  if(ram.valid(base,extent))offset=base&0x1FFFFFFFU;
  else {
    if(base!=metadata.linked_vram)return nullptr;
    // Normalized overlay addresses are below KSEG0 (credits:03B00000).
    // Match the loader's unsigned wrapping subtraction into the reserved
    // guest span; rejecting base<KSEG0 made native credits unskippable.
    offset=base-kKseg0;
    if(offset>kGuestAddressSpan || extent>kGuestAddressSpan-offset)return nullptr;
  }
  auto* bytes=state.rdram+offset;
  const auto u16=[&](unsigned at) {return (unsigned{bytes[at^3U]}<<8)|bytes[(at+1U)^3U];};
  const auto instruction=(u16(game_overlay_site("cutscene.credits.entry",OriginalModule::credits))<<16)|u16(game_overlay_site("cutscene.credits.entry",OriginalModule::credits)+2U);
  if(instruction!=game_instruction_word("cutscene.credits.entry") || u16(game_overlay_data("cutscene.credits.end",OriginalModule::credits))!=0U ||
     !ram.instruction_matches("guard.game.mainTitlePageInit.entry0"))return nullptr;
  return bytes;
}
void update_cutscene_completion(State& state,recomp_context& context) {
  NativeGameMemory ram({state.rdram,kRdramSize});
  const auto level=game_view(ram).u32(game_data_ref("globals.currentLevel")),header=game_view(ram).u32(game_data_ref("globals.levelHeader"));
  const auto group=game_view(ram).u32(game_data_ref("globals.cutsceneGroup")),start=game_view(ram).u32(game_data_ref("globals.cutsceneScriptStart"));
  const auto cursor=game_view(ram).u32(game_data_ref("globals.cutsceneScriptCursor"));
  const bool cinematic=ram.valid(header,game_member("layout.levelHeader.kind")+1U) &&
    (ram.u8(header+game_member("layout.levelHeader.kind"))==1U||ram.u8(header+game_member("layout.levelHeader.kind"))==2U);
  if(!cinematic || level==0U || level==127U) {
    state.cutscene_skip_scene=0;state.cutscene_chain=false;state.cutscene_prompt.transition=false;return;
  }
  if(game_view(ram).u32(game_data_ref("globals.cutsceneOwner"))==0 || game_view(ram).u32(game_data_ref("globals.cutscenePlaying"))!=1U ||
     game_view(ram).u8(game_data_ref("globals.multiPlayerGame"))!=0 || game_view(ram).u8(game_data_ref("globals.pauseActive"))!=0 ||
     game_view(ram).u8(game_data_ref("globals.transitionCountdown"))!=0 || group>255U || !ram.valid(start,4U) ||
     cursor<start || cursor-start>28672U) {
    state.cutscene_skip_scene=0;return;
  }
  const std::uint64_t scene=(std::uint64_t{level}<<48U)|(std::uint64_t{group}<<32U)|start;
  const bool first=scene!=state.cutscene_cached_scene;
  if(first) {
    state.cutscene_cached_scene=scene;
    // Copy a bounded view; the parser stops at the original sentinel.
    const auto size=std::min<std::uint32_t>(28672U,kRdramSize-(start&0x1FFFFFFFU));
    std::vector<std::uint8_t> bytes(size);
    for(unsigned i=0;i<size;++i)bytes[i]=ram.u8(start+i);
    state.cutscene_script=jfg::inspect_cutscene_script(bytes);
    if(state.cutscene_chain && (level!=state.cutscene_chain_level || group!=state.cutscene_chain_group))
      state.cutscene_chain=false;
  }
  auto plan=jfg::plan_cutscene_completion(state.cutscene_script,cursor-start,
    {game_view(ram).u32(game_data_ref("globals.cutsceneSequence")),group});
  auto* credits_memory=plan && plan->native_credits && level==360U
    ? cutscene_credits_memory(state,ram):nullptr;
  if(plan && plan->native_credits && !credits_memory)plan.reset();
  const bool actors_reviewed=cutscene_actors_reviewed(ram);
  const bool qualified=plan.has_value() && actors_reviewed &&
    ram.instruction_matches("guard.game.animseqUpdate.entry0") && ram.instruction_matches("guard.game.animseqProcessCommandList.entry0") &&
    ram.instruction_matches("guard.game.mainChangeLevel.entry0");
  const auto previous_qualified_scene=state.cutscene_skip_scene.load(std::memory_order_acquire);
  state.cutscene_skip_scene.store(qualified?scene:0,std::memory_order_release);
  if(!first && previous_qualified_scene!=(qualified?scene:0))
    state.gameplay_trace.event("cutscene-skip-eligibility",{state.vi_retraces,level,group,
      qualified?1U:0U,plan.has_value()?1U:0U,actors_reviewed?1U:0U,cursor-start});
    if(!actors_reviewed && (first || previous_qualified_scene!=0)) {
      state.gameplay_trace.event("cutscene-skip-review-context",{state.vi_retraces,
        ram.u32(game_data("diagnostic.cameraPlayerState")),game_view(ram).u32(game_data_ref("globals.playerCount")),ram.u32(game_data("diagnostic.cameraPlayerIndex")),
        game_view(ram).u32(game_data_ref("globals.objectAssetCount")),game_view(ram).u32(game_data_ref("globals.objectAssetTable"))});
      const auto actor_list=game_view(ram).u32(game_data_ref("globals.objectList")),actor_count=game_view(ram).u32(game_data_ref("globals.objectCount"));
      if(actor_count<=1024U && ram.valid(actor_list,std::uint64_t{actor_count}*4U))
        for(unsigned n=0;n<actor_count;++n) {
          const auto a=ram.u32(actor_list+n*4U);
          if(!ram.valid(a,0x80U))continue;
          const auto data=ram.u32(a+0x40U),anim=ram.u32(a+0x4CU);
          state.gameplay_trace.event("cutscene-skip-actor-check",{
            state.vi_retraces,level,group,a,ram.u16(a+0x48U),ram.u32(a+0x7CU),
            ram.valid(data,0xD8U)?ram.u32(data+game_member("layout.objectHeader.animationEvents")):0xFFFFFFFFU,
            ram.valid(anim,10U)?ram.u8(anim+9U):0xFFU,
            ram.valid(a,0x8CU)?ram.u32(a+0x88U):0xFFFFFFFFU,
            ram.valid(ram.u32(a+0x3CU),0x16U)?ram.u8(ram.u32(a+0x3CU)+0x10U):0xFFU});
        }
    }
  if(first) {
    if(!state.cutscene_chain)state.cutscene_prompt.transition=false;
    state.gameplay_trace.event("cutscene-skip-scene",{state.vi_retraces,level,group,
      static_cast<unsigned>(state.cutscene_script.status),qualified?1U:0U,start,
      plan.has_value()?1U:0U,actors_reviewed?1U:0U,cursor-start,game_view(ram).u32(game_data_ref("globals.cutsceneSequence"))});
    // Let the newly loaded scene perform its first ordinary update.
    return;
  }
  if(!qualified) {state.cutscene_chain=false;state.cutscene_prompt.transition=false;return;}
  const auto requested=state.cutscene_skip_request.load(std::memory_order_acquire);
  if(requested!=scene && !state.cutscene_chain)return;
  const auto stack=static_cast<std::uint32_t>(context.r29)-0x80U;
  if(!ram.valid(stack-0x1000U,0x1080U))return;
  constexpr std::array<std::uint32_t,19> functions{
    game_code("game.mainChangeLevel"),game_code("game.mainSetAnimGroup"),game_code("game.mainGetNextCharacter"),game_code("game.mainGetGame"),game_code("game.frontGetMode"),
    game_code("game.mainGetGameFlag"),game_code("game.mainSetGameFlag"),game_code("game.mainFrontInit"),game_code("game.frontCharSelectSetQuitMode"),
    game_code("game.joyDisable"),game_code("game.joyEnable"),game_code("game.amTuneSetFade"),game_code("game.amTuneSetVolume"),game_code("game.amTuneResetFade"),game_code("game.amTunePlay"),
    game_code("game.amAmbientPlay"),game_code("game.amAmbientResetFade"),game_code("game.amAmbientSetVolume"),game_code("game.mainTitlePageInit")};
  for(const auto fn:functions)
    if(!jfg_generated_lookup_function(static_cast<std::int32_t>(fn)))return;
  hle::GuestMemory memory({state.rdram,kRdramSize},hle::GuestMemory::Layout::native_word_big_endian);
  const auto call=[&](std::uint32_t fn,std::uint32_t a=0,std::uint32_t b=0,
                      std::uint32_t c=0,std::uint32_t d=0,
                      std::uint32_t e=0,std::uint32_t f=0) {
    auto cpu=context;
    cpu.f_odd=cpu.mips3_float_mode?&cpu.f1.u32l:&cpu.f0.u32h;
    // amTuneSetFade(0 seconds, target) has a native immediate-completion
    // branch, which sets the envelope target/count and real audio volume.
    if(fn==game_code("game.amTuneSetFade")){cpu.f12.u32l=0;cpu.f12.u32h=0;}
    cpu.r29=static_cast<std::int32_t>(stack);
    cpu.r4=static_cast<std::int32_t>(a);cpu.r5=static_cast<std::int32_t>(b);
    cpu.r6=static_cast<std::int32_t>(c);cpu.r7=static_cast<std::int32_t>(d);
    (void)memory.write_u32(stack+0x10U,e);(void)memory.write_u32(stack+0x14U,f);
    if(!dispatch(&state,static_cast<std::int32_t>(fn),state.rdram,&cpu))
      jfg_generated_lookup_function(static_cast<std::int32_t>(fn))(state.rdram,&cpu);
    set_cop1_cs(context.fcr31);
    return static_cast<std::uint32_t>(cpu.r2);
  };
  // Claim once on the native update thread. Do not run transition functions
  // on the controller/audio thread, or mutate the guest's sequence clock.
  state.cutscene_skip_request=0;state.cutscene_skip_scene=0;
  if(!state.cutscene_chain) {
    state.cutscene_chain_count=0;
    state.cutscene_transition_started=state.vi_retraces;
  }
  state.cutscene_prompt.transition=true;
  // mainSyncNextLevel makes the loader wait for a cue from the unplayed
  // remainder of the scene. Clear any previously scheduled cue wait and
  // omit future opcode 76 requests only after a confirmed completion.
  state.rdram[(game_data("globals.transitionCutsceneActive")&0x1FFFFFFFU)^3U]=0;
  ++state.cutscene_chain_count;
  state.cutscene_chain=false;
  (void)memory.write_u32(game_data("globals.cutscenePlaying"),0U);
  if(!plan->native_credits)
  (void)memory.write_u32(game_data("globals.cutsceneScriptCursor"),start+plan->sentinel_offset);
  for(const auto& action:plan->actions) {
    using K=jfg::CutsceneCompletionActionKind;
    switch(action.kind) {
      case K::credits_end:
        // Match the original -4 credits command: mark its native completion,
        // then call the original frontend exit/next-level selection handler.
        credits_memory[game_overlay_data("cutscene.credits.end",OriginalModule::credits)^3U]=0;
        credits_memory[(game_overlay_data("cutscene.credits.end",OriginalModule::credits)+1U)^3U]=1;
        call(game_code("game.mainTitlePageInit"));
        state.gameplay_trace.event("cutscene-credits-complete",{state.vi_retraces,level,group});
        break;
      case K::music_track:
        // Native opcode 21 starts the requested tune and cancels its prior
        // fade. Preserve that audio state before the native departure.
        call(game_code("game.amTunePlay"),action.argument);call(game_code("game.amTuneResetFade"));break;
      case K::music_fade:call(game_code("game.amTuneSetFade"),0,action.argument);break;
      case K::music_volume:
        // Native opcode 23 sets volume then cancels any old fade, in that order.
        call(game_code("game.amTuneSetVolume"),action.argument);call(game_code("game.amTuneResetFade"));break;
      case K::ambient_track:
        // Native opcode 24 starts ambient sequence, then cancels its old fade.
        call(game_code("game.amAmbientPlay"),action.argument);call(game_code("game.amAmbientResetFade"));break;
      case K::ambient_volume:
        // Native opcode 26 sets ambient volume, then cancels its old fade.
        call(game_code("game.amAmbientSetVolume"),action.argument);call(game_code("game.amAmbientResetFade"));break;
      case K::game_flag:call(game_code("game.mainSetGameFlag"),action.argument,action.value);break;
      case K::input_disable:call(game_code("game.joyDisable"),action.argument);break;
      case K::input_enable:call(game_code("game.joyEnable"),action.argument);break;
      case K::front_control:
        // The original 74/75 leaf only writes this front-end control byte.
        state.rdram[(game_data("cutscene.frontControl")&0x1FFFFFFFU)^3U]=static_cast<std::uint8_t>(action.argument);break;
      case K::change_level: {
        const auto game=call(game_code("game.mainGetGame"));
        const auto dest=jfg::cutscene_destination(action.argument,action.value,
          call(game_code("game.mainGetNextCharacter")),game_view(ram).u8(game_data_ref("globals.racingCharacter")),
          ram.valid(game,2U)?ram.u8(game+1U):0U,call(game_code("game.frontGetMode")));
        call(game_code("game.mainChangeLevel"),dest.level,dest.character,dest.entrance,dest.mode,1,0);
        call(game_code("game.mainSetAnimGroup"),dest.group);
        state.cutscene_chain=state.cutscene_chain_count<16U;
        state.cutscene_chain_level=dest.level;state.cutscene_chain_group=dest.group;
        break;
      }
      case K::conditional_end:
        if(call(game_code("game.mainGetGameFlag"),90)&&call(game_code("game.mainGetGameFlag"),91)&&call(game_code("game.mainGetGameFlag"),92))
          call(game_code("game.mainChangeLevel"),212,call(game_code("game.mainGetNextCharacter")),0,call(game_code("game.frontGetMode")),1,0);
        else {call(game_code("game.mainFrontInit"),5,127,0);call(game_code("game.frontCharSelectSetQuitMode"),0);}
        break;
    }
  }
  // Explicit completion already covers the transition with a black native
  // overlay. Finish only the outgoing visual countdown; the native transition
  // routine still checks video readiness and performs every cleanup/load step.
  // It also installs the destination's ordinary fade-in after loading.
  if(state.cutscene_chain && state.cutscene_prompt.transition &&
     !plan->native_credits && game_view(ram).u8(game_data_ref("globals.transitionPrompt"))==0 &&
     ram.u8(game_data("globals.transitionCutsceneActive"))==0 &&
     game_view(ram).u16(game_data_ref("globals.pendingLevel"))==state.cutscene_chain_level &&
     game_view(ram).u16(game_data_ref("globals.pendingCutsceneGroup"))==state.cutscene_chain_group &&
     ram.instruction_matches("guard.game.mainPrepareTransition.entry0") &&
     ram.instruction_matches("native.transition_count_load") &&
     ram.instruction_matches("native.transition_count_subtract") &&
     ram.instruction_matches("native.transition_count_store") &&
     ram.instruction_matches("native.transition_finish_call")) {
    const auto wait=game_view(ram).u8(game_data_ref("globals.transitionCountdown"));
    if(wait==10U || wait==30U) {
      state.rdram[(game_data("globals.transitionCountdown")&0x1FFFFFFFU)^3U]=1U;
      state.gameplay_trace.event("cutscene-transition-wait",{
        state.vi_retraces,level,group,state.cutscene_chain_level,wait,1U});
    }
  }
  state.cutscene_prompt.visible=false;
  state.gameplay_trace.event("cutscene-skip-complete",{state.vi_retraces,level,group,
    plan->destination,plan->group,plan->conditional?1U:0U,state.cutscene_chain_count});
  jfg::support_event("cutscene=explicit-completion level="+std::to_string(level)+
      " group="+std::to_string(group));
}
#endif

int dispatch(void *opaque, std::int32_t address, std::uint8_t *rdram,
             recomp_context *context) {
  auto &state = *static_cast<State *>(opaque);
#if defined(_WIN32) && defined(JFG_PHASE8_LIVE_RUNTIME)
  const auto dispatch_prefix_started = state.diagnostic_cpu_costs ? std::chrono::steady_clock::now()
      : std::chrono::steady_clock::time_point{};
#endif
  const auto target = static_cast<std::uint32_t>(address);
#if defined(_WIN32) && defined(JFG_PHASE8_LIVE_RUNTIME)
  FunctionProfileScope function_profile_scope(state,target,*context);
  if(target==game_code("game.levelGetTune")) {
    const NativeGameMemory music_ram({state.rdram,kRdramSize});
    const auto level=static_cast<std::uint32_t>(context->r4);
    if(const auto selected=jfg::flight_transition_next_music(music_ram,level,
        static_cast<std::uint32_t>(context->r31))) {
      context->r2=*selected;
      state.gameplay_trace.event("flight-music-next",{state.vi_retraces,level,
        game_view(music_ram).u16(game_data_ref("globals.pendingCutsceneGroup")),*selected});
      return 1;
    }
  }
  if(target==game_code("game.levelTunePlay")) {
    NativeGameMemory music_ram({state.rdram,kRdramSize});
    const auto header=game_view(music_ram).u32(game_data_ref("globals.levelHeader"));
    const auto previous=music_ram.valid(header,0x73U)?music_ram.u8(header+game_member("layout.levelHeader.music")):0U;
    if(jfg::apply_flight_transition_music_header(music_ram))
      state.gameplay_trace.event("flight-music-correction",{state.vi_retraces,
        game_view(music_ram).u32(game_data_ref("globals.currentLevel")),game_view(music_ram).u32(game_data_ref("globals.cutsceneGroup")),previous,7U});
  }
  // Record sparse native audio state changes during cinematic handoff. This
  // observes the original calls without changing the sample queue or music.
  if(state.gameplay_trace && (target==game_code("game.amTunePlay") || target==game_code("game.amTuneStop") ||
      target==game_code("game.amTuneSetFade") || target==game_code("game.amTuneSetVolume") || target==game_code("game.amTuneResetFade") ||
      target==game_code("game.amAmbientResetFade") || target==game_code("game.amSndStop") || target==game_code("game.animseqStopSounds") ||
      target==game_code("game.amSndPlay") || target==game_code("game.amSndPlayXYZ") || target==game_code("game.amSndStopXYZ") ||
      target==game_code("game.amAmbientPlay"))) {
    NativeGameMemory audio_ram({state.rdram,kRdramSize});
    const auto audio_header=game_view(audio_ram).u32(game_data_ref("globals.levelHeader"));
    if(audio_ram.valid(audio_header,0x75U) &&
       (audio_ram.u8(audio_header+0x6CU)==1U || audio_ram.u8(audio_header+0x6CU)==2U ||
        state.cutscene_chain)) {
      state.gameplay_trace.event("cutscene-audio-call",{state.vi_retraces,
        game_view(audio_ram).u32(game_data_ref("globals.currentLevel")),game_view(audio_ram).u32(game_data_ref("globals.cutsceneGroup")),target,
        static_cast<std::uint32_t>(context->r4),static_cast<std::uint32_t>(context->r5),
        static_cast<std::uint32_t>(context->r6),context->f12.u32l,
        state.cutscene_chain?1U:0U,state.cutscene_chain_count,
        audio_ram.u8(audio_header+0x72U),game_view(audio_ram).u8(game_data_ref("globals.tuneVolume")),
        game_view(audio_ram).u32(game_data_ref("globals.tuneFade")),state.host_audio.queued_bytes(),
        state.host_audio.underruns(),state.host_audio.overruns()});
    }
  }
  if(state.cutscene_chain && (target==game_code("game.amSndPlay") || target==game_code("game.amSndPlayXYZ"))) {
    NativeGameMemory sound_ram({state.rdram,kRdramSize});
    const auto stack=static_cast<std::uint32_t>(context->r29);
    if(target==game_code("game.amSndPlay") || (stack<=0xFFFFFFEBU && sound_ram.valid(stack+0x14U,4U))) {
      const auto handle=target==game_code("game.amSndPlay")?static_cast<std::uint32_t>(context->r5):
          sound_ram.u32(stack+0x14U);
      const jfg::CutsceneSoundCall sound_call{state.cutscene_chain,
          state.cutscene_skip_scene.load(std::memory_order_acquire),
          state.cutscene_chain_level,state.cutscene_chain_group,target,
          static_cast<std::uint32_t>(context->r31),handle,
          static_cast<std::uint32_t>(context->r16)};
      if(jfg::omit_skipped_cutscene_sound(sound_ram,sound_call,jfg::game::linked::descriptor,kCutsceneSoundBindings)) {
        state.gameplay_trace.event("cutscene-skip-sound-omitted",{state.vi_retraces,
          sound_call.destination,sound_call.group,target,
          static_cast<std::uint32_t>(context->r4),sound_call.return_address,handle});
        return 1;
      }
    }
  }
  if(target==game_code("game.animseqFreeGroup")) {
    state.cutscene_skip_scene=0;state.cutscene_cached_scene=0;
    state.cutscene_skip_request=0;state.cutscene_skip_gesture=0;
    state.cutscene_prompt.visible=false;
  }
  if(target==game_code("game.animseqUpdate")) {
    if(update_cutscene_review(state,*context))return 1;
    update_cutscene_completion(state,*context);
  }

  if(target==game_code("game.fontSetWindow0")) {
    const auto width=static_cast<unsigned>(context->r4),height=static_cast<unsigned>(context->r5);
    if(width>=160U&&width<=1023U&&height>=100U&&height<=1023U) {
      state.cutscene_prompt.width=width;state.cutscene_prompt.height=height;
    }
  }
  if(target==game_code("game.setupClearScreen") && state.gameplay_trace) {
    const NativeGameMemory ram({state.rdram,kRdramSize});
    state.gameplay_trace.event("cinematic-fade-request",{state.vi_retraces,
      game_view(ram).u32(game_data_ref("globals.currentLevel")),static_cast<std::uint32_t>(context->r4),
      static_cast<std::uint32_t>(context->r5),static_cast<std::uint32_t>(context->r6),
      static_cast<std::uint32_t>(context->r7),static_cast<std::uint32_t>(context->r31)});
  }
  if(target==game_code("game.rcpFast3d")) {
    if(context->r6==0 && state.gameplay_trace) {
      const NativeGameMemory ram({state.rdram,kRdramSize});
      const auto level=game_view(ram).u32(game_data_ref("globals.currentLevel")),header=game_view(ram).u32(game_data_ref("globals.levelHeader"));
      const auto kind=ram.valid(header,game_member("layout.levelHeader.kind")+1U)?ram.u8(header+game_member("layout.levelHeader.kind")):0U;
      if(level!=0U && level!=127U && (kind==1U || kind==2U))
        state.cutscene_trace_until_vi=state.vi_retraces+180U;
      if(state.cutscene_trace_until_vi && state.vi_retraces<=state.cutscene_trace_until_vi) {
        state.gameplay_trace.event("cinematic-frame-state",{state.vi_retraces,
          level,game_view(ram).u32(game_data_ref("globals.cutsceneGroup")),static_cast<std::uint32_t>(context->r4),
          static_cast<std::uint32_t>(context->r5),static_cast<std::uint32_t>(context->r7),
          game_view(ram).u8(game_data_ref("globals.transitionCountdown")),state.cutscene_prompt.transition?1U:0U,
          ram.u32(game_data("diagnostic.cutsceneState")),ram.u8(game_data("diagnostic.cutsceneByte0")),ram.u8(game_data("diagnostic.cutsceneByte1")),
          ram.u8(game_data("diagnostic.cutsceneByte2")),ram.u8(game_data("diagnostic.cutsceneByte3")),game_view(ram).u32(game_data_ref("globals.cutsceneScriptCursor"))});
      }
    }
    // Capture the prompt with the native primary graphics task. Offscreen
    // clone/refraction/blur tasks must never acquire the HUD in their textures.
    const auto list=static_cast<std::uint32_t>(context->r4)&0x00FFFFFFU;
    state.daynight_fog_frames.submit(list, context->r6 == 0,
        state.active_overlay_sections.contains(game_module(OriginalModule::day_night)) &&
        !state.active_overlay_sections.contains(game_module(OriginalModule::mantis_lighting)) &&
        !state.active_overlay_sections.contains(game_module(OriginalModule::vela_magic)));

    const auto gesture=state.cutscene_skip_gesture.load(std::memory_order_acquire);
    state.cutscene_prompt.visible=gesture!=0 && state.cutscene_skip_scene.load(std::memory_order_acquire)!=0;
    state.cutscene_prompt.progress=gesture?static_cast<float>(gesture-1U)/1000.0f:0.0f;
    if(context->r6==0 && state.cutscene_prompt.transition) {
      NativeGameMemory skip_ram({state.rdram,kRdramSize});
      const auto skip_level=game_view(skip_ram).u32(game_data_ref("globals.currentLevel"));
      const auto skip_header=game_view(skip_ram).u32(game_data_ref("globals.levelHeader"));
      if(game_view(skip_ram).u8(game_data_ref("globals.transitionCountdown"))==0 && skip_ram.valid(skip_header,game_member("layout.levelHeader.kind")+1U) &&
         (skip_level==0U || skip_level==127U ||
          (skip_ram.u8(skip_header+game_member("layout.levelHeader.kind"))!=1U && skip_ram.u8(skip_header+game_member("layout.levelHeader.kind"))!=2U))) {
        state.cutscene_prompt.transition=false;state.cutscene_chain=false;
      }
    }
    // An unsupported handoff resumes ordinary playback. Never leave a
    // transition cover behind indefinitely if a destination fails to settle.
    if(state.cutscene_prompt.transition &&
       state.vi_retraces-state.cutscene_transition_started>900U) {
      state.cutscene_prompt.transition=false;state.cutscene_chain=false;
      jfg::support_event("cutscene=completion-timeout-resume");
    }
    if(context->r6==0 && (state.cutscene_prompt.visible || state.cutscene_prompt.transition)) {
      if(state.cutscene_prompt_submissions.size()>=16)state.cutscene_prompt_submissions.clear();
      state.cutscene_prompt_submissions[list]=state.cutscene_prompt;
    } else state.cutscene_prompt_submissions.erase(list);
  }

#endif
#if defined(JFG_PHASE8_LIVE_RUNTIME)
  for (std::size_t watch = 0U;
       !state.progress_path.empty() &&
       watch < state.matrix_watch_addresses.size(); ++watch) {
    const std::uint32_t watched = state.matrix_watch_addresses[watch];
    if (watched == 0U)
      continue;
    // These observations use the native-word layout. Validate the same
    // aligned RDRAM range before loading directly, avoiding an out-of-line
    // GuestMemory call for each of the eight words on every dispatch.
    if ((watched & 3U) != 0U || watched < kKseg0 ||
        watched - kKseg0 > kRdramSize - sizeof(std::uint32_t))
      continue;
    std::uint32_t current = 0U;
    std::memcpy(&current, rdram + (watched - kKseg0), sizeof(current));
    if (current == state.matrix_watch_words[watch])
      continue;
    const std::size_t slot = state.recent_matrix_watch_position %
        state.recent_matrix_watch_addresses.size();
    state.recent_matrix_watch_addresses[slot] = watched;
    state.recent_matrix_watch_before[slot] = state.matrix_watch_words[watch];
    state.recent_matrix_watch_after[slot] = current;
    state.recent_matrix_watch_targets[slot] =
        state.recent_dispatch_position == 0U
            ? 0U
            : state.recent_dispatches[(state.recent_dispatch_position - 1U) %
                                      state.recent_dispatches.size()];
    state.recent_matrix_watch_callers[slot] =
        state.recent_dispatch_position < 2U
            ? 0U
            : state.recent_dispatches[(state.recent_dispatch_position - 2U) %
                                      state.recent_dispatches.size()];
    state.recent_matrix_watch_current_targets[slot] = target;
    state.recent_matrix_watch_return_addresses[slot] =
        static_cast<std::uint32_t>(context->r31);
    if (watched == (game_data("diagnostic.cameraViewState")+4U)) {
      state.poison_matrix_watch = {
          state.matrix_watch_words[watch], current,
          state.recent_matrix_watch_targets[slot],
          state.recent_matrix_watch_callers[slot], target,
          state.recent_matrix_watch_return_addresses[slot]};
      const std::size_t history_count =
          (std::min)(state.recent_dispatch_position,
                     state.poison_dispatch_history.size());
      state.poison_dispatch_history.fill(0U);
      for (std::size_t index = 0U; index < history_count; ++index) {
        const std::size_t distance = history_count - index;
        state.poison_dispatch_history[index] =
            state.recent_dispatches[(state.recent_dispatch_position - distance) %
                                    state.recent_dispatches.size()];
      }
    }
    ++state.recent_matrix_watch_position;
    state.matrix_watch_words[watch] = current;
  }
#endif
  if (target == 0xFFFFFFFEU) {
    if (state.scheduler == nullptr || !state.scheduler_running ||
        state.scheduler->current_thread_id() < 0) {
      fail_closed_dispatch(state, "scheduler", "pause-outside-thread",
                           target);
    }
    state.journal.append(NativeEventKind::kThreadPaused, target,
                         static_cast<std::uint32_t>(
                             state.scheduler->current_thread_id()));
    state.scheduler->pause_current();
    fail_closed_dispatch(state, "scheduler", "pause-resumed", target);
  }
  if (state.mmio_trace != nullptr &&
      state.mmio_trace->unsupported_accesses != 0U)
    fail_closed_dispatch(state, "mmio", "unsupported-register", target);
  ++state.dispatch_calls;
#if defined(_WIN32) && defined(JFG_PHASE8_LIVE_RUNTIME)
  // Read-only, explicitly requested private gameplay diagnostics. Keep the
  // original weapon handler and all ammunition/charge logic untouched.
  if(target==game_code("game.controlUpdateWeapon") && state.gameplay_trace) {
    NativeGameMemory ram({rdram,kRdramSize});
    const auto actor=static_cast<std::uint32_t>(context->r4);
    const auto control=static_cast<std::uint32_t>(context->r5);
    const auto game=game_view(ram).u32(game_data_ref("globals.selectedPlayer"));
    if(ram.instruction_matches("guard.game.controlUpdateWeapon.entry0") && ram.instruction_matches("guard.game.controlUpdateWeapon.entry4") &&
       ram.instruction_matches("guard.game.controlUpdateWeapon.entry8") && ram.valid(actor,0xA4U) &&
       ram.valid(control,0x5C4U) && ram.u32(actor+game_member("layout.actor.control"))==control &&
       ram.valid(game,0x538U) && jfg::mod::gameplay_active(ram,actor)) {
      const auto character=ram.u8(control+game_member("layout.playerControl.characterFlags"))&3U;
      const auto port=jfg::mod::pc_input_port(ram,ram.u8(control));
      if(character<3U && port<4U) {
        const auto saved=game+0x15CU+character*0x76U;
        const auto weapon=ram.u8(saved+0x70U);
        if(weapon<16U)state.gameplay_trace.event("pc-weapon-state",{
          state.vi_retraces,actor,port,character,weapon,
          ram.u16(saved+0x14U+weapon*2U),ram.u16(saved+0x34U+weapon*2U),
          ram.u8(control+game_member("layout.playerControl.movement")),ram.u32(game+0x474U+weapon*4U),
          ram.u16(control+game_member("layout.playerControl.fireCounter")),ram.u16(control+game_member("layout.playerControl.weaponCounter")),
          ram.u32(game_data("globals.portControlModes")+port*4U),ram.u32(game_data("diagnostic.inputPollState"))});
      }
    }
  }
  // Keep native transparent-object ordering for a proximity-faded player.
  // Renderer metadata resolves its nearest surface in a separate depth layer
  // and blends the result once, rather than blending interior mesh surfaces.
  if(target==game_code("game.trackDrawTransparentActors") && state.modern_controls_active &&
     (state.play_mode || state.input_replay_loaded) &&
     (state.input_record_path.empty() || state.pc_record_extended)) {
    NativeGameMemory ram({rdram,kRdramSize});
    const auto actor=static_cast<std::uint32_t>(context->r4);
    const auto control=ram.valid(actor,0xA4U)?ram.u32(actor+game_member("layout.actor.control")):0U;
    if(ram.valid(control,0x5C4U) && ram.instruction_matches("guard.game.trackDrawTransparentActors.entry0") &&
       ram.instruction_matches("guard.game.trackDrawTransparentActors.entry4") && ram.instruction_matches("guard.game.trackDrawTransparentActors.entry8") &&
       jfg::mod::gameplay_active(ram,actor) && game_view(ram).u8(game_data_ref("globals.pauseActive"))==0 &&
       !jfg::mod::scripted_camera_active(ram,actor)) {
      const auto port=jfg::mod::pc_input_port(ram,ram.u8(control));
      if(port<4 && modern_controls_selected(state,port) &&
         !state.modern_controls[port].combat_transparency &&
         state.controller_ports.samples[port].connected &&
         jfg::mod::pc_player_for_port(ram,port)==actor) {
        const auto camera=jfg::mod::control_camera(ram);
        auto* original=jfg_generated_lookup_function(static_cast<std::int32_t>(target));
        if(camera.known && original) {
          original(rdram,context);
          const int native_alpha=static_cast<std::int32_t>(context->r2);
          // This API contains only the player camera/aim fade. Death, scene
          // fades and other actors use their own opacity paths.
          const jfg::PcOrbitPoint body{ram.f32(actor+game_member("layout.actor.x")),ram.f32(actor+game_member("layout.actor.y")),ram.f32(actor+game_member("layout.actor.z"))};
          const int alpha=jfg::pc_camera_player_alpha(body,
            {camera.position.x,camera.position.y,camera.position.z},255);
          context->r2=alpha;
          state.gameplay_trace.event("pc-combat-opacity",{
            state.vi_retraces,actor,static_cast<std::uint32_t>(native_alpha),
            static_cast<std::uint32_t>(alpha),ram.u8(control+game_member("layout.playerControl.movement")),port});
          state.pc_camera_fades[port]={actor,control,ram.u32(actor+game_member("layout.actor.header")),
              state.vi_retraces,state.camera_fade_updates,static_cast<unsigned>(alpha)};
          return 1;
        }
      }
      if(port<4 && state.controller_ports.samples[port].connected &&
         state.pc_orbits[port].active && state.pc_orbits[port].actor==actor &&
         state.vi_retraces-state.pc_orbits[port].retrace<=15U &&
         jfg::pc_normal_camera_owns_look((state.controller_ports.samples[port].buttons&0x10)!=0,ram.u8(control+game_member("layout.playerControl.movement")))) {
        const auto mode=state.pc_frames[port].pc_mode;
        const auto camera=jfg::mod::control_camera(ram);
        auto* original=jfg_generated_lookup_function(static_cast<std::int32_t>(target));
        if((mode==3 || mode==4 || mode==5) && camera.known && original) {
          const jfg::PcOrbitPoint body{ram.f32(actor+game_member("layout.actor.x")),ram.f32(actor+game_member("layout.actor.y")),ram.f32(actor+game_member("layout.actor.z"))};
          original(rdram,context);
          const int before=static_cast<std::int32_t>(context->r2);
          const int after=jfg::pc_camera_player_alpha(body,
              {camera.position.x,camera.position.y,camera.position.z},before);
          // Native alpha selects the original transparent-object ordering.
          // Only our added fade (native opacity255) uses the isolated layer;
          // native aim/death fades remain on their existing path.
          if(before==255)context->r2=after;
          state.pc_camera_fades[port]={actor,control,ram.u32(actor+game_member("layout.actor.header")),
              state.vi_retraces,state.camera_fade_updates,before==255?static_cast<unsigned>(after):255U};
          if(after!=before)state.gameplay_trace.event("pc-camera-fade",{
            state.vi_retraces,actor,static_cast<std::uint32_t>(before),static_cast<std::uint32_t>(after)});
          return 1;
        }
      }
    }
  }
  // The stock camera moves the player to maintain 32 horizontal units of
  // separation. At an upward view limit its floor collision can repeatedly
  // push an idle modern player forward. Keep camera collision/clearance and
  // ordinary player physics; suppress only this qualified camera-body push.
  if(target==game_code("game.objMoveXYZ") && state.pc_camera_actor!=0 &&
     static_cast<std::uint32_t>(context->r4)==state.pc_camera_actor &&
     static_cast<std::uint32_t>(context->r31)==game_instruction("native.camera_height_return")) {
    NativeGameMemory ram({rdram,kRdramSize});
    const auto port=jfg::mod::pc_input_port(ram,ram.u8(state.pc_camera_control));
    if(ram.instruction_matches("native.camera_height_call") &&
       modern_shoulder_camera_current(state,port,state.pc_camera_actor)) {
      state.gameplay_trace.event("pc-camera-push-suppressed",{state.vi_retraces,
        state.pc_camera_actor,static_cast<std::uint32_t>(context->r5),
        static_cast<std::uint32_t>(context->r6),static_cast<std::uint32_t>(context->r7)});
      return 1;
    }
  }
  // The normal camera has computed its desired point, but has not yet run
  // scenery constraints. Feed the orbit into that existing solver, never over
  // its final position. Qualify both the owning routine and this call site.
  if(target==game_code("game.levelGetCamera") && state.pc_camera_actor!=0 &&
     static_cast<std::uint32_t>(context->r29)==state.pc_camera_stack) {
    NativeGameMemory ram({rdram,kRdramSize});
    const auto stack=static_cast<std::uint32_t>(context->r29);
    const auto actor=state.pc_camera_actor,control=state.pc_camera_control;
    const auto port=jfg::mod::pc_input_port(ram,ram.u8(control));
    if(port<4 && ram.valid(stack,0xF4U) && ram.u32(stack+0xF0U)==actor && ram.instruction_matches("native.camera_surface_call")) {
      auto &orbit=state.pc_orbits[port];
      const auto camera=game_view(ram).u32(game_data_ref("globals.controlledCamera"));
      const float px=ram.f32(actor+game_member("layout.actor.x")),py=ram.f32(actor+game_member("layout.actor.y"))+40.0F,pz=ram.f32(actor+game_member("layout.actor.z"));
      const float dx=ram.f32(stack+0x8CU)-px,dy=ram.f32(stack+0x90U)-py,dz=ram.f32(stack+0x94U)-pz;
      const float native_radius=std::sqrt(dx*dx+dy*dy+dz*dz);
      const float radius=modern_shoulder_camera_current(state,port,actor)?jfg::kPcShoulderDistance:native_radius;
      if(ram.valid(camera,0x4CU) && std::isfinite(px) && std::isfinite(py) && std::isfinite(pz) &&
         std::isfinite(radius) && radius>=40.0F && radius<=1000.0F) {
        if(!orbit.active || orbit.actor!=actor || state.vi_retraces-orbit.retrace>15U) {
          orbit.yaw=ram.s16(camera+game_member("layout.camera.yaw"));
          orbit.pitch=static_cast<int>(std::lround(std::atan2(dy,std::sqrt(dx*dx+dz*dz))*65536.0F/6.283185307179586F));
        }
        orbit.active=true;orbit.actor=actor;orbit.retrace=state.vi_retraces;
        if(modern_shoulder_camera_current(state,port,actor)) {
          orbit.yaw=jfg::pc_shoulder_camera_yaw(state.pc_shoulders[port].yaw);
          orbit.pitch=state.pc_shoulders[port].pitch;
        } else {
          orbit.yaw=jfg::pc_wrap_angle(orbit.yaw+state.pc_camera_look.x);
          orbit.pitch=std::clamp(orbit.pitch-state.pc_camera_look.y,-8192,12288);
        }
        const auto point=jfg::pc_orbit_point(orbit.yaw,orbit.pitch,radius);
        const jfg::PcOrbitPoint desired{px+point.x,py+point.y,pz+point.z};
        auto requested=desired;
        if(modern_shoulder_camera_current(state,port,actor)) {
          auto& transition=state.pc_shoulders[port].aim_return;
          const bool returning=transition.returning;
          requested=transition.apply(desired,state.pc_camera_ticks/60.0F);
          if(returning)state.gameplay_trace.event("pc-aim-return",{state.vi_retraces,actor,
            std::bit_cast<std::uint32_t>(state.pc_camera_ticks),
            std::bit_cast<std::uint32_t>(requested.x),std::bit_cast<std::uint32_t>(requested.y),
            std::bit_cast<std::uint32_t>(requested.z),std::bit_cast<std::uint32_t>(desired.x),
            std::bit_cast<std::uint32_t>(desired.y),std::bit_cast<std::uint32_t>(desired.z),
            transition.returning?1U:0U});
        }
        // The complete transition point goes through the existing scenery and
        // clearance solver. Never blend the final collision-safe position later.
        hle::GuestMemory memory({rdram,kRdramSize},hle::GuestMemory::Layout::native_word_big_endian);
        (void)memory.write_u32(stack+0x8CU,std::bit_cast<std::uint32_t>(requested.x));
        (void)memory.write_u32(stack+0x90U,std::bit_cast<std::uint32_t>(requested.y));
        (void)memory.write_u32(stack+0x94U,std::bit_cast<std::uint32_t>(requested.z));
        state.gameplay_trace.event("pc-orbit",{state.vi_retraces,state.controller_samples,port,
          static_cast<std::uint16_t>(orbit.yaw),static_cast<std::uint16_t>(orbit.pitch),
          std::bit_cast<std::uint32_t>(radius),static_cast<std::uint32_t>(state.pc_camera_look.x),
          static_cast<std::uint32_t>(state.pc_camera_look.y)});
      }
    }
  }
  // The scenery solver can leave its point exactly on a wall. Keep a small
  // near-plane clearance toward its focus, only when collision moved the
  // requested orbit point. Preserve the solver's unblocked result verbatim.
  if(target==game_code("game.controlCameraSceneryCollision") && state.pc_camera_actor!=0 &&
     static_cast<std::uint32_t>(context->r29)==state.pc_camera_stack) {
    NativeGameMemory ram({rdram,kRdramSize});
    const auto focus=static_cast<std::uint32_t>(context->r4),point=static_cast<std::uint32_t>(context->r5);
    const auto stack=state.pc_camera_stack;
    if(focus==stack+0x98U && point==stack+0x8CU && ram.valid(stack,0xA4U) &&
       ram.instruction_matches("guard.game.controlCameraSceneryCollision.entry0") && ram.instruction_matches("guard.game.controlCameraSceneryCollision.entry4")) {
      const jfg::PcOrbitPoint from{ram.f32(focus),ram.f32(focus+4U),ram.f32(focus+8U)};
      const jfg::PcOrbitPoint wanted{ram.f32(point),ram.f32(point+4U),ram.f32(point+8U)};
      auto* original=jfg_generated_lookup_function(static_cast<std::int32_t>(target));
      if(original) {
        const auto entry=*context;
        const auto camera_started = state.gameplay_trace ? std::chrono::steady_clock::now()
                                                        : std::chrono::steady_clock::time_point{};
        const auto camera_count = state.cpu_count;
        original(rdram,context);
        const auto returned=*context;
        const auto camera_body_started = state.gameplay_trace ? std::chrono::steady_clock::now()
                                                             : std::chrono::steady_clock::time_point{};
        const auto camera_body_count = state.cpu_count;
        const auto camera_body_wait = state.profile_host_wait_us;
        unsigned camera_queries = 0U;
        const jfg::PcOrbitPoint resolved{ram.f32(point),ram.f32(point+4U),ram.f32(point+8U)};
        auto clear=jfg::pc_camera_clearance(from,wanted,resolved);
        hle::GuestMemory memory({rdram,kRdramSize},hle::GuestMemory::Layout::native_word_big_endian);
        const auto put=[&](std::uint32_t address,jfg::PcOrbitPoint p) {
          (void)memory.write_u32(address,std::bit_cast<std::uint32_t>(p.x));
          (void)memory.write_u32(address+4U,std::bit_cast<std::uint32_t>(p.y));
          (void)memory.write_u32(address+8U,std::bit_cast<std::uint32_t>(p.z));
        };
        const auto port=jfg::mod::pc_input_port(ram,ram.u8(state.pc_camera_control));
        const bool shoulder=modern_shoulder_camera_current(state,port,state.pc_camera_actor);
        if(shoulder) {
          auto& boom=state.pc_shoulders[port].camera_boom;
          std::optional<jfg::PcCameraBroadphase> geometry;
          const auto validate_height=[&](jfg::PcOrbitPoint candidate,jfg::PcOrbitPoint result) {
            if(std::abs(result.x-candidate.x)<=0.01F &&
               std::abs(result.z-candidate.z)<=0.01F &&
               std::abs(result.y-candidate.y)>0.01F) {
              if(!geometry)geometry.emplace(ram);
              // The guest height query can extrapolate a steep rim's plane
              // beyond its finite triangle. Ignore only a height-only result
              // when the complete scene and registered model bounds certify
              // both the view segment and the 16-unit camera volume as clear.
              if(!geometry->volume_possible(candidate,16.0F) &&
                 !geometry->possible(from,candidate)) {
                state.gameplay_trace.event("pc-camera-height-clear",{state.vi_retraces,
                  std::bit_cast<std::uint32_t>(candidate.x),std::bit_cast<std::uint32_t>(candidate.y),
                  std::bit_cast<std::uint32_t>(candidate.z),std::bit_cast<std::uint32_t>(result.y)});
                return candidate;
              }
            }
            return result;
          };
          const bool swimming=modern_swimming_view_current(state,state.pc_camera_actor);
          clear=jfg::pc_camera_resolve(boom,swimming,from,wanted,
            swimming?resolved:validate_height(wanted,resolved),state.pc_camera_ticks/60.0F,
            [&](jfg::PcOrbitPoint candidate) {
              put(point,candidate);*context=entry;original(rdram,context);
              return validate_height(candidate,
                {ram.f32(point),ram.f32(point+4U),ram.f32(point+8U)});
            });
          camera_queries=boom.queries;
          state.gameplay_trace.event(swimming?"pc-swimming-camera":"pc-camera-boom",{state.vi_retraces,
            std::bit_cast<std::uint32_t>(boom.distance),boom.queries,
            boom.constrained?1U:0U,boom.fallback?1U:0U,
            std::bit_cast<std::uint32_t>(state.pc_camera_ticks),
            std::bit_cast<std::uint32_t>(from.x),std::bit_cast<std::uint32_t>(from.y),std::bit_cast<std::uint32_t>(from.z)});
          *context=returned;
        }
        // The guest helper tests the head-height focus and can then raise an
        // inward contact back to the requested camera height (0x8002CF54).
        // Query trackNearestIntersection directly for body visibility. It
        // retains the game's own scenery and moving-model collision rules.
        constexpr std::uint32_t ray_target=game_code("game.trackNearestIntersection");
        auto* ray=jfg_generated_lookup_function(static_cast<std::int32_t>(ray_target));
        if(!shoulder && ray && stack>=0x80000400U && ram.valid(stack-0x400U,0x400U) &&
           ram.instruction_matches("guard.game.trackNearestIntersection.entry0") && ram.instruction_matches("guard.game.trackNearestIntersection.entry4")) {
          const std::uint32_t scratch=stack-0x80U;
          // A torso ray can pass above a narrow tree edge while the legs stay
          // hidden. Start just above the actor's feet, in world coordinates.
          const jfg::PcOrbitPoint body{ram.f32(state.pc_camera_actor+game_member("layout.actor.x")),
            ram.f32(state.pc_camera_actor+game_member("layout.actor.y"))+8.0F,ram.f32(state.pc_camera_actor+game_member("layout.actor.z"))};
          const jfg::PcCameraBroadphase broadphase(ram);
          for(unsigned pass=0;pass<2;++pass) {
            auto candidate=clear;
            jfg::PcOrbitPoint nearest_hit{};
            const auto distance2=[&](jfg::PcOrbitPoint p) {
              const float x=p.x-from.x,y=p.y-from.y,z=p.z-from.z;return x*x+y*y+z*z;
            };
            for(const auto probe:jfg::pc_camera_body_probes(body,clear)) {
              if(!broadphase.possible(probe,clear))continue;
              put(scratch+0x20U,probe);put(scratch+0x30U,clear);
              (void)memory.write_u32(scratch+0x10U,0U);
              (void)memory.write_u32(scratch+0x14U,0U);
              // Recompiled memory operands require sign-extended addresses;
              // timing/dispatch hooks must retain the live thread context.
              const auto guest_address=[](std::uint32_t value){return static_cast<gpr>(static_cast<std::int32_t>(value));};
              *context=entry;context->r29=guest_address(scratch);context->r4=0;
              context->r5=guest_address(scratch+0x20U);context->r6=guest_address(scratch+0x30U);context->r7=guest_address(scratch+0x40U);
              ++camera_queries;
              ray(rdram,context);
              if(context->r2==0)continue;
              const jfg::PcOrbitPoint hit{ram.f32(scratch+0x44U),ram.f32(scratch+0x48U),ram.f32(scratch+0x4CU)};
              const auto shortened=jfg::pc_camera_body_clearance(from,clear,probe,hit);
              if(distance2(shortened)<distance2(candidate)){candidate=shortened;nearest_hit=hit;}
            }
            if(candidate.x==clear.x && candidate.y==clear.y && candidate.z==clear.z)break;
            put(point,candidate);*context=entry;original(rdram,context);
            const jfg::PcOrbitPoint checked{ram.f32(point),ram.f32(point+4U),ram.f32(point+8U)};
            clear=jfg::pc_camera_clearance(from,candidate,checked);
            state.gameplay_trace.event("pc-camera-body",{state.vi_retraces,pass,
              std::bit_cast<std::uint32_t>(nearest_hit.x),std::bit_cast<std::uint32_t>(nearest_hit.y),std::bit_cast<std::uint32_t>(nearest_hit.z),
              std::bit_cast<std::uint32_t>(clear.x),std::bit_cast<std::uint32_t>(clear.y),std::bit_cast<std::uint32_t>(clear.z)});
          }
          *context=returned;
        }
        if (state.gameplay_trace) {
          const auto end = std::chrono::steady_clock::now();
          state.gameplay_trace.event("pc-camera-work", {state.vi_retraces,
              camera_body_count - camera_count, state.cpu_count - camera_body_count,
              static_cast<std::uint64_t>(std::chrono::duration_cast<std::chrono::microseconds>(
                  camera_body_started-camera_started).count()),
              static_cast<std::uint64_t>(std::chrono::duration_cast<std::chrono::microseconds>(
                  end-camera_body_started).count()),
              state.profile_host_wait_us-camera_body_wait, camera_queries});
        }
        state.pc_camera_resolved=clear;state.pc_camera_resolved_valid=true;
        (void)memory.write_u32(point,std::bit_cast<std::uint32_t>(clear.x));
        (void)memory.write_u32(point+4U,std::bit_cast<std::uint32_t>(clear.y));
        (void)memory.write_u32(point+8U,std::bit_cast<std::uint32_t>(clear.z));
        state.gameplay_trace.event("pc-camera-clearance",{state.vi_retraces,
          std::bit_cast<std::uint32_t>(wanted.x),std::bit_cast<std::uint32_t>(wanted.y),std::bit_cast<std::uint32_t>(wanted.z),
          std::bit_cast<std::uint32_t>(resolved.x),std::bit_cast<std::uint32_t>(resolved.y),std::bit_cast<std::uint32_t>(resolved.z),
          std::bit_cast<std::uint32_t>(clear.x),std::bit_cast<std::uint32_t>(clear.y),std::bit_cast<std::uint32_t>(clear.z)});
        return 1;
      }
    }
  }
  if(target==game_code("game.controlUpdateCamera") && state.modern_controls_active && (state.play_mode || state.input_replay_loaded) &&
     (state.input_record_path.empty() || state.pc_record_extended) &&
     state.pc_camera_actor==0) {
    NativeGameMemory ram({rdram,kRdramSize});
    const auto actor=static_cast<std::uint32_t>(context->r4),control=static_cast<std::uint32_t>(context->r5);
    if(ram.valid(control,0x5C4U) && ram.valid(actor,0xA4U) && ram.u32(actor+game_member("layout.actor.control"))==control &&
       ram.instruction_matches("guard.game.controlUpdateCamera.entry0") && ram.instruction_matches("guard.game.controlUpdateCamera.entry4") &&
       (jfg::mod::pc_gameplay_active(ram,actor) || modern_landing_view_current(state,actor)) && game_view(ram).u8(game_data_ref("globals.pauseActive"))==0 && !jfg::mod::scripted_camera_active(ram,actor)) {
      const auto port=jfg::mod::pc_input_port(ram,ram.u8(control));
      if(port<4 && state.controller_ports.samples[port].connected) {
        const auto &frame=state.pc_frames[port];
        const bool shoulder=modern_shoulder_camera_current(state,port,actor);
        // Keep the normal view through the first aim-press update, until the
        // native state has actually handed ownership to its aiming camera.
        const bool normal_view=modern_landing_view_current(state,actor) || modern_ledge_view_current(state,actor) ||
          (shoulder && !state.pc_shoulders[port].aiming) ||
          jfg::pc_normal_camera_owns_look((state.controller_ports.samples[port].buttons&0x10)!=0,ram.u8(control+game_member("layout.playerControl.movement")));
        if((frame.pc_mode==3 || frame.pc_mode==4 || frame.pc_mode==5) && normal_view &&
           (!state.pc_input_blocked || shoulder)) {
          auto* original=jfg_generated_lookup_function(static_cast<std::int32_t>(target));
          if(original) {
            auto look=jfg::PcLookDelta{frame.look_x,frame.look_y};
            if(frame.pc_mode==3) {
              if(state.pc_mouse_used[port])look={};
              state.pc_mouse_used[port]=true;
            }
            state.pc_scope_motion[port].clear();
            state.pc_camera_actor=actor;state.pc_camera_control=control;
            state.pc_camera_stack=static_cast<std::uint32_t>(context->r29)-0xF0U;
            const float ticks=std::bit_cast<float>(static_cast<std::uint32_t>(context->r6));
            state.pc_camera_look=shoulder?jfg::PcLookDelta{}:
              frame.pc_mode==5?state.pc_stick_motion[port].take(look,ticks,actor):
              jfg::pc_camera_delta(frame.pc_mode,look,ticks);
            state.pc_camera_ticks=ticks;
            state.pc_camera_resolved_valid=false;
            if(shoulder) {
              const auto camera=game_view(ram).u32(game_data_ref("globals.controlledCamera"));
              if(ram.valid(camera,0x4CU)) {
                const jfg::PcOrbitPoint actual{ram.f32(camera+game_member("layout.camera.x")),
                  ram.f32(camera+game_member("layout.camera.y")),ram.f32(camera+game_member("layout.camera.z"))};
                if(state.pc_shoulders[port].aim_return.release(actual))
                  state.gameplay_trace.event("pc-aim-return-start",{state.vi_retraces,actor,
                    std::bit_cast<std::uint32_t>(actual.x),std::bit_cast<std::uint32_t>(actual.y),
                    std::bit_cast<std::uint32_t>(actual.z)});
              }
            }
            original(rdram,context);
            if(shoulder && state.pc_camera_resolved_valid) {
              // Use the collision-resolved position this update. The original
              // camera's follow interpolation otherwise adds drift to raw look.
              const auto camera=game_view(ram).u32(game_data_ref("globals.controlledCamera"));
              if(ram.valid(camera,0x4CU)) {
                const auto point=state.pc_camera_resolved;
                hle::GuestMemory memory({rdram,kRdramSize},hle::GuestMemory::Layout::native_word_big_endian);
                (void)memory.write_u32(camera+game_member("layout.camera.x"),std::bit_cast<std::uint32_t>(point.x));
                (void)memory.write_u32(camera+game_member("layout.camera.y"),std::bit_cast<std::uint32_t>(point.y));
                (void)memory.write_u32(camera+game_member("layout.camera.z"),std::bit_cast<std::uint32_t>(point.z));
                // Scenery may move the camera off its ideal orbit. Preserve
                // that safe position without rotating away from the input view;
                // otherwise entering aim changes direction beside a wall.
                const auto &view=state.pc_shoulders[port];
                const int yaw=jfg::pc_shoulder_camera_yaw(view.yaw);
                const int pitch=view.pitch;
                ram.put16(camera+game_member("layout.camera.yaw"),static_cast<std::uint16_t>(yaw));ram.put16(camera+game_member("layout.camera.pitch"),static_cast<std::uint16_t>(pitch));
                state.gameplay_trace.event("pc-shoulder-camera",{state.vi_retraces,actor,
                  static_cast<std::uint16_t>(yaw),static_cast<std::uint16_t>(pitch),
                  ram.u32(camera+game_member("layout.camera.x")),ram.u32(camera+game_member("layout.camera.y")),ram.u32(camera+game_member("layout.camera.z"))});
              }
            }
            state.gameplay_trace.event("pc-camera-context",{state.vi_retraces,actor,
              ram.u8(control+game_member("layout.playerControl.movement")),ram.u16(actor+game_member("layout.actor.type")),ram.u32(control+game_member("layout.playerControl.forwardVelocity")),
              ram.u32(control+game_member("layout.playerControl.verticalVelocity")),ram.u32(control+game_member("layout.playerControl.sideVelocity"))});
            state.pc_camera_actor=state.pc_camera_control=state.pc_camera_stack=0;state.pc_camera_look={};
            return 1;
          }
        } else {
          state.pc_orbits[port].active=false;
          if(shoulder && !normal_view && state.pc_shoulders[port].aiming)
            state.pc_shoulders[port].aim_return.observe_aim();
        }
      }
    }
  }
  if(target==game_code("game.controlUpdatePlayerAim") && modern_air_aim_active(state,static_cast<std::uint32_t>(context->r4),static_cast<std::uint32_t>(context->r5))) {
    NativeGameMemory ram({rdram,kRdramSize});
    const auto control=static_cast<std::uint32_t>(context->r5);
    // Match the character dispatcher's aimed targeting policy: keep recoil
    // countdown, but do not replace the player's aim with a hip-fire target.
    const int ticks=static_cast<int>(ram.u32(static_cast<std::uint32_t>(context->r29)+0x1CU));
    const auto counter=ram.u8(control+game_member("layout.playerControl.viewImpulseTimer"));
    if(ram.u8(control+game_member("layout.playerControl.viewImpulseActive")))
      ram.put16(control+game_member("layout.playerControl.viewImpulseTimer"),static_cast<std::uint16_t>((std::max(0,int(counter)-ticks)<<8U)|ram.u8(control+game_member("layout.playerControl.actionLock"))));
    ram.put16(control+game_member("layout.playerControl.viewImpulseActive"),static_cast<std::uint16_t>(0x100U|ram.u8(control+game_member("layout.playerControl.viewImpulseActive")+1U)));
    return 1;
  }
  // Modern Jump is a locomotion action even while Aim is held. Reuse the
  // character's complete native ground jump handler (animation, collision
  // eligibility, takeoff and weapon logic); never synthesize vertical velocity.
  // Its ABI matches the aim handler's actor/control/movement/heading/ticks.
  const std::uint32_t aim_jump_ground=
    (target==game_overlay_token("overlay.vela.motion_callback") || target==game_overlay_token("overlay.vela.aim"))?game_overlay_token("overlay.vela.movement_handler"):
    (target==game_overlay_token("overlay.juno.motion_callback") || target==game_overlay_token("overlay.juno.aim"))?game_overlay_token("overlay.juno.movement_handler"):
    (target==game_overlay_token("overlay.lupus.motion_callback") || target==game_overlay_token("overlay.lupus.aim"))?game_overlay_token("overlay.lupus.movement_handler"):0U;
  if(aim_jump_ground && state.modern_controls_active && !state.pc_input_blocked) {
    NativeGameMemory ram({rdram,kRdramSize});
    const auto actor=static_cast<std::uint32_t>(context->r4),control=static_cast<std::uint32_t>(context->r5);
    if(ram.valid(actor,0xA4U) && ram.valid(control,0x5D0U) && ram.u32(actor+game_member("layout.actor.control"))==control) {
      const auto port=jfg::mod::pc_input_port(ram,ram.u8(control));
      const auto movement=ram.u8(control+game_member("layout.playerControl.movement"));
      const auto table=game_view(ram).u32(game_data_ref("globals.controlModeTable"));
      if(modern_shoulder_current(state,port,actor) &&
         (movement==10U || movement==11U) && ram.u8(control+game_member("layout.playerControl.animationLock"))==0 &&
         (game_view(ram).u32(game_data_ref("globals.controlPressedButtons"))&8U) && ram.valid(table,0x24U) && ram.u32(table+0xCU)==8U &&
         !jfg::mod::scripted_camera_active(ram,actor)) {
        if(auto* ground=jfg_generated_lookup_function(static_cast<std::int32_t>(aim_jump_ground))) {
          hle::GuestMemory memory({rdram,kRdramSize},hle::GuestMemory::Layout::native_word_big_endian);
          const auto held=game_view(ram).u32(game_data_ref("globals.controlButtons"));
          // Ground's Aim-first branch otherwise prevents its native Jump test.
          // Mask only that branch for this action dispatch; retain the user's
          // held/toggled Aim intent so ordinary landing re-enters aiming.
          (void)memory.write_u32(game_data("globals.controlButtons"),held&~0x10U);
          ram.put16(control+game_member("layout.playerControl.movement"),ram.u8(control+game_member("layout.playerControl.direction")));
          ground(rdram,context);
          (void)memory.write_u32(game_data("globals.controlButtons"),held);
          const auto after=ram.u8(control+game_member("layout.playerControl.movement"));
          if(after==0U)ram.put16(control+game_member("layout.playerControl.movement"),static_cast<std::uint16_t>((movement<<8U)|ram.u8(control+game_member("layout.playerControl.direction"))));
          state.gameplay_trace.event("modern-aim-jump",{state.vi_retraces,actor,movement,after,held});
          return 1;
        }
      }
    }
  }
  // Mission steering is consumed inside sidekickControl before its reticle
  // routine. Admit only its two original input-read return sites, after the
  // native button mapping, so ordinary player/controller/co-op input is intact.
  if(target==game_code("game.controlReadJoypad") && state.modern_controls_active && !state.pc_input_blocked &&
     (state.play_mode || state.input_replay_loaded) &&
     (state.input_record_path.empty() || state.pc_record_extended) &&
     (static_cast<std::uint32_t>(context->r31)==game_instruction("native.sidekick_coop_return") ||
      static_cast<std::uint32_t>(context->r31)==game_instruction("native.sidekick_owner_return"))) {
    NativeGameMemory ram({rdram,kRdramSize});
    const auto floyd=jfg::mod::pc_floyd_context(ram);
    if(floyd && floyd.mission && modern_controls_selected(state,floyd.port) &&
       state.controller_ports.samples[floyd.port].connected) {
      const auto port=floyd.port;const auto& frame=state.pc_frames[port];
      if(frame.pc_mode==3 && (frame.modern_flags&jfg::kModernActionsFlag)) {
        if(auto* original=jfg_generated_lookup_function(static_cast<std::int32_t>(target))) {
          original(rdram,context);
          auto look=jfg::PcLookDelta{frame.look_x,frame.look_y};
          if(state.pc_mouse_used[port])look={};
          state.pc_mouse_used[port]=true;
          const auto heading=jfg::pc_floyd_mouse_flight(look,
            ram.s16(floyd.control+game_member("layout.sidekickControl.headingYaw")),ram.s16(floyd.control+game_member("layout.sidekickControl.headingPitch")));
          ram.put16(floyd.control+game_member("layout.sidekickControl.headingYaw"),static_cast<std::uint16_t>(heading.x));
          ram.put16(floyd.control+game_member("layout.sidekickControl.headingPitch"),static_cast<std::uint16_t>(heading.y));
          ram.put16(floyd.control+game_member("layout.sidekickControl.turnYaw"),0);ram.put16(floyd.control+game_member("layout.sidekickControl.turnPitch"),0);
          hle::GuestMemory memory({rdram,kRdramSize},hle::GuestMemory::Layout::native_word_big_endian);
          (void)memory.write_u32(game_data("globals.controlAbsoluteStickX"),0);(void)memory.write_u32(game_data("globals.controlAbsoluteStickY"),0);
          state.gameplay_trace.event("modern-floyd-flight",{state.vi_retraces,port,floyd.actor,
            static_cast<std::uint32_t>(look.x),static_cast<std::uint32_t>(look.y),
            static_cast<std::uint32_t>(heading.x),static_cast<std::uint32_t>(heading.y)});
          return 1;
        }
      }
    }
  }
  // Insert side thrust before native velocity integration and scenery collision.
  // This call site rotates only forward thrust; its saved magnitude controls
  // whether sidekickControl accelerates or coasts, including A/D without W.
  if(target==game_code("game.mathOneFloatPY") && state.modern_controls_active && !state.pc_input_blocked &&
     (state.play_mode || state.input_replay_loaded) &&
     (state.input_record_path.empty() || state.pc_record_extended) &&
     static_cast<std::uint32_t>(context->r31)==game_instruction("native.sidekick_flight_return")) {
    NativeGameMemory ram({rdram,kRdramSize});
    const auto floyd=jfg::mod::pc_floyd_context(ram);
    const auto stack=static_cast<std::uint32_t>(context->r29);
    const auto vector=static_cast<std::uint32_t>(context->r5);
    if(floyd && floyd.mission && modern_controls_selected(state,floyd.port) &&
       state.controller_ports.samples[floyd.port].connected &&
       static_cast<std::uint32_t>(context->r4)==floyd.control+game_member("layout.sidekickControl.headingYaw") &&
       ram.valid(stack,0x128U) && vector==stack+0xC8U) {
      const auto& frame=state.pc_frames[floyd.port];
      const int sideways=state.controller_ports.samples[floyd.port].x;
      if(frame.pc_mode==3 && (frame.modern_flags&jfg::kModernActionsFlag) && sideways) {
        if(auto* original=jfg_generated_lookup_function(static_cast<std::int32_t>(target))) {
          original(rdram,context);
          const auto thrust=jfg::pc_floyd_mouse_strafe(
            {ram.f32(vector),ram.f32(vector+4U),ram.f32(vector+8U)},
            ram.s16(floyd.control+game_member("layout.sidekickControl.headingYaw")),sideways,static_cast<float>(ram.u32(stack+0x124U)));
          hle::GuestMemory memory({rdram,kRdramSize},hle::GuestMemory::Layout::native_word_big_endian);
          (void)memory.write_u32(vector,std::bit_cast<std::uint32_t>(thrust.x));
          (void)memory.write_u32(vector+4U,std::bit_cast<std::uint32_t>(thrust.y));
          (void)memory.write_u32(vector+8U,std::bit_cast<std::uint32_t>(thrust.z));
          (void)memory.write_u32(stack+0xA8U,std::bit_cast<std::uint32_t>(std::hypot(thrust.x,thrust.y,thrust.z)));
          state.gameplay_trace.event("modern-floyd-strafe",{state.vi_retraces,floyd.port,floyd.actor,
            static_cast<std::uint32_t>(sideways),std::bit_cast<std::uint32_t>(thrust.x),
            std::bit_cast<std::uint32_t>(thrust.y),std::bit_cast<std::uint32_t>(thrust.z)});
          return 1;
        }
      }
    }
  }
  if(target==game_code("game.controlUpdateFloyd") && state.modern_controls_active && !state.pc_input_blocked &&
     (state.play_mode || state.input_replay_loaded) && (state.input_record_path.empty() || state.pc_record_extended)) {
    NativeGameMemory ram({rdram,kRdramSize});
    const auto floyd=jfg::mod::pc_floyd_context(ram);
    if(floyd && floyd.actor==static_cast<std::uint32_t>(context->r4) &&
       floyd.control==static_cast<std::uint32_t>(context->r5) && modern_controls_selected(state,floyd.port) &&
       state.controller_ports.samples[floyd.port].connected && ram.instruction_matches("guard.game.controlUpdateFloyd.entry0")) {
      const auto port=floyd.port;const auto& frame=state.pc_frames[port];
      if((frame.modern_flags&jfg::kModernActionsFlag) && (frame.pc_mode==3 || frame.pc_mode==5)) {
        if(auto* original=jfg_generated_lookup_function(static_cast<std::int32_t>(target))) {
          const bool mouse=frame.pc_mode==3;
          auto look=jfg::PcLookDelta{frame.look_x,frame.look_y};
          if(mouse && state.pc_mouse_used[port])look={};
          if(mouse)state.pc_mouse_used[port]=true;
          jfg::PcLookDelta aim{};
          if(mouse && floyd.mission) {
            // Flight direction owns mouse aim in missions. Remove the old
            // co-op reticle offset immediately when changing modes.
            state.pc_floyd_look[port].clear();
            ram.put16(floyd.control+game_member("layout.sidekickControl.aimX"),0);ram.put16(floyd.control+game_member("layout.sidekickControl.aimX")+2U,0);
            ram.put16(floyd.control+game_member("layout.sidekickControl.aimY"),0);ram.put16(floyd.control+game_member("layout.sidekickControl.aimY")+2U,0);
          } else aim=state.pc_floyd_look[port].take(look,mouse,
            (std::uint64_t{floyd.actor}<<8U)|frame.pc_mode|(std::uint64_t{floyd.mission}<<7U),
            std::bit_cast<float>(ram.u32(floyd.control+game_member("layout.sidekickControl.aimX"))),std::bit_cast<float>(ram.u32(floyd.control+game_member("layout.sidekickControl.aimY"))));
          hle::GuestMemory memory({rdram,kRdramSize},hle::GuestMemory::Layout::native_word_big_endian);
          const auto x=game_view(ram).u32(game_data_ref("globals.controlAbsoluteStickX")),y=game_view(ram).u32(game_data_ref("globals.controlAbsoluteStickY"));
          (void)memory.write_u32(game_data("globals.controlAbsoluteStickX"),static_cast<std::uint32_t>(aim.x));
          (void)memory.write_u32(game_data("globals.controlAbsoluteStickY"),static_cast<std::uint32_t>(aim.y));
          state.gameplay_trace.event("modern-floyd-input",{state.vi_retraces,port,floyd.actor,floyd.mission?1U:0U,
            game_view(ram).u32(game_data_ref("globals.controlButtons")),game_view(ram).u32(game_data_ref("globals.controlPressedButtons")),static_cast<std::uint32_t>(aim.x),static_cast<std::uint32_t>(aim.y)});
          original(rdram,context);
          (void)memory.write_u32(game_data("globals.controlAbsoluteStickX"),x);(void)memory.write_u32(game_data("globals.controlAbsoluteStickY"),y);
          return 1;
        }
      }
    }
  }
  // Separate look input is recorded alongside movement; older replays remain stock.
  if(target==game_code("game.controlGetManualAim") && state.modern_controls_active && (state.play_mode || state.input_replay_loaded) &&
     (state.input_record_path.empty() || state.pc_record_extended) && !state.pc_input_blocked) {
    NativeGameMemory pc_memory({rdram,kRdramSize});
    const auto actor=static_cast<std::uint32_t>(context->r4);
    const auto control=static_cast<std::uint32_t>(context->r5);
    if(pc_memory.valid(control,0x5C4U) && pc_memory.valid(actor,0xA4U) &&
       pc_memory.u32(actor+game_member("layout.actor.control"))==control && pc_memory.instruction_matches("guard.game.controlGetManualAim.entry0") &&
       pc_memory.instruction_matches("guard.game.controlGetManualAim.entry4") &&
       jfg::mod::pc_actions_active(pc_memory,actor) && game_view(pc_memory).u8(game_data_ref("globals.pauseActive"))==0 && !jfg::mod::scripted_camera_active(pc_memory,actor)) {
      const auto port=jfg::mod::pc_input_port(pc_memory,pc_memory.u8(control));
      if(port<4U && state.controller_ports.samples[port].connected) {
        const auto &frame=state.pc_frames[port];
        const bool mouse=frame.pc_mode==1 || frame.pc_mode==3;
        const bool direct=frame.pc_mode==3 || frame.pc_mode==4 || frame.pc_mode==5;
        if(frame.pc_mode==0)state.pc_boss_aim_motion[port].clear();
        if(frame.pc_mode!=0) {
          auto look=jfg::PcLookDelta{frame.look_x,frame.look_y};
          if(mouse && state.pc_mouse_used[port])look={};
          if(mouse)state.pc_mouse_used[port]=true;
          const auto stack=static_cast<std::uint32_t>(context->r29);
          const bool valid_limits=pc_memory.valid(stack,0x24U);
          const float ticks=valid_limits?std::bit_cast<float>(pc_memory.u32(stack+0x20U)):0.0F;
          if(frame.pc_mode==5)look=state.pc_stick_motion[port].take(look,ticks,actor|1U);
          else if(frame.pc_mode==4)look=jfg::pc_camera_delta(frame.pc_mode,look,ticks);
          const int minimum=valid_limits?static_cast<std::int32_t>(pc_memory.u32(stack+0x10U)):0;
          const int maximum=valid_limits?static_cast<std::int32_t>(pc_memory.u32(stack+0x14U)):0;
          const auto before=jfg::PcLookDelta{pc_memory.s16(control+game_member("layout.playerControl.heading")),pc_memory.s16(control+game_member("layout.playerControl.manualPitch"))};
          // All three character boss handlers save their nominal facing here
          // before substituting the body yaw for the common aiming helper.
          // Qualify the caller ABI as well as combat state before using it.
          const auto caller=static_cast<std::uint32_t>(context->r31);
          const auto boss=pc_memory.u32(control+game_member("layout.playerControl.boss"));
          const auto boss_state=pc_memory.u8(control+game_member("layout.playerControl.movement"));
          const auto yaw_output=valid_limits?pc_memory.u32(stack+0x18U):0U;
          const auto pitch_output=valid_limits?pc_memory.u32(stack+0x1CU):0U;
          const bool boss_aim=direct && (boss_state==32U || boss_state==35U) &&
            pc_memory.valid(boss,0xA4U) && pc_memory.valid(stack,0x5CU) &&
            context->r6==0xE38U && context->r7==0xE38U &&
            minimum==-0x2AAA && maximum==0x2AAA &&
            yaw_output==stack+0x56U && pitch_output==stack+0x54U &&
            pc_memory.u32(stack+0x58U)<=0xFFFFU;
          if((boss_state==32U || boss_state==35U) && state.pc_aim_calls%120U==0U)
            state.gameplay_trace.event("pc-boss-contract",{state.vi_retraces,port,
              boss_state,boss,caller,stack,static_cast<std::uint32_t>(context->r6),
              static_cast<std::uint32_t>(context->r7),static_cast<std::uint32_t>(minimum),
              static_cast<std::uint32_t>(maximum),yaw_output,pitch_output,
              pc_memory.valid(caller-4U,8U)?pc_memory.u32(caller-4U):UINT32_MAX,
              pc_memory.valid(caller,4U)?pc_memory.u32(caller):UINT32_MAX,
              static_cast<unsigned>(boss_aim)});
          const int boss_center=boss_aim?pc_memory.u16(stack+0x5AU):0;
          const auto boss_initial=jfg::PcLookDelta{
            pc_memory.s16(control+game_member("layout.playerControl.aimRoll")),pc_memory.s16(control+game_member("layout.playerControl.weaponYaw"))};
          if(!boss_aim || state.pc_boss_aim_modes[port]!=frame.pc_mode ||
             state.pc_boss_aim_controls[port]!=control)
            state.pc_boss_aim_motion[port].clear();
          state.pc_boss_aim_modes[port]=frame.pc_mode;
          state.pc_boss_aim_controls[port]=control;
          hle::GuestMemory memory({rdram,kRdramSize},hle::GuestMemory::Layout::native_word_big_endian);
          std::uint32_t x=0,y=0;
          if(memory.read_u32(game_data("globals.controlAbsoluteStickX"),x) && memory.read_u32(game_data("globals.controlAbsoluteStickY"),y)) {
            auto* original=jfg_generated_lookup_function(static_cast<std::int32_t>(target));
            if(original) {
              (void)memory.write_u32(game_data("globals.controlAbsoluteStickX"),direct?0U:static_cast<std::uint32_t>(look.x));
              (void)memory.write_u32(game_data("globals.controlAbsoluteStickY"),direct?0U:static_cast<std::uint32_t>(look.y));
              const auto modern_character=pc_memory.u8(control+game_member("layout.playerControl.characterFlags"))&3U;
              const bool modern_scope=(frame.modern_flags&jfg::kModernActionsFlag) &&
                modern_character<3U && jfg::mod::pc_player_weapon(pc_memory,control)==7U &&
                pc_memory.u8(control+game_member("layout.playerControl.aimInhibited"))==0;
              std::uint32_t held=0;
              if(modern_scope && memory.read_u32(game_data("globals.controlButtons"),held)) {
                (void)memory.write_u32(game_data("globals.controlButtons"),held&~0xCU);
                (void)memory.write_u32(control+game_member("layout.playerControl.cameraSpring"),0);
                const auto before_zoom=std::bit_cast<float>(pc_memory.u32(control+game_member("layout.playerControl.zoom")));
                const auto after_zoom=state.modern_scope_zoom[port].take(before_zoom);
                if(after_zoom!=before_zoom && std::isfinite(after_zoom)) {
                  (void)memory.write_u32(control+game_member("layout.playerControl.zoom"),std::bit_cast<std::uint32_t>(after_zoom));
                  state.gameplay_trace.event("modern-scope",{state.vi_retraces,port,
                    std::bit_cast<std::uint32_t>(before_zoom),std::bit_cast<std::uint32_t>(after_zoom)});
                }
              }
              original(rdram,context);
              if(modern_scope)(void)memory.write_u32(game_data("globals.controlButtons"),held);
              (void)memory.write_u32(game_data("globals.controlAbsoluteStickX"),x);(void)memory.write_u32(game_data("globals.controlAbsoluteStickY"),y);
              ++state.pc_aim_calls;
              if(direct && valid_limits && minimum>=-32768 && maximum<=32767 && minimum<=maximum) {
                const auto raw_look=look;
                float zoom=1.0F;
                const auto character=pc_memory.u8(control+game_member("layout.playerControl.characterFlags"))&3U;
                if(character<3U && jfg::mod::pc_player_weapon(pc_memory,control)==7U)
                  zoom=std::bit_cast<float>(pc_memory.u32(control+game_member("layout.playerControl.zoom")));
                look=state.pc_scope_motion[port].take(look,zoom,(std::uint64_t{actor}<<8U)|frame.pc_mode);
                if(zoom>1.0F && zoom<=5.0F)
                  state.gameplay_trace.event("pc-scope",{state.vi_retraces,port,
                    std::bit_cast<std::uint32_t>(zoom),static_cast<std::uint32_t>(raw_look.x),
                    static_cast<std::uint32_t>(raw_look.y),static_cast<std::uint32_t>(look.x),static_cast<std::uint32_t>(look.y)});
                // The guest aim pitch is positive up; the normal camera's
                // world pitch is positive down. Keep one mouse convention.
                const auto aim_look=jfg::pc_guest_aim_look(look,
                    (frame.modern_flags&jfg::kModernActionsFlag)!=0);
                auto after=jfg::pc_direct_aim(before.x,before.y,aim_look,minimum,maximum);
                if(boss_aim) {
                  const int extra=jfg::pc_boss_aim_limit(0xE38,zoom);
                  const auto combined=state.pc_boss_aim_motion[port].take(
                    before,boss_center,aim_look,minimum,maximum,{extra,extra},
                    (std::uint64_t{actor}<<32U)|boss,boss_initial);
                  after=combined.body;
                  pc_memory.put16(yaw_output,static_cast<std::uint16_t>(combined.offset.x));
                  pc_memory.put16(pitch_output,static_cast<std::uint16_t>(combined.offset.y));
                  state.gameplay_trace.event("pc-boss-aim",{state.vi_retraces,port,
                    frame.pc_mode,actor,boss,caller,static_cast<std::uint32_t>(boss_center),
                    static_cast<std::uint32_t>(after.x),static_cast<std::uint32_t>(after.y),
                    static_cast<std::uint32_t>(combined.offset.x),
                    static_cast<std::uint32_t>(combined.offset.y),static_cast<std::uint32_t>(extra)});
                }
                pc_memory.put16(control+game_member("layout.playerControl.heading"),static_cast<std::uint16_t>(after.x));
                pc_memory.put16(control+game_member("layout.playerControl.manualPitch"),static_cast<std::uint16_t>(after.y));
                if(modern_shoulder_current(state,port,actor)) {
                  state.pc_shoulders[port].yaw=after.x;state.pc_shoulders[port].pitch=-after.y;
                }
                (void)memory.write_u32(control+game_member("layout.playerControl.cameraDistance"),0);(void)memory.write_u32(control+game_member("layout.playerControl.camera"),0);
                ++state.pc_direct_aim_calls;
              }
              // Ground aiming otherwise ignores the movement stick. The guest
              // consumes these local velocities in its ordinary physics/collision
              // path. Leave jumps, swimming, damage and scripted states alone.
              const auto movement_state=pc_memory.u8(control+game_member("layout.playerControl.movement"));
              if((frame.pc_mode==3 || frame.pc_mode==4 || frame.pc_mode==5) && (movement_state==10 || movement_state==11) && (pc_memory.u8(control+game_member("layout.playerControl.characterFlags"))&3U)<3U) {
                const auto &move=state.controller_ports.samples[port];
                const auto velocity=jfg::pc_aim_movement(move.x,move.y,movement_state==11U);
                (void)memory.write_u32(control+game_member("layout.playerControl.sideVelocity"),std::bit_cast<std::uint32_t>(velocity.side));
                (void)memory.write_u32(control+game_member("layout.playerControl.forwardVelocity"),std::bit_cast<std::uint32_t>(velocity.forward));
              }
              state.gameplay_trace.event("pc-aim",{state.vi_retraces,state.controller_samples,port,frame.pc_mode,
                static_cast<std::uint32_t>(look.x),static_cast<std::uint32_t>(look.y),
                pc_memory.u16(control+game_member("layout.playerControl.heading")),pc_memory.u16(control+game_member("layout.playerControl.manualPitch")),movement_state,
                pc_memory.u32(control+game_member("layout.playerControl.forwardVelocity")),pc_memory.u32(control+game_member("layout.playerControl.sideVelocity"))});
              return 1;
            }
          }
        }
      }
    }
  }
  // mainChangeLevel is the explicit lifetime boundary, including transitions
  // which recycle the same player/control addresses. Never carry the outgoing
  // shoulder heading into a new native entrance sequence.
  if(target==game_code("game.mainChangeLevel") && state.modern_controls_active) {
    state.pc_shoulders.fill({});state.pc_orbits.fill({});
    for(auto &motion:state.pc_floyd_look)motion.clear();
    for(auto &motion:state.pc_boss_aim_motion)motion.clear();
    state.gameplay_trace.event("pc-view-area-reset",{state.vi_retraces,
      static_cast<std::uint32_t>(context->r4),static_cast<std::uint32_t>(context->r5)});
  }
  if (state.navigation_mod.observing()) {
    NativeGameMemory memory({rdram,kRdramSize});
    if (target==game_code("game.mainChangeLevel")) {
      state.navigation_mod.transition();
      // Invalidate the old map before the game starts loading another room.
      std::ostringstream output;
      state.navigation_mod.write_state(output,memory,{},UINT32_MAX,false);
      if(!write_mod_export(state, state.navigation_output/L"live.json",output.str()))
        ++state.navigation_mod.invalid;
    }
    if (target==game_code("game.controlPlayer")) {
      if(state.navigation_mod.has_exit_warp_selection()) {
        try {
          const auto now=std::chrono::duration_cast<std::chrono::milliseconds>(
              std::chrono::system_clock::now().time_since_epoch()).count();
          std::uint32_t replaced=0;
          if(state.navigation_mod.apply_exit_warp_selection(memory,jfg::mod::actors(memory),
                static_cast<std::uint32_t>(context->r4),now,replaced))
            state.gameplay_trace.event("exit-warp-consume",{state.vi_retraces,
                state.navigation_mod.generation,state.navigation_mod.warp_nonce,
                replaced,memory.u32(memory.u32(state.navigation_mod.player+game_member("layout.actor.control"))+0xF4U)});
        } catch(const std::runtime_error &) { ++state.navigation_mod.invalid; }
      }
      (void)state.navigation_mod.observe_player(memory,static_cast<std::uint32_t>(context->r4));
      (void)state.navigation_mod.full_health(memory,static_cast<std::uint32_t>(context->r4));
    }
    if (target==game_overlay_token("overlay.collision.squaddie_control"))
      (void)state.navigation_mod.clear_enemy(memory,static_cast<std::uint32_t>(context->r4));
  }
#endif
#if defined(JFG_PHASE8_LIVE_RUNTIME)
  if (target == game_code("game.scHandleRetrace") || target == game_code("game.amHandleFrameMsg") || target == game_code("game.amAudioMgrGetNextFrameCount") || target == game_code("game.n_alAudioFrame")) {
    static const bool audio_scheduler_trace = [] {
      char value[2]{};
      return GetEnvironmentVariableA("JFG_DIAGNOSTIC_AUDIO_SCHEDULER", value, 2U)==1U && value[0]=='1';
    }();
    if (audio_scheduler_trace && state.gameplay_trace && state.mmio_trace) {
      hle::GuestMemory m({state.rdram,kRdramSize},hle::GuestMemory::Layout::native_word_big_endian);
      std::uint32_t countdown=0,frames=0,maximum=0,minimum=0,queued=0,mode=0;
      if(m.read_u32(game_data("globals.nextFrameCountdown"),countdown) && m.read_u32(game_data("audio.frame_count"),frames) &&
         m.read_u32(game_data("globals.audioMaximumFrames"),maximum) && m.read_u32(game_data("globals.audioMinimumFrames"),minimum)) {
        (void)m.read_u32((game_data("audio.frame_queue")+8U),queued);(void)m.read_u32(game_data("globals.audioQueueMode"),mode);
        state.gameplay_trace.event("audio-scheduler",{
          state.vi_retraces,state.controller_samples,target,state.cpu_count,
          state.mmio_trace->ai_dma.read(4U,state.cpu_count).value_or(UINT32_MAX),
          state.mmio_trace->ai_dma.deadline().value_or(0U),countdown>>24U,frames,maximum,minimum,
          state.host_audio.queued_bytes(),state.host_audio.consumed_bytes(),
          static_cast<std::uint32_t>(context->r7),queued,mode,
          0U,state.guest_active_rsp_type});
      }
    }
  }
  if(state.diagnostic_host_clock && state.native_audio_playback) {
    // Run a completed audio command list as soon as its RSP slot is free.
    // Waiting for the next notification retrace can strand the audio thread.
    if(target==game_code("game.scSchedule") && (static_cast<std::uint32_t>(context->r7)&2U)) {
      hle::GuestMemory m({state.rdram,kRdramSize},hle::GuestMemory::Layout::native_word_big_endian);
      const auto scheduler=static_cast<std::uint32_t>(context->r4);
      std::uint32_t expected=0,head=0,active=0,kind=0,mode=0,frames=0;
      if(m.read_u32(game_data("globals.audioScheduler"),expected) && scheduler==expected &&
          m.read_u32(scheduler+0x2E4U,head) && head &&
          m.read_u32(scheduler+0x304U,active) && active==0U &&
          m.read_u32(head+0x10U,kind) && kind==2U &&
          m.read_u32(game_data("globals.audioQueueMode"),mode) && mode==0U &&
          m.read_u32(game_data("audio.frame_count"),frames) && frames==2U) {
        if(!m.write_u32(scheduler+0x304U,1U))
          fail_closed_dispatch(state,"audio","ready-task-state",target);
        if(state.gameplay_trace)state.gameplay_trace.event("audio-ready-task",{
            state.vi_retraces,state.cpu_count,scheduler,head,state.host_audio.queued_bytes(),
            state.host_audio.consumed_bytes()});
      }
    }
    if(target==game_code("game.scHandleRetrace") && state.host_audio.started()) {
      hle::GuestMemory m({state.rdram,kRdramSize},hle::GuestMemory::Layout::native_word_big_endian);
      std::uint32_t countdown=0,frames=0,mode=0,queued=0;
      const auto buffered=state.host_audio.buffered_bytes();
      if(m.read_u32(game_data("globals.nextFrameCountdown"),countdown) && m.read_u32(game_data("audio.frame_count"),frames) &&
          m.read_u32(game_data("globals.audioQueueMode"),mode) && m.read_u32((game_data("audio.frame_queue")+8U),queued)) {
        const auto adjusted=native_audio_countdown(countdown,frames,mode,queued,
            state.mmio_trace->ai_dma.read(12U,state.cpu_count).value_or(UINT32_MAX),
            state.host_audio.frequency(),buffered);
        if(adjusted) {
          if(!m.write_u32(game_data("globals.nextFrameCountdown"),*adjusted))
            fail_closed_dispatch(state,"audio","demand-countdown",target);
          if(state.gameplay_trace)state.gameplay_trace.event("audio-demand",{
              state.vi_retraces,state.cpu_count,buffered,
              native_audio_target_bytes(state.host_audio.frequency())});
        }
      }
    }
  }
  // Private fixture travel request; let mainChangeLevel prepare all globals.
  if (target == game_code("game.mainChangeLevel") && state.timing_fixture) {
    if (state.timing_trace)
      state.timing_trace << "travel-request\t" << state.vi_frames << '\t'
          << context->r4 << '\t' << context->r5 << '\t'
          << context->r6 << '\t' << context->r7 << '\t' << context->r31 << '\n';
    if (context->r4 == 127U || context->r4 == 214U) context->r5 = 2U;
    if (context->r4 == 214U) {
      char value[16]{};
      const auto length = GetEnvironmentVariableA("QUARRY_FIXTURE_DESTINATION", value, 16U);
      const auto destination = length > 0U && length < 16U ? std::stoul(value) : 294U;
      if (destination != 294U && destination != 272U && destination != 283U && destination != 354U && destination != 411U && destination != 357U)
        fail_closed_dispatch(state, "diagnostic", "fixture-destination", target);
      context->r4 = destination;
      char group[16]{};
      const auto group_length = GetEnvironmentVariableA("QUARRY_FIXTURE_GROUP", group, 16U);
      if (group_length > 0U && group_length < 16U) context->r7 = std::stoul(group);


      if (state.timing_trace)
        state.timing_trace << "travel-fixture\t" << state.vi_frames << '\t'
            << destination << '\t' << context->r5 << '\t' << context->r6 << '\t'
            << context->r7 << '\n';
    }
  }
  switch (target) {
  case game_overlay_token("overlay.mrhints.control"): // overlay 32: mrhintsControl / KingBear
    note_hints_control_call(state, target, *context);
    break;
  case game_overlay_token("overlay.mrhints.talk"): // overlay 32: mrHintsTalk
    ++state.phase9_hints_talk_calls;
    break;
  case game_overlay_token("overlay.hint.start"): // overlay 7: hinttextStart
    ++state.phase9_hinttext_start_calls;
    break;
  case game_overlay_token("overlay.hint.stop"): // overlay 7: hinttextStop
    ++state.phase9_hinttext_stop_calls;
    break;
  case game_overlay_token("overlay.hint.advance"): // overlay 7: advance queued hint page
    ++state.phase9_hinttext_advance_calls;
    break;
  case game_overlay_token("overlay.hint.active"): // overlay 7: hinttextActive
    ++state.phase9_hinttext_active_calls;
    break;
  case game_overlay_token("overlay.hint.update"): // overlay 7: hinttextUpdate
    ++state.phase9_hinttext_update_calls;
    break;
  case game_overlay_token("overlay.hint.accept"): // overlay 7: accept/parse current hint page
    ++state.phase9_hinttext_accept_calls;
    break;
  case game_code("game.rumbleStart"): // rumbleStart
  case game_code("game.rumbleStop"): // rumbleStop
  case game_code("game.rumbleAlter"): // rumbleAlter
  case game_code("game.rumbleMax"): { // rumbleMax
    NativeGameMemory ram({rdram,kRdramSize});
    const auto player=static_cast<std::uint32_t>(context->r4);
    state.gameplay_trace.event("pc-rumble-request",{
      state.vi_retraces,target,player,static_cast<std::uint32_t>(context->r5),
      static_cast<std::uint32_t>(context->r6),game_view(ram).u8(game_data_ref("globals.rumbleEnabled")),
      game_view(ram).u8(game_data_ref("globals.pauseActive")),player<4U?ram.u8(game_data("globals.playerPorts")+player):255U});
    request_pc_rumble(state,target,*context);
    break;
  }
  case game_code("game.controlPlayer"): // controlPlayer
    ++state.phase9_player_control_calls;
    state.phase9_player_actor = static_cast<std::uint32_t>(context->r4);
    break;
  case game_code("game.controlUpdateWeapon"): { // controlUpdateWeapon
    ++state.phase9_weapon_update_calls;
    hle::GuestMemory memory(
        {rdram, kRdramSize},
        hle::GuestMemory::Layout::native_word_big_endian);
    std::uint32_t held = 0U;
    std::uint32_t pressed = 0U;
    if (memory.read_u32(game_data("globals.controlButtons"), held) && (held & 0x2000U) != 0U)
      ++state.phase9_weapon_fire_held_updates;
    if (memory.read_u32(game_data("globals.controlPressedButtons"), pressed) && (pressed & 0x2000U) != 0U)
      ++state.phase9_weapon_fire_pressed_updates;
    break;
  }
  case game_code("game.controlFireWeapon"): // func_80038488 (shooting_func)
    ++state.phase9_weapon_fire_calls;
    break;
  case game_code("game.controlFireDummyShot"): // controlFireDummyShot
    ++state.phase9_weapon_dummy_fire_calls;
    break;
  case game_code("game.mainIncreaseWeaponShots"): // mainIncreaseWeaponShots
    ++state.phase9_weapon_shot_calls;
    break;
  case game_code("game.mainIncreaseWeaponHits"): // mainIncreaseWeaponHits
    ++state.phase9_weapon_hit_calls;
    break;
  case game_code("game.mainIncreaseWeaponKills"): // mainIncreaseWeaponKills
    ++state.phase9_enemy_kill_calls;
    break;
  case game_code("game.trackGetPlayerIntersect"): // trackGetPlayerIntersect
  case game_code("game.controlGroundHits"): // controlGroundHits
    ++state.phase9_collision_calls;
    break;
  case game_code("game.partUpdateParticles"): // partUpdateParticles
    ++state.phase9_particle_update_calls;
    break;
  case game_code("game.mainChangeLevel"): // mainChangeLevel
    ++state.phase9_level_change_calls;
    if(state.gameplay_trace)state.gameplay_trace.event("route-transition", {
      state.vi_retraces,state.controller_samples,target,
      static_cast<std::uint32_t>(context->r4),static_cast<std::uint32_t>(context->r5),
      state.phase9_level_change_calls});
    break;
  case game_code("game.mainRestartAfterDeath"): // mainRestartAfterDeath
    ++state.phase9_death_restart_calls;
    if(state.gameplay_trace)state.gameplay_trace.event("route-transition", {
      state.vi_retraces,state.controller_samples,target,
      static_cast<std::uint32_t>(context->r4),static_cast<std::uint32_t>(context->r5),
      state.phase9_death_restart_calls});
    break;
  case game_code("game.animseqCamera"): // animseqCamera
    ++state.phase9_cutscene_camera_calls;
    break;
  case game_code("game.hitPlayer"): // hitPlayer
    ++state.phase9_player_hit_check_calls;
    break;
  default:
    break;
  }
#endif
#if !defined(JFG_PHASE8_LIVE_RUNTIME)
  state.journal.append(NativeEventKind::kDispatch, target);
#endif
  if (!state.guest_os_probe) {
    state.cpu_count += kCountTicksPerDispatch;
    service_si_deadline(state, target);
    service_timers(state, target);
  }
  state.recent_dispatches[state.recent_dispatch_position %
                          state.recent_dispatches.size()] = target;
  ++state.recent_dispatch_position;
#if defined(_WIN32) && defined(JFG_PHASE8_LIVE_RUNTIME)
  if (state.vi_retraces >= 5683U && state.dispatch_calls % 1024U == 0U)
    write_private_progress(state, "dispatch");
#endif

#if defined(_WIN32) && defined(JFG_PHASE8_LIVE_RUNTIME)
  const bool keyboard_draw = target == game_code("game.frontDrawObject");
  const bool keyboard_caller = state.presentation_identity_enabled && section_addresses &&
      static_cast<std::uint32_t>(context->r31) ==
          static_cast<std::uint32_t>(section_addresses[game_module(OriginalModule::save_keyboard)]) +
          game_overlay_site("render.keyboard.key_draw", OriginalModule::save_keyboard) + 8U;
  jfg::KeyboardPresentationScope keyboard_scope(state.presentation_keyboard_key,
      keyboard_draw, keyboard_caller,
      keyboard_draw ? jfg::PresentationGuestView({rdram,kRdramSize}).u8(kRendererGameLayout.frontend_mode) : 0U,
      static_cast<std::uint32_t>(context->r4), static_cast<std::uint32_t>(context->r17));
  // Interpolated presentation keeps the camera's four low angle bits.
  // Original mode and all non-camera trig calls retain the native result.
  const bool precision_camera_call=jfg::camera_precision_call(kRendererGameLayout,
      (state.presentation_identity_enabled || jfg::shadow_quality_preference().load(std::memory_order_relaxed)==jfg::ShadowQuality::enhanced),target,
      static_cast<std::uint32_t>(context->r31),static_cast<std::uint32_t>(context->r6),
      static_cast<std::uint32_t>(context->r5));
  const auto precision_camera_angle=precision_camera_call ?
      static_cast<std::uint32_t>(context->r4)+(target==game_code("game.Cosf")?0x4000U:0U):0U;
  const auto finish_precision_camera=[&] {
    if(!precision_camera_call)return;
    std::fenv_t saved{};
    if(std::feholdexcept(&saved)!=0)return;
    const auto value=jfg::camera_precision_sine(precision_camera_angle,[&](unsigned index) {
      float entry=0.0f;std::memcpy(&entry,rdram+(game_data("math.sineTable")&0x1FFFFFFFU)+index*4U,4U);return entry;
    });
    if(std::fesetenv(&saved)!=0)
      fail_closed_dispatch(state,"camera-precision","restore-fenv",target);
    if(value)context->f0.fl=*value;
  };
  // Qualified bounded resident leaves cannot call, yield, write
  // memory or change section ownership. Preserve dispatch/watch history above.
  // Original timing, instruction observers and focused dispatch diagnostics
  // retain the complete generated path. Helper admission cannot cross a poll.
  if(state.resident_math_enabled &&
     (target==game_code("game.Arctanf") || target==game_code("game.mathDiffAngle") || target==game_code("game.Cosf") || target==game_code("game.Sinf")) &&
     state.guest_os_probe && !state.diagnostic_cpu_costs && state.focus_update_start==0U &&
     !state.guest_clock_trace.is_open() && state.point_probe_pcs.empty() &&
     !state.device_event_stream && !state.eret_transfer_stream.is_open() &&
     !state.instruction_effect_stream.is_open()) {
    if(target==game_code("game.Arctanf") && jfg_native_angle_try(kNativeMathLayout,rdram,context)) {
      ++state.generated_calls;++state.pure_angle_calls;return 1;
    }

    if((target==game_code("game.Cosf") || target==game_code("game.Sinf")) &&
       jfg_native_trig_try(kNativeMathLayout,rdram,context,target==game_code("game.Cosf"))) {
      finish_precision_camera();
      ++state.generated_calls;++state.pure_trig_calls;return 1;
    }
    if(target==game_code("game.mathDiffAngle") && jfg_native_angle_diff_try(kNativeMathLayout,rdram,context)) {
      ++state.generated_calls;++state.pure_diff_calls;return 1;
    }
  }
#endif
  if (state.guest_os_probe && state.native_audio_source &&
      target == kAudioSourceLayout.callback) {
    hle::GuestMemory memory({rdram,kRdramSize},hle::GuestMemory::Layout::native_word_big_endian);
    const auto source=static_cast<std::uint32_t>(context->r4);
    const auto length=static_cast<std::uint32_t>(context->r5);
    const auto loaded=jfg::boot::provide_native_audio_source(memory,kAudioSourceLayout,
        {state.rom,state.rom_size},source,length);
    if(!loaded) fail_closed_dispatch(state,"native-audio","source-cache-contract",target);
    context->r2=loaded->physical_address;
    ++state.native_audio_source_requests;
#if defined(_WIN32) && defined(JFG_PHASE8_LIVE_RUNTIME)
    if((state.native_audio_source_requests&1023U)==1U)
      state.gameplay_trace.event("native-audio-source",{state.vi_retraces,
          state.native_audio_source_requests,source,length,loaded->physical_address});
#endif
    return 1;
  }
  const auto mapping = std::lower_bound(
      std::begin(kMappings), std::end(kMappings), target,
      [](const Mapping &candidate, const std::uint32_t lookup_address) {
        return candidate.vram < lookup_address;
      });
  // Normalized overlay imports (including original CIC routines) must use
  // the same checked publication/lease path as other generated overlays.
  // The OS-execution profile never substitutes a mapped HLE overlay call.
  const bool mapped = mapping != std::end(kMappings) && mapping->vram == target &&
      !(state.guest_os_probe && target < kKseg0);
  const char *name = mapped ? mapping->name : nullptr;
  const std::size_t mapping_index =
      mapped ? static_cast<std::size_t>(mapping - std::begin(kMappings))
             : kMappingCount;
  if (name == nullptr) {
    if (recomp_func_t *const generated =
            jfg_generated_lookup_function(address)) {
#if defined(JFG_PHASE8_LIVE_RUNTIME)
      // Generated calls do not preserve a meaningful guest return address, so
      // retain the host dispatch nesting explicitly. The shared hint-text
      // overlay is updated by a resident loop guarded by
      // runlinkIsModuleLoaded(). Its stable cross-overlay entry points can
      // otherwise execute while that guard still reports it as unloaded.
      const std::uint32_t caller_section = state.executing_generated_section;
      const bool caller_is_overlay = state.executing_generated_overlay;
      std::uint32_t target_section = UINT32_MAX;
      JfgGeneratedSectionMetadata target_metadata{};
      const auto cached_section = state.generated_section_cache.find(target);
      if (cached_section != state.generated_section_cache.end()) {
        target_section = cached_section->second.first;
        target_metadata = cached_section->second.second;
      } else {
        for (std::uint32_t section = 0U;
             section < jfg_generated_section_count(); ++section) {
          JfgGeneratedSectionMetadata metadata{};
          if (jfg_generated_section_metadata(section, &metadata) == 0)
            fail_closed_dispatch(state, "generated", "section-metadata",
                                 target);
          const std::uint64_t text_begin = metadata.linked_vram;
          const std::uint64_t text_end = text_begin + metadata.text_size;
          if (target < text_begin || target >= text_end)
            continue;
          target_section = section;
          target_metadata = metadata;
          break;
        }
        state.generated_section_cache.emplace(target,
            std::make_pair(target_section, target_metadata));
      }
      if (target == kRunlinkColdLoad &&
          !note_guest_cold_overlay_load(state, static_cast<std::uint32_t>(context->r4)))
        fail_closed_dispatch(state, "runlink", "cold-load-identity", target);
      if (target_metadata.is_overlay == 1U) {
        if (!ensure_guest_overlay_allocation(state, target_metadata, *context))
          fail_closed_dispatch(state, "runlink", "guest-overlay-load", target);
        if (state.pending_cold_overlay_images.contains(target_metadata.linked_vram) &&
            !publish_synthetic_overlay(state, target_section, target_metadata))
          fail_closed_overlay_publication(state, target);
      }
      if (caller_is_overlay && target_metadata.is_overlay == 1U &&
          target_section == kHintTextOverlaySection &&
          target_section != caller_section) {
        const bool was_active =
            state.active_overlay_sections.contains(target_section);
        if (!publish_synthetic_overlay(state, target_section,
                                       target_metadata)) {
          fail_closed_overlay_publication(state, target);
        }
        if (!was_active)
          state.journal.append(NativeEventKind::kOverlayPublished,
                               target_section, target_metadata.linked_vram,
                               target);
      }
#endif
#if defined(JFG_PHASE8_LIVE_RUNTIME)
      const bool trace_matrix_conversion = target == game_code("game.mathMtxF2L");
      const std::uint32_t matrix_source =
          static_cast<std::uint32_t>(context->r4);
      const std::uint32_t matrix_destination =
          static_cast<std::uint32_t>(context->r5);
      std::array<std::uint32_t, 4U> matrix_first_row{};
#if defined(JFG_PHASE8_LIVE_RUNTIME)
      const bool trace_matrix_cat = target == game_code("game.mathMtxCatF");
      const std::size_t matrix_cat_slot =
          state.recent_matrix_cat_position % state.recent_matrix_cat_args.size();
      if (trace_matrix_cat) {
        state.recent_matrix_cat_args[matrix_cat_slot] = {
            static_cast<std::uint32_t>(context->r4),
            static_cast<std::uint32_t>(context->r5),
            static_cast<std::uint32_t>(context->r6)};
        hle::GuestMemory memory(
            {rdram, kRdramSize},
            hle::GuestMemory::Layout::native_word_big_endian);
        for (std::size_t word = 0U; word < 4U; ++word)
          (void)memory.read_u32(
              static_cast<std::uint32_t>(context->r4) +
                  static_cast<std::uint32_t>(word * 4U),
              state.recent_matrix_cat_words[matrix_cat_slot][word]);
        for (std::size_t word = 0U; word < 4U; ++word)
          (void)memory.read_u32(
              static_cast<std::uint32_t>(context->r5) +
                  static_cast<std::uint32_t>(word * 16U),
              state.recent_matrix_cat_words[matrix_cat_slot][word + 4U]);
      }
#endif
      if (trace_matrix_conversion) {
        hle::GuestMemory memory(
            {rdram, kRdramSize},
            hle::GuestMemory::Layout::native_word_big_endian);
        for (std::size_t index = 0U; index < matrix_first_row.size(); ++index)
          (void)memory.read_u32(
              matrix_source + static_cast<std::uint32_t>(index * 4U),
              matrix_first_row[index]);
      }
#endif
      context->r0 = 0;
      if (state.generated_relocation_targets.contains(target)) {
#if defined(_WIN32) && defined(JFG_PHASE8_LIVE_RUNTIME)
        const bool measure_relocation = state.diagnostic_cpu_costs;
        const auto relocation_start = measure_relocation ? std::chrono::steady_clock::now()
            : std::chrono::steady_clock::time_point{};
        std::uint64_t relocation_probes = 0U;
#endif
        // Resolve the continuation with the same table/lifecycle as its function.
        context->r0 = jfg_generated_lookup_entry_offset(static_cast<std::int32_t>(target), nullptr);
#if defined(_WIN32) && defined(JFG_PHASE8_LIVE_RUNTIME)
        if (measure_relocation) relocation_probes = 1U;
#endif
#if defined(_WIN32) && defined(JFG_PHASE8_LIVE_RUNTIME)
        if (measure_relocation) {
          ++state.profile_relocation_calls;
          state.profile_relocation_probes += relocation_probes;
          state.profile_relocation_ns += static_cast<std::uint64_t>(std::chrono::duration_cast<std::chrono::nanoseconds>(
              std::chrono::steady_clock::now()-relocation_start).count());
        }
#endif
      }
      ++state.generated_calls;
#if defined(JFG_PHASE8_LIVE_RUNTIME)
      state.executing_generated_section = target_section;
      state.executing_generated_overlay =
          target_metadata.is_overlay == 1U;
#endif
      [[maybe_unused]] const std::uint32_t allocation_size =
          static_cast<std::uint32_t>(context->r4);
#if defined(_WIN32) && defined(JFG_PHASE8_LIVE_RUNTIME)
      if (target == game_code("game.mainUpdate"))
        trace_phase9_event(state, "update-begin", state.controller_samples);
      const bool focus_window = state.focus_update_start != 0U &&
          state.completed_game_updates + 1U >= state.focus_update_start - 1U &&
          state.completed_game_updates + 1U <= state.focus_update_end + 1U;
      const bool watch_active = state.watch_word_address != 0U &&
          focus_window;
      std::uint32_t watch_before = 0U;
      const std::uint32_t watch_return_address =
          static_cast<std::uint32_t>(context->r31);
      if (watch_active) {
        hle::GuestMemory watch_memory(
            {rdram, kRdramSize},
            hle::GuestMemory::Layout::native_word_big_endian);
        if (!watch_memory.read_u32(state.watch_word_address, watch_before))
          fail_closed_dispatch(state, "diagnostic", "watch-word-read", target);
        ++state.watch_dispatch_depth;
      }
      if (state.entry_probe_target == target && focus_window) {
        trace_guest_clock(state, "entry", target);
        if (++state.entry_probe_hits > 1024U)
          fail_closed_dispatch(state, "diagnostic", "entry-probe-overflow", target);
        state.entry_probe_trace << state.completed_game_updates + 1U << '\t'
            << state.vi_retraces << '\t' << state.controller_samples << '\t'
            << std::hex << "0x" << target << '\t' << "0x"
            << static_cast<std::uint32_t>(context->r4) << '\t' << "0x"
            << static_cast<std::uint32_t>(context->r5) << '\t' << "0x"
            << static_cast<std::uint32_t>(context->r6) << '\t' << "0x"
            << static_cast<std::uint32_t>(context->r7) << std::dec << '\n';
        state.entry_probe_trace.flush();
        if (state.entry_fpu_trace.is_open()) {
          state.entry_fpu_trace << state.completed_game_updates + 1U << '\t'
              << state.vi_retraces << '\t' << state.controller_samples << '\t'
              << std::hex << "0x" << target;
          const fpr *registers = &context->f0;
          for (std::size_t index = 0U; index < 32U; ++index) {
            state.entry_fpu_trace << '\t' << "0x" << std::setw(8)
                << std::setfill('0') << registers[index].u32l << '\t'
                << "0x" << std::setw(8) << registers[index].u32h;
          }
          state.entry_fpu_trace << std::setfill(' ') << std::dec << '\n';
          state.entry_fpu_trace.flush();
        }
        if (state.entry_gpr_trace.is_open()) {
          state.entry_gpr_trace << state.completed_game_updates + 1U << '\t'
              << state.vi_retraces << '\t' << state.controller_samples << '\t'
              << std::hex << "0x" << target;
          const gpr *registers = &context->r0;
          for (std::size_t index = 0U; index < 32U; ++index) {
            const auto value = static_cast<std::uint64_t>(registers[index]);
            state.entry_gpr_trace << '\t' << "0x" << std::setw(8)
                << std::setfill('0') << static_cast<std::uint32_t>(value)
                << '\t' << "0x" << std::setw(8)
                << static_cast<std::uint32_t>(value >> 32U);
          }
          state.entry_gpr_trace << std::setfill(' ') << std::dec << '\n';
          state.entry_gpr_trace.flush();
        }
        if (state.entry_memory_trace.is_open()) {
          hle::GuestMemory entry_memory(
              {rdram, kRdramSize},
              hle::GuestMemory::Layout::native_word_big_endian);
          state.entry_memory_trace << state.completed_game_updates + 1U << '\t'
              << state.vi_retraces << '\t' << state.controller_samples << '\t'
              << std::hex << "0x" << target;
          for (const std::uint64_t argument :
               {context->r5, context->r6, context->r7}) {
            const auto pointer_address = static_cast<std::uint32_t>(argument);
            if (pointer_address < 0x80000000U ||
                pointer_address > 0x803FFF00U)
              fail_closed_dispatch(state, "diagnostic", "entry-memory-range", target);
            state.entry_memory_trace << '\t';
            for (std::uint32_t offset = 0U; offset < 256U; offset += 4U) {
              std::uint32_t word = 0U;
              if (!entry_memory.read_u32(pointer_address + offset, word))
                fail_closed_dispatch(state, "diagnostic", "entry-memory-read", target);
              state.entry_memory_trace << std::setw(8) << std::setfill('0')
                  << word;
            }
          }
          state.entry_memory_trace << std::setfill(' ') << std::dec << '\n';
          state.entry_memory_trace.flush();
        }
      }
#endif
#if defined(JFG_PHASE8_LIVE_RUNTIME)
      // Native day/nightUpdate rewrites ambient descriptors after the ordinary
      // object-light pass. Refresh the affected object's derived lighting before
      // drawing; otherwise the unattenuated value flashes for one native frame.
      // Keep this scoped to the original controller's setter call.
      const bool refresh_daynight_lighting =
          target == game_code("game.lightSetObjectLight") && caller_is_overlay && caller_section == game_module(OriginalModule::day_night);
      const auto daynight_actor = static_cast<std::uint32_t>(context->r2);
      const auto daynight_descriptor = static_cast<std::uint32_t>(context->r4);
#endif

#if defined(_WIN32) && defined(JFG_PHASE8_LIVE_RUNTIME)
      const bool trace_atmosphere = state.gameplay_trace && state.gameplay_trace_actors &&
          (target == game_overlay_token("overlay.day.update") || target == game_overlay_token("overlay.day.fog") || target == game_overlay_token("overlay.day.track_fade"));
      std::array<std::uint32_t, 5> atmosphere_outputs{};
      if (trace_atmosphere && target != game_overlay_token("overlay.day.update")) {
        atmosphere_outputs = {static_cast<std::uint32_t>(context->r4),
            static_cast<std::uint32_t>(context->r5), static_cast<std::uint32_t>(context->r6),
            static_cast<std::uint32_t>(context->r7), 0U};
        const NativeGameMemory atmosphere_ram({rdram, kRdramSize});
        const auto argument5 = static_cast<std::uint32_t>(context->r29) + 0x10U;
        if (target == game_overlay_token("overlay.day.fog") && atmosphere_ram.valid(argument5, 4U))
          atmosphere_outputs[4] = atmosphere_ram.u32(argument5);
      }
#endif
      [[maybe_unused]] const auto mod_actor_argument=static_cast<std::uint32_t>(context->r4);
      const auto sound_event_argument = static_cast<std::uint32_t>(context->r5);
#if defined(_WIN32) && defined(JFG_PHASE8_LIVE_RUNTIME)
      if (state.navigation_mod.enabled && target == game_overlay_token("overlay.juno.movement_handler")) {
        NativeGameMemory memory({rdram, kRdramSize});
        const auto original = static_cast<std::uint32_t>(context->r6);
        const auto boosted = state.navigation_mod.juno_run_target(
            memory, mod_actor_argument, sound_event_argument, original);
        context->r6 = boosted;
        if (boosted != original && state.navigation_mod.juno_run_boosts == 1U)
          jfg::support_event("mod=juno-run-speed-2x-applied");
      }
#endif
      {
#if defined(_WIN32) && defined(JFG_PHASE8_LIVE_RUNTIME)
        // Sound must run on the native menu update stack, never on the input
        // polling/audio thread. A stationary cursor queues no new event.
        if(state.menu_selection_feedback && (target==game_overlay_token("overlay.pause.screen") || target==game_overlay_token("overlay.settings.page"))) {
          const auto pending=*state.menu_selection_feedback;state.menu_selection_feedback.reset();
          const auto current=read_guest_menu(state);
          NativeGameMemory menu_ram({rdram,kRdramSize});
          const auto stack=static_cast<std::uint32_t>(context->r29);
          if(current.ready && current.kind==pending.kind && current.identity==pending.identity &&
             menu_ram.valid(stack-0x600U,0x600U) && menu_ram.instruction_matches("guard.game.amSndPlay.entry0")) {
            if(auto* sound=jfg_generated_lookup_function(static_cast<std::int32_t>(game_code("game.amSndPlay")))) {
              auto sound_context=*context;
              sound_context.f_odd=sound_context.mips3_float_mode
                  ? &sound_context.f1.u32l : &sound_context.f0.u32h;
              sound_context.r29=stack-0x40U;
              sound_context.r4=0x16BU;sound_context.r5=0;
              sound(rdram,&sound_context);
              set_cop1_cs(context->fcr31);
              state.gameplay_trace.event("menu-hover-sound",{state.vi_retraces,static_cast<unsigned>(current.kind),0x16BU});
            }
          }
        }
        NativeGameMemory door_render_ram({state.rdram,kRdramSize});
        const bool door_render_call=target==game_code("game.objPrintModelObject") &&
          door_render_ram.instruction_matches("guard.game.objPrintModelObject.entry0") &&
          door_render_ram.instruction_matches("guard.game.objPrintModelObject.entry4");
        const auto door_render_actor=door_render_call?static_cast<std::uint32_t>(context->r4):0U;
        if(door_render_actor && state.gameplay_trace && jfg::blur_source_audit_enabled() &&
           door_render_ram.valid(door_render_actor,0xA4U)) {
          const auto models=door_render_ram.u32(door_render_actor+game_member("layout.actor.models"));
          const auto base=door_render_ram.u8(door_render_actor+game_member("layout.actor.variant"));
          const auto slot=models+static_cast<unsigned>(base)*4U;
          const auto instance=door_render_ram.valid(slot,4U)?door_render_ram.u32(slot):0U;
          const auto model=door_render_ram.valid(instance,4U)?door_render_ram.u32(instance):0U;
          state.gameplay_trace.event("model-native-draw",{state.vi_retraces,
            door_render_actor,door_render_ram.u16(door_render_actor+game_member("layout.actor.type")),
            door_render_ram.u8(door_render_actor+game_member("layout.actor.alpha")),base,instance,model});
        }
        if(door_render_actor && door_render_ram.valid(door_render_actor,0xA4U) &&
           door_render_ram.u16(door_render_actor+game_member("layout.actor.type"))==67U) {
          const auto header=door_render_ram.u32(door_render_actor+game_member("layout.actor.header"));
          const auto control=door_render_ram.u32(door_render_actor+game_member("layout.actor.control"));
          state.gameplay_trace.event("door-indicator-draw",{state.vi_retraces,
            door_render_actor,door_render_ram.u8(door_render_actor+game_member("layout.actor.variant")),
            door_render_ram.u8(game_data("diagnostic.doorRenderMode")),door_render_ram.u32(header+game_member("layout.objectHeader.lodThreshold")),
            door_render_ram.u8(control+game_member("layout.doorIndicator.state")),door_render_ram.u8(door_render_actor+game_member("layout.actor.alpha"))});
          const auto models=door_render_ram.u32(door_render_actor+game_member("layout.actor.models"));
          const auto base=door_render_ram.u8(door_render_actor+game_member("layout.actor.variant"));
          const auto instance=door_render_ram.u32(models+base*4U);
          const auto model=door_render_ram.u32(instance);
          const auto textures=door_render_ram.u32(instance+game_member("layout.instance.textures"));
          state.gameplay_trace.event("door-indicator-material-v2",{state.vi_retraces,
            door_render_actor,model,door_render_ram.u16(textures),
            door_render_ram.u32(textures+4U),
            door_render_ram.u8(door_render_actor+game_member("layout.actor.viewVisibility"))});

        }

        // Private CPU-side material packet, buffered with the existing trace.
        // One completed unlocked marker per asset/opacity path, at most eight
        // packets per process. No GPU readback or frame-time file writes.
        bool capture_door_material=false;
        std::uint32_t door_material_model=0,door_material_instance=0;
        const auto door_dl_before=door_render_actor?game_view(door_render_ram).u32(game_data_ref("globals.objectDisplayListCursor")):0U;
        if(door_render_actor && state.gameplay_trace && jfg::blur_source_audit_enabled() &&
           door_render_ram.valid(door_render_actor,0xA4U) &&
           door_render_ram.u16(door_render_actor+game_member("layout.actor.type"))==67U) {
          const auto control=door_render_ram.u32(door_render_actor+game_member("layout.actor.control"));
          const auto models=door_render_ram.u32(door_render_actor+game_member("layout.actor.models"));
          const auto slot=models+4U*door_render_ram.u8(door_render_actor+game_member("layout.actor.variant"));
          if(door_render_ram.valid(control,9U) && door_render_ram.u8(control+game_member("layout.doorIndicator.state"))==1U &&
             door_render_ram.valid(slot,4U)) {
            door_material_instance=door_render_ram.u32(slot);
            if(door_render_ram.valid(door_material_instance,0x100U))
              door_material_model=door_render_ram.u32(door_material_instance);
            static std::set<std::pair<std::uint32_t,bool>> captured;
            const auto opacity=door_render_ram.u8(door_render_actor+game_member("layout.actor.alpha"));
            const auto key=std::make_pair(door_material_model,opacity==255U);
            if(opacity && door_render_ram.valid(door_material_model,0x10000U) &&
               captured.size()<8U && !captured.contains(key)) {
              captured.insert(key);capture_door_material=true;
              state.gameplay_trace.event("door-packet-begin",{state.vi_retraces,
                door_render_actor,door_material_instance,door_material_model,
                opacity,door_dl_before});
            }
          }
        }
        jfg::DoorIndicatorPresentationScope door_indicator_presentation(
            {rdram,kRdramSize},kRendererGameLayout,door_render_actor);
        if(door_indicator_presentation.applied())
          state.gameplay_trace.event("door-indicator-opacity-candidate",{
            state.vi_retraces,door_render_actor,door_indicator_presentation.original(),255U});

        ModernShoulderScope modern_shoulder(state,target,*context);
        modern_shoulder_physics(state,target,*context);
        ModernAirPhysicsScope modern_air_physics(state,target,*context);
        ModernAirAimPresentationScope modern_air_aim(state,target,*context);
        DiagnosticReticleDrawScope diagnostic_reticle(state,target,*context);
        DiagnosticLineOutputScope diagnostic_lines(state,target);
        DiagnosticWeatherScope diagnostic_weather_scope(state,target,*context);
        std::optional<jfg::rain::Dispatch> rain_fade;
        if (jfg::rain::Dispatch::observes(kRendererGameLayout,target))
          rain_fade.emplace(kRendererGameLayout,state.rain_fade, std::span<std::uint8_t>{rdram,kRdramSize}, target,
              jfg::rain::Call{static_cast<std::uint32_t>(context->r4), static_cast<std::uint32_t>(context->r5),
                  static_cast<std::uint32_t>(context->r6), static_cast<std::uint32_t>(context->r7),
                  static_cast<std::uint32_t>(context->r29), static_cast<std::uint32_t>(context->r31)});
        if (target == game_code("game.mainCPUeffects") && state.rain_fade.post && state.gameplay_trace) {
          const auto& frame = *state.rain_fade.post;
          state.gameplay_trace.event("rain-fade-frame", {state.vi_retraces, frame.buffer,
              frame.bytes, frame.fade.simple_in, frame.fade.alpha, frame.fade.rgb, frame.fade.transition});
          const auto& rain = state.rain_fade;
          state.gameplay_trace.event("rain-fade-spatial-frame", {state.vi_retraces,frame.buffer,
              frame.fade.spatial.supported,frame.fade.spatial.partially_visible,frame.fade.transition,
              static_cast<std::uint64_t>(frame.fade.spatial.shift),rain.spatial_attempts,
              rain.spatial_accepted,rain.scissor_attempts,rain.scissor_accepted,
              rain.spatial_lines,rain.spatial_pixels});
        }
        // Diagnostic observation only: distinguish missing native reticle
        // draws, off-screen coordinates, and lost framebuffer presentation.
        if(state.gameplay_trace && (target==game_overlay_token("overlay.target.player") || target==game_overlay_token("overlay.target.draw") ||
                                   (target==game_code("game.fxDrawLine") && diagnostic_reticle_lines()))) {
          NativeGameMemory ram({rdram,kRdramSize});
          const auto a=static_cast<std::uint32_t>(context->r4);
          const auto b=static_cast<std::uint32_t>(context->r5);
          const auto c=static_cast<std::uint32_t>(context->r6);
          const auto d=static_cast<std::uint32_t>(context->r7);
          const auto control=target==game_overlay_token("overlay.target.player")?b:target==game_overlay_token("overlay.target.draw")?a:0U;
          if(control && ram.valid(control,0x5C4U)) {
            const auto game=game_view(ram).u32(game_data_ref("globals.selectedPlayer"));
            const auto character=ram.u8(control+game_member("layout.playerControl.characterFlags"))&3U;
            const auto weapon=character<3U && ram.valid(game,0x538U)?
                ram.u8(game+0x15CU+character*0x76U+0x70U):255U;
            state.gameplay_trace.event(target==game_overlay_token("overlay.target.player")?"reticle-player":"reticle-draw",
                {state.vi_retraces,control,weapon,a,b,c,d,ram.u8(control+game_member("layout.playerControl.movement")),
                 ram.u16(control+game_member("layout.playerControl.aimYaw")),ram.u16(control+game_member("layout.playerControl.aimPitch")),ram.u32(control+game_member("layout.playerControl.weaponState")),
                 ram.u16(control+game_member("layout.playerControl.heading")),ram.u16(control+game_member("layout.playerControl.manualPitch"))});
          } else if(target==game_code("game.fxDrawLine")) {
            const auto stack=static_cast<std::uint32_t>(context->r29);
            state.gameplay_trace.event("reticle-line-append",{state.vi_retraces,a,b,c,d,
                ram.u32(stack+0x10U),ram.u32(stack+0x14U)});
          }
        }
        FlyingMotionScope flying_motion(state,target,*context);
        ModernAnimationScope modern_animation(state,target,*context);
        ModernGuestTableScope modern_table(state,target,static_cast<std::uint32_t>(context->r4));
        ModernRollScope modern_roll(state,target,*context);
        ModernCrawlDirectionScope modern_crawl_direction(state,target,*context);
        ModernProneRollMotionScope modern_prone_roll_motion(state,target,*context);
#endif
#if defined(_WIN32) && defined(JFG_PHASE8_LIVE_RUNTIME)
#if defined(JFG_EXPERIMENTAL_NATIVE_PLAY_TIMING)
        if (target == game_code("game.viFrameSync") && state.diagnostic_host_clock &&
            state.diagnostic_native_recovery_enabled) {
          // Preserve viFrameSync's real-overload test, waits and elapsed delta.
          // Remove only the console's sticky 31-fast-frame recovery delay.
          auto& recovery = rdram[(game_data("video.recoveryCounter")&0x1FFFFFFFU) ^ 3U];
          recovery = jfg::boot::native_frame_recovery_counter(true,
              rdram[(game_data("video.overloaded")&0x1FFFFFFFU) ^ 3U], recovery);
        }
#endif
        if (state.diagnostic_cpu_costs) {
          state.profile_dispatch_prefix_ns += static_cast<std::uint64_t>(std::chrono::duration_cast<std::chrono::nanoseconds>(
              std::chrono::steady_clock::now()-dispatch_prefix_started).count());
          ++state.profile_dispatch_prefix_calls;
        }
        const bool measure_vi_sync = target == game_code("game.viFrameSync") && state.gameplay_trace;
        const auto sync_count_before = measure_vi_sync ? state.cpu_count : 0U;
        const auto sync_vi_before = measure_vi_sync ? state.vi_retraces : 0U;
        if (measure_vi_sync) {
          NativeGameMemory sync_ram({rdram,kRdramSize});
          state.gameplay_trace.event("vi-sync-enter", {state.vi_retraces,state.cpu_count,
              game_view(sync_ram).u32(game_data_ref("globals.currentLevel")),game_view(sync_ram).u8(game_data_ref("globals.gVideoDeltaTime")),
              game_view(sync_ram).u8(game_data_ref("globals.gVideoDeltaCounter")),game_view(sync_ram).u8(game_data_ref("globals.gSkipVideoDeltaAdjust")),
              state.diagnostic_host_clock,state.diagnostic_native_recovery_enabled});
          if(state.diagnostic_function_profile && !state.diagnostic_host_clock) {
            (void)sample_model_thread(state,state.profile_model_owner);
            for(const auto& row:state.profile_model_threads) {
              if(row.value[0]==0U)continue;
              const auto thread_id=sync_ram.valid(row.id,0x1b0U)?sync_ram.u32(row.id+0x14U):UINT32_MAX;
              const auto priority=sync_ram.valid(row.id,0x1b0U)?sync_ram.u32(row.id+4U):UINT32_MAX;
              state.gameplay_trace.event("thread-model-total", {
                state.vi_retraces,state.cpu_count,game_view(sync_ram).u32(game_data_ref("globals.currentLevel")),
                row.id,thread_id,priority,row.value[0],row.value[1],row.value[2],
                row.value[3],row.value[4],row.value[5]});
            }
          }
          state.gameplay_trace.event("vi-sync-cache-enter", {state.vi_retraces,state.cpu_count,
              cache_stats[0],cache_stats[1],cache_stats[2],cache_stats[3],
              cache_stats[4],cache_stats[5],cache_stats[6],cache_stats[7],
              cache_stats[8],cache_stats[9],cache_stats[10],cache_stats[11]});
        }
        const bool measure_update = target == game_code("game.mainUpdate") && state.gameplay_trace;
        const auto pure_angle_before=state.pure_angle_calls,pure_diff_before=state.pure_diff_calls,pure_trig_before=state.pure_trig_calls;
        const auto cache_all_before=state.native_cache_all_calls;
        const auto shadow_filter_before=state.native_shadow_filter_calls;
        const auto bsp_before=measure_update && state.diagnostic_bsp_enabled ?
            jfg::boot::native_collision_counters() : jfg::boot::NativeCollisionCounters{};
        const auto bsp_calls_before=state.bsp_native_calls,bsp_refresh_before=state.bsp_clock_refreshes;
        if(measure_update && state.diagnostic_bsp_enabled)jfg::boot::native_collision_reset_max();


        if (measure_update && state.diagnostic_cpu_costs) state.profile_function_costs.clear();
        const auto update_started = measure_update ? std::chrono::steady_clock::now()
                                                  : std::chrono::steady_clock::time_point{};
        const auto update_count = measure_update ? state.cpu_count : 0U;
        const auto rom_before=measure_update && state.mmio_trace ?
            state.mmio_trace->pi_dma.rom_transfers() : jfg::boot::OriginalTimingPiDma::RomTransfers{};
        const auto update_idle = measure_update ? state.profile_idle_count_ticks : 0U;
        const auto update_wait = measure_update ? state.profile_host_wait_us : 0U;
        const auto update_instructions = measure_update ? state.observed_guest_instructions : 0U;
        const bool measure_update_cycles = measure_update && state.diagnostic_update_cycles;
        const auto update_cycles_before = measure_update_cycles ?
            (state.guest_transport?state.guest_transport->execution_cycles():BatonExecutor::host_cycles()):BatonExecutor::CycleSample{};
        const auto callback_start = state.profile_out_of_line_instructions;
        const auto full_probe_start = state.profile_full_execution_probes;
        const auto native_handler_start = measure_update ? state.profile_native_handler_ns : 0U;
        const auto dispatch_prefix_ns_start = state.profile_dispatch_prefix_ns;
        const auto dispatch_prefix_calls_start = state.profile_dispatch_prefix_calls;
        const auto inventory_ns_start = state.profile_overlay_inventory_ns;
        const auto inventory_calls_start = state.profile_overlay_inventory_calls;
        const auto span_instructions_start = state.native_span_instructions;
        const auto span_commits_start = state.native_span_commits;
        const auto relocation_ns_start = state.profile_relocation_ns;
        const auto relocation_calls_start = state.profile_relocation_calls;
        const auto relocation_probes_start = state.profile_relocation_probes;
        const auto dispatch_start = measure_update ? state.dispatch_calls : 0U;
        const auto mmio_start = measure_update && state.mmio_trace ? state.mmio_trace->accesses : 0U;
        const auto graphics_start = measure_update ? state.graphics_submit_microseconds : 0U;
        const auto handoff_start = state.guest_transport ? state.guest_transport->handoffs() : 0U;
        const auto transport_start = measure_update && state.diagnostic_cpu_costs && state.guest_transport
            ? state.guest_transport->timing() : BatonExecutor::Timing{};
        FILETIME process_created{}, process_exited{}, kernel_start{}, user_start{};
        ULONG64 process_cycles_start = 0;
        const bool process_costs = measure_update && state.diagnostic_cpu_costs &&
            GetProcessTimes(GetCurrentProcess(), &process_created, &process_exited, &kernel_start, &user_start) &&
            QueryProcessCycleTime(GetCurrentProcess(), &process_cycles_start);
#endif
#if defined(_WIN32) && defined(JFG_PHASE8_LIVE_RUNTIME)
        if ((state.presentation_identity_enabled || jfg::shadow_quality_preference().load(std::memory_order_relaxed)==jfg::ShadowQuality::enhanced)) {
          if (target == game_code("game.objFreeObject"))
            state.presentation_identities.retire(static_cast<std::uint32_t>(context->r4));
          else if (target == game_code("game.partRelease"))
            state.presentation_identities.particle_retire(static_cast<std::uint32_t>(context->r4));
          else if (target == game_code("game.partFreeLib"))
            state.presentation_identities.particles_clear();
          else if (target == game_code("game.camDoSprite")) {
            const jfg::PresentationGuestView ram({rdram,kRdramSize});
            const auto output = static_cast<std::uint32_t>(context->r6);
            const auto owner = static_cast<std::uint32_t>(context->r7);
            const auto asset = ram.u32(static_cast<std::uint32_t>(context->r29)+0x10U);
            if (static_cast<std::uint32_t>(context->r31) == game_instruction("native.collision_response_return"))
              state.presentation_identities.particle_sprite({rdram,kRdramSize},
                  output,owner,asset,state.vi_retraces);
            else if (section_addresses &&
                static_cast<std::uint32_t>(context->r31)==
                    static_cast<std::uint32_t>(section_addresses[game_module(OriginalModule::region_id)])+game_overlay_site("render.region.sprite_return",OriginalModule::region_id)) {
              // Qualified original region-id draw: a3 is a stack transform, while the
              // real actor and sorted sparkle index remain in its frame.
              const auto sp=static_cast<std::uint32_t>(context->r29);
              const auto cursor=static_cast<std::uint32_t>(context->r19);
              if(owner==sp+0x190U && cursor>=sp+0x281U && cursor<=sp+0x294U)
                state.presentation_identities.region_sprite({rdram,kRdramSize},
                    output,ram.u32(sp+0x2ACU),static_cast<std::uint32_t>(context->r21),
                    ram.u8(cursor-1U),asset,state.vi_retraces);
            }
            else
              state.presentation_identities.sprite({rdram,kRdramSize},
                  output,owner,asset,state.vi_retraces);
          }
          else if (target == game_code("game.camSetProjMtx"))
            state.presentation_identities.camera({rdram,kRdramSize},
                static_cast<std::uint32_t>(context->r5),state.vi_retraces);
        }
#endif
#if defined(_WIN32) && defined(JFG_PHASE8_LIVE_RUNTIME)
        static const bool audio_buffer_trace=[] {
          char value[2]{};
          return GetEnvironmentVariableA("JFG_DIAGNOSTIC_AUDIO_SCHEDULER",value,2U)==1U && value[0]=='1';
        }();
        static const bool shot_matrix_trace=[] {
          char value[2]{};
          return GetEnvironmentVariableA("JFG_DIAGNOSTIC_SHOT_MATCHING",value,2U)==1U && value[0]=='1';
        }();
        static const bool camera_motion_trace=[] {
          char value[2]{};
          return GetEnvironmentVariableA("JFG_DIAGNOSTIC_CAMERA_MOTION",value,2U)==1U && value[0]=='1';
        }();
        static const bool shadow_motion_trace=[] {
          char value[2]{};
          return GetEnvironmentVariableA("JFG_DIAGNOSTIC_SHADOW_MOTION",value,2U)==1U && value[0]=='1';
        }();
        // Optional read-only mask diagnostics: before and after the original
        // 64x64 filter, with no changes to the guest image or its cadence.
        const bool observe_shadow_filter=shadow_motion_trace && state.gameplay_trace &&
            target==game_overlay_token("overlay.shadows.filter") && target_section==game_module(OriginalModule::shadows) && target_metadata.is_overlay==1U;
        const auto shadow_filter_object=observe_shadow_filter?static_cast<std::uint32_t>(context->r4):0U;
        const auto trace_shadow_mask=[&](unsigned stage) {
          if(!observe_shadow_filter)return;
          const jfg::PresentationGuestView ram({rdram,kRdramSize});
          const auto image=ram.u32(shadow_filter_object+32U);
          if(!ram.valid(image,4096U))return;
          std::array<std::uint8_t,4096> pixels{};
          std::uint64_t hash=14695981039346656037ULL,sum=0U,mx=0U,my=0U;
          unsigned nonzero=0U,low=0U,high=0U;
          for(unsigned i=0;i<pixels.size();++i) {
            const auto value=ram.u8(image+i);pixels[i]=value;
            hash=(hash^value)*1099511628211ULL;sum+=value;
            mx+=std::uint64_t(value)*(i%64U);my+=std::uint64_t(value)*(i/64U);
            nonzero+=value!=0U;low+=value>0U && value<32U;high+=value>=128U;
          }
          state.gameplay_trace.event("shadow-mask-pixels",{state.vi_retraces,stage,
              shadow_filter_object,image,hash,sum,mx,my,nonzero,low,high});
          static std::ofstream masks=[] {
            std::array<wchar_t,32768> path{};
            const auto length=GetEnvironmentVariableW(L"JFG_DIAGNOSTIC_SHADOW_MASKS",path.data(),static_cast<DWORD>(path.size()));
            return length && length<path.size()?std::ofstream(std::filesystem::path(path.data()),std::ios::binary):std::ofstream{};
          }();
          static unsigned written=0U;
          if(masks.is_open() && written<40000U) {
            const std::array<std::uint32_t,4> header{
                static_cast<std::uint32_t>(state.vi_retraces),stage,shadow_filter_object,image};
            masks.write(reinterpret_cast<const char*>(header.data()),sizeof(header));
            masks.write(reinterpret_cast<const char*>(pixels.data()),pixels.size());++written;
          }
        };
        trace_shadow_mask(0U);
        const bool observe_shadow=((state.presentation_identity_enabled || jfg::shadow_quality_preference().load(std::memory_order_relaxed)==jfg::ShadowQuality::enhanced) || shadow_motion_trace) && target==game_code("game.shadowDrawReceiver");
        const jfg::PresentationGuestView shadow_ram({rdram,kRdramSize});
        const auto shadow_descriptor=observe_shadow ? static_cast<std::uint32_t>(context->r4) : 0U;
        const auto shadow_first=observe_shadow ? shadow_ram.u32(game_data("diagnostic.shadowBatchStart")) : 0U;
        const auto shadow_triangle_first=observe_shadow ? shadow_ram.u32(game_data("diagnostic.shadowTriangleStart")) : 0U;
        if((state.presentation_identity_enabled || jfg::shadow_quality_preference().load(std::memory_order_relaxed)==jfg::ShadowQuality::enhanced) && target==game_code("game.shadowBeginBuffers"))
          state.presentation_identities.shadow_begin({rdram,kRdramSize});
        if(target==game_code("game.shadowBoundingBox")) {
          const auto footprint=jfg::enhanced_shadow_receiver_query(kRendererGameLayout,
              {rdram,kRdramSize},target,static_cast<std::uint32_t>(context->r31),
              static_cast<std::uint32_t>(context->r29),static_cast<std::uint32_t>(context->r4),
              static_cast<std::uint32_t>(context->r5),
              jfg::shadow_quality_preference().load(std::memory_order_relaxed)==jfg::ShadowQuality::enhanced);
          // Explicit bounded evidence of the producer state at receiver sizing.
          // Useful when an exit snapshot has later, already-built bone palettes.
          static const std::filesystem::path query_capture=[] {
            std::array<wchar_t,32768> path{};
            const auto length=GetEnvironmentVariableW(L"JFG_SHADOW_QUERY_CAPTURE",path.data(),static_cast<DWORD>(path.size()));
            if(length&&length<path.size())return std::filesystem::path(path.data());
            // The launcher strips inherited diagnostics. Its explicit capture
            // mode supplies GAMEPLAY_TRACE, so keep bounded query evidence
            // inside that same capture rather than requiring inherited flags.
            if(GetEnvironmentVariableW(L"JFG_PHASE8_RDRAM_CAPTURE",nullptr,0U)==0U)
              return std::filesystem::path{};
            const auto trace=GetEnvironmentVariableW(L"JFG_GAMEPLAY_TRACE",path.data(),static_cast<DWORD>(path.size()));
            return trace&&trace<path.size()?std::filesystem::path(path.data()).parent_path()/L"shadow-queries":
                std::filesystem::path{};
          }();
          if(!query_capture.empty() && static_cast<std::uint32_t>(context->r31)==game_instruction("native.query_capture_return")) {
            const auto stack=static_cast<std::uint32_t>(context->r29);
            const auto actor=shadow_ram.u32(stack+0x74U);
            const auto header=shadow_ram.u32(actor+game_member("layout.actor.header"));
            const auto table=shadow_ram.u32(actor+game_member("layout.actor.models"));
            const auto instance=shadow_ram.u32(table+shadow_ram.u8(actor+game_member("layout.actor.variant"))*4U);
            const auto model=shadow_ram.u32(instance);
            static std::set<std::pair<std::uint32_t,unsigned>> captured;
            const unsigned status=footprint?(footprint->expanded?2U:1U):0U;
            const auto key=std::make_pair(model,status);
            if(shadow_ram.valid(header,0x70U) && shadow_ram.u8(header+game_member("layout.objectHeader.renderKind"))!=1U &&
               shadow_ram.valid(model,0x64U) && captured.size()<24U && captured.insert(key).second) {
              std::string bytes(kRdramSize,'\0');
              for(std::size_t i=0;i<bytes.size();++i)bytes[i]=static_cast<char>(rdram[i^3U]);
              const auto stem=std::to_string(model)+"-"+std::to_string(status);
              std::ostringstream metadata;
              metadata<<state.vi_retraces<<' '<<actor<<' '<<model<<' '<<stack<<' '<<status<<'\n';
              jfg::AsyncSnapshots::Batch files;
              files.push_back({query_capture/(stem+".bin"),std::make_shared<const std::string>(std::move(bytes))});
              files.push_back({query_capture/(stem+".txt"),std::make_shared<const std::string>(metadata.str())});
              (void)state.snapshot_writer.submit(0U,std::move(files));
              state.gameplay_trace.event("enhanced-shadow-query",{state.vi_retraces,actor,model,status,
                  shadow_ram.u32(instance+0x10U),shadow_ram.u32(instance+0x14U)});
            }
          }
          if(footprint && footprint->expanded && state.gameplay_trace)
            state.gameplay_trace.event("enhanced-shadow-footprint",{state.vi_retraces,
                shadow_ram.u32(static_cast<std::uint32_t>(context->r29)+0x74U),footprint->vertices,
                std::bit_cast<std::uint32_t>(footprint->points[0][0]),
                std::bit_cast<std::uint32_t>(footprint->points[0][1]),
                std::bit_cast<std::uint32_t>(footprint->points[2][0]),
                std::bit_cast<std::uint32_t>(footprint->points[2][1])});
        }
        const auto shadow_control=observe_shadow ? static_cast<std::uint32_t>(context->r6) : 0U;
        const auto shadow_light=observe_shadow ? static_cast<std::uint32_t>(context->r5) : 0U;
        const auto shadow_clip=(state.presentation_identity_enabled || jfg::shadow_quality_preference().load(std::memory_order_relaxed)==jfg::ShadowQuality::enhanced) && target==game_code("game.shadowClipReceiver")
            ?state.presentation_identities.shadow_clip({rdram,kRdramSize},
                static_cast<std::uint32_t>(context->r4),static_cast<std::uint32_t>(context->r6),
                static_cast<std::uint32_t>(context->r5),
                shadow_ram.u32(static_cast<std::uint32_t>(context->r29)+0x10U),
                static_cast<std::uint32_t>(context->r7))
            :std::optional<jfg::ShadowClipGeometry>{};

        const bool observe_reflection=(state.presentation_identity_enabled || jfg::shadow_quality_preference().load(std::memory_order_relaxed)==jfg::ShadowQuality::enhanced) &&
            target==game_code("game.mathMtxF2L") && section_addresses &&
            static_cast<std::uint32_t>(context->r31)==
                static_cast<std::uint32_t>(section_addresses[game_module(OriginalModule::reflections)])+game_overlay_site("render.reflection.matrix_return",OriginalModule::reflections);
        const auto reflection_actor=observe_reflection ? static_cast<std::uint32_t>(context->r21) : 0U;
        const auto reflection_stack=observe_reflection ? static_cast<std::uint32_t>(context->r29) : 0U;
        const auto tracer_caller=static_cast<std::uint32_t>(context->r31);
        const bool observe_tracer=(state.presentation_identity_enabled || jfg::shadow_quality_preference().load(std::memory_order_relaxed)==jfg::ShadowQuality::enhanced) && target==game_code("game.objDrawTracer") &&
            (tracer_caller==game_instruction("native.tracer_first_return") || tracer_caller==game_instruction("native.tracer_second_return"));
        const auto tracer_actor=observe_tracer ? static_cast<std::uint32_t>(context->r20) : 0U;
        const jfg::PresentationGuestView tracer_ram({rdram,kRdramSize});
        const auto tracer_vertex_output=observe_tracer ? static_cast<std::uint32_t>(context->r5) : 0U;
        const auto tracer_vertices=observe_tracer ? tracer_ram.u32(tracer_vertex_output) : 0U;
        const auto tracer_list=observe_tracer ? tracer_ram.u32(static_cast<std::uint32_t>(context->r4)) : 0U;
        const bool observe_shot_matrix=shot_matrix_trace && state.gameplay_trace &&
            (target==game_code("game.camPushMuzzleMtx") || target==game_code("game.camScaleModelMtx"));
        const auto shot_output=observe_shot_matrix ? static_cast<std::uint32_t>(context->r5) : 0U;
        const auto shot_matrix=observe_shot_matrix ? jfg::PresentationGuestView({rdram,kRdramSize}).u32(shot_output) : 0U;
        const auto shot_caller=observe_shot_matrix ? static_cast<std::uint32_t>(context->r31) : 0U;
        const auto shot_actor=observe_shot_matrix ? static_cast<std::uint32_t>(context->r21) : 0U;
        const bool observe_audio_buffer=audio_buffer_trace && target==game_code("audio.ai_submit");
        const auto ai_buffer_address=observe_audio_buffer ? static_cast<std::uint32_t>(context->r4) : 0U;
        const auto ai_buffer_length=observe_audio_buffer ? static_cast<std::uint32_t>(context->r5) : 0U;
        const bool observe_camera=((state.presentation_identity_enabled || jfg::shadow_quality_preference().load(std::memory_order_relaxed)==jfg::ShadowQuality::enhanced) || camera_motion_trace) && target==game_code("game.camSetProjMtx");
        const auto camera_output=observe_camera ? static_cast<std::uint32_t>(context->r5) : 0U;
        const auto camera_matrix=observe_camera ? jfg::PresentationGuestView({rdram,kRdramSize}).u32(camera_output) : 0U;
        // US ShirukenPushMtx has the same output/actor ABI as camPushModelMtx,
        // but builds its rolling/attached world matrix through camPushFloatModelMtx.
        // That call also publishes world at 0x800FAAB0. Bind after the complete
        // custom draw transform, before another actor reuses the scratch matrix.
        const bool observe_shuriken = (state.presentation_identity_enabled || jfg::shadow_quality_preference().load(std::memory_order_relaxed)==jfg::ShadowQuality::enhanced) && target == game_overlay_token("overlay.shuriken.matrix");
        const bool observe_rigid = (state.presentation_identity_enabled || jfg::shadow_quality_preference().load(std::memory_order_relaxed)==jfg::ShadowQuality::enhanced) &&
            (target == game_code("game.camPushModelMtx") || observe_shuriken);
        const auto keyboard_sub_id = observe_rigid && !observe_shuriken &&
            state.presentation_keyboard_key < 41U ? state.presentation_keyboard_key + 1U : 0U;
        const auto rigid_actor = keyboard_sub_id ?
            jfg::PresentationGuestView({rdram,kRdramSize}).u32(kRendererGameLayout.keyboard_key_actor) :
            observe_rigid ? static_cast<std::uint32_t>(context->r6) : 0U;
        const auto rigid_output = observe_rigid ? static_cast<std::uint32_t>(context->r5) : 0U;
        const auto rigid_matrix = observe_rigid ? jfg::PresentationGuestView({rdram,kRdramSize}).u32(rigid_output) : 0U;
#endif
#if defined(_WIN32) && defined(JFG_PHASE8_LIVE_RUNTIME)
        jfg::ActorLodPresentationScope actor_lod_presentation(kRendererGameLayout,
            {rdram,kRdramSize},target,static_cast<std::uint32_t>(context->r4),
            target==game_code("game.objPrintModelObject") && jfg::actor_lod_preference().load(std::memory_order_relaxed)==jfg::ActorLod::high);
        jfg::CameraHelperPresentationScope camera_helper_presentation(kRendererGameLayout,
            {rdram,kRdramSize},target,static_cast<std::uint32_t>(context->r7));
        const auto function_started = state.diagnostic_cpu_costs ? std::chrono::steady_clock::now()
            : std::chrono::steady_clock::time_point{};
        const auto function_children = state.profile_function_self_ns;
        const auto function_wait = state.profile_host_wait_us;
#endif

#if defined(_WIN32) && defined(JFG_PHASE8_LIVE_RUNTIME)
        if(target_metadata.is_overlay==0U && state.mmio_trace &&
           state.mmio_trace->direct_mi_mask_access && jfg::boot::direct_mi_mask_function(target,rdram,context)) {
          // Pinned context-save/restore mask accesses use the existing device
          // bridge. Every instruction hook, span guard and fallback survives.
        } else
        if(target_metadata.is_overlay==0U && state.mmio_trace &&
           state.mmio_trace->direct_sp_access && jfg::boot::direct_sp_function(target,rdram,context)) {
          // Same generated probes, register operations and device model.
        } else
        if(target==game_overlay_token("overlay.shadows.filter") && target_section==game_module(OriginalModule::shadows) && target_metadata.is_overlay==1U &&
           state.native_shadow_filter_enabled && state.diagnostic_host_clock &&
           state.native_spans_enabled && !state.native_clock_sample_input.is_open() &&
           state.native_fast_ready && state.native_fast_status==context->status_reg &&
           state.execution_fast_revision==*state.io_revision &&
           !state.diagnostic_cpu_costs && state.focus_update_start==0U &&
           !state.guest_clock_trace.is_open() && state.point_probe_pcs.empty() &&
           !state.device_event_stream && !state.eret_transfer_stream.is_open() &&
           !state.instruction_effect_stream.is_open() &&
           jfg::boot::native_shadow_filter_try(rdram,context)) {
          ++state.native_shadow_filter_calls;
          state.native_fast_ready=false;state.host_clock_poll_budget=0U;
        } else
        if(target==game_overlay_token("overlay.collision.accessor") && target_section==game_module(OriginalModule::collision) && target_metadata.is_overlay==1U &&
           state.diagnostic_bsp_enabled && !jfg::boot::native_collision_in_fallback() && state.diagnostic_host_clock &&
           state.native_spans_enabled && !state.native_clock_sample_input.is_open() &&
           state.native_fast_ready && state.native_fast_status==context->status_reg &&
           state.execution_fast_revision==*state.io_revision &&
           !state.diagnostic_cpu_costs && state.focus_update_start==0U &&
           !state.guest_clock_trace.is_open() && state.point_probe_pcs.empty() &&
           !state.device_event_stream && !state.eret_transfer_stream.is_open() &&
           !state.instruction_effect_stream.is_open()) {
          ++state.bsp_native_calls;
          if(jfg::boot::native_collision_execute(generated,rdram,context,{game_module(OriginalModule::collision),target_metadata.linked_vram,game_overlay_data("collision.edges",OriginalModule::collision),game_overlay_extent(OriginalModule::collision)})) {
            state.native_fast_ready=false;state.host_clock_poll_budget=0U;
            ++state.bsp_clock_refreshes;
          }
        } else
#endif
          generated(rdram, context);

#if defined(_WIN32) && defined(JFG_PHASE8_LIVE_RUNTIME)
        if (measure_vi_sync) {
          NativeGameMemory sync_ram({rdram,kRdramSize});
          state.gameplay_trace.event("vi-sync-return", {state.vi_retraces,state.cpu_count,
              game_view(sync_ram).u32(game_data_ref("globals.currentLevel")),static_cast<std::uint32_t>(context->r2),
              game_view(sync_ram).u8(game_data_ref("globals.gVideoDeltaTime")),game_view(sync_ram).u8(game_data_ref("globals.gVideoDeltaCounter")),
              state.vi_retraces-sync_vi_before,state.cpu_count-sync_count_before});
          state.gameplay_trace.event("vi-sync-cache-return", {state.vi_retraces,state.cpu_count,
              cache_stats[0],cache_stats[1],cache_stats[2],cache_stats[3],
              cache_stats[4],cache_stats[5],cache_stats[6],cache_stats[7],
              cache_stats[8],cache_stats[9],cache_stats[10],cache_stats[11]});
        }
        trace_shadow_mask(1U);
        finish_precision_camera();
        camera_helper_presentation.restore();
        if (rain_fade) {
          const auto native_result = context->r2;
          context->r2 = rain_fade->finish(context->r2);
          if (context->r2 != native_result && state.gameplay_trace)
            state.gameplay_trace.event("rain-fade-gate", {state.vi_retraces, target,
                static_cast<std::uint64_t>(native_result), static_cast<std::uint64_t>(context->r2)});
        }
        door_indicator_presentation.restore();
        if(capture_door_material) {
          const auto packet=[&](const char* name,std::uint32_t address,std::uint32_t bytes) {
            if((address&3U) || !door_render_ram.valid(address,bytes))return;
            for(std::uint32_t offset=0;offset+32U<=bytes;offset+=32U) {
              const auto a=address+offset;
              state.gameplay_trace.event(name,{state.vi_retraces,door_render_actor,a,
                door_render_ram.u32(a),door_render_ram.u32(a+4U),
                door_render_ram.u32(a+8U),door_render_ram.u32(a+12U),
                door_render_ram.u32(a+16U),door_render_ram.u32(a+20U),
                door_render_ram.u32(a+24U),door_render_ram.u32(a+28U)});
            }
          };
          packet("door-packet-actor",door_render_actor,0xA0U);
          packet("door-packet-instance",door_material_instance,0x100U);
          packet("door-packet-model",door_material_model,0x10000U);
          const auto output=game_view(door_render_ram).u32(game_data_ref("globals.objectDisplayListCursor"));
          if(output>=door_dl_before && output-door_dl_before<=0x4000U)
            packet("door-packet-draw",door_dl_before,(output-door_dl_before+31U)&~31U);
          const auto animations=door_render_ram.u32(door_material_instance+game_member("layout.instance.textures"));
          packet("door-packet-animation",animations,0x100U);
          state.gameplay_trace.event("door-packet-end",{state.vi_retraces,door_render_actor,output});
        }
#endif

#if defined(_WIN32) && defined(JFG_PHASE8_LIVE_RUNTIME)
        if (state.diagnostic_cpu_costs) {
          const auto wall_ns = static_cast<std::uint64_t>(std::chrono::duration_cast<std::chrono::nanoseconds>(
              std::chrono::steady_clock::now()-function_started).count());
          const auto wait_ns = (state.profile_host_wait_us-function_wait)*1000U;
          const auto active_ns = wall_ns > wait_ns ? wall_ns-wait_ns : 0U;
          const auto children_ns = state.profile_function_self_ns-function_children;
          const auto self_ns = active_ns > children_ns ? active_ns-children_ns : 0U;
          state.profile_function_self_ns += self_ns;
          auto& cost = state.profile_function_costs[target];
          cost.self_ns += self_ns;cost.inclusive_ns += active_ns;++cost.calls;
        }
        if(target==game_code("audio.ai_submit") && state.diagnostic_host_clock && state.native_audio_playback &&
            static_cast<std::uint32_t>(context->r2)==0U) {
          // Deliver completed PCM before returning to guest/renderer work.
          // SDL conversion must not alter the guest floating-point context.
          std::fenv_t audio_environment{};
          if(std::feholdexcept(&audio_environment)!=0)
            fail_closed_dispatch(state,"audio","save-fenv",target);
          const bool rounded=std::fesetround(FE_TONEAREST)==0;
          const bool delivered=rounded && service_host_audio(state,false);
          const bool restored=std::fesetenv(&audio_environment)==0;
          if(!delivered || !restored)
            fail_closed_dispatch(state,"audio","immediate-host-delivery",target);
        }
        if(observe_tracer && tracer_ram.u32(tracer_vertex_output)==tracer_vertices+40U &&
           tracer_ram.u32(tracer_list)==0x01010040U) {
          const auto tracer_matrix=tracer_ram.u32(tracer_list+4U);
          state.presentation_identities.tracer({rdram,kRdramSize},tracer_actor,
              tracer_vertices,tracer_matrix,state.vi_retraces);
          if(state.gameplay_trace)state.gameplay_trace.event("tracer-draw",
              {state.vi_retraces,tracer_actor,tracer_caller,tracer_vertices,tracer_matrix,
               tracer_ram.u16(tracer_actor+0x48U),tracer_ram.u32(tracer_actor+0x68U),
               game_view(tracer_ram).u32(game_data_ref("globals.currentLevel"))});
        }
        if(shadow_motion_trace && state.gameplay_trace && target==game_code("game.shadowClipReceiver")) {
          state.gameplay_trace.event("shadow-clip",{state.vi_retraces,
              shadow_clip?1U:0U,shadow_ram.u32(game_data("diagnostic.shadowClipState")),
              static_cast<std::uint32_t>(context->r2),shadow_clip?shadow_clip->receiver_key:0U});
        }
        if(shadow_clip)
          state.presentation_identities.shadow_clipped({rdram,kRdramSize},*shadow_clip,
              static_cast<std::uint32_t>(context->r2));
        if(observe_shadow && (state.presentation_identity_enabled || jfg::shadow_quality_preference().load(std::memory_order_relaxed)==jfg::ShadowQuality::enhanced) && context->r2==1U)
          state.presentation_identities.shadow({rdram,kRdramSize},shadow_descriptor,
              shadow_control,shadow_light,shadow_first,state.vi_retraces);
        if(observe_shadow && shadow_motion_trace && state.gameplay_trace) {
          const auto actor=shadow_ram.u32(shadow_descriptor);
          const auto last=shadow_ram.u32(game_data("diagnostic.shadowBatchStart"));
          state.gameplay_trace.event("shadow-binding",{state.vi_retraces,actor,
              state.presentation_identities.shadow_record_count(actor),shadow_ram.u32(game_data("diagnostic.shadowClipState"))});

          state.gameplay_trace.event("shadow-generated",{state.vi_retraces,actor,shadow_descriptor,
              shadow_ram.u32(game_data("diagnostic.shadowVertexStart")),shadow_first,last,shadow_ram.u32(game_data("diagnostic.shadowVertexCount")),
              shadow_triangle_first,shadow_ram.u32(game_data("diagnostic.shadowTriangleStart")),shadow_ram.u32(shadow_descriptor+4U),
              shadow_ram.u32(actor+game_member("layout.actor.x")),shadow_ram.u32(actor+game_member("layout.actor.y")),shadow_ram.u32(actor+game_member("layout.actor.z")),
              static_cast<std::uint32_t>(context->r2)});
          if(last>=shadow_first && last-shadow_first<=256U)for(auto i=shadow_first;i<last;++i) {
            const auto v=shadow_ram.u32(game_data("diagnostic.shadowVertexStart"))+i*10U;
            state.gameplay_trace.event("shadow-vertex",{state.vi_retraces,actor,i-shadow_first,v,
                shadow_ram.u16(v),shadow_ram.u16(v+2U),shadow_ram.u16(v+4U)});
          }
        }
        if(observe_reflection) {
          state.presentation_identities.reflection({rdram,kRdramSize},matrix_destination,
              reflection_actor,reflection_stack+0x23CU,reflection_stack+0x1FCU,state.vi_retraces);
          if(state.gameplay_trace)
            state.gameplay_trace.event("reflection-matrix",{state.vi_retraces,reflection_actor,matrix_destination});
        }
        if (observe_shot_matrix) {
          const jfg::PresentationGuestView shot_ram({rdram,kRdramSize});
          std::array<std::uint64_t,24> row{};
          row[0]=state.vi_retraces;row[1]=target;row[2]=shot_caller;row[3]=shot_actor;
          row[4]=shot_matrix;row[5]=shot_ram.u32(shot_output);
          row[6]=shot_ram.u16(shot_actor+0x48U);row[7]=shot_ram.u32(shot_actor+0x88U);
          for(unsigned i=0;i<16U;++i)row[8U+i]=shot_ram.u32(shot_matrix+i*4U);
          state.gameplay_trace.event("shot-draw-matrix",row);
        }
        if(observe_audio_buffer && state.gameplay_trace)
          state.gameplay_trace.event("audio-ai-buffer",{state.vi_retraces,state.cpu_count,
              ai_buffer_address,ai_buffer_length,static_cast<std::uint32_t>(context->r2),
              state.mmio_trace->ai_dma.read(12U,state.cpu_count).value_or(UINT32_MAX),
              state.host_audio.queued_bytes(),state.host_audio.consumed_bytes()});
        if (observe_camera && camera_matrix &&
            jfg::PresentationGuestView({rdram,kRdramSize}).u32(camera_output)==camera_matrix+64U) {
          if((state.presentation_identity_enabled || jfg::shadow_quality_preference().load(std::memory_order_relaxed)==jfg::ShadowQuality::enhanced))
            state.presentation_identities.camera_completed({rdram,kRdramSize},camera_matrix,state.vi_retraces);
          if(camera_motion_trace && state.gameplay_trace) {
            // Read the final view/projection immediately after emission, before
            // another draw reuses scratch globals. No guest writes or math.
            const jfg::PresentationGuestView camera_ram({rdram,kRdramSize});
            std::array<std::uint64_t,54> row{};
            row[0]=state.vi_retraces;row[1]=game_view(camera_ram).u32(game_data_ref("globals.currentLevel"));
            row[2]=camera_matrix;row[3]=camera_ram.u32(game_data("diagnostic.cameraViewport0"));
            row[4]=camera_ram.u32(game_data("diagnostic.cameraViewport1"));row[5]=state.gameplay_trace_updates;
            for(unsigned i=0;i<16U;++i) {
              row[6U+i]=camera_ram.u32(game_data("diagnostic.cameraViewState")+i*4U);
              row[22U+i]=camera_ram.u32(game_data("diagnostic.cameraMatrixInput")+i*4U);
              row[38U+i]=camera_ram.u32(camera_matrix+i*4U);
            }
            state.gameplay_trace.event("camera-emitted-pose",row);
          }
        }
        if (observe_rigid && (!observe_shuriken ||
            jfg::PresentationGuestView({rdram,kRdramSize}).u32(rigid_output)==rigid_matrix+64U)) {
          state.presentation_identities.rigid({rdram,kRdramSize},rigid_matrix,rigid_actor,state.vi_retraces,keyboard_sub_id);
          if (keyboard_sub_id && state.gameplay_trace)
            state.gameplay_trace.event("keyboard-key-matrix",{state.vi_retraces,keyboard_sub_id-1U,rigid_actor,rigid_matrix});
          if(observe_shuriken)
            state.gameplay_trace.event("shuriken-matrix",{state.vi_retraces,rigid_actor,rigid_matrix});
        }
        if ((state.presentation_identity_enabled || jfg::shadow_quality_preference().load(std::memory_order_relaxed)==jfg::ShadowQuality::enhanced) && target == game_code("game.partAllocate"))
          state.presentation_identities.particle_allocate({rdram,kRdramSize},
              static_cast<std::uint32_t>(context->r2));
        if (measure_update) {
          if(state.mmio_trace) {
            const auto rom_after=state.mmio_trace->pi_dma.rom_transfers();
            if(rom_after.calls!=rom_before.calls)
              state.gameplay_trace.event("rom-dma",{
                state.vi_retraces,state.controller_samples,rom_after.calls-rom_before.calls,
                rom_after.bytes-rom_before.bytes,rom_after.bus_ticks-rom_before.bus_ticks,
                rom_after.scheduled_ticks-rom_before.scheduled_ticks,
                rom_after.native_calls-rom_before.native_calls});
          }
          if(state.diagnostic_bsp_enabled) {
            const auto bsp_after=jfg::boot::native_collision_counters();
            state.gameplay_trace.event("bsp-execution",{
            state.vi_retraces,state.controller_samples,state.bsp_native_calls-bsp_calls_before,
            bsp_after.native_nodes-bsp_before.native_nodes,
            bsp_after.native_edges-bsp_before.native_edges,
            bsp_after.fallbacks-bsp_before.fallbacks,
            bsp_after.expired-bsp_before.expired,
            bsp_after.invalid-bsp_before.invalid,
            bsp_after.max_nanoseconds,state.bsp_clock_refreshes-bsp_refresh_before});
          }
          if(state.resident_math_enabled)state.gameplay_trace.event("resident-math",{
            state.vi_retraces,state.controller_samples,state.pure_angle_calls-pure_angle_before,
            state.pure_diff_calls-pure_diff_before,state.pure_trig_calls-pure_trig_before});

          if(state.native_shadow_filter_calls!=shadow_filter_before)
            state.gameplay_trace.event("native-shadow-filter",{state.vi_retraces,state.controller_samples,
                state.native_shadow_filter_calls-shadow_filter_before});
        if(state.mmio_trace && state.mmio_trace->direct_sp_access)
          state.gameplay_trace.event("direct-sp-access",{state.vi_retraces,state.controller_samples,
              state.mmio_trace->direct_sp_reads,state.mmio_trace->direct_sp_writes});
          state.gameplay_trace.event("update-work", {state.vi_retraces, state.controller_samples,
              state.cpu_count - update_count, state.profile_idle_count_ticks - update_idle,
              state.observed_guest_instructions - update_instructions,
              static_cast<std::uint64_t>(std::chrono::duration_cast<std::chrono::microseconds>(
                  std::chrono::steady_clock::now() - update_started).count()),
              state.profile_host_wait_us - update_wait});
          if (measure_update_cycles) {
            const auto update_cycles_after=state.guest_transport?state.guest_transport->execution_cycles():BatonExecutor::host_cycles();
            const bool valid = update_cycles_before.valid && update_cycles_after.valid &&
                update_cycles_before.participant==update_cycles_after.participant &&
                update_cycles_after.cycles>=update_cycles_before.cycles;
            // Cycles describe this participant only (OS thread or fiber).
            // Never convert them to milliseconds or add other participants.
            state.gameplay_trace.event("update-thread-cycles", {state.vi_retraces,
                state.controller_samples, valid, update_cycles_before.participant,
                valid ? update_cycles_after.cycles - update_cycles_before.cycles : 0U,
                state.observed_guest_instructions - update_instructions});
          }
          if (state.mmio_trace && state.mmio_trace->direct_mi_mask_access)
            state.gameplay_trace.event("direct-mi-mask",{state.vi_retraces,state.controller_samples,
                state.mmio_trace->direct_mi_mask_reads,state.mmio_trace->direct_mi_mask_writes});
          if (state.mmio_trace && state.mmio_trace->profile_faults) {
            // Cumulative counters avoid adding an array to every guest
            // function's dispatch stack. The reviewer differences adjacent
            // root-update records and checks the OS-thread identity.
            for(std::size_t page=0;page<state.mmio_trace->fault_costs.size();++page) {
              const auto& cost=state.mmio_trace->fault_costs[page];
              if(cost.reads || cost.writes)state.gameplay_trace.event("mmio-page-cost",{
                state.vi_retraces,state.controller_samples,page,kMmioGuestBases[page],
                cost.reads,cost.writes,cost.qpc,cost.max_qpc});
            }
            FILETIME created{},ended{},kernel{},user{};ULONG64 cycles=0;
            const bool valid=GetThreadTimes(GetCurrentThread(),&created,&ended,&kernel,&user) &&
                QueryThreadCycleTime(GetCurrentThread(),&cycles);
            const auto ticks=[](FILETIME value) {
              return (std::uint64_t(value.dwHighDateTime)<<32U)|value.dwLowDateTime;
            };
            state.gameplay_trace.event("root-host-cpu",{
              state.vi_retraces,state.controller_samples,GetCurrentThreadId(),
              valid?1U:0U,ticks(user),ticks(kernel),cycles});
          }
          if (state.native_cache_all_enabled)
            state.gameplay_trace.event("native-cache-all",{state.vi_retraces,state.controller_samples,state.native_cache_all_calls-cache_all_before});
          if (state.native_spans_enabled) {
            state.gameplay_trace.event("native-span-work", {state.vi_retraces,state.controller_samples,
                state.native_span_instructions-span_instructions_start,
                state.native_span_commits-span_commits_start});
          }
          if (state.diagnostic_cpu_costs) {
            std::vector<std::pair<std::uint32_t,State::FunctionCost>> function_costs(
                state.profile_function_costs.begin(),state.profile_function_costs.end());
            std::sort(function_costs.begin(),function_costs.end(),[](const auto& a,const auto& b) {
              return a.second.self_ns>b.second.self_ns;
            });
            for (std::size_t index=0;index<function_costs.size() && index<20U;++index) {
              const auto& item=function_costs[index];
              state.gameplay_trace.event("function-self-cost",{state.vi_retraces,state.controller_samples,
                  item.first,item.second.self_ns,item.second.inclusive_ns,item.second.calls});
            }
            FILETIME kernel_end{}, user_end{}; ULONG64 process_cycles_end = 0;
            const bool valid = process_costs &&
                GetProcessTimes(GetCurrentProcess(), &process_created, &process_exited, &kernel_end, &user_end) &&
                QueryProcessCycleTime(GetCurrentProcess(), &process_cycles_end);
            const auto ticks = [](FILETIME v) {
              return (std::uint64_t(v.dwHighDateTime)<<32U) | v.dwLowDateTime;
            };
            state.gameplay_trace.event("host-cpu-cost", {state.vi_retraces, state.controller_samples,
                state.observed_guest_instructions-update_instructions,
                state.profile_out_of_line_instructions-callback_start,
                state.profile_full_execution_probes-full_probe_start,
                state.guest_transport ? state.guest_transport->handoffs()-handoff_start : 0U,
                valid ? (ticks(kernel_end)-ticks(kernel_start))/10U : 0U,
                valid ? (ticks(user_end)-ticks(user_start))/10U : 0U,
                valid ? process_cycles_end-process_cycles_start : 0U, valid});
            if (state.guest_transport) {
              const auto transport_end = state.guest_transport->timing();
              state.gameplay_trace.event("transport-wake-cost", {state.vi_retraces, state.controller_samples,
                  transport_end.wakes - transport_start.wakes,
                  transport_end.wake_ns - transport_start.wake_ns, transport_end.max_wake_ns});
            }
            state.gameplay_trace.event("dispatch-prefix-cost", {state.vi_retraces, state.controller_samples,
                state.profile_dispatch_prefix_ns-dispatch_prefix_ns_start,
                state.profile_dispatch_prefix_calls-dispatch_prefix_calls_start,
                state.profile_overlay_inventory_ns-inventory_ns_start,
                state.profile_overlay_inventory_calls-inventory_calls_start});
            state.gameplay_trace.event("relocation-resolution-cost", {state.vi_retraces, state.controller_samples,
                state.profile_relocation_ns-relocation_ns_start,
                state.profile_relocation_calls-relocation_calls_start,
                state.profile_relocation_probes-relocation_probes_start});
            state.gameplay_trace.event("native-handler-cost", {state.vi_retraces, state.controller_samples,
                state.profile_native_handler_ns-native_handler_start,
                state.dispatch_calls-dispatch_start,
                state.mmio_trace ? state.mmio_trace->accesses-mmio_start : 0U,
                state.graphics_submit_microseconds-graphics_start,
                state.profile_host_wait_us-update_wait});
          }
        }
#endif
#if defined(_WIN32) && defined(JFG_PHASE8_LIVE_RUNTIME)
        modern_shoulder_aim_camera(state,target,mod_actor_argument,sound_event_argument);
#endif
      }
#if defined(JFG_PHASE8_LIVE_RUNTIME)
      if (refresh_daynight_lighting) {
        NativeGameMemory lighting_memory({rdram, kRdramSize});
        const auto lighting = lighting_memory.u32(daynight_actor + 0x54U);
        const auto level_header = game_view(lighting_memory).u32(game_data_ref("globals.levelHeader"));
        const auto stack = static_cast<std::uint32_t>(context->r29);
        // The alternate light selector has a different overlay-owned path.
        // Do not substitute the regular selector for that path.
        if (lighting_memory.valid(daynight_actor, 0xA2U) &&
            lighting_memory.valid(lighting, 0x90U) &&
            lighting + 0x10U == daynight_descriptor &&
            lighting_memory.valid(level_header, 0xE0U) &&
            lighting_memory.u8(level_header + 0x6BU) == 0U &&
            stack >= 0x80000800U && lighting_memory.valid(stack - 0x800U, 0x800U)) {
          if (auto* select_lights = jfg_generated_lookup_function(
                  static_cast<std::int32_t>(game_code("game.lightSelectNearby")))) {
            // Use independent register storage and a lower stack window. The
            // setter's return values and the controller's live frame survive.
            auto lighting_context = *context;
            lighting_context.f_odd = lighting_context.mips3_float_mode
                ? &lighting_context.f1.u32l : &lighting_context.f0.u32h;
            lighting_context.r29 = static_cast<std::int32_t>(stack - 0x400U);
            lighting_context.r4 = static_cast<std::int32_t>(daynight_actor);
            lighting_context.r5 = static_cast<std::int32_t>(lighting);
            select_lights(rdram, &lighting_context);
          }
        }
      }
#endif

#if defined(_WIN32) && defined(JFG_PHASE8_LIVE_RUNTIME)
      if (target == game_overlay_token("overlay.day.fog")) {
        const auto fog = capture_daynight_fog(state);
        state.daynight_fog_frames.queried(fog);
        state.gameplay_trace.event("daynight-fog-query", {state.vi_retraces,
            fog.valid ? 1U : 0U, fog.native_coefficients,
            fog.smooth_coefficients, fog.color});
      }
      if (trace_atmosphere)
        trace_daynight_atmosphere(state, target, atmosphere_outputs);
#endif
      if (target == game_code("audio.sound_next_event")) {
        hle::GuestMemory memory({rdram, kRdramSize},
                               hle::GuestMemory::Layout::native_word_big_endian);
        if (jfg::boot::recover_empty_sound_queue(kSoundQueueLayout,
                memory, *context, mod_actor_argument, sound_event_argument))
          ++state.sound_queue_recoveries;
      }
#if defined(_WIN32) && defined(JFG_PHASE8_LIVE_RUNTIME)
      if (state.navigation_mod.observing() && target==game_code("game.controlPlayer")) {
        NativeGameMemory memory({rdram,kRdramSize});
        (void)state.navigation_mod.observe_player(memory,mod_actor_argument);
        (void)state.navigation_mod.full_health(memory,mod_actor_argument);
      }
      if (target==game_code("game.mainUpdate")) update_navigation_mod(state);
#endif
#if defined(_WIN32) && defined(JFG_PHASE8_LIVE_RUNTIME)
      if (state.entry_probe_target == target && focus_window)
        trace_guest_clock(state, "entry-return", target);
      if (watch_active) {
        hle::GuestMemory watch_memory(
            {rdram, kRdramSize},
            hle::GuestMemory::Layout::native_word_big_endian);
        std::uint32_t watch_after = 0U;
        if (!watch_memory.read_u32(state.watch_word_address, watch_after))
          fail_closed_dispatch(state, "diagnostic", "watch-word-read", target);
        if (watch_before != watch_after) {
          if (++state.watch_dispatch_changes > 1024U)
            fail_closed_dispatch(state, "diagnostic", "watch-word-overflow", target);
          state.watch_word_trace << state.completed_game_updates + 1U << '\t'
              << state.vi_retraces << '\t' << state.controller_samples << '\t'
              << state.watch_dispatch_depth << '\t' << std::hex << "0x"
              << target << '\t' << "0x" << watch_return_address << '\t'
              << "0x" << watch_before << '\t' << "0x" << watch_after
              << std::dec << '\n';
          state.watch_word_trace.flush();
        }
        --state.watch_dispatch_depth;
      }
      if (target == game_code("game.mainUpdate") && state.diagnostic_clock_boundary_vi != 0U &&
          !state.diagnostic_clock_boundary_seen && state.vi_retraces >= state.diagnostic_clock_boundary_vi) {
        // Qualification only: preserve the entire original-clock prefix and
        // fingerprint it before selecting the candidate policy. Never edit RAM.
        jfg::testkernel::Sha256 hasher;
        hasher.update_bytes(state.rdram,kRdramSize);
        const auto digest = hasher.finish();
        std::array<std::uint32_t,8> words{};
        for (std::size_t i=0;i<digest.size();++i)
          words[i/4U] = (words[i/4U]<<8U) | std::to_integer<unsigned>(digest[i]);
        state.gameplay_trace.event("clock-boundary",{state.vi_retraces,state.controller_samples,
            state.cpu_count,state.diagnostic_host_clock_requested,words[0],words[1],words[2],words[3],
            words[4],words[5],words[6],words[7]});
        state.diagnostic_clock_boundary_seen = true;
        if (state.input_replay_gameplay_time) {
          if (state.controller_samples >= state.input_replay.events().size())
            fail_closed_dispatch(state,"recorded-input","boundary-past-recording",target);
          state.replay_gameplay_first_poll = static_cast<std::size_t>(state.controller_samples);
        }
        if (state.diagnostic_host_clock_requested) {
          state.diagnostic_host_clock = true;
          state.mmio_trace->native_elapsed_time = true;
          if(state.native_audio_playback && !state.mmio_trace->ai_dma.native_queue_capacity(4U))
            fail_closed_dispatch(state,"audio","native-queue-capacity",target);
          state.execution_fast_profile_ready = false;
          state.host_clock_poll_budget = 0U;
          if (!state.host_count_clock.start(state.cpu_count,std::chrono::steady_clock::now()))
            fail_closed_dispatch(state,"native-clock","boundary-initialization",target);
          if (state.diagnostic_boundary_stall_ms != 0U) {
            state.gameplay_trace.event("native-stall-begin",{state.vi_retraces,state.cpu_count,state.diagnostic_boundary_stall_ms});
            std::this_thread::sleep_for(std::chrono::milliseconds(state.diagnostic_boundary_stall_ms));
            state.gameplay_trace.event("native-stall-end",{state.vi_retraces,
                state.host_count_clock.sample(std::chrono::steady_clock::now()).value_or(UINT64_MAX)});
          }
        }
      }
      if (target == game_code("game.mainUpdate") && state.diagnostic_clock_release_vi != 0U &&
          !state.diagnostic_clock_released && state.vi_retraces >= state.diagnostic_clock_release_vi) {
        // Qualification-only transition, after a complete game update. Hash
        // the exact shared starting state before reanchoring elapsed time.
        // No guest RAM, CPU Count, input ordinal or device deadline is changed.
        jfg::testkernel::Sha256 hasher;hasher.update_bytes(state.rdram,kRdramSize);
        const auto digest=hasher.finish();std::array<std::uint32_t,8> words{};
        for (std::size_t i=0;i<digest.size();++i)
          words[i/4U]=(words[i/4U]<<8U)|std::to_integer<unsigned>(digest[i]);
        if (!state.diagnostic_host_clock || !state.native_clock_samples.release_prefix(state.cpu_count))
          fail_closed_dispatch(state,"native-clock-tape","invalid-prefix-release",target);
        state.native_clock_sample_input.close();
        state.gameplay_trace.event("native-clock-release",{state.vi_retraces,state.controller_samples,
            state.cpu_count,state.observed_guest_instructions,state.native_clock_samples.samples(),
            words[0],words[1],words[2],words[3],words[4],words[5],words[6],words[7]});
        state.host_count_clock=HostCountClock{};
        state.native_fast_ready=false;state.host_clock_poll_budget=0U;
        if (!state.host_count_clock.start(state.cpu_count,std::chrono::steady_clock::now()))
          fail_closed_dispatch(state,"native-clock-tape","release-clock-start",target);
        state.diagnostic_clock_released=true;
      }
      if (target == game_code("game.mainUpdate")) {
#if defined(JFG_PHASE8_LIVE_RUNTIME)
        ++state.camera_fade_updates;
#endif
        trace_gameplay_state(state, true);
        if (state.timing_trace.is_open())
          state.timing_trace << "game-update\t" << state.vi_frames << '\t'
                             << state.vi_retraces << "\t0\t"
                             << ++state.timing_game_updates << "\t0\t0\t0\n";
      }
      if (target == game_code("game.mainUpdate") && state.update_hash_trace.is_open()) {
        ++state.completed_game_updates;
        trace_phase9_event(state, "update-end", state.controller_samples);
        write_retrace_semantic_hash(state, &state.update_hash_trace);
        if (state.update_word_trace.is_open()) {
          hle::GuestMemory word_memory(
              {rdram, kRdramSize},
              hle::GuestMemory::Layout::native_word_big_endian);
          std::uint32_t value = 0U;
          if (!word_memory.read_u32(state.update_word_address, value))
            fail_closed_dispatch(state, "diagnostic", "update-word-read", target);
          state.update_word_trace << state.completed_game_updates << '\t'
              << state.controller_samples << '\t' << state.vi_retraces
              << '\t' << state.vi_frames << '\t' << std::hex << "0x"
              << std::setw(8) << std::setfill('0') << state.update_word_address
              << '\t' << "0x" << std::setw(8) << value << std::setfill(' ')
              << std::dec << '\n';
        }
        if (state.focus_update_start != 0U &&
            state.completed_game_updates >= state.focus_update_start &&
            state.completed_game_updates <= state.focus_update_end) {
          const auto path = std::filesystem::path(state.retrace_hash_path).parent_path() /
              ("focus-update-" + std::to_string(state.completed_game_updates) + ".rdram");
          if (!write_logical_rdram_capture(state, path)) {
            std::fputs("native focus RDRAM capture failed\n", stderr);
            state.exit_requested = true;
          }
        }

      }
      if (target == game_code("game.mmAlloc") && state.actor_timing_trace &&
          state.vi_retraces <= 100U && state.timing_trace.is_open()) {
        state.timing_trace << "mm-alloc\t" << state.vi_frames << '\t'
                           << state.vi_retraces << "\t0\t" << allocation_size
                           << '\t' << static_cast<std::uint32_t>(context->r2)
                           << "\t0\t0\n";
      }
#endif
#if defined(JFG_PHASE8_LIVE_RUNTIME)
      state.executing_generated_section = caller_section;
      state.executing_generated_overlay = caller_is_overlay;
#endif
#if defined(JFG_PHASE8_LIVE_RUNTIME)
      if (target == game_code("game.objCutCameraActive") && context->r2 != 0) // objCutCameraActive
        ++state.phase9_cutscene_active_calls;
      if (target == game_overlay_token("overlay.hint.active")) {
        state.phase9_hinttext_active_last_return =
            static_cast<std::uint32_t>(context->r2);
        if (context->r2 == 0U)
          ++state.phase9_hinttext_active_zero_returns;
        else
          ++state.phase9_hinttext_active_nonzero_returns;
      }
#endif
#if defined(JFG_PHASE8_LIVE_RUNTIME)
      if (trace_matrix_cat) {
        hle::GuestMemory memory(
            {rdram, kRdramSize},
            hle::GuestMemory::Layout::native_word_big_endian);
        (void)memory.read_u32(state.recent_matrix_cat_args[matrix_cat_slot][2],
                              state.recent_matrix_cat_words[matrix_cat_slot][8]);
        ++state.recent_matrix_cat_position;
      }
#endif
#if defined(JFG_PHASE8_LIVE_RUNTIME)
      if (trace_matrix_conversion) {
        const std::size_t slot = state.recent_matrix_conversion_position %
            state.recent_matrix_conversion_sources.size();
        state.recent_matrix_conversion_sources[slot] = matrix_source;
        state.recent_matrix_conversion_destinations[slot] =
            matrix_destination;
        state.recent_matrix_conversion_first_rows[slot] = matrix_first_row;
        hle::GuestMemory memory(
            {rdram, kRdramSize},
            hle::GuestMemory::Layout::native_word_big_endian);
        (void)memory.read_u32(matrix_destination,
                              state.recent_matrix_conversion_output_words[slot][0]);
        (void)memory.read_u32(matrix_destination + 4U,
                              state.recent_matrix_conversion_output_words[slot][1]);
        (void)memory.read_u32(matrix_destination + 32U,
                              state.recent_matrix_conversion_output_words[slot][2]);
        (void)memory.read_u32(matrix_destination + 36U,
                              state.recent_matrix_conversion_output_words[slot][3]);
        if (matrix_source == game_data("diagnostic.cameraMatrixSource")) {
          std::size_t watch = 0U;
          while (watch < state.matrix_watch_addresses.size() &&
                 state.matrix_watch_addresses[watch] != 0U &&
                 state.matrix_watch_addresses[watch] != matrix_destination)
            ++watch;
          if (watch < state.matrix_watch_addresses.size()) {
            state.matrix_watch_addresses[watch] = matrix_destination;
            state.matrix_watch_words[watch] =
                state.recent_matrix_conversion_output_words[slot][0];
          }
        }
        ++state.recent_matrix_conversion_position;
      }
#endif
      return 1;
    }
    if (state.runtime != nullptr &&
        state.runtime->invoke_leased_function_by_guest_address(
            target, rdram, context) == jfg::GeneratedOverlayError::none)
      return 1;
    // The normalized generated ABI gives overlays stable synthetic call
    // addresses. A direct transfer to an exact generated overlay is therefore
    // its publication boundary in this native profile; arbitrary addresses
    // remain fail-closed.
    for (std::uint32_t section = 0U;
         section < jfg_generated_section_count(); ++section) {
      JfgGeneratedSectionMetadata metadata{};
      if (jfg_generated_section_metadata(section, &metadata) == 0)
        fail_closed_dispatch(state, "generated", "section-metadata",
                             target);
      const std::uint64_t text_begin = metadata.linked_vram;
      const std::uint64_t text_end = text_begin + metadata.text_size;
      if (metadata.is_overlay != 1U || target < text_begin || target >= text_end)
        continue;
#if defined(JFG_PHASE8_LIVE_RUNTIME)
      if (!ensure_guest_overlay_allocation(state, metadata, *context) ||
          !publish_synthetic_overlay(state, section, metadata)) {
#else
      if (jfg_generated_relocation_count(section) != 0U ||
          jfg_generated_section_lifecycle(
              1U, section, static_cast<std::int32_t>(metadata.linked_vram)) !=
              0) {
#endif
        fail_closed_overlay_publication(state, target);
      }
      state.journal.append(NativeEventKind::kOverlayPublished, section,
                           metadata.linked_vram, target);
      recomp_func_t *const published =
          jfg_generated_lookup_function(address);
      if (published == nullptr)
        fail_closed_dispatch(state, "generated", "overlay-lookup", target);
#if defined(JFG_PHASE8_LIVE_RUNTIME)
      const std::uint32_t overlay_offset = target - metadata.linked_vram;
      if (section == game_module(OriginalModule::mr_hints) && overlay_offset == 0x2E8U) {
        note_hints_control_call(state, target, *context);
      } else if (section == game_module(OriginalModule::mr_hints) && overlay_offset == 0x2540U) {
        ++state.phase9_hints_talk_calls;
      }
#endif
      context->r0 = 0;
      if (state.generated_relocation_targets.contains(target)) {
#if defined(_WIN32) && defined(JFG_PHASE8_LIVE_RUNTIME)
        const bool measure_relocation = state.diagnostic_cpu_costs;
        const auto relocation_start = measure_relocation ? std::chrono::steady_clock::now()
            : std::chrono::steady_clock::time_point{};
        std::uint64_t relocation_probes = 0U;
#endif
        // Resolve the continuation with the same table/lifecycle as its function.
        context->r0 = jfg_generated_lookup_entry_offset(static_cast<std::int32_t>(target), nullptr);
#if defined(_WIN32) && defined(JFG_PHASE8_LIVE_RUNTIME)
        if (measure_relocation) relocation_probes = 1U;
#endif
#if defined(_WIN32) && defined(JFG_PHASE8_LIVE_RUNTIME)
        if (measure_relocation) {
          ++state.profile_relocation_calls;
          state.profile_relocation_probes += relocation_probes;
          state.profile_relocation_ns += static_cast<std::uint64_t>(std::chrono::duration_cast<std::chrono::nanoseconds>(
              std::chrono::steady_clock::now()-relocation_start).count());
        }
#endif
      }
      published(rdram, context);
#if defined(JFG_PHASE8_LIVE_RUNTIME)
      if (target == game_overlay_token("overlay.hint.active")) {
        state.phase9_hinttext_active_last_return =
            static_cast<std::uint32_t>(context->r2);
        if (context->r2 == 0U)
          ++state.phase9_hinttext_active_zero_returns;
        else
          ++state.phase9_hinttext_active_nonzero_returns;
      }
#endif
      return 1;
    }
#if defined(JFG_PHASE8_LIVE_RUNTIME)
    // Runlink may preserve its own compact load base instead of the normalized
    // synthetic address. Translate calls through the live module table back to
    // the generated section identity and offset. Matching the full identity
    // prevents a nearby asset DMA from being mistaken for executable code.
    hle::GuestMemory runlink_memory(
        {rdram, kRdramSize},
        hle::GuestMemory::Layout::native_word_big_endian);
    RunlinkAddressResolution resolution{};
    const RunlinkAddressResult resolution_result =
        resolve_runlink_text_address(runlink_memory,
                                     kRunlinkModuleTablePointer,
                                     kRunlinkOverlaySlotCount, target,
                                     resolution);
    if (resolution_result == RunlinkAddressResult::resolved) {
      std::uint32_t matched_section = UINT32_MAX;
      JfgGeneratedSectionMetadata matched_metadata{};
      for (std::uint32_t section = 0U;
           section < jfg_generated_section_count(); ++section) {
        JfgGeneratedSectionMetadata metadata{};
        if (jfg_generated_section_metadata(section, &metadata) == 0)
          fail_closed_dispatch(state, "generated", "section-metadata",
                               target);
        if (metadata.is_overlay != 1U ||
            metadata.rom_start != resolution.identity.rom_start ||
            metadata.text_size != resolution.identity.text_size ||
            metadata.data_size != resolution.identity.data_size ||
            metadata.bss_size != resolution.identity.bss_size)
          continue;
        if (matched_section != UINT32_MAX)
          fail_closed_dispatch(state, "generated", "runlink-identity-duplicate",
                               target);
        matched_section = section;
        matched_metadata = metadata;
      }
      if (matched_section == UINT32_MAX ||
          resolution.text_offset >= matched_metadata.text_size ||
          resolution.text_offset > UINT32_MAX - matched_metadata.linked_vram)
        fail_closed_dispatch(state, "generated", "runlink-identity",
                             target);
      const std::uint32_t translated_target =
          matched_metadata.linked_vram + resolution.text_offset;
      if (!publish_synthetic_overlay(state, matched_section,
                                     matched_metadata)) {
        fail_closed_overlay_publication(state, target);
      }
      recomp_func_t *const published = jfg_generated_lookup_function(
          static_cast<std::int32_t>(translated_target));
      if (published == nullptr)
        fail_closed_dispatch(state, "generated", "runlink-overlay-lookup",
                             target);
      if (matched_section == game_module(OriginalModule::mr_hints) && resolution.text_offset == 0x2E8U) {
        note_hints_control_call(state, target, *context);
      } else if (matched_section == game_module(OriginalModule::mr_hints) &&
                 resolution.text_offset == 0x2540U) {
        ++state.phase9_hints_talk_calls;
      } else if (matched_section == game_module(OriginalModule::hint_text)) {
        switch (resolution.text_offset) {
        case 0x148U:
          ++state.phase9_hinttext_start_calls;
          break;
        case 0xD6CU:
          ++state.phase9_hinttext_stop_calls;
          break;
        case 0x70CU:
          ++state.phase9_hinttext_advance_calls;
          break;
        case 0xD80U:
          ++state.phase9_hinttext_active_calls;
          break;
        case 0x1CCCU:
          ++state.phase9_hinttext_update_calls;
          break;
        case 0x16B4U:
          ++state.phase9_hinttext_accept_calls;
          break;
        default:
          break;
        }
      }
      state.journal.append(NativeEventKind::kOverlayPublished,
                           matched_section, matched_metadata.linked_vram,
                           target);
      context->r0 = 0;
      if (state.generated_relocation_targets.contains(translated_target)) {
#if defined(_WIN32) && defined(JFG_PHASE8_LIVE_RUNTIME)
        const bool measure_relocation = state.diagnostic_cpu_costs;
        const auto relocation_start = measure_relocation ? std::chrono::steady_clock::now()
            : std::chrono::steady_clock::time_point{};
        std::uint64_t relocation_probes = 0U;
#endif
        // Resolve the continuation with the same table/lifecycle as its function.
        context->r0 = jfg_generated_lookup_entry_offset(static_cast<std::int32_t>(translated_target), nullptr);
#if defined(_WIN32) && defined(JFG_PHASE8_LIVE_RUNTIME)
        if (measure_relocation) relocation_probes = 1U;
#endif
#if defined(_WIN32) && defined(JFG_PHASE8_LIVE_RUNTIME)
        if (measure_relocation) {
          ++state.profile_relocation_calls;
          state.profile_relocation_probes += relocation_probes;
          state.profile_relocation_ns += static_cast<std::uint64_t>(std::chrono::duration_cast<std::chrono::nanoseconds>(
              std::chrono::steady_clock::now()-relocation_start).count());
        }
#endif
      }
      ++state.generated_calls;
      published(rdram, context);
      if (matched_section == game_module(OriginalModule::hint_text) && resolution.text_offset == 0xD80U) {
        state.phase9_hinttext_active_last_return =
            static_cast<std::uint32_t>(context->r2);
        if (context->r2 == 0U)
          ++state.phase9_hinttext_active_zero_returns;
        else
          ++state.phase9_hinttext_active_nonzero_returns;
      }
      return 1;
    }
    if (resolution_result == RunlinkAddressResult::memory_fault ||
        resolution_result == RunlinkAddressResult::duplicate_module ||
        resolution_result == RunlinkAddressResult::invalid_argument)
      fail_closed_dispatch(state, "generated", "runlink-address-table",
                           target);
#endif
    if (state.last_pi_size != 0U) {
      std::array<char, 96U> operation{};
      (void)std::snprintf(operation.data(), operation.size(),
                          "unresolved-dma-%08x-%08x-%08x",
                          state.last_pi_rom, state.last_pi_dram,
                          state.last_pi_size);
      fail_closed_dispatch(state, "generated", operation.data(), target);
    }
    fail_closed_dispatch(state, "generated", "unresolved", target);
  }
  ++state.mapped_calls;
  ++state.mapped_call_counts[mapping_index];
  hle::GuestMemory memory({rdram, kRdramSize},
                          hle::GuestMemory::Layout::native_word_big_endian);
  const auto a0 = static_cast<std::uint32_t>(context->r4),
             a1 = static_cast<std::uint32_t>(context->r5),
             a2 = static_cast<std::uint32_t>(context->r6),
             a3 = static_cast<std::uint32_t>(context->r7);
  if (state.guest_os_probe) {
    // Every mapped OS call requires its original instrumented body. The
    // opt-in native coherent-cache leaf below retains that body's register
    // effects; recorded timing and detailed observers keep the original path.
    // Missing device behavior fails closed.
    recomp_func_t *const generated = jfg_generated_lookup_function(address);
    if (generated == nullptr)
      fail_closed_dispatch(state, "guest-os", "original-body-unavailable", target);
    // Input is latched at the same SDK poll boundary as the recorded route.
    // Original code still builds/reads every PIF packet and delivers messages.
    if (target == original_os_entry("osContStartReadData")) {
      ++state.controller_read_start_calls;
#if defined(_WIN32) && defined(JFG_PHASE8_LIVE_RUNTIME)
      sample_live_controller(state);
#endif
      state.mmio_trace->si_dma.sample(state.controller_ports.samples);
    }
    if (target == original_os_entry("osContGetReadData"))
      ++state.controller_get_data_calls;
    if (target == original_os_entry("osSpTaskLoad")) {
      if (state.mmio_trace->sp_deadline || state.mmio_trace->sp_launch ||
          !memory.read_u32(a0, state.loaded_rsp_task_type))
        fail_closed_dispatch(state, "guest-rsp", "task-load-state", target);
      state.loaded_rsp_task = a0;
      ++state.sp_task_load_calls;
    }
    if (target == original_os_entry("osSpTaskStartGo")) ++state.sp_task_start_calls;
    if (target == original_os_entry("osRecvMesg")) ++state.queue_recv_calls;
    if (target == original_os_entry("osSendMesg")) ++state.queue_send_calls;
    if (state.guest_clock_trace.is_open() && state.observed_guest_instructions < 1000000U)
      state.guest_clock_trace << "call\t" << std::hex << target << '\t' << a0 << '\t'
          << a1 << '\t' << a2 << std::dec << '\t' << state.cpu_count << '\n';
#if defined(_WIN32) && defined(JFG_PHASE8_LIVE_RUNTIME)
    if(target==original_os_entry("osWritebackDCacheAll") &&
       state.native_cache_all_enabled && state.diagnostic_host_clock &&
       state.native_spans_enabled && !state.native_clock_sample_input.is_open() &&
       state.native_fast_ready && state.native_fast_status==context->status_reg &&
       state.execution_fast_revision==*state.io_revision &&
       !state.diagnostic_cpu_costs && state.focus_update_start==0U &&
       !state.guest_clock_trace.is_open() && state.point_probe_pcs.empty() &&
       !state.device_event_stream && !state.eret_transfer_stream.is_open() &&
       !state.instruction_effect_stream.is_open() &&
       jfg::boot::native_cache_all_try(rdram,context)) {
      ++state.native_cache_all_calls;
      state.native_fast_ready=false;state.host_clock_poll_budget=0U;
    } else
#endif
    generated(rdram, context);
#if defined(_WIN32) && defined(JFG_PHASE8_LIVE_RUNTIME)
    // The original SDK routine must complete its PIF/DMA submission before a
    // poll probe stops. This matches the declared controller-read return
    // boundary without replacing guest device behavior with an HLE service.
    if (target == original_os_entry("osContStartReadData") &&
        state.poll_target != 0U && state.controller_samples == state.poll_target)
      probe_target_gate(state);
    if(a0==game_data("audio.frame_queue") && (target==original_os_entry("osSendMesg") ||
        target==original_os_entry("osRecvMesg"))) {
      static const bool observe=[] {
        char value[2]{};
        return GetEnvironmentVariableA("JFG_DIAGNOSTIC_AUDIO_SCHEDULER",value,2U)==1U && value[0]=='1';
      }();
      if(observe && state.gameplay_trace) {
        std::uint32_t queued=0;(void)memory.read_u32(a0+8U,queued);
        state.gameplay_trace.event("audio-notify",{state.vi_retraces,state.cpu_count,target,
            a0,a1,a2,static_cast<std::uint32_t>(context->r2),queued,state.guest_active_rsp_type});
      }
    }
#endif
    if (target == kOsInitialize) state.os_initialized = true;
    if (target == original_os_entry("osContInit"))
      state.controller_initialized = static_cast<std::uint32_t>(context->r2) == 0U;
    // Read-only host observers. The original bodies above own all guest
    // register, queue and thread mutations, including interrupt delivery.
    if (target == original_os_entry("osCreateMesgQueue")) {
      state.queues.insert(a0);
      ++state.queue_create_calls;
    }
    if (target == original_os_entry("osSetEventMesg")) state.events[a0] = {a1, a2};
    if (target == original_os_entry("osViSetEvent")) {
      state.vi_queue = a0; state.vi_message = a1; state.vi_retrace_interval = a2;
    }
#if defined(_WIN32) && defined(JFG_PHASE8_LIVE_RUNTIME)
    if (target == original_os_entry("osViSetMode")) {
      if (!configure_live_vi_mode(state, memory, a0))
        fail_closed_dispatch(state, "guest-vi", "invalid-mode", target);
      state.vi_mode = a0;
    }
    if (target == original_os_entry("osViSetSpecialFeatures")) {
      state.vi_special_features = a0;
      state.rt64_vi.status = jfg::vi_apply_special_features(
          state.rt64_vi.status, state.vi_mode_control, a0);
    }
    if (target == original_os_entry("osViBlack")) {
      state.vi_blacked = a0 != 0;
      state.rt64_vi.horizontal_start = state.vi_blacked ? 0 : state.vi_mode_horizontal_start;
    }
#endif
    if (target == original_os_entry("osViSwapBuffer")) {
      ++state.vi_swap_calls;
      state.vi_current_framebuffer = state.vi_next_framebuffer;
      state.vi_next_framebuffer = a0;
    }
    if (target == original_os_entry("osSendMesg") && context->r2 == 0 &&
        a0 == state.vi_queue && a1 == state.vi_message) {
      ++state.vi_messages_delivered;
      present_completed_video(state,target);
    }
    if (target == original_os_entry("osRecvMesg") && context->r2 == 0 && a0 == state.vi_queue && a1 != 0) {
      std::uint32_t message = 0;
      if (!memory.read_u32(a1, message)) fail_closed_dispatch(state, "guest-vi", "message-unreadable", target);
      if (message == state.vi_message) {
        ++state.vi_retraces;
        {
#if defined(_WIN32) && defined(JFG_PHASE8_LIVE_RUNTIME)
        const DiagnosticHostStage breadcrumb_stage(state,"host-profile-breadcrumb");
#endif
        jfg::support_breadcrumb(state.vi_frames, state.vi_retraces, state.controller_samples);
#if defined(_WIN32) && defined(JFG_PHASE8_LIVE_RUNTIME)
        support_mouse_snapshot(state);
#endif
        }
#if defined(_WIN32) && defined(JFG_PHASE8_LIVE_RUNTIME)
        write_retrace_semantic_hash(state);
        write_private_progress(state);
#endif
        if (state.vi_retraces >= state.retrace_target) retrace_gate(state);
      }
    }
    if (state.guest_clock_trace.is_open() && state.observed_guest_instructions < 1000000U) {
      state.guest_clock_trace << "return\t" << std::hex << target << std::dec << '\t'
          << state.cpu_count << '\n';
      state.guest_clock_trace.flush();
    }
    return 1;
  }
  if (state.guest_initializing) {
    // The independently executed cold-boot closure. Mapped private helpers
    // must execute their original bodies as well as the public OS entry.
    // Only mapped calls reach this branch. Other original helpers remain
    // generated guest calls and do not acquire a host dispatch disposition.
    const bool original_helper = std::strcmp(name, "osWritebackDCache") == 0 ||
        std::strcmp(name, "osInvalICache") == 0 ||
        std::strcmp(name, "__osSetSR") == 0 || std::strcmp(name, "__osGetSR") == 0;
    recomp_func_t *const generated = jfg_generated_lookup_function(address);
    if (!original_helper || generated == nullptr)
      fail_closed_dispatch(state, "guest-leaf", "initialize-closure", target);
    generated(rdram, context);
    return 1;
  }
  // These two leaf HLE calls account for most mapped dispatches in JFG. Use
  // their bound semantic addresses before the descriptive name chain so normal
  // play does not repeat dozens of string comparisons for each call.
  if (target == kOsVirtualToPhysical) {  // osVirtualToPhysical
    const std::uint32_t segment = a0 & 0xE0000000U;
    if (state.guest_leaf_probe) {
      // Execute the original supported-ROM routine, including its TLB
      // helper. The diagnostic CP0 bridge supplies explicit reference state;
      // unsupported operations still trap rather than bypassing the helper.
      recomp_func_t *const generated = jfg_generated_lookup_function(address);
      if (generated == nullptr)
        fail_closed_dispatch(state, "guest-leaf", "unavailable", target);
      trace_guest_clock(state, "guest-leaf-entry", target);
      generated(rdram, context);
      trace_guest_clock(state, "guest-leaf-return", target);
      if ((segment == 0x80000000U || segment == 0xA0000000U) &&
          static_cast<std::uint32_t>(context->r2) != (a0 & 0x1FFFFFFFU))
        fail_closed_dispatch(state, "guest-leaf", "translation-result", target);
      return 1;
    }
    const std::uint32_t physical =
        segment == 0x80000000U || segment == 0xA0000000U
            ? a0 & 0x1FFFFFFFU
            : a0;
    set_result(context, static_cast<std::int32_t>(physical));
    return 1;
  }
  if (target == kOsSetIntMask) {  // osSetIntMask
    if (state.guest_leaf_probe) {
      recomp_func_t *const generated = jfg_generated_lookup_function(address);
      if (generated == nullptr || state.mmio_trace == nullptr ||
          !state.mmio_trace->guest_mi_mask || !state.mmio_trace->mi_mask.initialized())
        fail_closed_dispatch(state, "guest-leaf", "interrupt-mask-unavailable", target);
      trace_guest_clock(state, "guest-mask-entry", target);
      generated(rdram, context);
      trace_guest_clock(state, "guest-mask-return", target);
      state.interrupt_mask =
          (static_cast<std::uint32_t>(cop0_status_read(context)) & 0xff01U) |
          (state.mmio_trace->mi_mask.read() << 16U);
      state.journal.append(NativeEventKind::kInterruptMask,
                           static_cast<std::uint32_t>(context->r2), state.interrupt_mask);
      return 1;
    }
    const std::uint32_t previous = state.interrupt_mask;
    state.interrupt_mask = a0;
    set_result(context, static_cast<std::int32_t>(previous));
    state.journal.append(NativeEventKind::kInterruptMask, previous, a0);
    return 1;
  }
  // osInitialize has no arguments or return value in the public libultra ABI.
  // The native runner has already established the memory image and generated
  // dispatch before guest entry, so its observable contract at this boundary
  // is to make initialization idempotent and allow execution to continue.
  if (std::strcmp(name, "osInitialize") == 0) {
    if (state.guest_leaf_probe) {
      recomp_func_t *const generated = jfg_generated_lookup_function(address);
      if (state.os_initialized || generated == nullptr || state.mmio_trace == nullptr ||
          !state.mmio_trace->guest_pif_boot)
        fail_closed_dispatch(state, "guest-leaf", "initialize-state", target);
      state.guest_initializing = true;
      generated(rdram, context);
      state.guest_initializing = false;
      if (!state.mmio_trace->pif_boot.acknowledged())
        fail_closed_dispatch(state, "guest-leaf", "initialize-pif", target);
    }
    state.os_initialized = true;
    return 1;
  }
  if (std::strcmp(name, "osCreateThread") == 0) {
    const std::uint32_t stack = static_cast<std::uint32_t>(context->r29);
    std::uint32_t guest_sp = 0U;
    std::uint32_t priority = 0U;
    if (!state.os_initialized || state.scheduler == nullptr ||
        !memory.read_u32(stack + 0x10U, guest_sp) ||
        !memory.read_u32(stack + 0x14U, priority) || a0 == 0U ||
        a2 == 0U || guest_sp < 16U || state.threads.contains(a0)) {
      fail_closed_dispatch(state, "hle", "malformed-thread", target);
    }
    recomp_func_t *const entry_function =
        jfg_generated_lookup_function(static_cast<std::int32_t>(a2));
    const bool synthetic_vi_manager =
        // The diagnostic inventory now contains this worker's original body.
        // Keep the cooperative control profile explicit, not dependent on a
        // missing symbol. The guest-OS scheduler will own its separate path.
        a2 == kOsViWorker && !state.vi_manager_thread_created &&
        state.events.contains(7U) && state.events.contains(3U);
    if (entry_function == nullptr && !synthetic_vi_manager) {
      fail_closed_dispatch(state, "generated", "thread-entry-unresolved", a2);
    }
    const std::uint32_t vi_internal_queue =
        synthetic_vi_manager ? state.events.at(7U).first : 0U;
    constexpr std::uint32_t kThreadStatus = 0x0400FF03U;
    const std::uint32_t thread_status =
        static_cast<std::int32_t>(a1) < 0
            ? kThreadStatus & ~0x04000000U
            : kThreadStatus;
    const int thread_id = state.scheduler->create_thread(
        priority, [&state, entry = a2, argument = a3,
                   guest_sp, entry_function,
                   vi_internal_queue,
                   thread_status, synthetic_vi_manager](ThreadScheduler &scheduler, int) {
          if (synthetic_vi_manager) {
            for (;;) {
              (void)scheduler.recv_blocking(vi_internal_queue, 0U);
              if (state.vi_queue == 0U ||
                  scheduler.send(state.vi_queue, state.vi_message, false) !=
                      hle::kOsSuccess) {
                fail_closed_dispatch(state, "vi", "retrace-delivery", entry);
              }
              ++state.vi_messages_delivered;
              state.journal.append(NativeEventKind::kViMessageDelivered,
                                   state.vi_queue, state.vi_message,
                                   static_cast<std::uint32_t>(
                                       state.vi_messages_delivered));
            }
          }
          recomp_context thread_context{};
          thread_context.r4 = sign_extend_mips32(argument);
          thread_context.r29 = sign_extend_mips32(guest_sp - 16U);
          // osCreateThread stores an exception-return context, not the live
          // entry Status. The native handoff replaces __osDispatchThread's
          // ERET, so apply its Status transition before running guest code.
          cop0_status_write(&thread_context, status_after_exception_return(thread_status));
#if defined(JFG_PHASE8_LIVE_RUNTIME)
          if (state.guest_leaf_probe && state.timing_trace.is_open())
            state.timing_trace << "thread-entry-status\t" << std::hex << entry << '\t'
                               << cop0_status_read(&thread_context) << '\t'
                               << state.mmio_trace->mi_mask.read() << std::dec << '\n';
#endif
          entry_function(state.rdram, &thread_context);
        });
    state.vi_manager_thread_created |= synthetic_vi_manager;
    if (state.guest_leaf_probe) {
      if (static_cast<std::size_t>(thread_id) != state.saved_rcp_masks.size())
        fail_closed_dispatch(state, "guest-leaf", "thread-mask-index", target);
      // Independent original-OS thread-entry probe: all six sources enabled.
      state.saved_rcp_masks.push_back(0x3fU);
    }
    state.threads.emplace(a0, thread_id);
    state.thread_order.emplace_back(a0, thread_id);
    state.thread_entries.push_back(a2);
    state.journal.append(NativeEventKind::kThreadCreated, a0, a2, priority);
    return 1;
  }
  if (std::strcmp(name, "osStartThread") == 0) {
    const auto thread = state.threads.find(a0);
    if (state.scheduler == nullptr || thread == state.threads.end()) {
      fail_closed_dispatch(state, "hle", "unknown-thread", target);
    }
    state.scheduler->start_thread(thread->second);
    state.journal.append(NativeEventKind::kThreadStarted, a0,
                         static_cast<std::uint32_t>(thread->second));
    if (state.scheduler_running) {
      state.scheduler->yield_current();
    } else {
      state.scheduler_running = true;
      auto outcome = state.scheduler->run(1'000'000U);
      while ((outcome == ScheduleOutcome::kQuiescent ||
              outcome == ScheduleOutcome::kTimeslice) &&
             state.vi_retraces < state.retrace_target &&
             state.vi_retrace_interval != 0U &&
             state.vi_internal_queue != 0U) {
#if defined(_WIN32) && defined(JFG_PHASE8_LIVE_RUNTIME)
        if (state.focus_update_start != 0U &&
            state.completed_game_updates + 1U >= state.focus_update_start - 1U &&
            state.completed_game_updates + 1U <= state.focus_update_end + 1U &&
            state.timing_trace.is_open()) {
          std::string blocked_threads;
          for (const auto &[guest, id] : state.thread_order) {
            (void)guest;
            const auto snapshot = state.scheduler->snapshot_of(id);
            if (!snapshot.has_value() ||
                snapshot->state != ThreadState::kBlocked)
              continue;
            if (!blocked_threads.empty())
              blocked_threads.push_back(',');
            char queue[11U]{};
            (void)std::snprintf(queue, sizeof(queue), "%08x",
                                snapshot->blocked_queue);
            blocked_threads += std::to_string(id) + "@" + queue;
          }
          std::vector<std::pair<std::uint32_t, std::uint32_t>> mapped_events;
          mapped_events.reserve(state.events.size());
          for (const auto &[event, queue_and_message] : state.events) {
            mapped_events.emplace_back(event, queue_and_message.first);
          }
          std::sort(mapped_events.begin(), mapped_events.end());
          std::string event_queues;
          for (const auto &[event, queue_address] : mapped_events) {
            if (!event_queues.empty())
              event_queues.push_back(',');
            char queue[11U]{};
            (void)std::snprintf(queue, sizeof(queue), "%08x",
                                queue_address);
            event_queues += std::to_string(event) + "@" + queue;
          }
          state.timing_trace << "vi-service\t" << state.vi_frames << '\t'
                             << state.vi_retraces << "\t0\t"
                             << (outcome == ScheduleOutcome::kTimeslice
                                     ? "timeslice"
                                     : "quiescent")
                             << '\t' << state.completed_game_updates << '\t'
                             << state.interrupt_timeslices << '\t'
                             << state.pending_graphics_tasks.size() << ':'
                             << state.pending_si_completions << ':'
                             << state.scheduler->dispatch_count() << ':'
                             << blocked_threads << ':' << event_queues << '\n';
        }
#endif
        service_vi_frame(state, target);
        outcome = state.scheduler->run(1'000'000U);
      }
      state.scheduler_running = false;
      if (outcome == ScheduleOutcome::kUnbounded)
        fail_closed_dispatch(state, "scheduler", "step-budget", target);
    }
    return 1;
  }
  if (std::strcmp(name, "osSetThreadPri") == 0) {
    if (a0 == 0U) {
      const int current = state.scheduler == nullptr
                              ? -1
                              : state.scheduler->current_thread_id();
      if (state.scheduler_running && current >= 0) {
        if (!state.scheduler->set_priority(current, a1)) {
          fail_closed_dispatch(state, "hle", "unknown-thread", target);
        }
        state.scheduler->yield_current();
      } else {
        state.root_priority = a1;
      }
      return 1;
    }
    const auto thread = state.threads.find(a0);
    if (state.scheduler == nullptr || thread == state.threads.end() ||
        !state.scheduler->set_priority(thread->second, a1)) {
      fail_closed_dispatch(state, "hle", "unknown-thread", target);
    }
    return 1;
  }
  if (std::strcmp(name, "osGetThreadPri") == 0) {
    if (a0 == 0U) {
      const int current = state.scheduler == nullptr
                              ? -1
                              : state.scheduler->current_thread_id();
      const auto priority =
          state.scheduler_running && current >= 0
              ? state.scheduler->priority_of(current)
              : std::optional<std::uint32_t>{state.root_priority};
      set_result(context, static_cast<std::int32_t>(*priority));
      return 1;
    }
    const auto thread = state.threads.find(a0);
    const auto priority =
        thread == state.threads.end() || state.scheduler == nullptr
            ? std::optional<std::uint32_t>{}
            : state.scheduler->priority_of(thread->second);
    if (!priority.has_value()) {
      fail_closed_dispatch(state, "hle", "unknown-thread", target);
    }
    set_result(context, static_cast<std::int32_t>(*priority));
    return 1;
  }
  if (std::strcmp(name, "osSetEventMesg") == 0) {
    if (!state.queues.contains(a1)) {
      fail_closed_dispatch(state, "hle", "unknown-queue", target);
    }
    state.events[a0] = {a1, a2};
    if (a0 == 7U) {
      state.vi_internal_queue = a1;
      state.vi_internal_message = a2;
    }
    return 1;
  }
  if (std::strcmp(name, "osCreatePiManager") == 0) {
    if (state.pi_command_queue != 0U) {
      set_result(context, static_cast<std::int32_t>(state.pi_command_queue));
      return 1;
    }
    if (state.scheduler == nullptr || a1 == 0U || a2 == 0U || a3 == 0U ||
        !state.scheduler->create_queue(a1, a2,
                                       static_cast<std::int32_t>(a3))) {
      fail_closed_dispatch(state, "hle", "pi-manager-setup", target);
    }
    state.queues.insert(a1);
    state.pi_command_queue = a1;
    state.journal.append(NativeEventKind::kQueueCreated, a1, a2, a3);
    set_result(context, static_cast<std::int32_t>(a1));
    return 1;
  }
  if (std::strcmp(name, "osPiGetCmdQueue") == 0) {
    if (state.pi_command_queue == 0U)
      fail_closed_dispatch(state, "hle", "pi-manager-uninitialized", target);
    set_result(context,
               static_cast<std::int32_t>(state.pi_command_queue));
    return 1;
  }
  if (std::strcmp(name, "osPiStartDma") == 0) {
    const std::uint32_t stack = static_cast<std::uint32_t>(context->r29);
    std::uint32_t dram_address = 0U;
    std::uint32_t size = 0U;
    std::uint32_t completion_queue = 0U;
    if (state.rom == nullptr || state.scheduler == nullptr || a0 == 0U ||
        a2 != 0U || !memory.read_u32(stack + 0x10U, dram_address) ||
        !memory.read_u32(stack + 0x14U, size) ||
        !memory.read_u32(stack + 0x18U, completion_queue) || size == 0U ||
        !state.queues.contains(completion_queue)) {
      fail_closed_dispatch(state, "hle", "invalid-pi-dma", target);
    }
    const std::uint32_t segment = dram_address & 0xE0000000U;
    const std::uint64_t dram_offset = dram_address & 0x1FFFFFFFU;
    const std::uint64_t rom_offset =
        a3 >= 0x10000000U ? std::uint64_t{a3} - 0x10000000U : a3;
    if ((segment != 0x80000000U && segment != 0xA0000000U) ||
        dram_offset > kRdramSize || size > kRdramSize - dram_offset ||
        rom_offset > state.rom_size || size > state.rom_size - rom_offset) {
      fail_closed_dispatch(state, "hle", "pi-dma-range", target);
    }
    for (std::uint32_t index = 0U; index < size; ++index) {
      state.rdram[(static_cast<std::size_t>(dram_offset) + index) ^ 3U] =
          state.rom[static_cast<std::size_t>(rom_offset) + index];
    }
    for (std::uint32_t section = 0U;
         section < jfg_generated_section_count(); ++section) {
      JfgGeneratedSectionMetadata metadata{};
      if (jfg_generated_section_metadata(section, &metadata) == 0 ||
          metadata.is_overlay != 1U || metadata.rom_start != rom_offset)
        continue;
      // A runlink module may load text and data with separate PI requests.
      // Matching the module's exact ROM start is the publication boundary;
      // publish_synthetic_overlay independently validates and materializes the
      // complete normalized image from the supported ROM.
#if defined(JFG_PHASE8_LIVE_RUNTIME)
      SyntheticOverlayPublication publication =
          SyntheticOverlayPublication::ensure_active;
      if (section == game_module(OriginalModule::instruments) &&
          state.phase9_death_restart_calls >
              state.health_overlay_death_reload_generation &&
          state.active_overlay_sections.contains(section)) {
        // The same ROM range can be read for reasons other than loading its
        // overlay. Reload mutable data/BSS only when the DMA destination is
        // the base of the matching live runlink module. Treating every ROM
        // read as an unload/reload resets instrument state continuously and
        // can prevent the scene framebuffer from ever becoming presentable.
        RunlinkAddressResolution resolution{};
        const std::uint32_t dma_guest_address =
            kKseg0 | static_cast<std::uint32_t>(dram_offset);
        if (resolve_runlink_text_address(
                memory, kRunlinkModuleTablePointer,
                kRunlinkOverlaySlotCount, dma_guest_address,
                resolution) == RunlinkAddressResult::resolved &&
            resolution.text_offset == 0U &&
            resolution.identity.rom_start == metadata.rom_start &&
            resolution.identity.text_size == metadata.text_size &&
            resolution.identity.data_size == metadata.data_size &&
            resolution.identity.bss_size == metadata.bss_size)
          publication = SyntheticOverlayPublication::reload;
      }
#endif
      if (
#if defined(JFG_PHASE8_LIVE_RUNTIME)
          !publish_synthetic_overlay(state, section, metadata, publication)
#else
          jfg_generated_relocation_count(section) != 0U ||
          jfg_generated_section_lifecycle(
              1U, section, static_cast<std::int32_t>(metadata.linked_vram)) !=
              0
#endif
      ) {
        fail_closed_overlay_publication(state, metadata.linked_vram);
      }
#if defined(JFG_PHASE8_LIVE_RUNTIME)
      if (publication == SyntheticOverlayPublication::reload)
        state.health_overlay_death_reload_generation =
            state.phase9_death_restart_calls;
#endif
      state.journal.append(NativeEventKind::kOverlayPublished, section,
                           metadata.linked_vram,
                           static_cast<std::uint32_t>(dram_offset));
      break;
    }
    if (!memory.write_u32(a0 + 0x00U, completion_queue) ||
        !memory.write_u32(a0 + 0x04U, a1) ||
        !memory.write_u32(a0 + 0x08U, 0U) ||
        !memory.write_u32(a0 + 0x0CU, dram_address) ||
        !memory.write_u32(a0 + 0x10U, a3) ||
        !memory.write_u32(a0 + 0x14U, size) ||
        state.scheduler->send(completion_queue, a0, false) !=
            hle::kOsSuccess) {
      fail_closed_dispatch(state, "hle", "pi-dma-completion", target);
    }
    state.journal.append(NativeEventKind::kPiDma, a3, dram_address, size);
    state.last_pi_rom = a3;
    state.last_pi_dram = dram_address;
    state.last_pi_size = size;
    set_result(context, hle::kOsSuccess);
    return 1;
  }
  if (std::strcmp(name, "__osSiRawStartDma") == 0) {
    if (state.si_count_probe && state.si_deadline.next()) {
      set_result(context, -1);
      return 1;
    }
    recomp_func_t *const generated = jfg_generated_lookup_function(address);
    if (generated == nullptr)
      fail_closed_dispatch(state, "si", "raw-dma-unavailable", target);
    generated(rdram, context);
    if (static_cast<std::uint32_t>(context->r2) == 0U) {
      if (a0 > 1U)
        fail_closed_dispatch(state, "si", "raw-dma-direction", target);
      if (a0 == 1U) {
        std::array<std::uint8_t, jfg::kPifRamBytes> transfer{};
        for (std::size_t index = 0U; index < transfer.size(); ++index) {
          std::size_t guest_offset = 0U;
          if (!guest_byte_offset(
                  a1 + static_cast<std::uint32_t>(index), guest_offset)) {
            fail_closed_dispatch(state, "si", "raw-dma-range", target);
          }
          transfer[index] = state.rdram[guest_offset];
        }
        // The high-level controller path owns ordinary PIF channel traffic.
        // Retain only a real CIC challenge here; mirroring unimplemented
        // controller commands back into RDRAM would overwrite the controller
        // data produced by that HLE path.
        if (jfg::process_cic_nus_6105_challenge(transfer) ||
            (state.controller_guest_init_probe &&
             jfg::process_controller_status_query(transfer, state.controller_ports.mask()))) {
          state.pif_ram = transfer;
          state.cic_response_pending = true;
        }
      } else if (state.cic_response_pending) {
        for (std::size_t index = 0U; index < state.pif_ram.size(); ++index) {
          std::size_t guest_offset = 0U;
          if (!guest_byte_offset(
                  a1 + static_cast<std::uint32_t>(index), guest_offset)) {
            fail_closed_dispatch(state, "si", "raw-dma-range", target);
          }
          state.rdram[guest_offset] = state.pif_ram[index];
        }
        state.cic_response_pending = false;
      }
      if (state.pending_si_completions ==
          (std::numeric_limits<std::uint32_t>::max)())
        fail_closed_dispatch(state, "si", "completion-overflow", target);
      ++state.pending_si_completions;
      if (state.si_count_probe) schedule_si_deadline(state, target);
    }
    return 1;
  }
#if defined(JFG_PHASE8_LIVE_RUNTIME)
  if (std::strcmp(name, "osSetTimer") == 0) {
    const auto sp = static_cast<std::uint32_t>(context->r29);
    std::uint32_t interval_hi = 0, interval_lo = 0, queue = 0, message = 0;
    if (sp > UINT32_MAX - 0x1CU ||
        !memory.read_u32(sp + 0x10U, interval_hi) ||
        !memory.read_u32(sp + 0x14U, interval_lo) ||
        !memory.read_u32(sp + 0x18U, queue) ||
        !memory.read_u32(sp + 0x1CU, message) ||
        !state.timers.set(memory, state.cpu_count, a0,
                         (std::uint64_t{a2} << 32U) | a3,
                         (std::uint64_t{interval_hi} << 32U) | interval_lo,
                         queue, message))
      fail_closed_dispatch(state, "timer", "invalid-timer-arguments", target);
    set_result(context, hle::kOsSuccess);
    return 1;
  }
  if (std::strcmp(name, "osStopTimer") == 0) {
    state.timers.stop(a0);
    return 1;
  }
  if (std::strcmp(name, "osGetCount") == 0) {
    set_result(context, static_cast<std::int32_t>(state.cpu_count));
    return 1;
  }
  if (std::strcmp(name, "osSetTime") == 0) {
    state.os_time_base = (std::uint64_t{a0} << 32U) | a1;
    state.os_time_count_origin = state.cpu_count;
    return 1;
  }
  if (std::strcmp(name, "osGetTime") == 0) {
    const std::uint64_t value =
        state.os_time_base + (state.cpu_count - state.os_time_count_origin);
    context->r2 = sign_extend_mips32(static_cast<std::uint32_t>(value >> 32U));
    context->r3 = sign_extend_mips32(static_cast<std::uint32_t>(value));
    return 1;
  }
  if (std::strcmp(name, "osFlashInit") == 0 ||
      std::strcmp(name, "osFlashReInit") == 0) {
    set_result(context, static_cast<std::int32_t>(kOsFlashHandle));
    return 1;
  }
  if (std::strcmp(name, "osFlashReadStatus") == 0) {
    if (!write_guest_byte(state, a0, jfg::boot::FlashDevice::ready_status))
      fail_closed_dispatch(state, "flashram", "status-output", target);
    set_result(context, hle::kOsSuccess);
    return 1;
  }
  if (std::strcmp(name, "osFlashReadId") == 0) {
    if (!memory.write_u32(a0, jfg::boot::FlashDevice::silicon_type) ||
        !memory.write_u32(a1, jfg::boot::FlashDevice::silicon_id))
      fail_closed_dispatch(state, "flashram", "id-output", target);
    set_result(context, hle::kOsSuccess);
    return 1;
  }
  if (std::strcmp(name, "osFlashClearStatus") == 0) {
    set_result(context, hle::kOsSuccess);
    return 1;
  }
  if (std::strcmp(name, "osFlashAllErase") == 0) {
    if (!state.flashram.begin_erase_all().ok() ||
        !complete_flash_operation(state)) {
      set_result(context, -1);
      return 1;
    }
    set_result(context, hle::kOsSuccess);
    return 1;
  }
  if (std::strcmp(name, "osFlashSectorErase") == 0) {
    if (!state.flashram.begin_erase_sector(a0).ok() ||
        !complete_flash_operation(state)) {
      set_result(context, -1);
      return 1;
    }
    set_result(context, hle::kOsSuccess);
    return 1;
  }
  if (std::strcmp(name, "osFlashWriteBuffer") == 0) {
    std::array<std::uint8_t, jfg::kFlashRamPageBytes> page{};
    const std::uint32_t physical = a2 & 0x1FFFFFFFU;
    if (state.scheduler == nullptr || !state.queues.contains(a3) ||
        physical > kRdramSize || page.size() > kRdramSize - physical)
      fail_closed_dispatch(state, "flashram", "write-buffer-arguments", target);
    for (std::size_t index = 0U; index < page.size(); ++index)
      page[index] = state.rdram[(physical + index) ^ 3U];
    if (!state.flashram.stage_write(page).ok() ||
        state.scheduler->send(a3, 0U, false) != hle::kOsSuccess)
      fail_closed_dispatch(state, "flashram", "write-buffer-completion", target);
    set_result(context, hle::kOsSuccess);
    if (state.scheduler_running)
      state.scheduler->yield_current();
    return 1;
  }
  if (std::strcmp(name, "osFlashWriteArray") == 0) {
    if (!state.flashram.begin_program(a0).ok() ||
        !complete_flash_operation(state)) {
      set_result(context, -1);
      return 1;
    }
    set_result(context, hle::kOsSuccess);
    return 1;
  }
  if (std::strcmp(name, "osFlashReadArray") == 0) {
    const std::uint32_t stack = static_cast<std::uint32_t>(context->r29);
    std::uint32_t page_count = 0U, completion_queue = 0U;
    const std::uint64_t flash_offset =
        std::uint64_t{a2} * jfg::kFlashRamPageBytes;
    const std::uint32_t physical = a3 & 0x1FFFFFFFU;
    if (state.scheduler == nullptr ||
        !memory.read_u32(stack + 0x10U, page_count) ||
        !memory.read_u32(stack + 0x14U, completion_queue) || page_count == 0U ||
        !state.queues.contains(completion_queue))
      fail_closed_dispatch(state, "flashram", "read-array-arguments", target);
    const std::uint64_t byte_count =
        std::uint64_t{page_count} * jfg::kFlashRamPageBytes;
    if (flash_offset > jfg::kFlashRamSizeBytes ||
        byte_count > jfg::kFlashRamSizeBytes - flash_offset ||
        physical > kRdramSize || byte_count > kRdramSize - physical)
      fail_closed_dispatch(state, "flashram", "read-array-range", target);
    const auto read = state.flashram.read(static_cast<std::size_t>(flash_offset),
                                          static_cast<std::size_t>(byte_count));
    if (!read.ok())
      fail_closed_dispatch(state, "flashram", "read-array-device", target);
    for (std::size_t index = 0U; index < read.bytes.size(); ++index)
      state.rdram[(physical + index) ^ 3U] = read.bytes[index];
    if (state.scheduler->send(completion_queue, 0U, false) != hle::kOsSuccess)
      fail_closed_dispatch(state, "flashram", "read-array-completion", target);
    set_result(context, hle::kOsSuccess);
    if (state.scheduler_running)
      state.scheduler->yield_current();
    return 1;
  }
#endif
  if (std::strcmp(name, "osContInit") == 0) {
#if defined(_WIN32)
    char probe_value[2]{};
    const bool guest_init_probe = GetEnvironmentVariableA(
        "JFG_PHASE9_CONTROLLER_GUEST_INIT", probe_value, sizeof(probe_value)) == 1 &&
        probe_value[0] == '1';
#else
    const char *probe_value = std::getenv("JFG_PHASE9_CONTROLLER_GUEST_INIT");
    const bool guest_init_probe = probe_value != nullptr &&
                                  std::strcmp(probe_value, "1") == 0;
#endif
    if (guest_init_probe) {
#if defined(_WIN32)
      char si_probe_value[2]{};
      state.si_count_probe = GetEnvironmentVariableA("JFG_PHASE9_SI_COUNT_PROBE",
          si_probe_value, sizeof(si_probe_value)) == 1 && si_probe_value[0] == '1';
#else
      const char *si_probe_value = std::getenv("JFG_PHASE9_SI_COUNT_PROBE");
      state.si_count_probe = si_probe_value != nullptr && std::strcmp(si_probe_value, "1") == 0;
#endif
      // Bounded diagnostic candidate: original code establishes the guest
      // channel count, command state, access queues, and initialization guard.
      state.controller_guest_init_probe = true;
      recomp_func_t *const generated = jfg_generated_lookup_function(address);
      if (generated == nullptr)
        fail_closed_dispatch(state, "si", "controller-init-unavailable", target);
      generated(rdram, context);
      state.controller_initialized = static_cast<std::uint32_t>(context->r2) == 0U;
      return 1;
    }
#if defined(_WIN32) && defined(JFG_PHASE8_LIVE_RUNTIME)
    sample_controller_ports(state);
    const auto connected_mask=state.input_replay_loaded ? std::uint8_t{1} : state.controller_ports.mask();
#else
    const std::uint8_t connected_mask=1;
#endif
    if (state.scheduler == nullptr || !state.queues.contains(a0) || a1 == 0U ||
        a2 == 0U || !write_guest_byte(state, a1, connected_mask)) {
      fail_closed_dispatch(state, "hle", "controller-init", target);
    }
    for (std::uint32_t controller = 0U; controller < 4U; ++controller) {
      const std::uint32_t status = a2 + controller * 4U;
      const bool connected = (connected_mask & (1U<<controller))!=0;
      if (!write_guest_byte(state, status, 0U) ||
          !write_guest_byte(state, status + 1U, connected ? 5U : 0U) ||
          !write_guest_byte(state, status + 2U, 0U) ||
          !write_guest_byte(state, status + 3U, connected ? 0U : 8U)) {
        fail_closed_dispatch(state, "hle", "controller-status", target);
      }
    }
    state.controller_initialized = true;
    state.journal.append(NativeEventKind::kController, 1U, a0);
    set_result(context, hle::kOsSuccess);
    return 1;
  }
  if (std::strcmp(name, "osContStartReadData") == 0) {
    if (state.si_count_probe && state.si_deadline.next()) {
      set_result(context, -1);
      return 1;
    }
    ++state.controller_read_start_calls;
#if defined(_WIN32) && defined(JFG_PHASE8_LIVE_RUNTIME)
    trace_phase9_event(state, "start-entry", state.controller_samples);
#endif
    state.controller_read_thread = state.scheduler == nullptr
                                       ? -1
                                       : state.scheduler->current_thread_id();
    const auto si = state.events.find(5U);
    if (!state.controller_initialized || state.scheduler == nullptr ||
        !state.queues.contains(a0) || si == state.events.end() ||
        si->second.first != a0 ||
        state.pending_si_completions ==
            (std::numeric_limits<std::uint32_t>::max)()) {
      fail_closed_dispatch(state, "hle", "controller-read-start", target);
    }
    ++state.pending_si_completions;
    if (state.si_count_probe) schedule_si_deadline(state, target);
#if defined(_WIN32) && defined(JFG_PHASE8_LIVE_RUNTIME)
    trace_si_timing(state, "read-start", a0, 0U, 0);
    if (state.play_mode || state.input_replay_loaded) {
      std::size_t pressed_high = 0U, pressed_low = 0U;
      std::size_t current_stick_x = 0U, current_stick_y = 0U;
      std::size_t menu_stick_x = 0U, menu_stick_y = 0U;
      std::uint16_t game_pressed = 0U;
      if (!guest_byte_offset(game_data("diagnostic.controllerPressed"), pressed_high) ||
          !guest_byte_offset((game_data("diagnostic.controllerPressed")+1U), pressed_low) ||
          !guest_byte_offset(game_data("diagnostic.controllerStickX"), current_stick_x) ||
          !guest_byte_offset(game_data("diagnostic.controllerStickY"), current_stick_y) ||
          !guest_byte_offset(game_data("globals.frontendStickX"), menu_stick_x) ||
          !guest_byte_offset(game_data("globals.frontendStickY"), menu_stick_y))
        fail_closed_dispatch(state, "controller", "pressed-observation",
                             target);
      game_pressed = static_cast<std::uint16_t>(
          (static_cast<std::uint16_t>(state.rdram[pressed_high]) << 8U) |
          state.rdram[pressed_low]);
      if (game_pressed != 0U) {
        ++state.game_pressed_observations;
        state.last_game_pressed_buttons = game_pressed;
      }
      const auto game_stick_x =
          static_cast<std::int8_t>(state.rdram[current_stick_x]);
      const auto game_stick_y =
          static_cast<std::int8_t>(state.rdram[current_stick_y]);
      if (game_stick_x != 0 || game_stick_y != 0) {
        ++state.game_stick_observations;
        state.last_game_stick_x = game_stick_x;
        state.last_game_stick_y = game_stick_y;
      }
      const auto observed_menu_stick_x =
          static_cast<std::int8_t>(state.rdram[menu_stick_x]);
      const auto observed_menu_stick_y =
          static_cast<std::int8_t>(state.rdram[menu_stick_y]);
      if (observed_menu_stick_x != 0 || observed_menu_stick_y != 0) {
        ++state.menu_stick_observations;
        state.last_menu_stick_x = observed_menu_stick_x;
        state.last_menu_stick_y = observed_menu_stick_y;
      }
      sample_live_controller(state);
      if (state.poll_hash_trace.is_open())
        write_retrace_semantic_hash(state, nullptr, &state.poll_hash_trace);
      trace_phase9_event(state, "start-exit", state.controller_samples - 1U);
    }
#endif
    state.journal.append(NativeEventKind::kController, 2U, a0,
                         si->second.second);
    set_result(context, hle::kOsSuccess);
#if defined(_WIN32) && defined(JFG_PHASE8_LIVE_RUNTIME)
    // Stop after the Nth controller-read HLE is complete, before the guest
    // consumes its result. This is an input-poll boundary, not a VI boundary.
    if (state.poll_target != 0U &&
        state.controller_samples == state.poll_target)
      probe_target_gate(state);
#endif
    return 1;
  }
  if (std::strcmp(name, "osContGetReadData") == 0) {
    ++state.controller_get_data_calls;
#if defined(_WIN32) && defined(JFG_PHASE8_LIVE_RUNTIME)
    trace_phase9_event(state, "get-entry", state.controller_samples == 0U
                                             ? 0U : state.controller_samples - 1U);
#endif
    if (!state.controller_initialized || a0 == 0U) {
      fail_closed_dispatch(state, "hle", "controller-read-data", target);
    }
    for (std::uint32_t controller = 0U; controller < 4U; ++controller) {
      for (std::uint32_t byte = 0U; byte < 6U; ++byte) {
        std::uint8_t value = byte == 4U && controller != 0U ? 8U : 0U;
#if defined(_WIN32) && defined(JFG_PHASE8_LIVE_RUNTIME)
        if (state.play_mode || state.input_replay_loaded) {
          const auto& port=state.controller_ports.samples[controller];
          if (!port.connected) {
            value = byte == 4U ? 8U : 0U;
          } else {
          switch (byte) {
          case 0U:
            value = static_cast<std::uint8_t>(
                port.buttons >> 8U);
            break;
          case 1U:
            value = static_cast<std::uint8_t>(
                port.buttons);
            break;
          case 2U:
            value = static_cast<std::uint8_t>(
                port.x);
            break;
          case 3U:
            value = static_cast<std::uint8_t>(
                port.y);
            break;
          default:
            value = 0U;
            break;
          }
          if (byte == 0U && port.buttons != 0U)
            ++state.non_neutral_controller_writes;
          }
        }
#endif
        if (!write_guest_byte(state, a0 + controller * 6U + byte, value)) {
          fail_closed_dispatch(state, "hle", "controller-pad-range", target);
        }
      }
    }
    state.journal.append(NativeEventKind::kController, 3U, a0);
#if defined(_WIN32) && defined(JFG_PHASE8_LIVE_RUNTIME)
    trace_phase9_event(state, "get-exit", state.controller_samples == 0U
                                            ? 0U : state.controller_samples - 1U);
    if (state.controller_return_trace.is_open()) {
      const std::uint64_t poll = state.controller_samples == 0U
                                     ? 0U : state.controller_samples - 1U;
      bool selected = false;
      for (std::size_t index = 0U; index < state.event_range_count; ++index) {
        const auto [first, last] = state.event_ranges[index];
        selected |= poll >= first && poll <= last;
      }
      if (selected) {
        if (++state.controller_return_rows > 256U)
          fail_closed_dispatch(state, "diagnostic", "controller-return-overflow",
                               target);
        state.controller_return_trace << state.controller_return_rows << '\t'
            << poll << '\t' << state.completed_game_updates << '\t'
            << state.vi_retraces << '\t' << state.vi_frames << '\t'
            << "0x" << std::hex << std::setw(8) << std::setfill('0') << a0
            << '\t';
        for (std::uint32_t byte = 0U; byte < 24U; ++byte) {
          std::size_t offset = 0U;
          if (!guest_byte_offset(a0 + byte, offset))
            fail_closed_dispatch(state, "diagnostic", "controller-return-range",
                                 target);
          state.controller_return_trace << std::setw(2)
                                        << static_cast<unsigned>(state.rdram[offset]);
        }
        state.controller_return_trace << std::setfill(' ') << std::dec << '\n';
      }
    }
#endif
    return 1;
  }
  if (std::strcmp(name, "bzero") == 0) {
    const auto length = static_cast<std::int32_t>(a1);
    const auto guest_bzero = [&]() {
      if (static_cast<std::int64_t>(context->r5) != static_cast<std::int64_t>(length))
        fail_closed_dispatch(state, "guest-leaf", "bzero-length-extension", target);
      recomp_func_t *const generated = jfg_generated_lookup_function(address);
      if (generated == nullptr)
        fail_closed_dispatch(state, "guest-leaf", "bzero-unavailable", target);
      trace_guest_clock(state, "guest-memory-entry", target);
      generated(rdram, context);
      trace_guest_clock(state, "guest-memory-return", target);
    };
    if (length <= 0) {
      if (state.guest_leaf_probe) guest_bzero();
      return 1;
    }
    state.active_bzero_address = a0;
    state.active_bzero_length = a1;
    std::size_t offset = 0U;
    if (!resolve_bzero_host_offset(state, a0,
                                   static_cast<std::uint32_t>(length),
                                   offset)) {
      const std::uint32_t caller =
          state.recent_dispatch_position < 2U
              ? 0U
              : state.recent_dispatches[
                    (state.recent_dispatch_position - 2U) %
                    state.recent_dispatches.size()];
      const std::uint32_t parent =
          state.recent_dispatch_position < 3U
              ? 0U
              : state.recent_dispatches[
                    (state.recent_dispatch_position - 3U) %
                    state.recent_dispatches.size()];
      std::array<char, 128U> operation{};
      (void)std::snprintf(operation.data(), operation.size(),
                          "bzero-%08x-%08x-ra%08x-sp%08x-c%08x-p%08x", a0,
                          a1,
                          static_cast<std::uint32_t>(context->r31),
                          static_cast<std::uint32_t>(context->r29), caller,
                          parent);
      fail_closed_dispatch(state, "memory", operation.data(), target);
    }
    if (state.guest_leaf_probe) {
      guest_bzero();
    } else {
      for (std::uint32_t index = 0U;
           index < static_cast<std::uint32_t>(length); ++index) {
        state.rdram[(offset + index) ^ 3U] = 0U;
      }
    }
    state.active_bzero_address = 0U;
    state.active_bzero_length = 0U;
    return 1;
  }
  if (std::strcmp(name, "osVirtualToPhysical") == 0) {
    const std::uint32_t segment = a0 & 0xE0000000U;
    const std::uint32_t physical =
        segment == 0x80000000U || segment == 0xA0000000U
            ? a0 & 0x1FFFFFFFU
            : a0;
    set_result(context, static_cast<std::int32_t>(physical));
    return 1;
  }
  if (std::strcmp(name, "osSetIntMask") == 0) {
    const std::uint32_t previous = state.interrupt_mask;
    state.interrupt_mask = a0;
    set_result(context, static_cast<std::int32_t>(previous));
    state.journal.append(NativeEventKind::kInterruptMask, previous, a0);
    return 1;
  }
  if (std::strcmp(name, "osWritebackDCacheAll") == 0) {
    state.journal.append(NativeEventKind::kCacheMaintenance, 1U);
    if (state.guest_leaf_probe) {
      recomp_func_t *const generated = jfg_generated_lookup_function(address);
      if (generated == nullptr)
        fail_closed_dispatch(state, "guest-leaf", "cache-unavailable", target);
      trace_guest_clock(state, "guest-cache-entry", target);
      generated(rdram, context);
      trace_guest_clock(state, "guest-cache-return", target);
    }
    return 1;
  }
  if (std::strcmp(name, "osWritebackDCache") == 0 ||
      std::strcmp(name, "osInvalDCache") == 0 ||
      std::strcmp(name, "osInvalICache") == 0) {
    const auto length = static_cast<std::int32_t>(a1);
    if (length > 0) {
      const std::uint32_t segment = a0 & 0xE0000000U;
      if ((segment != 0x80000000U && segment != 0xA0000000U) ||
          (a0 & 0x1FFFFFFFU) >= kRdramSize ||
          static_cast<std::uint64_t>(a0 & 0x1FFFFFFFU) +
                  static_cast<std::uint32_t>(length) >
              kRdramSize) {
        fail_closed_dispatch(state, "hle", "invalid-cache-range", target);
      }
    }
    const std::uint32_t operation =
        std::strcmp(name, "osWritebackDCache") == 0 ? 2U
        : std::strcmp(name, "osInvalDCache") == 0   ? 3U
                                                      : 4U;
    state.journal.append(NativeEventKind::kCacheMaintenance, operation, a0,
                         a1);
    if (state.guest_leaf_probe) {
      if (static_cast<std::int64_t>(context->r5) != static_cast<std::int64_t>(length))
        fail_closed_dispatch(state, "guest-leaf", "cache-length-extension", target);
      recomp_func_t *const generated = jfg_generated_lookup_function(address);
      if (generated == nullptr)
        fail_closed_dispatch(state, "guest-leaf", "cache-unavailable", target);
      trace_guest_clock(state, "guest-cache-entry", target);
      generated(rdram, context);
      trace_guest_clock(state, "guest-cache-return", target);
    }
    return 1;
  }
  if (std::strcmp(name, "osViSetMode") == 0) {
    if (a0 < kKseg0 || a0 - kKseg0 > kRdramSize - 0x50U) {
      fail_closed_dispatch(state, "hle", "invalid-vi-mode", target);
    }
#if defined(JFG_PHASE8_LIVE_RUNTIME)
    if (!configure_live_vi_mode(state, memory, a0))
      fail_closed_dispatch(state, "hle", "invalid-vi-mode", target);
#endif
    state.vi_mode = a0;
    return 1;
  }
  if (std::strcmp(name, "osViBlack") == 0) {
    state.vi_blacked = a0 != 0U;
#if defined(JFG_PHASE8_LIVE_RUNTIME)
    state.rt64_vi.horizontal_start =
        state.vi_blacked ? 0U : state.vi_mode_horizontal_start;
#endif
    return 1;
  }
  if (std::strcmp(name, "osViSetEvent") == 0) {
    if (!state.queues.contains(a0) || a2 == 0U) {
      fail_closed_dispatch(state, "hle", "invalid-vi-event", target);
    }
    state.vi_queue = a0;
    state.vi_message = a1;
    state.vi_retrace_interval = a2;
    state.journal.append(NativeEventKind::kViConfigured, a0, a1, a2);
    return 1;
  }
  if (std::strcmp(name, "osViSwapBuffer") == 0) {
    ++state.vi_swap_calls;
    if (a0 < kKseg0 || a0 - kKseg0 >= kRdramSize) {
      fail_closed_dispatch(state, "hle", "invalid-framebuffer", target);
    }
    state.vi_current_framebuffer = state.vi_next_framebuffer;
    state.vi_next_framebuffer = a0;
    return 1;
  }
  if (std::strcmp(name, "osViGetCurrentFramebuffer") == 0) {
    set_result(context,
               static_cast<std::int32_t>(state.vi_current_framebuffer));
    return 1;
  }
  if (std::strcmp(name, "osViGetNextFramebuffer") == 0) {
    set_result(context, static_cast<std::int32_t>(state.vi_next_framebuffer));
    return 1;
  }
  if (std::strcmp(name, "osViSetSpecialFeatures") == 0) {
    state.vi_special_features = a0;
#if defined(JFG_PHASE8_LIVE_RUNTIME)
    state.rt64_vi.status = jfg::vi_apply_special_features(
        state.rt64_vi.status, state.vi_mode_control, a0);
    state.gameplay_trace.event("vi-features", {state.vi_retraces, a0, state.rt64_vi.status});
#endif
    return 1;
  }
#if defined(JFG_PHASE8_LIVE_RUNTIME)
  if (!state.guest_leaf_probe && std::strcmp(name, "osSpTaskYield") == 0) {
    // A yield request gives waiting audio a chance to run. Our RSP backend
    // cannot suspend a task, so finish the pending graphics work now through
    // its sole SP/DP completion path. Waiting for another VI here delays the
    // audio task and changes the guest scheduler's buffer/frame cadence.
    // This neither advances the VI clock nor resubmits a graphics task.
    if (++state.rsp_yield_requests == 1U)
      jfg::support_event("rsp=yield-request-run-to-completion");
#if defined(_WIN32)
    state.gameplay_trace.event("rsp-yield", {state.vi_retraces,
        state.controller_samples, state.gameplay_trace_updates,
        state.pending_graphics_tasks.size(), state.rsp_yield_requests});
    complete_pending_live_graphics_tasks(state, target);
#endif
    return 1;
  }
  if (!state.guest_leaf_probe && std::strcmp(name, "osSpTaskYielded") == 0) {
    // The scheduler asks after SP completion. No task was suspended, so it
    // must retire this task rather than enqueueing it again as yielded.
    set_result(context, 0);
    if (++state.rsp_yield_queries == 1U)
      jfg::support_event("rsp=yield-query-completed");
    return 1;
  }
#endif
  hle::HleFunction function{};
  if (std::strcmp(name, "osCreateMesgQueue") == 0) {
    function = hle::HleFunction::kOsCreateMesgQueue;
    ++state.queue_create_calls;
  } else if (std::strcmp(name, "osSendMesg") == 0) {
    function = hle::HleFunction::kOsSendMesg;
    ++state.queue_send_calls;
  } else if (std::strcmp(name, "osJamMesg") == 0) {
    function = hle::HleFunction::kOsJamMesg;
    ++state.queue_send_calls;
  } else if (std::strcmp(name, "osRecvMesg") == 0) {
    function = hle::HleFunction::kOsRecvMesg;
    ++state.queue_recv_calls;
  } else if (std::strcmp(name, "osSpTaskLoad") == 0) {
    ++state.sp_task_load_calls;
    std::uint32_t task_type = 0U;
    if (a0 == 0U || !memory.read_u32(a0, task_type) || task_type > 7U)
      fail_closed_dispatch(state, "hle", "invalid-rsp-task", target);
    if (state.guest_leaf_probe) {
      const auto stack = static_cast<std::uint32_t>(context->r29);
      std::uint32_t flags = 0U;
      recomp_func_t *const generated = jfg_generated_lookup_function(address);
      if (generated == nullptr || state.mmio_trace == nullptr ||
          !state.mmio_trace->guest_sp_status ||
          (state.mmio_trace->sp_status.read() & 0x1dU) != 1U ||
          !memory.read_u32(a0 + 4U, flags) || (flags & 1U) != 0U ||
          (stack & 7U) != 0U || stack < kKseg0 + 0x80U ||
          stack > kKseg0 + kRdramSize - 4U)
        fail_closed_dispatch(state, "guest-leaf", "rsp-load-state", target);
      const auto transfers = state.mmio_trace->sp_dma.transfers();
      trace_guest_clock(state, "guest-sp-load-entry", target);
      generated(rdram, context);
      trace_guest_clock(state, "guest-sp-load-return", target);
      if (static_cast<std::uint32_t>(context->r29) != stack ||
          (state.mmio_trace->sp_status.read() & 0x7dU) != 0x41U ||
          state.mmio_trace->sp_dma.transfers() - transfers != 2U)
        fail_closed_dispatch(state, "guest-leaf", "rsp-load-result", target);
    }
    state.loaded_rsp_task = a0;
    state.loaded_rsp_task_type = task_type;
    return 1;
  } else if (std::strcmp(name, "osSpTaskStartGo") == 0) {
    ++state.sp_task_start_calls;
    if (a0 == 0U || a0 != state.loaded_rsp_task)
      fail_closed_dispatch(state, "hle", "rsp-task-not-loaded", target);
    if (state.guest_leaf_probe) {
      const auto stack = static_cast<std::uint32_t>(context->r29);
      recomp_func_t *const generated = jfg_generated_lookup_function(address);
      if (generated == nullptr || state.mmio_trace == nullptr ||
          !state.mmio_trace->guest_sp_status ||
          (state.mmio_trace->sp_status.read() & 0x1dU) != 1U ||
          (stack & 7U) != 0U || stack < kKseg0 + 0x20U ||
          stack > kKseg0 + kRdramSize - 4U)
        fail_closed_dispatch(state, "guest-leaf", "rsp-start-state", target);
      trace_guest_clock(state, "guest-sp-start-entry", target);
      generated(rdram, context);
      trace_guest_clock(state, "guest-sp-start-return", target);
      if ((state.mmio_trace->sp_status.read() & 0x7fU) != 0x40U ||
          static_cast<std::uint32_t>(context->r29) != stack)
        fail_closed_dispatch(state, "guest-leaf", "rsp-start-result", target);
    }
#if defined(JFG_PHASE8_LIVE_RUNTIME)
    if (state.loaded_rsp_task_type == 2U) {
#if defined(_WIN32)
      write_private_progress(state, "audio-begin");
#endif
      const auto audio_start = std::chrono::steady_clock::now();
      const bool audio_ok = execute_live_audio_task(state, memory);
      state.audio_task_microseconds += static_cast<std::uint64_t>(
          std::chrono::duration_cast<std::chrono::microseconds>(
              std::chrono::steady_clock::now() - audio_start)
              .count());
#if defined(_WIN32)
      write_private_progress(state, "audio-end");
#endif
      if (!audio_ok)
        fail_closed_dispatch(state, "rsp", "audio-task-rejected", target);
#if defined(_WIN32)
      complete_guest_sp_status(state, target);
      write_private_progress(state, "audio-completion-begin");
#endif
      const auto sp = state.events.find(4U);
      if (state.scheduler == nullptr || sp == state.events.end() ||
          state.scheduler->send(sp->second.first, sp->second.second, false) !=
              hle::kOsSuccess)
        fail_closed_dispatch(state, "rsp", "sp-completion", target);
#if defined(_WIN32)
      write_private_progress(state, "audio-completion-end");
#endif
      state.loaded_rsp_task = 0U;
      state.loaded_rsp_task_type = 0U;
      if (state.scheduler_running) {
#if defined(_WIN32)
        write_private_progress(state, "audio-yield-begin");
#endif
        state.scheduler->yield_current();
#if defined(_WIN32)
        write_private_progress(state, "audio-yield-end");
#endif
      }
      return 1;
    }
#if defined(_WIN32)
    if (state.loaded_rsp_task_type == 1U) {
      write_private_progress(state, "graphics-prepare-begin");
      const auto graphics_start = std::chrono::steady_clock::now();
      constexpr std::uint64_t kFastReplayRenderWindow = 240U;
      // A requested RDRAM capture is a renderer diagnostic and must preserve
      // the complete RT64 task history; otherwise a late failure can disappear
      // because all of its prerequisite workloads were intentionally skipped.
      const bool skip_graphics =
          state.fast_replay && !state.renderer_writeback_probe && state.poll_target == 0U &&
          state.rdram_capture_path.empty() &&
          state.vi_retraces + kFastReplayRenderWindow < state.retrace_target;
      bool graphics_ok = true;
      std::uint32_t command_size = 0U;
      if (skip_graphics &&
          !memory.read_u32(state.loaded_rsp_task + 0x34U, command_size))
        graphics_ok = false;
      const bool preserve_immediate_task =
          skip_graphics && is_immediate_offscreen_task_candidate(command_size);
      if (graphics_ok && skip_graphics && !preserve_immediate_task) {
        PendingLiveGraphicsTask pending{};
        pending.skipped = true;
        state.pending_graphics_tasks.push_back(std::move(pending));
      } else if (graphics_ok) {
        graphics_ok = execute_live_graphics_task(state, memory);
      }
      const auto prepare_us = static_cast<std::uint64_t>(
          std::chrono::duration_cast<std::chrono::microseconds>(
              std::chrono::steady_clock::now() - graphics_start)
              .count());
      state.gameplay_trace.event("prepare", {state.vi_retraces, state.controller_samples,
          state.gameplay_trace_updates, prepare_us, state.last_graphics_command_address,
          state.last_graphics_descriptor[5]});
      state.graphics_prepare_microseconds += prepare_us;
      state.graphics_prepare_max_us =
          (std::max)(state.graphics_prepare_max_us, prepare_us);
      if (state.timing_trace) {
        state.timing_trace << "prepare\t" << state.vi_frames << '\t'
                           << state.vi_retraces << '\t' << prepare_us << '\t'
                           << std::hex << state.last_graphics_command_address
                           << std::dec << '\n';
      }
      write_private_progress(state, "graphics-prepare-end");
      if (!graphics_ok) {
        std::array<char, 192U> operation{};
        (void)std::snprintf(
            operation.data(), operation.size(),
            "gfx-%u-c%08x-n%x-m%u-a%08x-w%08x-%08x-"
            "p%08x-%08x-%08x-b%08x-s%08x",
            static_cast<unsigned>(state.last_rt64_error),
            state.last_graphics_command_address,
            state.last_graphics_descriptor[5],
            state.materialize_reject_reason,
            state.materialize_reject_address,
            state.materialize_reject_word0,
            state.materialize_reject_word1,
            state.materialize_parent_address,
            state.materialize_parent_word0,
            state.materialize_parent_word1,
            state.materialize_block_address,
            state.materialize_parent_segment_base);
        fail_closed_dispatch(state, "rsp", operation.data(), target);
      }
      // Tiny actor passes can finish within the same VI as in the oracle.
      // The completion path fails closed if one ever targets a displayed
      // framebuffer; main scene tasks retain VI-boundary completion pacing.
      if (!state.pending_graphics_tasks.empty() &&
          !state.pending_graphics_tasks.back().skipped &&
          is_immediate_offscreen_task_candidate(
              state.last_graphics_descriptor[5]))
        complete_pending_live_graphics_tasks(state, target, true);
      state.loaded_rsp_task = 0U;
      state.loaded_rsp_task_type = 0U;
      if (state.scheduler_running)
        state.scheduler->yield_current();
      return 1;
    }
#endif
#endif
    fail_closed_dispatch(state, "hle",
                         state.loaded_rsp_task_type == 1U
                             ? "osSpTaskStartGo-gfx"
                             : "osSpTaskStartGo-other",
                         target);
  } else {
    fail_closed_dispatch(state, "hle", name, target);
  }
  const bool recv = function == hle::HleFunction::kOsRecvMesg;
  const bool clock_queue = a0 == game_data("diagnostic.schedulerQueue") || a0 == game_data("diagnostic.cloneDoneQueue") ||
                           a0 == game_data("diagnostic.clockQueue");
  if (clock_queue) trace_guest_clock(state, recv ? "recv" : "queue-call", a0);
#if defined(_WIN32) && defined(JFG_PHASE8_LIVE_RUNTIME)
  if (state.focus_update_start != 0U &&
      state.completed_game_updates + 1U >= state.focus_update_start - 1U &&
      state.completed_game_updates + 1U <= state.focus_update_end + 1U &&
      state.timing_trace.is_open() &&
      (a0 == game_data("diagnostic.schedulerQueue") || a0 == game_data("diagnostic.cloneDoneQueue") ||
       a0 == game_data("diagnostic.clockQueue"))) {
    state.timing_trace << "game-queue-call\t" << state.vi_frames << '\t'
                       << state.vi_retraces << "\t0\t"
                       << (recv ? "recv" :
                           function == hle::HleFunction::kOsCreateMesgQueue
                               ? "create" : "send")
                       << '\t' << state.completed_game_updates << '\t'
                       << state.scheduler->current_thread_id() << '\t'
                       << std::hex << a0 << ':' << a1 << ':' << a2 << ':'
                       << static_cast<std::uint32_t>(context->r31)
                       << std::dec << '\n';
  }
#endif
  if (recv) {
    trace_si_timing(state, "recv-entry", a0,
                    static_cast<std::uint32_t>(context->r31),
                    static_cast<std::int32_t>(a2));
    const auto si = state.events.find(5U);
    if (si != state.events.end() && a0 == si->second.first) {
      ++state.si_receive_calls;
      state.last_si_receive_return = static_cast<std::uint32_t>(context->r31);
      state.last_si_receive_block = a2;
      if (a2 == static_cast<std::uint32_t>(hle::kOsMesgBlock)) {
        for (std::size_t index = 0U;
             index < state.last_si_dispatch_trace.size(); ++index) {
          const std::size_t distance =
              state.last_si_dispatch_trace.size() - index;
          state.last_si_dispatch_trace[index] =
              state.recent_dispatch_position >= distance
                  ? state.recent_dispatches[
                        (state.recent_dispatch_position - distance) %
                        state.recent_dispatches.size()]
                  : 0U;
        }
      }
    }
  }
  const bool send = function == hle::HleFunction::kOsSendMesg ||
                    function == hle::HleFunction::kOsJamMesg;
  if (send) {
    const auto block = static_cast<std::int32_t>(a2);
    if (state.scheduler == nullptr || !state.queues.contains(a0) ||
        (block != hle::kOsMesgNoBlock && block != hle::kOsMesgBlock)) {
      fail_closed_dispatch(state, "hle", "invalid-send", target);
    }
    const auto result = state.scheduler->send(
        a0, a1, function == hle::HleFunction::kOsJamMesg);
    if (result == hle::kOsSuccess) {
      set_result(context, result);
      if (state.scheduler_running)
        state.scheduler->yield_current();
      return 1;
    }
    if (block == hle::kOsMesgNoBlock) {
      set_result(context, hle::kOsFull);
      return 1;
    }
    if (!state.scheduler_running || state.scheduler->current_thread_id() < 0)
      fail_closed_dispatch(state, "hle", "blocking-send-outside-thread", target);
    // Validate the full queue before parking; corrupt state must not become
    // an endless wait. No other guest runs between the failed send and here.
    if (hle::dispatch_queue_call(memory, {function, a0, a1, a2}).disposition !=
        hle::QueueDispatchDisposition::block)
      fail_closed_dispatch(state, "hle", "blocking-send-invalid-queue", target);
    set_result(context, state.scheduler->send_blocking(
        a0, a1, function == hle::HleFunction::kOsJamMesg));
    return 1;
  }
  const auto received_vi_message = [&]() {
    std::uint32_t message = 0U;
    return recv && a0 == state.vi_queue && a1 != 0U &&
           memory.read_u32(a1, message) && message == state.vi_message;
  };
  const auto trace_vi_queue_receive = [&]() {
#if defined(_WIN32) && defined(JFG_PHASE8_LIVE_RUNTIME)
    const bool focused_receive = state.focus_update_start != 0U &&
        state.completed_game_updates + 1U >= state.focus_update_start - 1U &&
        state.completed_game_updates + 1U <= state.focus_update_end + 1U;
    if (recv && a0 == state.vi_queue &&
        (state.actor_timing_trace || focused_receive) &&
        state.timing_trace.is_open()) {
      std::uint32_t message = 0U;
      const bool readable = a1 != 0U && memory.read_u32(a1, message);
      state.timing_trace << "vi-queue-receive\t" << state.vi_frames << '\t'
                         << state.vi_retraces << "\t0\t"
                         << (readable ? std::to_string(message) : "unreadable")
                         << '\t' << state.vi_message << '\t'
                         << state.vi_messages_delivered << '\t'
                         << (received_vi_message() &&
                             state.vi_messages_delivered > state.vi_retraces)
                         << '\n';
    }
#endif
  };
  const auto result = hle::dispatch_queue_call(memory, {function, a0, a1, a2});
  if (state.guest_leaf_probe && recv && a1 == 0U && a2 == 0U &&
      result.disposition == hle::QueueDispatchDisposition::accepted &&
      result.return_value == hle::kOsEmpty) {
    // The validated empty nonblocking path made no queue mutation and never
    // follows guest wait lists. Execute its original Status/save/restore path.
    // Other queue paths still require a guest-thread bridge; they are NOT
    // silently declared instruction-accounted by this partial probe.
    const auto sp = static_cast<std::uint32_t>(context->r29);
    if ((sp & 7U) != 0U || sp < kKseg0 + 0x28U ||
        sp > kKseg0 + kRdramSize - 12U)
      fail_closed_dispatch(state, "guest-leaf", "queue-stack-range", target);
    recomp_func_t *const generated = jfg_generated_lookup_function(address);
    if (generated == nullptr)
      fail_closed_dispatch(state, "guest-leaf", "queue-unavailable", target);
    const auto status = cop0_status_read(context);
    trace_guest_clock(state, "guest-queue-empty-entry", target);
    generated(rdram, context);
    trace_guest_clock(state, "guest-queue-empty-return", target);
    if (static_cast<std::int64_t>(context->r2) != hle::kOsEmpty ||
        static_cast<std::uint32_t>(context->r29) != sp || cop0_status_read(context) != status)
      fail_closed_dispatch(state, "guest-leaf", "queue-empty-result", target);
  }
  if (recv && result.disposition == hle::QueueDispatchDisposition::accepted)
    trace_si_timing(state, "recv-return", a0,
                    static_cast<std::uint32_t>(context->r31), result.return_value);
  if (result.disposition == hle::QueueDispatchDisposition::accepted) {
    if (recv && clock_queue) trace_guest_clock(state, "recv-return", a0);
    if (function == hle::HleFunction::kOsCreateMesgQueue) {
      state.queues.insert(a0);
      state.journal.append(NativeEventKind::kQueueCreated, a0, a1, a2);
    }
    if (function != hle::HleFunction::kOsCreateMesgQueue) {
      set_result(context, result.return_value);
    }
    if (recv && result.return_value == hle::kOsSuccess && state.scheduler != nullptr)
      state.scheduler->notify_received(a0);
#if defined(JFG_PHASE8_LIVE_RUNTIME)
    if (recv) {
      state.last_receive_queue = a0;
      state.last_receive_block = a2;
      state.last_receive_result = result.return_value;
      if (result.return_value == hle::kOsSuccess)
        ++state.receive_successes;
      else
        ++state.receive_empties;
    }
    if (recv && result.return_value == hle::kOsSuccess) {
      state.empty_receive_polls.erase(a0);
    } else if (recv &&
               a2 == static_cast<std::uint32_t>(hle::kOsMesgNoBlock)) {
      std::uint32_t &poll_count = state.empty_receive_polls[a0];
      ++poll_count;
      if (poll_count >= kEmptyReceivePollTimeslice &&
          state.scheduler_running && state.scheduler != nullptr &&
          state.scheduler->current_thread_id() >= 0 &&
          state.vi_internal_queue != 0U) {
        state.empty_receive_polls.clear();
        ++state.interrupt_timeslices;
        state.scheduler->preempt_current();
      }
    }
#endif
    if (recv && result.return_value == hle::kOsSuccess)
      trace_vi_queue_receive();
    if (function == hle::HleFunction::kOsRecvMesg &&
        result.return_value == hle::kOsSuccess && received_vi_message() &&
        state.vi_messages_delivered > state.vi_retraces) {
      ++state.vi_retraces;
      {
#if defined(_WIN32) && defined(JFG_PHASE8_LIVE_RUNTIME)
        const DiagnosticHostStage breadcrumb_stage(state,"host-profile-breadcrumb");
#endif
        jfg::support_breadcrumb(state.vi_frames, state.vi_retraces, state.controller_samples);
#if defined(_WIN32) && defined(JFG_PHASE8_LIVE_RUNTIME)
        support_mouse_snapshot(state);
#endif
        }
#if defined(_WIN32) && defined(JFG_PHASE8_LIVE_RUNTIME)
      trace_phase9_event(state, "vi-consumed", state.controller_samples);
#endif
      state.journal.append(NativeEventKind::kViMessageConsumed, a0, a1,
                           static_cast<std::uint32_t>(state.vi_retraces));
#if defined(_WIN32) && defined(JFG_PHASE8_LIVE_RUNTIME)
      write_retrace_semantic_hash(state);
      write_private_progress(state);
#endif
      if (state.vi_retraces >= state.retrace_target)
        retrace_gate(state);
    }
    return 1;
  }
  if (result.disposition == hle::QueueDispatchDisposition::reject) {
    const auto block = static_cast<std::int32_t>(a2);
    if (!state.queues.contains(a0)) {
      std::array<char, 32U> operation{};
      (void)std::snprintf(operation.data(), operation.size(),
                          "unknown-queue-%08x", a0);
      fail_closed_dispatch(state, "hle", operation.data(), target);
    }
    const char *reason = block != hle::kOsMesgNoBlock &&
                                   block != hle::kOsMesgBlock
                             ? "invalid-block-mode"
                         : recv && a1 != 0U &&
                                   (a1 < kKseg0 || a1 - kKseg0 >
                                                       kRdramSize - 4U)
                             ? "invalid-message-output"
                             : "corrupt-queue";
    fail_closed_dispatch(state, "hle", reason, target);
  }
  if (recv && state.scheduler != nullptr && state.scheduler_running) {
#if defined(JFG_PHASE8_LIVE_RUNTIME)
    ++state.receive_blocks;
    state.last_receive_queue = a0;
    state.last_receive_block = a2;
#endif
    const std::int32_t receive_result =
        state.scheduler->recv_blocking(a0, a1);
    if (clock_queue) trace_guest_clock(state, "recv-resume", a0);
    trace_si_timing(state, "recv-resume", a0,
                    static_cast<std::uint32_t>(context->r31), receive_result);
    set_result(context, receive_result);
    if (receive_result == hle::kOsSuccess)
      trace_vi_queue_receive();
#if defined(JFG_PHASE8_LIVE_RUNTIME)
    state.last_receive_result = receive_result;
    if (receive_result == hle::kOsSuccess)
      ++state.receive_successes;
#endif
    if (receive_result == hle::kOsSuccess && received_vi_message() &&
        state.vi_messages_delivered > state.vi_retraces) {
      ++state.vi_retraces;
      {
#if defined(_WIN32) && defined(JFG_PHASE8_LIVE_RUNTIME)
        const DiagnosticHostStage breadcrumb_stage(state,"host-profile-breadcrumb");
#endif
        jfg::support_breadcrumb(state.vi_frames, state.vi_retraces, state.controller_samples);
#if defined(_WIN32) && defined(JFG_PHASE8_LIVE_RUNTIME)
        support_mouse_snapshot(state);
#endif
        }
#if defined(_WIN32) && defined(JFG_PHASE8_LIVE_RUNTIME)
      trace_phase9_event(state, "vi-consumed", state.controller_samples);
#endif
      state.journal.append(NativeEventKind::kViMessageConsumed, a0, a1,
                           static_cast<std::uint32_t>(state.vi_retraces));
#if defined(_WIN32) && defined(JFG_PHASE8_LIVE_RUNTIME)
      write_retrace_semantic_hash(state);
      write_private_progress(state);
#endif
      if (state.vi_retraces >= state.retrace_target)
        retrace_gate(state);
    }
    return 1;
  }
  fail_closed_dispatch(state, "hle",
                       recv ? "blocking-recv"
                            : (function == hle::HleFunction::kOsJamMesg
                                   ? "blocking-jam"
                                   : "blocking-send"),
                       target);
}

int native_cpu_operation(void* opaque, void* guest_context, std::uint32_t operation,
                         std::uint32_t selector, std::uint64_t* value) {
  auto& state = *static_cast<State*>(opaque);
  if (!state.guest_leaf_probe || guest_context == nullptr || value == nullptr) return 0;
  auto* context = static_cast<recomp_context*>(guest_context);
  // This bridge has only a 32-bit virtual-address model. Do not pretend
  // that enabling extended addressing supplies a compatible EntryHi state.
  if ((static_cast<std::uint32_t>(cop0_status_read(context)) & 0xe0U) != 0U) return 0;
  if (state.guest_os_probe) {
    if (operation == JFG_CPU_READ_MI_MASK || operation == JFG_CPU_WRITE_MI_MASK) {
      auto* trace = state.mmio_trace;
      if (selector != 0xa430000cU || trace == nullptr ||
          !state.diagnostic_host_clock || !trace->native_elapsed_time ||
          !trace->guest_execution || !trace->guest_mi_mask ||
          !trace->mi_mask.initialized() || trace->pending_page != nullptr) return 0;
      const auto address = reinterpret_cast<std::uintptr_t>(trace->pages[2U]) + 0x0cU;
      if (operation == JFG_CPU_READ_MI_MASK) {
        trace->record(2U, address, false);
        *value = trace->mi_mask.read();
        ++trace->direct_mi_mask_reads;
        return 1;
      }
      auto next = trace->mi_mask;
      if (*value > UINT32_MAX || !next.command(static_cast<std::uint32_t>(*value))) return 0;
      trace->record(2U, address, true);
      trace->mi_mask = next;
      ++trace->direct_mi_mask_writes;
      ++trace->execution_io_revision;
      trace->device_write_page = 2U;
      trace->device_write_offset = 0x0cU;
      trace->device_write_value = next.read();
      // The device model owns this register. Any subsequent guarded access
      // refreshes the page mirror before the host load executes.
      return 1;
    }
    const auto extend = [](std::uint32_t word) {
      return static_cast<std::uint64_t>(static_cast<std::int64_t>(static_cast<std::int32_t>(word)));
    };
    if (operation == JFG_CPU_READ_REGISTER) {
      if (selector == 9U) { *value = extend(static_cast<std::uint32_t>(state.cpu_count)); return 1; }
      if (selector == 11U) { *value = extend(state.guest_timer.read()); return 1; }
      if (selector == 13U) {
        *value = extend(state.guest_cause |
            (state.guest_timer.interrupt() ? 0x8000U : 0U) |
            ((state.mmio_trace->mi_pending & state.mmio_trace->mi_mask.read()) ? 0x400U : 0U));
        return 1;
      }
      if (selector == 14U) { *value = extend(state.guest_epc); return 1; }
    }
    if (operation == JFG_CPU_WRITE_REGISTER) {
      state.execution_fast_deadline = 0U;
      state.native_fast_ready = false;
      if (selector == 11U) {
        if (!state.guest_timer.write(state.cpu_count, static_cast<std::uint32_t>(*value)))
          fail_closed_dispatch(state, "guest-cpu", "unqualified-compare-write", state.guest_last_pc);
        if (state.guest_clock_trace)
          state.guest_clock_trace << "compare\t" << state.cpu_count << '\t'
              << static_cast<std::uint32_t>(*value) << '\n';
        return 1;
      }
      if (selector == 13U) {
        state.guest_cause = (state.guest_cause & ~0x300U) | (static_cast<std::uint32_t>(*value) & 0x300U);
        return 1;
      }
      if (selector == 14U) { state.guest_epc = static_cast<std::uint32_t>(*value); return 1; }
    }
    if (operation == JFG_CPU_EXCEPTION_RETURN) {
      std::uint32_t next = 0U;
      hle::GuestMemory memory({state.rdram, kRdramSize}, hle::GuestMemory::Layout::native_word_big_endian);
      if ((context->status_reg & 6U) != 2U || state.guest_transport == nullptr ||
          !memory.read_u32(kOsCurrentThread, next) || next < kKseg0 || next > kKseg0 + kRdramSize - 0x1b0U)
        return 0;
      cop0_status_write(context, context->status_reg & ~2U);
      state.guest_previous_branch = state.guest_previous_delay = false;
      state.guest_eret_boundary = true;
      state.native_fast_ready = false;
#if defined(_WIN32) && defined(JFG_PHASE8_LIVE_RUNTIME)
      if(state.diagnostic_function_profile && !state.diagnostic_host_clock)
        (void)sample_model_thread(state,next,next);
#endif
      state.guest_transport->eret(next, state.guest_epc, *context);
      return 1;
    }
  }
  if (operation == JFG_CPU_CACHE_OPERATION)
    return reference_coherent_cache_operation(selector, *value, kRdramSize) ? 1 : 0;
  if (operation == JFG_CPU_READ_REGISTER) {
    // Only the independently qualified cold-boot osInitialize path. The
    // cooperative runtime does not model live Cause/exception delivery.
    if (selector == 13U && !state.os_initialized && !state.scheduler_running) {
      *value = 0U;
      return 1;
    }
    const auto result = state.tlb_registers.read(selector);
    if (!result) return 0;
    *value = static_cast<std::uint64_t>(static_cast<std::int64_t>(
        static_cast<std::int32_t>(*result)));
    return 1;
  }
  if (operation == JFG_CPU_WRITE_REGISTER)
    return state.tlb_registers.write(selector, static_cast<std::uint32_t>(*value)) ? 1 : 0;
  if (operation == JFG_CPU_TLB_OPERATION) {
    switch (selector) {
    case 0: return state.tlb_registers.probe() ? 1 : 0;
    case 1: return state.tlb_registers.read_indexed() ? 1 : 0;
    case 2: return state.tlb_registers.write_indexed() ? 1 : 0;
    default: return 0;
    }
  }
  return 0;
}



#if defined(_WIN32)
// These helpers are called only by pinned private SP-routine variants. Unknown
// addresses, unsupported device operations and disabled mode retain the original
// guarded memory access. No guarded MMIO page is unprotected or written here.
static std::optional<std::pair<std::size_t,std::uint32_t>> direct_sp_address(std::uint64_t base,std::int16_t offset) {
  if(!g_mmio_trace || !g_mmio_trace->direct_sp_access || !g_mmio_trace->guest_sp_status ||
      !g_mmio_trace->guest_execution || g_mmio_trace->pending_page)return std::nullopt;
  const auto address=base+static_cast<std::uint64_t>(static_cast<std::int64_t>(offset));
  const auto low=static_cast<std::uint32_t>(address);
  if(address!=U64(S32(low)) || (low&3U))return std::nullopt;
  if(low>=0xa4040000U && low<=0xa404001cU)return std::pair<std::size_t,std::uint32_t>{0U,low-0xa4040000U};
  if(low==0xa4080000U)return std::pair<std::size_t,std::uint32_t>{8U,0U};
  return std::nullopt;
}
extern "C" std::int32_t jfg_sp_load_word(std::uint8_t* rdram,std::uint64_t base,std::int16_t offset) {
  if(const auto location=direct_sp_address(base,offset)) {
    const auto [page,reg]=*location;
    if(const auto value=read_sp_register(*g_mmio_trace,page,reg)) {
      g_mmio_trace->record(page,reinterpret_cast<std::uintptr_t>(g_mmio_trace->pages[page])+reg,false);
      ++g_mmio_trace->direct_sp_reads;
      return static_cast<std::int32_t>(*value);
    }
  }
  return MEM_W(base,offset);
}
extern "C" void jfg_sp_store_word(std::uint8_t* rdram,std::uint64_t base,std::int16_t offset,std::int32_t input) {
  if(const auto location=direct_sp_address(base,offset)) {
    const auto [page,reg]=*location;auto value=static_cast<std::uint32_t>(input);
    if(apply_sp_register_write(*g_mmio_trace,page,reg,value)) {
      g_mmio_trace->record(page,reinterpret_cast<std::uintptr_t>(g_mmio_trace->pages[page])+reg,true);
      ++g_mmio_trace->direct_sp_writes;
      ++g_mmio_trace->execution_io_revision;
      g_mmio_trace->device_write_page=static_cast<std::uint32_t>(page);
      g_mmio_trace->device_write_offset=reg;g_mmio_trace->device_write_value=value;
      return;
    }
  }
  MEM_W(offset,base)=input;
}
#endif

// Called only by an explicitly instrumented, private generated-code copy.
// An ordinary generated root contains no call sites and is unaffected.
extern "C" void jfg_phase9_instruction_probe(uint32_t pc, uint8_t *rdram,
                                               recomp_context *context) {
#if defined(_WIN32) && defined(JFG_PHASE8_LIVE_RUNTIME)
  State *const state = g_active_child_state;
  if (state == nullptr || !state->instruction_probe_trace.is_open() ||
      rdram != state->rdram || context == nullptr ||
      state->focus_update_start == 0U ||
      state->completed_game_updates + 1U < state->focus_update_start - 1U ||
      state->completed_game_updates + 1U > state->focus_update_end + 1U)
    return;
  if (++state->instruction_probe_hits > 1024U) {
    std::fputs("native instruction probe overflow\n", stderr);
    std::abort();
  }
  auto &out = state->instruction_probe_trace;
  out << state->completed_game_updates + 1U << '\t'
      << state->vi_retraces << '\t' << state->controller_samples << '\t'
      << "0x" << std::hex << std::setw(8) << std::setfill('0') << pc;
  const std::array<std::uint64_t, 11U> gprs = {
      context->r4, context->r5, context->r6, context->r7,
      context->r10, context->r15, context->r19, context->r20,
      context->r21, context->r23, context->r25};
  for (const auto value : gprs)
    out << '\t' << "0x" << std::setw(8)
        << static_cast<std::uint32_t>(value);
  out << '\t' << "0x" << std::setw(8) << context->f4.u32l
      << '\t' << "0x" << std::setw(8) << context->f22.u32l
      << '\t' << "0x" << std::setw(8)
      << (context->f_odd != nullptr ? context->f_odd[(23U - 1U) * 2U] : 0U)
      << std::dec << '\t' << std::fegetround() << '\n';
  out.flush();
#else
  (void)pc;
  (void)rdram;
  (void)context;
#endif
}

#if defined(_WIN32) && defined(JFG_PHASE8_LIVE_RUNTIME)
// Host-only diagnostic data. Instruction-entry/successor samples do not by
// themselves prove retirement, a completed receive or caller equivalence.
static void emit_device_event(State& state, const recomp_context& cpu,
    unsigned phase, unsigned source, std::uint32_t pc, std::uint32_t word,
    std::optional<std::uint64_t> deadline = std::nullopt) {
  if (!state.device_event_stream || state.device_event_probe.complete) return;
  const auto invocation = state.completed_game_updates + 1U;
  if (invocation < state.device_event_probe.first) return;
  if (invocation > state.device_event_probe.last) {
    if (!jfg_device_event_finish(&state.device_event_probe))
      fail_closed_dispatch(state, "device-event-probe", "output-failed", pc);
    return;
  }
  jfg_device_event_row row{};
  row.invocation = static_cast<std::uint32_t>(invocation);
  row.phase = phase; row.source = source; row.pc = pc; row.opcode = word;
  row.previous_pc = state.device_event_previous_pc;
  row.previous_opcode = state.device_event_previous_word;
  row.clock_raw = static_cast<std::uint32_t>(state.cpu_count);
  row.clock_anchor_pc = pc;
  row.deadline_valid = deadline.has_value() ? 1U : 0U;
  row.deadline = static_cast<std::uint32_t>(deadline.value_or(0));
  row.status = cpu.status_reg;
  row.mi_pending = state.mmio_trace->mi_pending;
  row.mi_mask = state.mmio_trace->mi_mask.read();
  // Same pure value composition as JFG_CPU_READ_REGISTER selector 13; do not
  // report only the software latch while omitting pending hardware lines.
  row.cause = state.guest_cause | (state.guest_timer.interrupt() ? 0x8000U : 0U) |
      ((row.mi_pending & row.mi_mask) ? 0x400U : 0U);
  hle::GuestMemory memory({state.rdram, kRdramSize}, hle::GuestMemory::Layout::native_word_big_endian);
  if (!memory.read_u32(kOsCurrentThread, row.thread))
    fail_closed_dispatch(state, "device-event-probe", "thread-read", pc);
  const std::array<std::uint64_t, 32> registers = {
    0, cpu.r1, cpu.r2, cpu.r3, cpu.r4, cpu.r5, cpu.r6, cpu.r7,
    cpu.r8, cpu.r9, cpu.r10, cpu.r11, cpu.r12, cpu.r13, cpu.r14, cpu.r15,
    cpu.r16, cpu.r17, cpu.r18, cpu.r19, cpu.r20, cpu.r21, cpu.r22, cpu.r23,
    cpu.r24, cpu.r25, cpu.r26, cpu.r27, cpu.r28, cpu.r29, cpu.r30, cpu.r31};
  std::copy(registers.begin(), registers.end(), row.gpr);
  if (!jfg_device_event_emit(&state.device_event_probe, &row))
    fail_closed_dispatch(state, "device-event-probe", "output-or-budget", pc);
}

void emit_instruction_effect(State& state, const recomp_context& cpu,
    unsigned phase, unsigned section, unsigned pc, unsigned word,
    std::uint32_t target, std::uint32_t selected_owner) {
  if (!state.instruction_effect_stream.is_open()) return;
  const auto invocation = static_cast<std::uint32_t>(state.completed_game_updates + 1U);
  if (!state.instruction_effect_trace.advance(invocation))
    fail_closed_dispatch(state, "instruction-effect-probe", "incomplete-or-output", pc);
  if (invocation != state.instruction_effect_update) return;
  if (!state.guest_os_probe || !state.guest_transport || !state.device_event_stream ||
      state.device_event_probe.complete)
    fail_closed_dispatch(state, "instruction-effect-probe", "unqualified-runtime", pc);
  InstructionEffectRow row{};
  row.phase = phase; row.section = section; row.pc = pc; row.opcode = word;
  row.owner = state.guest_transport->current();
  row.count = static_cast<std::uint32_t>(state.cpu_count);
  row.status = cpu.status_reg;
  row.cause = state.guest_cause | (state.guest_timer.interrupt() ? 0x8000U : 0U) |
      ((state.mmio_trace->mi_pending & state.mmio_trace->mi_mask.read()) ? 0x400U : 0U);
  row.target = target; row.selected_owner = selected_owner;
  row.device_sequence = state.device_event_probe.rows;
  hle::GuestMemory memory({state.rdram, kRdramSize}, hle::GuestMemory::Layout::native_word_big_endian);
  if (!memory.read_u32(kOsCurrentThread, row.thread_word))
    fail_closed_dispatch(state, "instruction-effect-probe", "thread-read", pc);
  row.gpr = {0, cpu.r1, cpu.r2, cpu.r3, cpu.r4, cpu.r5, cpu.r6, cpu.r7,
    cpu.r8, cpu.r9, cpu.r10, cpu.r11, cpu.r12, cpu.r13, cpu.r14, cpu.r15,
    cpu.r16, cpu.r17, cpu.r18, cpu.r19, cpu.r20, cpu.r21, cpu.r22, cpu.r23,
    cpu.r24, cpu.r25, cpu.r26, cpu.r27, cpu.r28, cpu.r29, cpu.r30, cpu.r31};
  if (!state.instruction_effect_trace.emit(invocation, row))
    fail_closed_dispatch(state, "instruction-effect-probe", "pair-boundary-or-budget", pc);
  if (phase == 0U) state.instruction_effect_section = section;
}
#endif

// The generated entry hook is after execution_probe returns: asynchronous
// exception processing must finish before this instruction becomes pending.
extern "C" void jfg_phase9_instruction_effect_entry(unsigned section, unsigned pc,
    unsigned word, unsigned qualification, void* context) {
#if defined(_WIN32) && defined(JFG_PHASE8_LIVE_RUNTIME)
  if (g_active_child_state != nullptr && context != nullptr) {
    auto& state = *g_active_child_state;
    if (!state.instruction_effect_stream.is_open()) return;
    if (state.completed_game_updates + 1U == state.instruction_effect_update &&
        (qualification > 1U || (qualification == 1U) != (word == 0x42000018U)))
      fail_closed_dispatch(state, "instruction-effect-probe", "unqualified-instruction", pc);
    emit_instruction_effect(state, *static_cast<recomp_context*>(context), 0U, section, pc, word);
  }
#else
  (void)section; (void)pc; (void)word; (void)qualification; (void)context;
#endif
}

extern "C" void jfg_phase9_instruction_effect(unsigned section, unsigned pc,
    unsigned word, void* context) {
#if defined(_WIN32) && defined(JFG_PHASE8_LIVE_RUNTIME)
  if (g_active_child_state != nullptr && context != nullptr)
    emit_instruction_effect(*g_active_child_state, *static_cast<recomp_context*>(context),
                            1U, section, pc, word);
#else
  (void)section; (void)pc; (void)word; (void)context;
#endif
}

// Only called by a separately regenerated private observation root. Count
// entered instruction sites, including loop iterations and executed slots.
// The default is observation-only. The separate guest-OS diagnostic executes
// original OS bodies, with the bounded reference CPU/device profile below.
// Keep the execution probe out of hot instruction sites on every compiler.
#if defined(_MSC_VER)
#define JFG_EXECUTION_NOINLINE __declspec(noinline)
#elif defined(__GNUC__) || defined(__clang__)
#define JFG_EXECUTION_NOINLINE __attribute__((noinline))
#else
#define JFG_EXECUTION_NOINLINE
#endif
extern "C" JFG_EXECUTION_NOINLINE void jfg_phase9_execution_probe_slow(
    unsigned section, unsigned pc, unsigned word, void* context);

// Keep the common instruction path independent of the rare device/exception
// path's large stack frame. The same predicate, cost and state updates run.
extern "C" void jfg_phase9_execution_probe(unsigned section, unsigned pc,
                                          unsigned word, void* context) {
#if defined(_WIN32) && defined(JFG_PHASE8_LIVE_RUNTIME)
  if (g_active_child_state != nullptr && context != nullptr) {
    auto& state = *g_active_child_state;
    if (state.diagnostic_cpu_costs) ++state.profile_out_of_line_instructions;
    if (state.diagnostic_host_clock) {
      jfg_phase9_execution_probe_slow(section,pc,word,context);
      return;
    }
    // Private optimization: ordinary instructions before the next event need
    // only the same cost and pipeline bookkeeping. Hardware writes, interrupt
    // eligibility, exception return and observers fall back to the full path.
    if ((state.execution_fast_profile_ready ||
         (state.diagnostic_host_clock && state.host_clock_poll_budget > 0U && --state.host_clock_poll_budget > 0U)) &&
        !state.guest_eret_boundary && word != 0x1000FFFFU &&
        pc != kViInitializeSite && pc != kViManagerIdleSite &&
        (state.play_mode || state.observed_guest_instructions < 24000000000ULL) &&
        state.execution_fast_deadline > state.cpu_count &&
        state.execution_fast_revision == state.mmio_trace->execution_io_revision) {
      auto& cpu = *static_cast<recomp_context*>(context);
      const unsigned primary = word >> 26U;
      const bool fpu = primary == 0x11U || primary == 0x31U ||
          primary == 0x35U || primary == 0x39U || primary == 0x3DU;
      const bool eligible = (cpu.status_reg & 7U) == 1U &&
          (state.execution_fast_pending & cpu.status_reg & 0xFF00U) != 0U;
      const bool park = primary == 3U &&
          (((pc + 4U) & 0xF0000000U) | ((word & 0x03FFFFFFU) << 2U)) == kOsSchedulerPark;
      if (!eligible && !(fpu && (cpu.status_reg & 0x20000000U) == 0U) && !park) {
        ++state.observed_guest_instructions;
        ++state.execution_fast_hits;
        const bool delay = state.guest_previous_branch && pc == state.guest_last_pc + 4U;
        if (!state.diagnostic_host_clock) {
          const auto cycles = jfg_full_cache_cost(pc,word,&cpu,state.rdram) + state.diagnostic_cpu_half_tick;
          state.cpu_count += cycles / 2U;
          state.diagnostic_cpu_half_tick = cycles % 2U;
        }
        state.mmio_trace->guest_count = state.cpu_count;
        state.guest_last_pc = pc;
        state.guest_last_word = word;
        state.guest_previous_delay = delay;
        state.guest_previous_branch = primary == 1U || (primary >= 2U && primary <= 7U) ||
            (primary >= 20U && primary <= 23U) ||
            (primary == 0U && ((word & 63U) == 8U || (word & 63U) == 9U)) ||
            (primary == 0x11U && ((word >> 21U) & 31U) == 8U);
        return;
      }
    }
  }
#endif
  jfg_phase9_execution_probe_slow(section,pc,word,context);
}

extern "C" void jfg_phase9_execution_probe_predecoded(unsigned metadata, unsigned pc,
                                          unsigned word, void* context) {
  const unsigned section=metadata&255U;
#if defined(_WIN32) && defined(JFG_PHASE8_LIVE_RUNTIME)
  if (g_active_child_state != nullptr && context != nullptr) {
    auto& state = *g_active_child_state;
    if (state.diagnostic_cpu_costs) ++state.profile_out_of_line_instructions;
    if (state.diagnostic_host_clock) {
      jfg_phase9_execution_probe_slow(section,pc,word,context);
      return;
    }
    // Private optimization: ordinary instructions before the next event need
    // only the same cost and pipeline bookkeeping. Hardware writes, interrupt
    // eligibility, exception return and observers fall back to the full path.
    if ((state.execution_fast_profile_ready ||
         (state.diagnostic_host_clock && state.host_clock_poll_budget > 0U && --state.host_clock_poll_budget > 0U)) &&
        !state.guest_eret_boundary && (metadata&0x800U)==0U &&
        (state.play_mode || state.observed_guest_instructions < 24000000000ULL) &&
        state.execution_fast_deadline > state.cpu_count &&
        state.execution_fast_revision == state.mmio_trace->execution_io_revision) {
      auto& cpu = *static_cast<recomp_context*>(context);
      const bool fpu=(metadata&0x100U)!=0U;
      const bool eligible = (cpu.status_reg & 7U) == 1U &&
          (state.execution_fast_pending & cpu.status_reg & 0xFF00U) != 0U;
      const bool park=(metadata&0x200U)!=0U;
      if (!eligible && !(fpu && (cpu.status_reg & 0x20000000U) == 0U) && !park) {
        ++state.observed_guest_instructions;
        ++state.execution_fast_hits;
        const bool delay = state.guest_previous_branch && pc == state.guest_last_pc + 4U;
        if (!state.diagnostic_host_clock) {
          const auto cycles = jfg_full_cache_cost_predecoded(pc,word,&cpu,state.rdram,metadata) + state.diagnostic_cpu_half_tick;
          state.cpu_count += cycles / 2U;
          state.diagnostic_cpu_half_tick = cycles % 2U;
        }
        state.mmio_trace->guest_count = state.cpu_count;
        state.guest_last_pc = pc;
        state.guest_last_word = word;
        state.guest_previous_delay = delay;
        state.guest_previous_branch=(metadata&0x400U)!=0U;
        return;
      }
    }
  }
#endif
  jfg_phase9_execution_probe_slow(section,pc,word,context);
}

extern "C" JFG_EXECUTION_NOINLINE void jfg_phase9_execution_probe_slow(unsigned section, unsigned pc,
                                          unsigned word, void *context) {
#if defined(_WIN32) && defined(JFG_PHASE8_LIVE_RUNTIME)
  if (g_active_child_state != nullptr && context != nullptr) {
    auto& state = *g_active_child_state;
    if (!state.rdram_capture_path.empty())
      state.private_fault_cpu = static_cast<recomp_context*>(context);
    if (state.private_model_pointer_watch && state.vi_retraces >= 2000U) {
      if (state.private_model_page_watch && !state.private_model_pages_ready &&
          !arm_private_memory_pages(state))
        fail_closed_dispatch(state,"private-memory-watch","page-setup",pc);
      if (state.private_model_hardware_watch && !private_model_watch_armed) {
        if (!arm_private_model_write_watch(state))
          fail_closed_dispatch(state,"private-memory-watch","debug-register-in-use",pc);
      }

      std::uint32_t current_model = 0U;
      std::memcpy(&current_model,state.rdram+(game_data("diagnostic.currentModel")&0x1FFFFFFFU),sizeof(current_model));
      const auto previous_model=state.private_model_pointer;
      if (current_model != previous_model) {
        if (previous_model >= 0x80000000U && previous_model < 0x80400000U &&
            current_model != 0U && (current_model < 0x80000000U || current_model >= 0x80400000U)) {
          FILE* private_model_capture_stream = nullptr;
          (void)fopen_s(&private_model_capture_stream,
                       (state.rdram_capture_path+".fault.txt").c_str(),"wb");
          FILE* const private_model_output = private_model_capture_stream != nullptr
                                               ? private_model_capture_stream : stderr;
        std::fprintf(private_model_output,
            "private-model-change vi=%llu poll=%llu pc=%08x last_pc=%08x word=%08x "
            "old=%08x new=%08x\n",
            static_cast<unsigned long long>(state.vi_retraces),
            static_cast<unsigned long long>(state.controller_samples),
            pc,state.guest_last_pc,word,previous_model,current_model);
          const auto count=(std::min)(state.private_model_probe_position,
                                      std::uint64_t{state.private_model_probe_pcs.size()});
          for (std::uint64_t distance=count; distance>0U; --distance)
            std::fprintf(private_model_output,"private-model-pc %08x\n",
                state.private_model_probe_pcs[(state.private_model_probe_position-distance)%
                                             state.private_model_probe_pcs.size()]);
          const auto& cpu=*static_cast<recomp_context*>(context);
          std::fprintf(private_model_output,
              "private-model-registers a0=%016llx a1=%016llx a2=%016llx a3=%016llx "
              "v0=%016llx v1=%016llx t0=%016llx t1=%016llx t2=%016llx t3=%016llx "
              "s0=%016llx s1=%016llx sp=%016llx ra=%016llx\n",
              cpu.r4,cpu.r5,cpu.r6,cpu.r7,cpu.r2,cpu.r3,cpu.r8,cpu.r9,cpu.r10,cpu.r11,
              cpu.r16,cpu.r17,cpu.r29,cpu.r31);
          std::fflush(private_model_output);
          if (private_model_capture_stream != nullptr) std::fclose(private_model_capture_stream);
          fail_closed_dispatch(state,"private-memory-watch","level-model-pointer-corrupt",pc);
        }
        state.private_model_pointer=current_model;
      }
      state.private_model_probe_pcs[state.private_model_probe_position++%
                                   state.private_model_probe_pcs.size()]=pc;
    }
    if (state.diagnostic_cpu_costs) ++state.profile_full_execution_probes;
    const bool measure_native_handler = state.diagnostic_cpu_costs && state.diagnostic_host_clock;
    const auto native_handler_began = measure_native_handler ? std::chrono::steady_clock::now()
        : std::chrono::steady_clock::time_point{};
    const auto native_handler_wait = measure_native_handler ? state.profile_host_wait_us : 0U;
    const auto native_handler_graphics = measure_native_handler ? state.graphics_submit_microseconds : 0U;
    if (state.eret_transfer_stream.is_open() &&
        !state.eret_transfer_probe.advance(static_cast<std::uint32_t>(state.completed_game_updates + 1U)))
      fail_closed_dispatch(state, "eret-transfer-probe", "output-or-order", pc);
    ++state.observed_guest_instructions;
    if (!state.guest_os_probe &&
        (word == 0x1000ffffU || ((word >> 26U) == 2U &&
          (((pc + 4U) & 0xf0000000U) | ((word & 0x03ffffffU) << 2U)) == pc))) {
      // Preserve the old cooperative control's permanent idle park even
      // when this root emits executable guest idle loops for the new CPU.
      pause_self(state.rdram);
    }
    if (state.guest_os_probe) {
      auto& cpu = *static_cast<recomp_context*>(context);
      auto& mmio = *state.mmio_trace;
      if (state.diagnostic_host_clock) {
        // Only the exhausted instruction quantum can take the checked poll
        // shortcut below. Every other reason for a full handler stays full.
        const bool poll_certificate = state.native_fast_ready &&
            state.host_clock_poll_budget == 1U;
        const auto now = std::chrono::steady_clock::now();
        if (!state.host_count_clock.ready() && !state.host_count_clock.start(state.cpu_count,now))
          fail_closed_dispatch(state,"native-clock","initialization",pc);
        auto count = state.native_clock_samples.replaying() ? std::optional<std::uint64_t>{}
            : state.host_count_clock.sample(now);
        count = state.native_clock_samples.sample(state.observed_guest_instructions,pc,word,0U,count);
        if (!count && state.native_clock_samples.boundary_mismatch()) {
          const auto& expected=state.native_clock_samples.mismatch_expected();
          const auto& observed=state.native_clock_samples.mismatch_observed();
          state.gameplay_trace.event("native-clock-mismatch",{state.vi_retraces,
              state.controller_samples,state.native_clock_samples.samples(),
              expected[0],expected[1],expected[2],expected[3],
              observed[0],observed[1],observed[2],observed[3]});
          // Fatal replay rejection exits without ordinary shutdown. Drain the
          // async diagnostic writer so the failure record reaches disk.
          state.gameplay_trace.finish();
          fail_closed_dispatch(state,"native-clock","sample-boundary-mismatch",pc);
        }
        if (!count || *count < state.cpu_count)
          fail_closed_dispatch(state,"native-clock",state.native_clock_samples.limit_reached() ? "sample-limit" : "non-monotonic-time",pc);
        state.cpu_count = *count;
        mmio.guest_count = *count;
        state.host_clock_poll_budget = State::kHostClockPollInstructions;
        state.native_fast_ready = false;
        const unsigned poll_primary=word>>26U;
        const bool poll_fpu=poll_primary==0x11U || poll_primary==0x31U ||
            poll_primary==0x35U || poll_primary==0x39U || poll_primary==0x3dU;
        const bool poll_park=poll_primary==3U &&
            (((pc+4U)&0xf0000000U)|((word&0x03ffffffU)<<2U))==kOsSchedulerPark;
        // The clock is sampled at the identical instruction boundary above.
        // Reuse the existing device certificate only while no deadline has
        // arrived and no CPU or I/O owner has invalidated it. Hardware/cache,
        // idle parks and observer sites always retain the full path.
        if (poll_certificate && !state.guest_eret_boundary &&
            state.native_fast_status==cpu.status_reg &&
            state.execution_fast_revision==mmio.execution_io_revision &&
            state.cpu_count<state.execution_fast_deadline &&
            (state.play_mode || state.observed_guest_instructions<=24000000000ULL) &&
            poll_primary!=0x10U && poll_primary!=0x2fU &&
            word!=0x1000ffffU && pc!=kViInitializeSite && pc!=kViManagerIdleSite &&
            !poll_park && (!poll_fpu || (cpu.status_reg&0x20000000U)!=0U) &&
            mmio.device_error==nullptr && !mmio.sp_launch &&
            mmio.flash_bus.mutations()==mmio.persisted_flash_mutations &&
            !state.guest_clock_trace.is_open() && state.point_probe_pcs.empty() &&
            !state.device_event_stream && !state.eret_transfer_stream.is_open() &&
            !state.instruction_effect_stream.is_open()) {
          if (measure_native_handler)
            state.profile_native_handler_ns+=static_cast<std::uint64_t>(
                std::chrono::duration_cast<std::chrono::nanoseconds>(
                    std::chrono::steady_clock::now()-native_handler_began).count());
          const bool delay=state.guest_previous_branch && pc==state.guest_last_pc+4U;
          state.guest_last_pc=pc;state.guest_last_word=word;
          state.guest_previous_delay=delay;
          state.guest_previous_branch=poll_primary==1U ||
              (poll_primary>=2U && poll_primary<=7U) ||
              (poll_primary>=20U && poll_primary<=23U) ||
              (poll_primary==0U && ((word&63U)==8U || (word&63U)==9U)) ||
              (poll_primary==0x11U && ((word>>21U)&31U)==8U);
          // Refresh also clamps a diagnostic's remaining instruction budget.
          // Keep that boundary even when the device certificate is unchanged.
          jfg_native_timing_refresh(&state,&cpu);
          return;
        }
      }
      // A cached BEQ zero,zero,self + NOP loop has no architectural effect
      // between device events. Only skip after observing a complete warm
      // iteration and with no interrupt currently eligible for delivery.
      const auto pending_idle_interrupt =
          ((mmio.mi_pending & mmio.mi_mask.read()) ? 0x400U : 0U) |
          (state.guest_timer.interrupt() ? 0x8000U : 0U) | (state.guest_cause & 0x300U);
      if (word == 0x1000FFFFU && state.guest_last_pc == pc + 4U &&
          state.guest_last_word == 0U && state.guest_previous_delay &&
          (cpu.status_reg & 7U) == 1U &&
          (pending_idle_interrupt & cpu.status_reg & 0xFF00U) == 0U) {
        auto deadline = mmio.vi_next;
        const auto admit = [&](std::optional<std::uint64_t> next) {
          if (next) deadline = (std::min)(deadline,*next);
        };
        admit(mmio.pi_dma.deadline()); admit(mmio.si_dma.deadline());
        admit(state.guest_timer.deadline()); admit(mmio.sp_deadline);
        admit(mmio.dp_deadline); admit(mmio.ai_dma.deadline()); admit(mmio.flash_bus.deadline());
        if (deadline > state.cpu_count) {
          const auto ticks=deadline-state.cpu_count;
          if (state.diagnostic_host_clock) {
            const auto before = std::chrono::steady_clock::now();
            const auto target_time = state.native_clock_samples.replaying()
                ? std::optional<HostCountClock::Time>{before}
                : state.host_count_clock.deadline(deadline,before);
            if (!target_time) fail_closed_dispatch(state,"native-clock","idle-deadline",pc);
            if (!state.native_clock_samples.replaying() && !state.host_deadline_wait.until(*target_time))
              fail_closed_dispatch(state,"native-clock","host-deadline-wait",pc);
            const auto after = std::chrono::steady_clock::now();
            auto count = state.native_clock_samples.replaying() ? std::optional<std::uint64_t>{}
                : state.host_count_clock.sample(after);
            count = state.native_clock_samples.sample(state.observed_guest_instructions,pc,word,deadline,count);
            if (!count || *count < deadline)
              fail_closed_dispatch(state,"native-clock","early-idle-wakeup",pc);
            state.profile_host_wait_us += static_cast<std::uint64_t>(
                std::chrono::duration_cast<std::chrono::microseconds>(after-before).count());
            if (state.gameplay_trace) {
              state.gameplay_trace.event("host-idle-wait", {state.vi_retraces,
                  state.cpu_count, deadline, *count,
                  static_cast<std::uint64_t>(std::chrono::duration_cast<std::chrono::microseconds>(after-before).count()),
                  static_cast<std::uint64_t>(std::chrono::duration_cast<std::chrono::microseconds>(after-*target_time).count())});
            }
            state.profile_idle_count_ticks += *count-state.cpu_count;
            state.cpu_count = *count;
            mmio.guest_count = *count;
          } else if (jfg_full_cache_idle_skip(pc,ticks,state.rdram)) {
            state.profile_idle_count_ticks += ticks;
            state.cpu_count=deadline;
            state.observed_guest_instructions+=ticks*2U;
            mmio.guest_count=state.cpu_count;
          }
        }
      }

      if (state.guest_clock_trace && mmio.traced_si_sequence != mmio.device_si_sequence) {
        state.guest_clock_trace << "si\t" << state.cpu_count << '\t' << std::hex
            << mmio.device_si_offset << '\t' << mmio.device_si_value << '\t'
            << mmio.si_dma.read(0).value_or(0) << std::dec << '\t'
            << mmio.device_si_prior_deadline.value_or(0) << '\t' << mmio.si_dma.transfers() << '\n';
        mmio.traced_si_sequence = mmio.device_si_sequence;
      }
      if (state.guest_clock_trace && (mmio.device_error ||
          mmio.traced_pi_transfers != mmio.pi_dma.transfers())) {
        state.guest_clock_trace << "pi\t" << state.cpu_count << '\t' << std::hex
            << mmio.device_pi_offset << '\t' << mmio.device_pi_value << '\t'
            << mmio.pi_dma.read(0U).value_or(0U) << '\t' << mmio.pi_dma.read(4U).value_or(0U)
            << std::dec << '\n';
        state.guest_clock_trace.flush();
        mmio.traced_pi_transfers = mmio.pi_dma.transfers();
      }
      if (state.guest_clock_trace && (pc == kViInitializeSite || pc == kViManagerIdleSite))
        state.guest_clock_trace << "vi-site\t" << std::hex << pc << std::dec << '\t' << state.cpu_count << '\n';
      if (mmio.device_error != nullptr) {
        if (state.guest_clock_trace) {
          state.guest_clock_trace << "device-error\t" << mmio.device_error << '\t' << state.cpu_count
              << '\t' << std::hex << mmio.device_write_page << '\t' << mmio.device_write_offset
              << '\t' << mmio.device_write_value << std::dec << '\n';
          const auto dram = mmio.si_dma.read(0).value_or(UINT32_MAX);
          state.guest_clock_trace << "si-error\t" << std::hex << mmio.device_si_offset << '\t'
              << mmio.device_si_value << '\t' << dram << '\t';
          if (dram <= kRdramSize - 64U)
            for (unsigned i = 0; i < 64; ++i)
              state.guest_clock_trace << std::setw(2) << std::setfill('0') << unsigned(mmio.device_rdram[(dram + i) ^ 3U]);
          state.guest_clock_trace << std::dec << '\n';
          state.guest_clock_trace << "pif-error\t";
          for (const auto value : mmio.si_dma.pif())
            state.guest_clock_trace << std::hex << std::setw(2) << std::setfill('0') << unsigned(value);
          state.guest_clock_trace << std::dec << '\n';
          state.guest_clock_trace.flush();
        }
        fail_closed_dispatch(state, "guest-device", mmio.device_error, pc);
      }
      if (!mmio.flash_bus.advance(state.cpu_count))
        fail_closed_dispatch(state,"guest-device","flash-clock-or-completion",pc);
      if (mmio.flash_bus.mutations() != mmio.persisted_flash_mutations) {
        if (!state.flash_path.empty() && !state.flashram.persist_atomic(state.flash_path).ok())
          fail_closed_dispatch(state, "guest-device", "flash-persist", pc);
        mmio.persisted_flash_mutations = mmio.flash_bus.mutations();
        ++state.flash_persist_count;
      }
      // No route-dependent budget or timing adjustment. Bound the diagnostic
      // until every reached device has an independently qualified owner.
      if (!state.play_mode && state.observed_guest_instructions > 24000000000ULL)
        fail_closed_dispatch(state, "guest-os", "instruction-budget", pc);
      if (mmio.sp_launch) {
        hle::GuestMemory memory({state.rdram, kRdramSize}, hle::GuestMemory::Layout::native_word_big_endian);
        std::uint32_t flags = 0, device_type = 0;
        std::memcpy(&device_type, mmio.sp_dma.memory().data() + 0xfc0U, 4U);
        if (state.guest_active_rsp_task || state.loaded_rsp_task == 0 ||
            (state.loaded_rsp_task_type != 1 && state.loaded_rsp_task_type != 2) ||
            device_type != state.loaded_rsp_task_type ||
            !memory.read_u32(state.loaded_rsp_task + 4, flags) || (flags & ~2U) != 0)
          fail_closed_dispatch(state, "guest-rsp", "unqualified-task-launch", pc);
        state.guest_active_rsp_task = state.loaded_rsp_task;
        state.guest_active_rsp_type = device_type;
        mmio.sp_deadline = *mmio.sp_launch + (device_type == 1 ? 1000U : 4000U);
        if (device_type == 1) {
          if (mmio.dp_deadline || !state.pending_graphics_tasks.empty() ||
              !execute_live_graphics_task(state, memory))
            fail_closed_dispatch(state, "guest-rsp", "graphics-task-rejected", pc);
          mmio.dp_deadline = mmio.sp_deadline;
        }
        mmio.sp_launch.reset();
      }
      const bool device_boundary = state.guest_previous_delay || state.guest_eret_boundary;
      if (device_boundary) {
        std::array<ReferenceEventCandidate, 7> candidates{};
        std::size_t event_count = 0;
        const auto add = [&](ReferenceEvent source, std::optional<std::uint64_t> deadline) {
          if (deadline) candidates[event_count++] = {source, *deadline};
        };
        add(ReferenceEvent::vi, mmio.vi_next);
        add(ReferenceEvent::pi, mmio.pi_dma.deadline());
        add(ReferenceEvent::si, mmio.si_dma.deadline());
        add(ReferenceEvent::compare, state.guest_timer.deadline());
        add(ReferenceEvent::sp, mmio.sp_deadline);
        add(ReferenceEvent::dp, mmio.dp_deadline);
        add(ReferenceEvent::ai, mmio.ai_dma.deadline());
        const auto events = std::span(candidates).first(event_count);
        const auto reference_selected = state.diagnostic_host_clock ? ReferenceEventSelection{}
            : select_reference_event(events, state.cpu_count);
        const auto native_batch = state.diagnostic_host_clock
            ? select_native_event_batch(events, state.cpu_count) : NativeEventBatch{};
        if (!native_batch.valid)
          fail_closed_dispatch(state, "native-clock", "invalid-device-batch", pc);
        // No guest CPU instruction or interrupt acceptance occurs within this
        // equal-deadline batch. Device transfer data is already visible; each
        // completion updates its own status/latch. SP work finishes before the
        // final CPU interrupt observation, including when DP shares its deadline.
        if (state.diagnostic_host_clock && native_batch.size > 1U)
          state.gameplay_trace.event("native-device-batch", {state.vi_retraces,
              state.cpu_count, native_batch.deadline, native_batch.size});
        const auto completions = state.diagnostic_host_clock
            ? (std::max)(native_batch.size, std::size_t{1}) : std::size_t{1};
        for (std::size_t completion = 0; completion < completions; ++completion) {
        const auto selected = state.diagnostic_host_clock
            ? ReferenceEventSelection{true, native_batch.size ?
                std::optional<ReferenceEvent>{native_batch.sources[completion]} : std::nullopt}
            : reference_selected;
        if (!selected.qualified) {
          // Preserve fail-closed ordering; capture evidence instead of guessing.
          std::cerr << "guest-event-tie Count=" << state.cpu_count << " VI=" << state.vi_retraces;
          for (const auto& candidate : std::span(candidates).first(event_count))
            std::cerr << " source=" << static_cast<unsigned>(candidate.source) << " deadline=" << candidate.deadline;
          std::cerr << '\n';
          fail_closed_dispatch(state, "guest-device", "unqualified-event-tie", pc);
        }
        std::optional<std::uint64_t> observed_deadline;
        unsigned observed_source = JFG_EVENT_NONE;
        if (state.device_event_stream && selected.source) {
          switch (*selected.source) {
          case ReferenceEvent::vi: observed_source = JFG_EVENT_VI; break;
          case ReferenceEvent::pi: observed_source = JFG_EVENT_PI; break;
          case ReferenceEvent::si: observed_source = JFG_EVENT_SI; break;
          case ReferenceEvent::compare: observed_source = JFG_EVENT_COMPARE; break;
          case ReferenceEvent::sp: observed_source = JFG_EVENT_SP; break;
          case ReferenceEvent::dp: observed_source = JFG_EVENT_DP; break;
          case ReferenceEvent::ai: observed_source = JFG_EVENT_AI; break;
          }
          for (const auto candidate : std::span(candidates).first(event_count))
            if (candidate.source == *selected.source) observed_deadline = candidate.deadline;
          emit_device_event(state, cpu, JFG_EVENT_DISPATCH, observed_source, pc, word, observed_deadline);
        }
        if (selected.source) switch (*selected.source) {
        case ReferenceEvent::vi:
          mmio.mi_pending |= 8U;
          ++state.vi_frames;
          // Host playback follows the original VI device clock. This does not
          // advance Count, invent a guest event, or adjust a cinematic cue.
          if (state.original_os_host_pacing && !state.diagnostic_host_clock && state.host_audio.started()) {
            if (!state.original_os_host_anchor_ready) {
              state.host_audio.settle_startup_queue();
              state.original_os_host_clock.anchor(mmio.vi_next,
                  std::chrono::steady_clock::now(), state.host_audio.underruns());
              state.original_os_host_anchor_ready = true;
            }
            // Poll actual output continuity before pacing, including stalls in
            // the window/renderer owner thread. Never catch up a stale clock
            // after the audio device has run dry.
            state.host_audio.service(0U, false);
            const auto target_time = state.original_os_host_clock.deadline(
                mmio.vi_next, std::chrono::steady_clock::now(),
                state.host_audio.underruns());
            const auto before_wait = std::chrono::steady_clock::now();
            if (before_wait < target_time)
              std::this_thread::sleep_until(target_time);
            const auto now = std::chrono::steady_clock::now();
            if (state.gameplay_trace) {
              state.profile_host_wait_us += static_cast<std::uint64_t>(
                  std::chrono::duration_cast<std::chrono::microseconds>(now-before_wait).count());
              state.gameplay_trace.event("vi-work", {state.vi_retraces, state.cpu_count,
                  state.observed_guest_instructions, state.profile_idle_count_ticks,
                  state.profile_host_wait_us, cache_stats[2], cache_stats[6], cache_stats[10]});
            }
            if (state.timing_trace) state.timing_trace << "os-host-vi\t"
                << state.vi_frames << '\t' << mmio.vi_next << '\t'
                << std::chrono::duration_cast<std::chrono::microseconds>(now.time_since_epoch()).count()
                << '\t' << std::chrono::duration_cast<std::chrono::microseconds>(now-target_time).count()
                << '\n';
          }
          if (state.diagnostic_host_clock) {
            if (!state.original_os_host_anchor_ready && state.host_audio.started()) {
              state.host_audio.settle_startup_queue();
              state.original_os_host_anchor_ready = true;
            }
            state.gameplay_trace.event("vi-work", {state.vi_retraces, state.cpu_count,
                state.observed_guest_instructions, state.profile_idle_count_ticks,
                state.profile_host_wait_us, cache_stats[2], cache_stats[6], cache_stats[10]});
          }
          if (state.timing_trace) {
            hle::GuestMemory observed({state.rdram,kRdramSize},hle::GuestMemory::Layout::native_word_big_endian);
            std::uint32_t loading=0;
            if (observed.read_u32(game_data("globals.levelLoading"),loading) && loading!=0U) {
              std::uint16_t level=0,next=0;
              std::memcpy(&level,state.rdram+((game_data("globals.currentLevel")&0x1FFFFFFFU)^2U),sizeof(level));
              std::memcpy(&next,state.rdram+((game_data("globals.pendingLevel")&0x1FFFFFFFU)^2U),sizeof(next));
              const auto original_address=[&](std::uint32_t value) {
                if(value<0x00100000U || value>=0x10000000U)return value;
                std::uint32_t table=0,base=0;
                if (!observed.read_u32(kRunlinkModuleTablePointer,table) ||
                    !observed.read_u32(table+(value>>20U)*32U,base))return 0U;
                return base+(value&0xFFFFFU);
              };
              state.timing_trace << "load-pc\t" << state.vi_frames << '\t'
                  << loading << '\t' << level << '\t' << next << '\t'
                  << std::hex << original_address(pc) << '\t'
                  << original_address(static_cast<std::uint32_t>(cpu.r31)) << '\t'
                  << static_cast<std::uint32_t>(cpu.r29) << '\t'
                  << mmio.sp_status.read() << '\t' << mmio.pi_dma.read(0x10U).value_or(0U)
                  << std::dec << '\n';
            }
          }

          {
#if defined(_WIN32) && defined(JFG_PHASE8_LIVE_RUNTIME)
        const DiagnosticHostStage breadcrumb_stage(state,"host-profile-breadcrumb");
#endif
        jfg::support_breadcrumb(state.vi_frames, state.vi_retraces, state.controller_samples);
#if defined(_WIN32) && defined(JFG_PHASE8_LIVE_RUNTIME)
        support_mouse_snapshot(state);
#endif
        }
          if (!mmio.vi_clock.advance(state.cpu_count))
            fail_closed_dispatch(state,"guest-device","vi-clock-overflow",pc);
          mmio.mi_pending=(mmio.mi_pending&~8U)|(mmio.vi_clock.interrupt()?8U:0U);
          mmio.vi_next=mmio.vi_clock.deadline().value_or(UINT64_MAX);
          if (!service_host_audio(state, true))
            fail_closed_dispatch(state, "audio", "host-device", pc);
          break;
        case ReferenceEvent::pi: mmio.pi_dma.advance(state.cpu_count); break;
        case ReferenceEvent::si: mmio.si_dma.advance(state.cpu_count); break;
        case ReferenceEvent::compare: state.guest_timer.advance(state.cpu_count); break;
        case ReferenceEvent::ai: mmio.ai_dma.advance(state.cpu_count); break;
        case ReferenceEvent::sp: {
          if (state.guest_active_rsp_type == 1) complete_pending_live_graphics_tasks(state, pc);
          else if (state.guest_active_rsp_type == 2) {
            hle::GuestMemory memory({state.rdram, kRdramSize}, hle::GuestMemory::Layout::native_word_big_endian);
            const auto loaded = state.loaded_rsp_task;
            state.loaded_rsp_task = state.guest_active_rsp_task;
            if (!execute_live_audio_task(state, memory))
              fail_closed_dispatch(state, "guest-rsp", "audio-task-rejected", pc);
            state.loaded_rsp_task = loaded;
          } else fail_closed_dispatch(state, "guest-rsp", "completion-without-task", pc);
          if (!mmio.sp_status.complete_task()) fail_closed_dispatch(state, "guest-rsp", "completion-status", pc);
          mmio.sp_deadline.reset();
          state.guest_active_rsp_task = state.guest_active_rsp_type = 0;
          break;
        }
        case ReferenceEvent::dp: mmio.mi_pending |= 32U; mmio.dp_deadline.reset(); break;
        }
        mmio.mi_pending = (mmio.mi_pending & ~1U) | (mmio.sp_status.interrupt() ? 1U : 0U);
        mmio.mi_pending = (mmio.mi_pending & ~2U) | (mmio.si_dma.interrupt() ? 2U : 0U);
        mmio.mi_pending = (mmio.mi_pending & ~4U) | (mmio.ai_dma.interrupt() ? 4U : 0U);
        mmio.mi_pending = (mmio.mi_pending & ~16U) | (mmio.pi_dma.interrupt() ? 16U : 0U);
        if (observed_source != JFG_EVENT_NONE)
          emit_device_event(state, cpu, JFG_EVENT_STATE, observed_source, pc, word, observed_deadline);
        } // Equal-time completions are visible together at the CPU boundary.
      }
      state.vi_interrupts = mmio.vi_acknowledgements;
      if (measure_native_handler) {
        // Measure only the prefix before any guest exception handler or thread
        // handoff can run. Subtract the already measured explicit waits and
        // graphics submission; nested guest execution must not be double counted.
        const auto elapsed = static_cast<std::uint64_t>(std::chrono::duration_cast<std::chrono::nanoseconds>(
            std::chrono::steady_clock::now()-native_handler_began).count());
        const auto excluded = (state.profile_host_wait_us-native_handler_wait+
            state.graphics_submit_microseconds-native_handler_graphics)*1000U;
        state.profile_native_handler_ns += elapsed > excluded ? elapsed-excluded : 0U;
      }
      bool delay = state.guest_previous_branch && pc == state.guest_last_pc + 4U;
      const auto cpu_pending = ((mmio.mi_pending & mmio.mi_mask.read()) ? 0x400U : 0U) |
          (state.guest_timer.interrupt() ? 0x8000U : 0U) | (state.guest_cause & 0x300U);
      const bool external = (cpu_pending & cpu.status_reg & 0xff00U) != 0U &&
          (cpu.status_reg & 7U) == 1U &&
          (device_boundary || (state.guest_last_word & 0xffe0ffffU) == 0x40806000U);
      state.guest_eret_boundary = false;
      const unsigned primary = word >> 26U;
      const bool fpu = primary == 0x11U || primary == 0x31U || primary == 0x35U || primary == 0x39U || primary == 0x3dU;
      const bool unusable = fpu && (cpu.status_reg & 0x20000000U) == 0U;
      if (external || unusable) {
        if (external)
          emit_device_event(state, cpu, JFG_EVENT_ACCEPT, JFG_EVENT_NONE, pc, word);
        if ((cpu.status_reg & 2U) != 0U || (unusable && delay))
          fail_closed_dispatch(state, "guest-os", "unqualified-exception-boundary", pc);
        const auto interrupted_pc = pc;
        state.guest_transport->park_at(pc);
        state.guest_epc = pc;
        state.guest_cause &= ~0x8000007cU;
        if (unusable) state.guest_cause = (state.guest_cause & ~0x30000000U) | 0x1000002cU;
        cop0_status_write(&cpu, cpu.status_reg | 2U);
        ++state.guest_exceptions;
        state.guest_previous_branch = state.guest_previous_delay = false;
        hle::GuestMemory memory({state.rdram, kRdramSize}, hle::GuestMemory::Layout::native_word_big_endian);
        for (std::uint32_t offset = 0U; offset < 16U; offset += 4U) {
          std::uint32_t source = 0U, installed = 0U;
          if (!memory.read_u32(kOsExceptionPreamble + offset, source) ||
              !memory.read_u32(0x80000180U + offset, installed) || source != installed)
            fail_closed_dispatch(state, "guest-os", "exception-vector-mismatch", pc);
        }
        if (state.guest_clock_trace.is_open()) {
          state.guest_clock_trace << "exception\t" << std::hex << pc << '\t' << mmio.mi_pending
              << '\t' << state.guest_cause << std::dec << '\t' << state.cpu_count << '\n';
          state.guest_clock_trace.flush();
        }
        const auto handler = jfg_generated_lookup_function(static_cast<std::int32_t>(kOsExceptionPreamble));
        if (handler == nullptr) fail_closed_dispatch(state, "guest-os", "exception-handler-unavailable", pc);
        if(state.diagnostic_function_profile && !state.diagnostic_host_clock)
          (void)sample_model_thread(state,0xfffffffeU,0xfffffffeU);
        handler(state.rdram, &cpu);
        if (state.guest_epc != interrupted_pc || (cpu.status_reg & 2U) != 0U)
          fail_closed_dispatch(state, "guest-os", "exception-resume-mismatch", pc);
        delay = false;
      }
      if (state.device_event_stream && !state.device_event_probe.complete) {
        const auto invocation = state.completed_game_updates + 1U;
        if (invocation > state.device_event_probe.last) {
          if (!jfg_device_event_finish(&state.device_event_probe))
            fail_closed_dispatch(state, "device-event-probe", "output-failed", pc);
        } else if (invocation >= state.device_event_probe.first) {
          hle::GuestMemory memory({state.rdram, kRdramSize}, hle::GuestMemory::Layout::native_word_big_endian);
          std::uint32_t thread = 0U;
          if (!memory.read_u32(kOsCurrentThread, thread))
            fail_closed_dispatch(state, "device-event-probe", "thread-read", pc);
          if (thread != state.device_event_previous_thread)
            emit_device_event(state, cpu, JFG_EVENT_THREAD, JFG_EVENT_NONE, pc, word);
          if (state.device_event_successor)
            emit_device_event(state, cpu, JFG_EVENT_SUCCESSOR, JFG_EVENT_NONE, pc, word);
          const bool selected_pc = std::find(state.point_probe_pcs.begin(), state.point_probe_pcs.end(), pc) != state.point_probe_pcs.end();
          if (selected_pc) emit_device_event(state, cpu, JFG_EVENT_INSTRUCTION, JFG_EVENT_NONE, pc, word);
          state.device_event_successor = selected_pc;
          state.device_event_previous_thread = thread;
          state.device_event_previous_pc = pc;
          state.device_event_previous_word = word;
        }
      }
      // Mupen's annulled ordinary likely slots still advance Count. Other
      // likely families require their own profile coverage before use.
      if (!state.diagnostic_host_clock) {
        const auto cycles = jfg_full_cache_cost(pc,word,&cpu,state.rdram)
            + state.diagnostic_cpu_half_tick;
        state.cpu_count += cycles / 2U;
        state.diagnostic_cpu_half_tick = cycles % 2U;
      }
      mmio.guest_count = state.cpu_count;
      state.guest_last_pc = pc;
      state.guest_last_word = word;
      state.guest_previous_delay = delay;
      state.guest_previous_branch = primary == 1U || (primary >= 2U && primary <= 7U) ||
          (primary >= 20U && primary <= 23U) ||
          (primary == 0U && ((word & 63U) == 8U || (word & 63U) == 9U)) ||
          (primary == 0x11U && ((word >> 21U) & 31U) == 8U);
      if (primary == 3U && (((pc + 4U) & 0xf0000000U) | ((word & 0x03ffffffU) << 2U)) == kOsSchedulerPark)
        state.guest_transport->park_at(pc + 8U);
      state.execution_fast_deadline = mmio.vi_next;
      const auto fast_admit = [&](std::optional<std::uint64_t> next) {
        if (next) state.execution_fast_deadline =
            (std::min)(state.execution_fast_deadline,*next);
      };
      fast_admit(mmio.pi_dma.deadline()); fast_admit(mmio.si_dma.deadline());
      fast_admit(state.guest_timer.deadline()); fast_admit(mmio.sp_deadline);
      fast_admit(mmio.dp_deadline); fast_admit(mmio.ai_dma.deadline()); fast_admit(mmio.flash_bus.deadline());
      state.execution_fast_revision = mmio.execution_io_revision;
      state.execution_fast_pending =
          ((mmio.mi_pending & mmio.mi_mask.read()) ? 0x400U : 0U) |
          (state.guest_timer.interrupt() ? 0x8000U : 0U) | (state.guest_cause & 0x300U);
      if (state.diagnostic_host_clock) jfg_native_timing_refresh(&state,&cpu);

      // After exception resumption and Count accounting, before the current
      // guest instruction. No clock reads/changes or guest writes in this hook.
      // Raw Count is deliberately omitted: the oracle exposes lazy core Count.
      if (!state.point_probe_pcs.empty() &&
          state.completed_game_updates + 1U >= state.focus_update_start - 1U &&
          state.completed_game_updates + 1U <= state.focus_update_end + 1U &&
          std::find(state.point_probe_pcs.begin(), state.point_probe_pcs.end(), pc) != state.point_probe_pcs.end()) {
        if (++state.point_probe_hits > 4096U)
          fail_closed_dispatch(state, "point-probe", "hit-budget", pc);
        hle::GuestMemory memory({state.rdram, kRdramSize}, hle::GuestMemory::Layout::native_word_big_endian);
        std::uint32_t opcode = 0;
        if (!memory.read_u32(pc, opcode) || opcode != word)
          fail_closed_dispatch(state, "point-probe", "instruction-bytes", pc);
        auto& out = state.point_probe_trace;
        out << state.completed_game_updates + 1U << '\t' << state.vi_retraces << '\t'
            << state.controller_samples << '\t' << "0x" << std::hex << std::setfill('0')
            << std::setw(8) << pc << '\t' << "0x" << std::setw(8) << opcode;
        const std::array<std::uint64_t, 32> registers = {
            0, cpu.r1, cpu.r2, cpu.r3, cpu.r4, cpu.r5, cpu.r6, cpu.r7,
            cpu.r8, cpu.r9, cpu.r10, cpu.r11, cpu.r12, cpu.r13, cpu.r14, cpu.r15,
            cpu.r16, cpu.r17, cpu.r18, cpu.r19, cpu.r20, cpu.r21, cpu.r22, cpu.r23,
            cpu.r24, cpu.r25, cpu.r26, cpu.r27, cpu.r28, cpu.r29, cpu.r30, cpu.r31};
        for (const auto value : registers)
          out << '\t' << "0x" << std::setw(8) << static_cast<std::uint32_t>(value)
              << '\t' << "0x" << std::setw(8) << static_cast<std::uint32_t>(value >> 32U);
        for (const auto address : state.point_probe_words) {
          std::uint32_t value = 0;
          if (!memory.read_u32(address, value))
            fail_closed_dispatch(state, "point-probe", "word-read", pc);
          out << '\t' << "0x" << std::setw(8) << value;
        }
        out << std::dec << std::setfill(' ') << '\n';
        out.flush();
        if (!out) fail_closed_dispatch(state, "point-probe", "output-failed", pc);
      }
    }
  }
#endif
  (void)section; (void)pc; (void)word; (void)context;
}


} // namespace jfg::boot::native::detail
