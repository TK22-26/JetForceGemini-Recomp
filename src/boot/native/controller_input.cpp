#include "runtime_services.hpp"
#include "gameplay_scopes.hpp"
namespace jfg::boot::native::detail {
void stop_pc_rumble(State& state) noexcept {
#if defined(_WIN32) && defined(JFG_PHASE8_LIVE_RUNTIME)
  if(state.pc_rumble_output)state.pc_rumble_output->stop();
#else
  (void)state;
#endif
}

#if defined(_WIN32) && defined(JFG_PHASE8_LIVE_RUNTIME)
State *g_active_child_state = nullptr;

void support_mouse_snapshot(State& state) noexcept {
  const auto now=GetTickCount64();
  if(now-state.mouse_support_last<1000U)return;
  state.mouse_support_last=now;
  wchar_t enabled[32768]{};if(!jfg::support_sibling(L"mouse.log",enabled))return;
  if(!state.mouse_support_origin)state.mouse_support_origin=now;
  auto snapshot=state.mouse_diagnostics.snapshot();
  snapshot.elapsed_ms=now-state.mouse_support_origin;snapshot.players=state.mouse_support_players;
  const HWND child=static_cast<HWND>(state.native_window);
  const HWND root=child?GetAncestor(child,GA_ROOT):nullptr;
  GUITHREADINFO gui{};gui.cbSize=sizeof(gui);
  const DWORD thread=child?GetWindowThreadProcessId(child,nullptr):0;
  const bool focus_known=thread && GetGUIThreadInfo(thread,&gui)!=FALSE;
  snapshot.state[3]=state.pc_mouse_captured.load()?1U:0U;
  snapshot.state[4]=root && GetForegroundWindow()==root?1U:0U;
  snapshot.state[5]=focus_known && gui.hwndFocus==child?1U:0U;
  snapshot.state[6]=focus_known?1U:0U;
  snapshot.state[7]=root && GetPropW(root,L"JfgSettingsOpen")?1U:0U;
  snapshot.state[8]=state.pc_input_blocked?1U:0U;
  snapshot.state[9]=state.input_replay_loaded?1U:0U;
  snapshot.state[10]=state.pc_record_extended?1U:0U;
  RAWINPUTDEVICE devices[32]{};UINT count=32;
  const UINT found=GetRegisteredRawInputDevices(devices,&count,sizeof(RAWINPUTDEVICE));
  if(found!=UINT(-1) && found<=32) {
    snapshot.state[11]=1;
    for(UINT i=0;i<found;++i)if(devices[i].usUsagePage==1 && devices[i].usUsage==2) {
      snapshot.state[12]=devices[i].hwndTarget==child?1U:0U;
      snapshot.state[13]=devices[i].dwFlags;break;
    }
  }
  state.mouse_support_history.push(snapshot);
  (void)jfg::write_mouse_support(state.mouse_support_history);
}



bool host_key_down(const State &state, const int virtual_key) noexcept {
  return virtual_key >= 0 && virtual_key < 256 &&
         (state.host_keys[static_cast<std::size_t>(virtual_key)] ||
          state.host_key_presses[static_cast<std::size_t>(virtual_key)]);
}

void trace_phase9_event(State &state, const char *event,
                        const std::uint64_t poll) {
  if (!state.event_trace.is_open())
    return;
  bool selected = false;
  for (std::size_t index = 0U; index < state.event_range_count; ++index) {
    const auto [first, last] = state.event_ranges[index];
    selected |= poll >= first && poll <= last;
  }
  if (!selected)
    return;
  if (++state.event_trace_rows > 4096U) {
    state.exit_requested = true;
    return;
  }
  state.event_trace << state.event_trace_rows << '\t' << event << '\t'
                    << poll << '\t' << state.completed_game_updates << '\t'
                    << state.vi_frames << '\t' << state.vi_retraces << '\t'
                    << state.controller_read_start_calls << '\t'
                    << state.controller_get_data_calls << '\t'
                    << (state.latched_controller_connected ? 1 : 0) << '\t'
                    << state.latched_controller_buttons << '\t'
                    << static_cast<int>(state.latched_controller_stick_x) << '\t'
                    << static_cast<int>(state.latched_controller_stick_y) << '\n';
}

struct XInputApi {
  using GetState=DWORD(WINAPI *)(DWORD,XINPUT_STATE*);
  using SetState=DWORD(WINAPI *)(DWORD,XINPUT_VIBRATION*);
  GetState get=nullptr;SetState set=nullptr;
};
const XInputApi& xinput_api() noexcept {
  static const XInputApi api=[]() noexcept {
    for(const wchar_t* library:{L"xinput1_4.dll",L"xinput1_3.dll",L"xinput9_1_0.dll"}) {
      const auto module=LoadLibraryW(library);
      if(!module)continue;
      const auto get=reinterpret_cast<XInputApi::GetState>(GetProcAddress(module,"XInputGetState"));
      const auto set=reinterpret_cast<XInputApi::SetState>(GetProcAddress(module,"XInputSetState"));
      if(get)return XInputApi{get,set};
      FreeLibrary(module);
    }
    return XInputApi{};
  }();
  return api;
}

bool read_xinput_device(int device,
                        jfg::StandardControllerSample &sample) noexcept {
  const auto get_state=xinput_api().get;
  if (get_state == nullptr)
    return false;
  if (device < 0 || device >= 4)
    return false;
  XINPUT_STATE state{};
  bool connected = false;
  static std::array<ULONGLONG, 4> retry_after{};
  const auto now = GetTickCount64();
  for (DWORD port = 0U; port < 4U; ++port) {
    if (now < retry_after[port])
      continue;
    if (port != static_cast<DWORD>(device))
      continue;
    if (get_state(port, &state) == ERROR_SUCCESS) {
      connected = true;
      break;
    }
    retry_after[port] = now + 500;
  }
  if (!connected)
    return false;
  constexpr std::array<WORD, 15> masks{0x1000, 0x2000, 0x4000, 0x8000, 0x20,
                                       0,      0x10,   0x40,   0x80,   0x100,
                                       0x200,  1,      2,      4,      8};
  for (std::size_t i = 0U; i < masks.size(); ++i)
    sample.buttons[i] = (state.Gamepad.wButtons & masks[i]) != 0;
  sample.axes = {state.Gamepad.sThumbLX,
                 -static_cast<int>(state.Gamepad.sThumbLY),
                 state.Gamepad.sThumbRX,
                 -static_cast<int>(state.Gamepad.sThumbRY),
                 state.Gamepad.bLeftTrigger * 32767 / 255,
                 state.Gamepad.bRightTrigger * 32767 / 255};
  return true;
}

jfg::PcInputConfig active_pc_input(const State &state,std::size_t port);

bool pc_rumble_eligible(const State& state,const NativeGameMemory& ram,std::size_t port) {
  return state.modern_controls_active && !state.pc_input_blocked && !state.exit_requested &&
    (state.play_mode || state.input_replay_loaded) && game_view(ram).u8(game_data_ref("globals.rumbleEnabled"))!=0 &&
    game_view(ram).u8(game_data_ref("globals.rumbleGameplayAllowed"))!=0 && game_view(ram).u8(game_data_ref("globals.pauseActive"))==0 &&
    active_pc_input(state,port).rumble_strength>0 && state.controller_ports.samples[port].connected &&
    (state.input_replay_loaded || (state.pc_devices[port]>=0 && state.pc_device_ready[port]));
}

void sync_pc_rumble(State& state) {
  NativeGameMemory ram({state.rdram,kRdramSize});
  for(std::size_t port=0;port<4;++port) {
    if(state.pc_rumble_devices[port]!=state.pc_devices[port] || !pc_rumble_eligible(state,ram,port))
      state.pc_rumble_effects[port].clear();
    state.pc_rumble_devices[port]=state.pc_devices[port];
    const auto level=state.pc_rumble_effects[port].sample(state.cpu_count,active_pc_input(state,port).rumble_strength);
    if(level!=state.pc_rumble_levels[port])state.gameplay_trace.event("pc-rumble-envelope",{
      state.vi_retraces,port,level,static_cast<std::uint32_t>(state.pc_devices[port]+3)});
    state.pc_rumble_levels[port]=level;
  }
  // Replays qualify guest requests and envelopes without touching host motors.
  auto desired=jfg::route_pc_rumble(state.pc_rumble_levels,state.pc_devices);
  if(!state.play_mode || state.input_replay_loaded)desired.fill(0);
  const auto set=xinput_api().set;
  if(!state.pc_rumble_output && set && std::any_of(desired.begin(),desired.end(),[](auto value){return value!=0;})) {
    state.pc_rumble_output=std::make_unique<jfg::PcRumbleOutput>(
      [set](unsigned device,std::uint16_t value) {
        XINPUT_VIBRATION vibration{value,value};
        return set(device,&vibration)==ERROR_SUCCESS;
      },[](std::uintptr_t token) {
        const auto root=reinterpret_cast<HWND>(token);
        return root && IsWindow(root) && GetForegroundWindow()==root && GetPropW(root,L"JfgSettingsOpen")==nullptr;
      });
  }
  if(state.pc_rumble_output) {
    const auto root=state.native_window?GetAncestor(static_cast<HWND>(state.native_window),GA_ROOT):nullptr;
    state.pc_rumble_output->publish(desired,reinterpret_cast<std::uintptr_t>(root));
  }
}

void request_pc_rumble(State& state,std::uint32_t target,const recomp_context& context) {
  NativeGameMemory ram({state.rdram,kRdramSize});
  const auto player=static_cast<std::uint32_t>(context.r4);
  // Function identity and the common call ABI are qualified from each ROM.
  // Guest execution still owns the regional rumble records and their stride.
  if(player>=4)return;
  const auto port=game_view(ram).u8(game_data_ref("globals.playerPorts"),player);
  if(port>=4)return;
  if(target==game_code("game.rumbleStop"))state.pc_rumble_effects[port].clear();
  else if(pc_rumble_eligible(state,ram,port)) {
    const auto kind=target==game_code("game.rumbleStart")?jfg::PcRumbleRequest::start:
      target==game_code("game.rumbleAlter")?jfg::PcRumbleRequest::alter:jfg::PcRumbleRequest::maximum;
    state.pc_rumble_effects[port].request(kind,static_cast<std::int32_t>(context.r5),
      std::bit_cast<float>(static_cast<std::uint32_t>(context.r6)),state.cpu_count,hardware_clocks().count_hz);
  }
  sync_pc_rumble(state);
}

bool modern_controls_selected(const State &state,std::size_t port) {
  return port<4U && state.modern_controls_active && state.modern_controls[port].enabled && state.rdram;
}
unsigned modern_actor_port(const State& state,std::uint32_t actor) {
  NativeGameMemory ram({state.rdram,kRdramSize});
  if(!ram.valid(actor,0xA4U))return 4U;
  const auto control=ram.u32(actor+game_member("layout.actor.control"));
  return ram.valid(control,0x5F0U)?jfg::mod::pc_input_port(ram,ram.u8(control)):4U;
}
jfg::PcInputConfig active_pc_input(const State &state,std::size_t port) {
  return modern_controls_selected(state,port)?state.modern_controls[port].look:jfg::effective_pc_input(false,state.pc_input[port]);
}
// Modern gameplay owns its view heading before the guest chooses movement.
// Original mappings and old replay formats never enter this adapter.
// Record only a real retained-view loss. Focus regressions need the clearing
// branch and its mode/device context, not just the later reacquisition.
void trace_modern_view_reset(State& state, std::size_t port, unsigned reason) {
  const auto& view=state.pc_shoulders[port];
  if(!view.active)return;
  const auto& frame=state.pc_frames[port];
  NativeGameMemory ram({state.rdram,kRdramSize});
  const auto movement=ram.valid(view.control,0x5D0U)?ram.u8(view.control+game_member("layout.playerControl.movement")):255U;
  const unsigned flags=unsigned(state.modern_controls_active) |
    (unsigned(state.controller_ports.samples[port].connected)<<1U) |
    (unsigned(jfg::mod::pc_gameplay_active(ram,view.actor))<<2U) |
    (unsigned(jfg::mod::scripted_camera_active(ram,view.actor))<<3U) |
    (unsigned(game_view(ram).u8(game_data_ref("globals.pauseActive"))!=0)<<4U) |
    (unsigned(state.pc_device_ready[port])<<5U);
  state.gameplay_trace.event("pc-view-reset-cause",{state.vi_retraces,reason,port,
    view.actor,view.control,static_cast<std::uint16_t>(view.yaw),
    static_cast<std::uint16_t>(view.pitch),state.pc_input_blocked?1U:0U,
    frame.pc_mode,frame.modern_flags,static_cast<std::uint32_t>(state.pc_devices[port]),
    flags,movement});
}
bool modern_shoulder_current(const State &state,std::size_t port,std::uint32_t actor) {
  NativeGameMemory ram({state.rdram,kRdramSize});
  return port<4 && state.pc_shoulder_actor==actor && state.pc_shoulders[port].active &&
    state.pc_shoulders[port].actor==actor && jfg::mod::pc_gameplay_active(ram,actor) &&
    !jfg::mod::pc_ledge_view_active(ram,actor) &&
    ram.u8(state.pc_shoulders[port].control+game_member("layout.playerControl.movement"))!=4U;
}
bool modern_free_movement_current(const State& state,std::size_t port) {
  return port<4U && state.pc_shoulders[port].free_movement &&
    !state.pc_shoulders[port].aiming && !(state.controller_ports.samples[port].buttons&0x10U);
}
bool modern_landing_view_current(const State& state,std::uint32_t actor) {
  const auto port=modern_actor_port(state,actor);
  if(!modern_controls_selected(state,port))return false;
  const auto& view=state.pc_shoulders[port];
  NativeGameMemory ram({state.rdram,kRdramSize});
  return view.active && view.actor==actor && ram.valid(actor,0xA4U) &&
    view.control==ram.u32(actor+game_member("layout.actor.control")) && jfg::mod::pc_landing_view_active(ram,actor,view.landing_recovery);
}
bool modern_ledge_view_current(const State& state,std::uint32_t actor) {
  // The retained Modern view belongs to the actor/control lifetime, whether
  // look comes from the mouse or a controller. Native ledge handlers still
  // own body alignment and locomotion.
  const auto port=modern_actor_port(state,actor);
  if(!modern_controls_selected(state,port))return false;
  const auto& view=state.pc_shoulders[port];
  NativeGameMemory ram({state.rdram,kRdramSize});
  return view.active && view.actor==actor && ram.valid(actor,0xA4U) &&
    view.control==ram.u32(actor+game_member("layout.actor.control")) && jfg::mod::pc_ledge_view_active(ram,actor);
}
// Swimming keeps native body heading and physics while the Modern camera
// retains its world orientation through the land/water handoff.
bool modern_swimming_view_current(const State& state,std::uint32_t actor) {
  const auto port=modern_actor_port(state,actor);
  if(!modern_controls_selected(state,port))return false;
  const auto& view=state.pc_shoulders[port];
  NativeGameMemory ram({state.rdram,kRdramSize});
  return view.active && view.actor==actor && ram.valid(actor,0xA4U) &&
    view.control==ram.u32(actor+game_member("layout.actor.control")) && jfg::mod::pc_gameplay_active(ram,actor) &&
    ram.u8(view.control+game_member("layout.playerControl.movement"))==4U;
}
bool modern_shoulder_camera_current(const State& state,std::size_t port,std::uint32_t actor) {
  return modern_shoulder_current(state,port,actor) ||
    (port<4U && state.pc_shoulder_actor==actor &&
      (modern_landing_view_current(state,actor) || modern_ledge_view_current(state,actor) ||
       modern_swimming_view_current(state,actor)));
}
int dispatch(void *opaque,std::int32_t address,std::uint8_t *rdram,recomp_context *context);
bool modern_air_aim_active(const State &state,std::uint32_t actor,std::uint32_t control) {
  NativeGameMemory ram({state.rdram,kRdramSize});
  if(!ram.valid(actor,0xA4U) || !ram.valid(control,0x5D0U) || ram.u32(actor+game_member("layout.actor.control"))!=control)return false;
  const auto port=jfg::mod::pc_input_port(ram,ram.u8(control));
  return modern_controls_selected(state,port) && state.pc_shoulders[port].active &&
    state.pc_shoulders[port].actor==actor && state.pc_shoulders[port].control==control &&
    state.pc_shoulders[port].movement_before_state!=4U &&
    (state.pc_frames[port].modern_flags&jfg::kModernActionsFlag) &&
    (state.pc_frames[port].pc_mode==3 || state.pc_frames[port].pc_mode==5) &&
    state.controller_ports.samples[port].connected && !state.pc_input_blocked &&
    jfg::mod::pc_gameplay_active(ram,actor) && !game_view(ram).u8(game_data_ref("globals.pauseActive")) &&
    !jfg::mod::scripted_camera_active(ram,actor) &&
    jfg::pc_air_aim((game_view(ram).u32(game_data_ref("globals.controlButtons"))&0x10U)!=0,ram.u8(control+game_member("layout.playerControl.movement")),state.pc_shoulders[port].air_aim);
}
void modern_air_aim_update(State &state,std::uint32_t actor,std::uint32_t control,
                           const recomp_context &context) {
  if(!modern_air_aim_active(state,actor,control))return;
  NativeGameMemory ram({state.rdram,kRdramSize});
  const auto stack=static_cast<std::uint32_t>(context.r29)-0x40U;
  if(!ram.valid(stack-0x600U,0x640U) || !ram.instruction_matches("guard.game.controlGetManualAim.entry0"))return;
  const auto port=jfg::mod::pc_input_port(ram,ram.u8(control));auto &view=state.pc_shoulders[port];
  // Invoke only the shared native aiming/zoom update, never its grounded
  // locomotion handler. Its scratch frame lives below the suspended caller.
  hle::GuestMemory memory({state.rdram,kRdramSize},hle::GuestMemory::Layout::native_word_big_endian);
  auto aim=context;aim.r29=static_cast<std::int32_t>(stack);aim.r4=static_cast<std::int32_t>(actor);aim.r5=static_cast<std::int32_t>(control);aim.r6=aim.r7=0xE38;
  (void)memory.write_u32(stack+0x10U,static_cast<std::uint32_t>(-10922));
  (void)memory.write_u32(stack+0x14U,10922U);
  (void)memory.write_u32(stack+0x18U,stack+0x30U);(void)memory.write_u32(stack+0x1CU,stack+0x32U);
  (void)memory.write_u32(stack+0x20U,static_cast<std::uint32_t>(context.r6));
  const auto heading=ram.u16(control+game_member("layout.playerControl.heading"));
  ram.put16(control+game_member("layout.playerControl.heading"),static_cast<std::uint16_t>(view.yaw));
  ram.put16(control+game_member("layout.playerControl.manualPitch"),static_cast<std::uint16_t>(-view.pitch));
  dispatch(&state,static_cast<std::int32_t>(game_code("game.controlGetManualAim")),state.rdram,&aim);
  ram.put16(control+game_member("layout.playerControl.heading"),heading); // Air steering retains its momentum heading.
  // Native grounded aim publishes these weapon directions after shared look.
  // Airborne animation remains the jump clip; its weapon uses the same view.
  for(auto offset:{game_member("layout.playerControl.cameraYaw"),game_member("layout.playerControl.aimYaw")})ram.put16(control+offset,static_cast<std::uint16_t>(view.yaw));
  for(auto offset:{game_member("layout.playerControl.cameraPitch"),game_member("layout.playerControl.aimPitch"),game_member("layout.playerControl.viewPitch"),game_member("layout.playerControl.weaponPitch")})ram.put16(control+offset,static_cast<std::uint16_t>(-view.pitch));
  ram.put16(control+game_member("layout.playerControl.aimRoll"),0);ram.put16(control+game_member("layout.playerControl.weaponRoll"),0);ram.put16(control+game_member("layout.playerControl.weaponYaw"),0);
  if(aim.r2) {
    auto zoom=context;zoom.r29=static_cast<std::int32_t>(stack);zoom.r4=ram.u8(control);zoom.r5=ram.u32(control+game_member("layout.playerControl.zoom"));
    dispatch(&state,static_cast<std::int32_t>(game_code("game.camSetZoom")),state.rdram,&zoom);
  }
  view.air_aim=view.aiming=true;
  state.gameplay_trace.event("pc-air-aim",{state.vi_retraces,actor,ram.u8(control+game_member("layout.playerControl.movement")),
    ram.u16(control+game_member("layout.playerControl.heading")),static_cast<std::uint16_t>(view.yaw),ram.u16(control+game_member("layout.playerControl.manualPitch"))});
}
// The stock camera, weapon, reticle and fade APIs encode Aim in the locomotion byte.
// Adapt that legacy parameter only for those calls. Gravity, collisions,
// airborne animation and landing always see the real locomotion state.


// Supply final ground velocity before the original animation update as well as
// physics. Animation and collision must consume the same local movement.
void modern_shoulder_physics(State &state,std::uint32_t target,const recomp_context &context) {
  const bool animation=target==game_overlay_token("overlay.vela.animation") || target==game_overlay_token("overlay.juno.animation") || target==game_overlay_token("overlay.lupus.animation");
  if(!animation && target!=game_overlay_token("overlay.vela.update") && target!=game_overlay_token("overlay.juno.update") && target!=game_overlay_token("overlay.lupus.update"))return;
  NativeGameMemory ram({state.rdram,kRdramSize});
  const auto actor=static_cast<std::uint32_t>(context.r4),control=static_cast<std::uint32_t>(context.r5);
  if(!ram.valid(actor,0xA4U) || !ram.valid(control,0x5D0U) || ram.u32(actor+game_member("layout.actor.control"))!=control)return;
  const auto port=jfg::mod::pc_input_port(ram,ram.u8(control));
  if(!modern_shoulder_current(state,port,actor))return;
  // A swim-to-air/shore transition occurring inside this update still owns
  // native swimming momentum; never convert it as a grounded takeoff.
  if(state.pc_shoulders[port].movement_before_state==4U)return;
  const auto movement=ram.u8(control+game_member("layout.playerControl.movement"));
  if(!jfg::pc_shoulder_state(movement) || (animation && movement!=0U))return;
  auto &view=state.pc_shoulders[port];
  const bool landing_aim=view.air_aim && (movement==10U || movement==11U);
  view.air_aim=jfg::pc_air_aim((game_view(ram).u32(game_data_ref("globals.controlButtons"))&0x10U)!=0,movement,view.air_aim) && !state.pc_input_blocked;
  const bool aiming=movement==10U || movement==11U || view.air_aim;
  if(aiming && (!view.aiming || landing_aim)) {
    // The stock run-to-aim transition clears pitch and copies the old body
    // orientation into the weapon camera. Seed it from the persistent view.
    for(auto offset:{game_member("layout.playerControl.manualPitch"),game_member("layout.playerControl.viewPitch"),game_member("layout.playerControl.weaponPitch"),game_member("layout.playerControl.cameraPitch"),game_member("layout.playerControl.aimPitch")})
      ram.put16(control+offset,static_cast<std::uint16_t>(-view.pitch));
    for(auto offset:{game_member("layout.playerControl.cameraYaw"),game_member("layout.playerControl.aimYaw")})ram.put16(control+offset,static_cast<std::uint16_t>(view.yaw));
    ram.put16(control+game_member("layout.playerControl.aimRoll"),0);ram.put16(control+game_member("layout.playerControl.weaponRoll"),0);ram.put16(control+game_member("layout.playerControl.weaponYaw"),0);
    state.gameplay_trace.event("pc-shoulder-transition",{state.vi_retraces,actor,
      static_cast<std::uint16_t>(view.yaw),static_cast<std::uint16_t>(view.pitch)});
  }
  view.aiming=aiming;
  if(modern_free_movement_current(state,port))return;
  if(movement==3U) {
    if(view.movement_before_state!=3U) {
      const auto momentum=jfg::pc_native_airborne_motion(view.movement_before_update,
        view.movement_before_yaw,ram.u8(control+game_member("layout.playerControl.direction"))!=0);
      hle::GuestMemory memory({state.rdram,kRdramSize},hle::GuestMemory::Layout::native_word_big_endian);
      (void)memory.write_u32(control+game_member("layout.playerControl.forwardVelocity"),std::bit_cast<std::uint32_t>(momentum.forward));
      (void)memory.write_u32(control+game_member("layout.playerControl.sideVelocity"),0U);
      ram.put16(control+game_member("layout.playerControl.heading"),static_cast<std::uint16_t>(momentum.yaw));
      state.gameplay_trace.event("pc-air-takeoff",{state.vi_retraces,actor,
        static_cast<std::uint16_t>(momentum.yaw),std::bit_cast<std::uint32_t>(momentum.forward)});
      view.movement_before_state=3U;
    }
    modern_air_aim_update(state,actor,control,context);
    return;
  }
  ram.put16(actor,static_cast<std::uint16_t>(view.yaw));
  ram.put16(control+game_member("layout.playerControl.heading"),static_cast<std::uint16_t>(view.yaw));
  ram.put16(control+game_member("layout.playerControl.turnDelta"),0);
  // Retain the guest's jump/roll/crouch momentum. Normal ground motion uses
  // camera-relative forward/back and lateral strafe without turning the body.
  if(movement==0U) {
    // Use the guest's already filtered/locked axes, not the raw host sample.
    // This retains its deadzone and its 65/16 normal running-speed limit.
    auto velocity=jfg::pc_shoulder_movement(
      static_cast<std::int32_t>(game_view(ram).u32(game_data_ref("globals.controlStickX"))),
      static_cast<std::int32_t>(game_view(ram).u32(game_data_ref("globals.controlStickY"))));
    if(state.pc_frames[port].pc_mode==3 && state.modern_controls[port].mouse_original_acceleration)
      velocity=jfg::pc_original_acceleration(view.movement_before_update,velocity,
        std::bit_cast<float>(static_cast<std::uint32_t>(animation?context.r7:context.r6)));
    hle::GuestMemory memory({state.rdram,kRdramSize},hle::GuestMemory::Layout::native_word_big_endian);
    (void)memory.write_u32(control+game_member("layout.playerControl.forwardVelocity"),std::bit_cast<std::uint32_t>(velocity.forward));
    (void)memory.write_u32(control+game_member("layout.playerControl.sideVelocity"),std::bit_cast<std::uint32_t>(velocity.side));
    // Native backward animation selection depends on this direction flag.
    // The original handler instead derives it from lock-on and turn intent.
    ram.put16(control+game_member("layout.playerControl.movement"),static_cast<std::uint16_t>((movement<<8U)|(velocity.forward>0.0F?1U:0U)));
    // Discard only the bank generated by a body turn which modern controls
    // replace with the view heading. Terrain, damage and airborne poses remain.
    ram.put16(control+game_member("layout.playerControl.turnDelta"),0);
  }
}

// The native physics routine computes world velocity, collision and gravity
// using its own airborne heading. Only restore visual facing after it returns.




// Read the native animation remapping table from the active character overlay.
// Its first column identifies the ordinary clip behind an armed variant. Never
// infer humanoid sidestep IDs for Lupus, whose animation catalog is different.
unsigned modern_animation_family(State &state,unsigned character,unsigned requested) {
  if(character>2U)return UINT32_MAX;
  constexpr std::array<unsigned,3> offsets{
    game_overlay_data("animation.vela.families",OriginalModule::vela_control),
    game_overlay_data("animation.juno.families",OriginalModule::juno_control),
    game_overlay_data("animation.lupus.families",OriginalModule::lupus_control)};
  constexpr std::array<unsigned,3> counts{
    game_data_ref("animation.vela.families").size/5U,
    game_data_ref("animation.juno.families").size/5U,
    game_data_ref("animation.lupus.families").size/5U};
  if(requested>=counts[character])return UINT32_MAX;
  constexpr std::array<unsigned,3> character_sections{game_module(OriginalModule::vela_control),game_module(OriginalModule::juno_control),game_module(OriginalModule::lupus_control)};
  const unsigned section=character_sections[character];
  if(!state.active_overlay_sections.contains(section))return UINT32_MAX;
  const auto base=section_addresses?static_cast<std::uint32_t>(section_addresses[section]):0U;
  const auto table=offsets[character];
  NativeGameMemory ram({state.rdram,kRdramSize});
  const auto decode=[&](const auto &memory)->unsigned {
    if(!memory.valid(base,table+counts[character]*5U) ||
       memory.u8(base+table)!=0U || memory.u8(base+table+5U)!=1U ||
       memory.u8(base+table+15U)!=3U)return UINT32_MAX;
    return memory.u8(base+table+requested*5U);
  };
  if(ram.valid(base,table+counts[character]*5U))return decode(ram);
  JfgGeneratedSectionMetadata metadata{};
  if(!state.active_overlay_sections.contains(section) ||
     !jfg_generated_section_metadata(section,&metadata) || metadata.is_overlay!=1U ||
     base!=metadata.linked_vram || (base&3U))return UINT32_MAX;
  const std::uint64_t extent=std::uint64_t(metadata.text_size)+metadata.data_size+metadata.bss_size;
  const std::uint32_t offset=base-kKseg0;
  if(extent>0x10000U || extent<table+counts[character]*5U ||
     offset>kGuestAddressSpan || extent>kGuestAddressSpan-offset || (extent&3U))return UINT32_MAX;
  const jfg::mod::DialogueMemory memory(ram,base,
    std::span<const std::uint8_t>(state.rdram+offset,static_cast<std::size_t>(extent)));
  return decode(memory);
}

// Retain explicit nesting: generated overlay calls do not carry a reliable RA.


// Normal ground aim retains the guest's position, collision, zoom and FOV.
// Its old pitch exaggeration and follow easing must not change the view angle
// when switching between third-person look and the aiming camera.
void modern_shoulder_aim_camera(State &state,std::uint32_t target,
                                std::uint32_t actor,std::uint32_t control) {
  if(target!=game_code("game.controlUpdateCameraMovement"))return;
  NativeGameMemory ram({state.rdram,kRdramSize});
  if(!ram.valid(actor,0xA4U) || !ram.valid(control,0x5D0U) || ram.u32(actor+game_member("layout.actor.control"))!=control)return;
  const auto port=jfg::mod::pc_input_port(ram,ram.u8(control));
  if(!modern_shoulder_current(state,port,actor) || !state.pc_shoulders[port].aiming)return;
  const auto camera=game_view(ram).u32(game_data_ref("globals.controlledCamera"));
  if(!ram.valid(camera,0x4CU))return;
  const auto &view=state.pc_shoulders[port];
  ram.put16(camera+game_member("layout.camera.yaw"),static_cast<std::uint16_t>(jfg::pc_shoulder_camera_yaw(view.yaw)));
  ram.put16(camera+game_member("layout.camera.pitch"),static_cast<std::uint16_t>(view.pitch));
}

bool diagnostic_weather() {
  static const bool enabled=[] {
    char value[2]{};
    return GetEnvironmentVariableA("JFG_DIAGNOSTIC_WEATHER",value,2U)==1U && value[0]=='1';
  }();
  return enabled;
}
// Explicit owner capture only. Observe native weather selection and the actual
// rainFastDraw pixel writes without changing weather, guest memory or timing.


bool diagnostic_reticle_lines() {
  static const bool enabled=[] {
    char value[2]{};
    return GetEnvironmentVariableA("JFG_DIAGNOSTIC_RETICLE_LINES",value,2U)==1U && value[0]=='1';
  }();
  return enabled;
}
// Optional bounded trace of the original deferred software-line writer.


// Rendering-only private fixture. Exercise the original shuriken reticle
// drawer on a copied replay without granting a weapon or editing a save.
// The current weapon is restored before this draw call returns.


// Temporarily supply a canonical action table to the original player update.
// Both stock tables are restored before returning; menus and original mapping
// never see the override, and the saved Normal/Expert option is left intact.


// The native crouch/prone helper owns roll animation, collision and held-repeat.
// Supply only its missing held side action, after native input/stance checks.

// Modern keeps the crawl heading at the view yaw. Retain a matching native
// forward/backward direction after the stock lock-on timeout is evaluated.

// A Modern lateral gesture becomes the native prone side action. Consume its
// analog crawl component at the native consumers, as for Classic C-side alone.

// Default-off attribution of host calls outside graphics submission. Nested
// spans overlap; CPU cycles are not elapsed time and must not be added to wall.

void reload_controller_ports(State &state) {
  const auto now = std::chrono::steady_clock::now();
  if (now - state.controller_config_check < std::chrono::milliseconds(250))
    return;
  state.controller_config_check = now;
  const DiagnosticHostStage cost(state,"host-profile-config");
  if (state.controller_config_path.empty())
    return;
  const auto files=state.controller_config_files.latest();
  if (!files || files->size()!=13U) return;
  const auto& automatic=(*files)[12];
  if(automatic.status==jfg::ConfigFileValue::Status::ready)
    (void)jfg::parse_controller_auto_assignment(automatic.text,state.controller_ports.auto_assignment);
  else if(automatic.status==jfg::ConfigFileValue::Status::missing)
    state.controller_ports.auto_assignment={};
  for (std::size_t p = 0; p < 4; ++p) {
    const auto& modern=(*files)[p*3U];
    if(modern.status==jfg::ConfigFileValue::Status::ready) {
      auto candidate=state.modern_controls[p];
      if(jfg::parse_modern_controls(modern.text,candidate) &&
         jfg::serialize_modern_controls(candidate)!=jfg::serialize_modern_controls(state.modern_controls[p])) {
        state.modern_controls[p]=candidate;state.modern_aim_latch[p].reset();state.modern_movement_latch[p].reset();
        state.modern_scope_zoom[p].reset();state.pc_device_release[p]={};state.pc_device_ready[p]=false;
        (void)state.controller_input_gate.blocked(true,state.controller_ports.samples);
      }
    } else if(modern.status==jfg::ConfigFileValue::Status::missing && state.modern_controls[p].enabled) {
      state.modern_controls[p].enabled=false;state.modern_aim_latch[p].reset();state.modern_scope_zoom[p].reset();
      state.pc_device_release[p]={};state.pc_device_ready[p]=false;
      (void)state.controller_input_gate.blocked(true,state.controller_ports.samples);
    }
    const auto& pc=(*files)[p*3U+1U];
    if(pc.status==jfg::ConfigFileValue::Status::ready)
      (void)jfg::parse_pc_input(pc.text,state.pc_input[p]);
    const auto& file=(*files)[p*3U+2U];
    if(file.status!=jfg::ConfigFileValue::Status::ready) continue;
    jfg::ControllerMapping mapping;
    if (jfg::parse_controller_mapping(file.text, mapping)) {
      if(mapping.device==-4)mapping.device=state.controller_catalog.reserve(mapping.device_key);
      state.controller_ports.configure(p, mapping);
    }
  }
  // The selected style is the only opt-in. The obsolete profile switch is ignored.
  const bool pc_enabled=std::any_of(state.modern_controls.begin(),state.modern_controls.end(),
    [](const auto& config){return config.enabled;});
  if(pc_enabled!=state.modern_controls_active) {
    state.modern_controls_active=pc_enabled;state.pc_aim.fill({});
    for(auto &latch:state.modern_aim_latch)latch.reset();
    for(auto &scope:state.modern_scope_zoom)scope.reset();
    state.pc_mouse.clear();state.pc_wheel.clear();state.pc_wheel_key=0;
    const bool was_captured=state.pc_mouse_captured.exchange(false);
    if(was_captured && state.play_mode && state.native_window) {
      ClipCursor(nullptr);SetCursor(LoadCursorW(nullptr,MAKEINTRESOURCEW(32512)));
    }
    (void)state.controller_input_gate.blocked(true,state.controller_ports.samples);
  }

}
jfg::ControllerPortSample sample_keyboard_port(const State &state,std::size_t port) {
  const auto down=[&](int key) {
    return key>=256?state.pc_wheel_key==key:host_key_down(state,key);
  };
  auto sample=jfg::map_pc_keyboard(jfg::effective_pc_input(false,state.pc_input[port]),down);
  return sample;
}
void sample_controller_ports(State &state,bool discover_sdl) {
  const DiagnosticHostStage host_stage(state,"host-profile-devices");
  reload_controller_ports(state);
  state.pc_wheel_key=state.pc_wheel.sample();
  state.pc_aim.fill({});state.modern_live_flags.fill(0);state.modern_physical_neutral.fill(true);
  state.cutscene_physical_actions=0;state.cutscene_mapped_buttons=0;
  std::array<bool, jfg::kControllerDeviceCount> available{};
  std::array<jfg::StandardControllerSample, jfg::kControllerDeviceCount> hardware{};
  // Replay boot reaches this function before replay loading; defer SDK startup
  // until live polling so recordings never discover or open physical SDL pads.
  if(discover_sdl && !state.input_replay_loaded) {
    state.sdl_controllers.open(jfg::SdlControllerBackend::executable_directory());
    state.controller_catalog.update(state.sdl_controllers.poll());
    for(int device=4;device<static_cast<int>(jfg::kControllerDeviceCount);++device) {
      const auto* info=state.controller_catalog.get(device);
      available[static_cast<std::size_t>(device)]=info->connected && !info->session_only;
      hardware[static_cast<std::size_t>(device)]=info->sample;
    }
  }
  for (std::size_t p = 0; p < 4; ++p)
    available[p] = read_xinput_device(static_cast<int>(p), hardware[p]);
  const auto devices = state.controller_ports.devices(available,&state.controller_catalog);
  state.pc_devices=devices;
  NativeGameMemory pc_memory({state.rdram,kRdramSize});
  for (std::size_t p = 0; p < 4; ++p) {
    auto &sample = state.controller_ports.samples[p];
    sample = {};
    const int device = devices[p];
    if(modern_controls_selected(state,p) &&
       (device==-3 || (device>=0 && available[static_cast<std::size_t>(device)]))) {
      const auto &config=state.modern_controls[p];
      auto input=device==-3?jfg::sample_modern_keyboard(config,[&](int key) {
          if(state.guest_menu.kind!=jfg::GuestMenuKind::none &&
             !jfg::modern_menu_key_allowed(config,key,state.guest_menu.kind==jfg::GuestMenuKind::floyd_pause))return false;
          return key>=256?state.pc_wheel_key==key:host_key_down(state,key);
        }):jfg::sample_modern_pad(config,hardware[static_cast<std::size_t>(device)]);
      state.modern_physical_neutral[p]=input.physically_neutral;
      if(p==0)state.cutscene_physical_actions=input.held;
      const auto actor=jfg::mod::pc_player_for_port(pc_memory,static_cast<unsigned>(p));
      const auto floyd=jfg::mod::pc_floyd_context(pc_memory);
      const bool flying=floyd && floyd.port==p;
      const bool boss=jfg::mod::pc_boss_gameplay_active(pc_memory,actor);
      const bool racing=state.active_overlay_sections.contains(game_module(OriginalModule::racing)) &&
        jfg::mod::pc_race_gameplay_active(pc_memory,actor,static_cast<unsigned>(p));
      const bool menu=game_view(pc_memory).u8(game_data_ref("globals.pauseActive"))!=0 ||
        !(flying || boss || racing || jfg::mod::pc_gameplay_active(pc_memory,actor)) ||
        jfg::mod::scripted_camera_active(pc_memory,actor);
      state.modern_aim_latch[p].apply(input,config.aim_toggle,
        !menu && !state.pc_input_blocked && state.pc_device_ready[p]);
      sample=racing && !menu ? jfg::map_modern_race_actions(input) : flying && !menu ? jfg::map_modern_floyd_actions(input,floyd.mission,device==-3,config.pad_floyd_flight_invert_y) :
        boss && !menu ? jfg::map_modern_boss_actions(input) :
        jfg::map_modern_actions(input,menu,state.guest_menu.kind==jfg::GuestMenuKind::pause_root &&
          state.guest_menu.ready && (state.guest_menu.enabled&0x100U)!=0,
          state.guest_menu.kind==jfg::GuestMenuKind::floyd_pause && state.guest_menu.ready);
      sample.buttons=state.menu_confirm[p].apply(menu?state.guest_menu:jfg::GuestMenuState{},sample.buttons);
      const bool free_movement=state.modern_movement_latch[p].sample(
        (input.held&jfg::modern_bit(jfg::ModernAction::movement_toggle))!=0,config.free_movement,
        !menu && !racing && !flying && !state.pc_input_blocked && state.pc_device_ready[p],device);
      state.modern_live_flags[p]=static_cast<std::uint8_t>(jfg::modern_scope_flags(menu?0:input.held) |
          (menu?0U:jfg::modern_roll_flags(input)) | (free_movement?jfg::kModernFreeMovementFlag:0U));
      if(device>=0 && !menu && !racing)state.pc_aim[p]=jfg::pc_stick_look(config.look,
        hardware[static_cast<std::size_t>(device)],config.movement_stick,flying || (sample.buttons&0x10)!=0,
        flying?jfg::PcStickLookShape::square:jfg::PcStickLookShape::radial);
      continue;
    }
    if (device == -3) {
      sample = sample_keyboard_port(state,p);
      continue;
    }
    if (device < 0 || !available[static_cast<std::size_t>(device)])
      continue;
    const auto mapped=jfg::map_pc_controller(state.controller_ports.mappings[p],
        hardware[static_cast<std::size_t>(device)],jfg::effective_pc_input(false,state.pc_input[p]),false);
    sample = {mapped.buttons, static_cast<std::int8_t>(mapped.stick.x),
              static_cast<std::int8_t>(mapped.stick.y), true};

  }
  state.cutscene_mapped_buttons=state.controller_ports.samples[0].buttons;
  for(std::size_t p=0;p<4;++p) {
    auto &sample=state.controller_ports.samples[p];
    auto release_sample=sample;
    if(modern_controls_selected(state,p) && !state.modern_physical_neutral[p])release_sample.buttons|=1;
    state.pc_device_ready[p]=!state.pc_device_release[p].blocked(devices[p],release_sample,state.pc_aim[p]);
    if(!state.pc_device_ready[p]) {
      trace_modern_view_reset(state,p,1U);
      sample.buttons=0;sample.x=sample.y=0;state.pc_aim[p]={};state.modern_live_flags[p]=0;
      state.modern_aim_latch[p].reset();state.modern_scope_zoom[p].reset();
      state.pc_stick_motion[p].clear();state.pc_scope_motion[p].clear();state.pc_boss_aim_motion[p].clear();state.modern_scope_sensitivity[p].clear();state.pc_orbits[p]={};state.pc_shoulders[p]={};
      if(devices[p]==-3){state.pc_mouse.clear();state.pc_wheel.clear();}
    }
  }
  state.controller_mapping = state.controller_ports.mappings[0];
  state.controller_mapping.device = devices[0];
}

constexpr jfg::mod::DialogueLayout kDialogueLayout{
  game_overlay_extent(OriginalModule::hint_text),
  game_overlay_data("dialogue.active",OriginalModule::hint_text),
  game_overlay_data("dialogue.type",OriginalModule::hint_text),
  game_overlay_data("dialogue.text",OriginalModule::hint_text),
  game_overlay_data("dialogue.table",OriginalModule::hint_text),
  game_overlay_data("dialogue.pending",OriginalModule::hint_text),
  game_overlay_data("dialogue.transition",OriginalModule::hint_text),
  game_overlay_data("dialogue.busy",OriginalModule::hint_text),
  game_overlay_data("dialogue.fade",OriginalModule::hint_text),
  game_overlay_data("dialogue.page0",OriginalModule::hint_text),
  game_overlay_data("dialogue.page1",OriginalModule::hint_text),
  game_overlay_data("dialogue.page2",OriginalModule::hint_text),
  {game_overlay_site("guard.dialogue.read",OriginalModule::hint_text),game_instruction_word("guard.dialogue.read"),0xffff0000U},
  {game_overlay_site("guard.dialogue.return",OriginalModule::hint_text),game_instruction_word("guard.dialogue.return")}};
constexpr jfg::mod::FloydPauseLayout kFloydPauseLayout{
  game_overlay_extent(OriginalModule::floyd_missions),
  game_overlay_data("menu.floyd.active",OriginalModule::floyd_missions),
  game_overlay_data("menu.floyd.state",OriginalModule::floyd_missions),
  {game_overlay_site("guard.floyd.pause_entry",OriginalModule::floyd_missions),game_instruction_word("guard.floyd.pause_entry")},
  {game_overlay_site("guard.floyd.pause_button",OriginalModule::floyd_missions),game_instruction_word("guard.floyd.pause_button")}};

jfg::mod::DialogueState navigation_dialogue(State &state) {
  NativeGameMemory ram({state.rdram,kRdramSize});
  const auto base=section_addresses!=nullptr?static_cast<std::uint32_t>(section_addresses[game_module(OriginalModule::hint_text)]):0U;
  if(!state.active_overlay_sections.contains(game_module(OriginalModule::hint_text)))return {};
  if(ram.valid(base,kDialogueLayout.extent))return jfg::mod::read_dialogue(ram,base,kDialogueLayout);
  JfgGeneratedSectionMetadata metadata{};
  if(!state.active_overlay_sections.contains(game_module(OriginalModule::hint_text)) ||
     !jfg_generated_section_metadata(game_module(OriginalModule::hint_text),&metadata) || metadata.is_overlay!=1U ||
     base!=metadata.linked_vram || (base&3U))return {};
  const std::uint64_t extent=std::uint64_t(metadata.text_size)+metadata.data_size+metadata.bss_size;
  const std::uint32_t offset=base-kKseg0;
  if(extent<kDialogueLayout.extent || extent>0x10000U || offset>kGuestAddressSpan ||
     extent>kGuestAddressSpan-offset || (extent&3U))return {};
  jfg::mod::DialogueMemory memory(ram,base,
      std::span<const std::uint8_t>(state.rdram+offset,static_cast<std::size_t>(extent)));
  return jfg::mod::read_dialogue(memory,base,kDialogueLayout);
}






// Each overlay view is qualified against the generated section and its mapped
// extent. Canonical overlay globals may reside outside physical 4 MiB RDRAM.
template<class Decode>
jfg::GuestMenuState decode_menu_overlay(State &state,unsigned section,std::uint32_t need,Decode decode) {
  NativeGameMemory ram({state.rdram,kRdramSize});
  const auto base=section_addresses?static_cast<std::uint32_t>(section_addresses[section]):0U;
  if(!state.active_overlay_sections.contains(section))return {};
  if(ram.valid(base,need))return decode(ram,base);
  JfgGeneratedSectionMetadata metadata{};
  if(!jfg_generated_section_metadata(section,&metadata)||metadata.is_overlay!=1U||base!=metadata.linked_vram||(base&3U))return {};
  const std::uint64_t extent=std::uint64_t(metadata.text_size)+metadata.data_size+metadata.bss_size;
  const std::uint32_t offset=base-kKseg0;
  if(extent<need||extent>0x10000U||offset>kGuestAddressSpan||extent>kGuestAddressSpan-offset||(extent&3U))return {};
  const jfg::mod::DialogueMemory memory(ram,base,std::span<const std::uint8_t>(state.rdram+offset,static_cast<std::size_t>(extent)));
  return decode(memory,base);
}
// JP stores this pause counter in resident state and widens it to a word;
// US/PAL retain a halfword in the pause overlay. Its original owner supplies
// both storage and width, while the caller still owns the active pause view.
template<class OverlayView>
std::uint32_t pause_secondary_counter(NativeGameMemory& ram,const OverlayView& memory,std::uint32_t base) {
  constexpr auto ref=game_data_ref("menu.root.stat_second");
  if(ref.section==game_module(OriginalModule::pause_root)) {
    const jfg::game::OverlayMemory view(jfg::game::linked::descriptor,game_module(OriginalModule::pause_root),base,memory);
    if(ref.size==2)return view.u16(ref);
    if(ref.size==4)return view.u32(ref);
  } else {
    if(ref.size==2)return game_view(ram).u16(ref);
    if(ref.size==4)return game_view(ram).u32(ref);
  }
  throw std::runtime_error("Unsupported pause counter width");
}

jfg::GuestMenuState read_pause_menu(State &state) {
  using Kind=jfg::GuestMenuKind;
  NativeGameMemory ram({state.rdram,kRdramSize});
  if(game_view(ram).u8(game_data_ref("globals.pauseActive"))==0 || game_view(ram).u8(game_data_ref("globals.frontendMode"))!=16)return {};
  return decode_menu_overlay(state,game_module(OriginalModule::pause_manager),game_overlay_extent(OriginalModule::pause_manager),[&](const auto &manager,std::uint32_t mb)->jfg::GuestMenuState {
    const auto screen=manager.u32(mb+game_overlay_data("menu.pause.page",OriginalModule::pause_manager));
    state.gameplay_trace.event("pause-page",{state.vi_retraces,screen,manager.u32(mb+game_overlay_data("menu.pause.transition",OriginalModule::pause_manager)),manager.u32(mb+game_overlay_data("menu.pause.state",OriginalModule::pause_manager))});
    if(manager.u32(mb+game_overlay_data("menu.pause.transition",OriginalModule::pause_manager))!=0 || manager.u32(mb+game_overlay_data("menu.pause.state",OriginalModule::pause_manager))!=2)return {};
    if(screen==6) {
      return decode_menu_overlay(state,game_module(OriginalModule::settings),game_overlay_extent(OriginalModule::settings),[&](const auto& m,std::uint32_t base)->jfg::GuestMenuState {
        if(m.u32(base+game_overlay_data("menu.options.transition",OriginalModule::settings))!=0 || m.u32(base+game_overlay_data("menu.options.busy",OriginalModule::settings))!=0)return {};
        const auto page=m.u32(base+game_overlay_data("menu.options.page",OriginalModule::settings)),selected=m.u32(base+game_overlay_data("menu.options.selected",OriginalModule::settings));
        state.gameplay_trace.event("options-page",{state.vi_retraces,page,selected,m.u32(base+game_overlay_data("menu.options.trace",OriginalModule::settings))});
        if(page>9 || selected>=8)return {};
        unsigned enabled=255U;
        if(game_view(ram).u32(game_data_ref("globals.frontendDisplayFlags"))&0x40000000U)enabled&=~8U; // unavailable screen-size option
        return {page==8?Kind::options:Kind::option_detail,static_cast<int>(selected),enabled,true,base,page};
      });
    }
    // These native pages expose B as Back; the modern Confirm adapter also
    // dismisses informational pages. Map keeps its native travel/confirm action.
    if(screen==2)return {Kind::pause_map,0,0,true,mb,screen};
    if(screen==3 || screen==4 || screen==5 || screen==7 || screen==9)
      return {Kind::pause_info,0,0,true,mb,screen};
    if(screen!=1 && screen!=8)return {};
    return decode_menu_overlay(state,game_module(OriginalModule::pause_root),game_overlay_extent(OriginalModule::pause_root),[&](const auto &m,std::uint32_t base)->jfg::GuestMenuState {
      if(m.u32(base+game_overlay_data("menu.root.transition",OriginalModule::pause_root))!=0)return {};
      if(m.u8(base+game_overlay_data("menu.root.character",OriginalModule::pause_root))!=0)
        return {Kind::pause_character,0,7U,m.u8(base+game_overlay_data("menu.root.character_ready",OriginalModule::pause_root))==255 && m.u8(base+game_overlay_data("menu.root.character_busy",OriginalModule::pause_root))==0,base};
      if(m.u8(base+game_overlay_data("menu.root.ready",OriginalModule::pause_root))!=255 || m.u8(base+game_overlay_data("menu.root.selected",OriginalModule::pause_root))>=8)return {};
      const auto player=game_view(ram).u32(game_data_ref("globals.selectedPlayer"));
      if(!ram.valid(player,0xC0U))return {};
      const auto flag=[&](unsigned n){return (ram.u8(player+game_member("layout.saveGame.flags")+(n>>3U))&(1U<<(n&7U)))!=0;};
      unsigned enabled=255U;
      if(flag(0x64U))enabled&=~2U;
      if(!flag(0x5FU))enabled&=~128U;
      if(m.s16(base+game_overlay_data("menu.root.stat_first",OriginalModule::pause_root))==0 && pause_secondary_counter(ram,m,base)==0)enabled|=256U;
      return {Kind::pause_root,m.u8(base+game_overlay_data("menu.root.selected",OriginalModule::pause_root)),enabled,true,base};
    });
  });
}

jfg::GuestMenuState read_guest_menu(State &state) noexcept {
  using Kind=jfg::GuestMenuKind;
  NativeGameMemory ram({state.rdram,kRdramSize});
  const auto mode=game_view(ram).u8(game_data_ref("globals.frontendMode"));
  if(game_view(ram).u8(game_data_ref("globals.pauseActive"))) {
    try {
      const auto mission=decode_menu_overlay(state,game_module(OriginalModule::floyd_missions),kFloydPauseLayout.extent,
        [&](const auto& m,std::uint32_t base)->jfg::GuestMenuState {
          if(!jfg::mod::pc_floyd_pause_screen(m,base,kFloydPauseLayout))return {};
          return {Kind::floyd_pause,0,0,true,base};
        });
      if(mission.kind!=Kind::none)return mission;
    } catch(...) {}
  }
  if(mode==16U) { try{return read_pause_menu(state);}catch(...){return {};} }
  if(mode!=3U && mode!=24U) return {};
  const unsigned section=mode==3U?game_module(OriginalModule::title):game_module(OriginalModule::save_keyboard);
  const auto base=section_addresses?static_cast<std::uint32_t>(section_addresses[section]):0U;
  if(!state.active_overlay_sections.contains(section))return {};
  const auto decode=[&](const auto &m)->jfg::GuestMenuState {
    try {
      if(mode==3U) {
        if(!m.valid(base,game_overlay_extent(OriginalModule::title))) return {};
        const auto stage=m.u32(base+game_overlay_data("menu.title.stage",OriginalModule::title));
        if(stage==1U) return {Kind::title,0,1U,true,base};
        const int selected=ram.u8(game_data("globals.startscreenOption"));
        if(stage==2U && selected<3 && m.u32(base+game_overlay_data("menu.title.ready",OriginalModule::title))==255U)
          return {Kind::start,selected,game_view(ram).u32(game_data_ref("globals.controllerCount"))>=2U?7U:5U,true,base};
      } else {
        if(!m.valid(base,game_overlay_extent(OriginalModule::save_keyboard))||
           m.u32(base+game_overlay_data("menu.save.active",OriginalModule::save_keyboard))==0U) return {};
        const unsigned stage=m.u8(base+game_overlay_data("menu.save.stage",OriginalModule::save_keyboard));
        const int selected=m.u8(base+game_overlay_data("menu.save.selected",OriginalModule::save_keyboard));
        if(m.s16(base+game_overlay_data("menu.save.readiness",OriginalModule::save_keyboard))<=0x7A00 || m.s16(base+game_overlay_data("menu.save.ready",OriginalModule::save_keyboard))!=255) return {};
        if(stage==0U && selected<6) return {Kind::saves,selected,63U,true,base};
        if(stage==4U && selected<4) {
          // The native save action page keeps the Play icon first.
          // Copy/erase and their confirmation pages remain keyboard-driven.
          const float slide=std::bit_cast<float>(m.u32(base+game_overlay_data("menu.save.slide",OriginalModule::save_keyboard)));
          if(slide>=21.5f && slide<=22.1f)
            return {Kind::save_actions,selected,1U,true,base};
        }
      }
    } catch(...) {}
    return {};
  };
  if(ram.valid(base,mode==3U?game_overlay_extent(OriginalModule::title):game_overlay_extent(OriginalModule::save_keyboard))) return decode(ram);
  JfgGeneratedSectionMetadata metadata{};
  if(!state.active_overlay_sections.contains(section) ||
     !jfg_generated_section_metadata(section,&metadata) || metadata.is_overlay!=1U ||
     base!=metadata.linked_vram || (base&3U)) return {};
  const std::uint64_t extent=std::uint64_t(metadata.text_size)+metadata.data_size+metadata.bss_size;
  const std::uint32_t offset=base-kKseg0;
  if(extent>0x10000U || extent<game_overlay_extent(OriginalModule::title) || offset>kGuestAddressSpan ||
     extent>kGuestAddressSpan-offset || (extent&3U)) return {};
  const jfg::mod::DialogueMemory memory(ram,base,
      std::span<const std::uint8_t>(state.rdram+offset,static_cast<std::size_t>(extent)));
  return decode(memory);
}

// Called only at the controller-poll boundary, after checking the live native
// menu and its overlay identity. Preview/render/activation remain native.
bool select_guest_menu(State& state, jfg::GuestMenuKind kind, int target) noexcept {
  const auto live=read_guest_menu(state);
  if(!live.ready || live.kind!=kind || live.identity!=state.guest_menu.identity ||
     target<0 || target>=(kind==jfg::GuestMenuKind::pause_root?9:kind==jfg::GuestMenuKind::options?8:6) || !(live.enabled&(1U<<target)))return false;
  if(kind==jfg::GuestMenuKind::pause_root && target==8)return true;
  std::uint32_t address=0;
  if(kind==jfg::GuestMenuKind::start)address=game_data("globals.startscreenOption");
  else if(kind==jfg::GuestMenuKind::saves || kind==jfg::GuestMenuKind::save_actions)
    address=live.identity+game_overlay_data("menu.save.selected",OriginalModule::save_keyboard);
  else if(kind==jfg::GuestMenuKind::pause_root)address=live.identity+game_overlay_data("menu.root.selected",OriginalModule::pause_root);
  else if(kind==jfg::GuestMenuKind::options)address=live.identity+game_overlay_data("menu.options.selected",OriginalModule::settings);
  if(!address)return false;
  // Relocated overlay addresses can be below KSEG0. Use the same wrapping
  // host offset as read_guest_menu's validated overlay view, not physical RAM
  // aliasing. The live decoder above has proved this exact field is mapped.
  const std::uint32_t offset=address-kKseg0;
  if(offset>=kGuestAddressSpan)return false;
  if(kind==jfg::GuestMenuKind::options) {
    for(unsigned i=0;i<4;++i)state.rdram[(offset+i)^3U]=i==3?static_cast<std::uint8_t>(target):0;
  } else state.rdram[offset^3U]=static_cast<std::uint8_t>(target);
  if(target!=live.selected && (kind==jfg::GuestMenuKind::pause_root || kind==jfg::GuestMenuKind::options))
    state.menu_selection_feedback=live;
  if(kind==jfg::GuestMenuKind::pause_root && target!=live.selected) {
    for(unsigned i=0;i<4;++i) {
      state.rdram[((live.identity+game_overlay_data("menu.root.selection_fade",OriginalModule::pause_root)-kKseg0+i)^3U)]=i==3?255:0;
      state.rdram[((live.identity+game_overlay_data("menu.root.selection_timer",OriginalModule::pause_root)-kKseg0+i)^3U)]=0;
    }
  }
  state.gameplay_trace.event("menu-select",{state.vi_retraces,static_cast<unsigned>(kind),
    static_cast<unsigned>(live.selected),static_cast<unsigned>(target)});
  state.guest_menu.selected=target;
  return true;
}

[[noreturn]] void fail_closed_dispatch(State &state, std::string_view category,
                                      std::string_view operation, std::uint32_t guest_target);

void sample_live_controller(State &state) noexcept {
  const DiagnosticHostStage host_stage(state,"host-profile-input");
  {
    const auto input=state.window_input.consume_frame(state.host_keys,state.host_key_presses,state.exit_requested);
    state.menu_pointer_frame=input.pointer;
    if(input.focus_lost){state.menu_pointer.reset();for(auto &effect:state.pc_rumble_effects)effect.clear();state.pc_mouse.clear();state.pc_wheel.clear();state.pc_input_blocked=true;(void)state.controller_input_gate.blocked(true,state.controller_ports.samples);}
    if(state.pc_mouse_captured.load()) {
      state.pc_mouse.add(input.x,input.y);
      if(input.x || input.y)state.mouse_diagnostics.increment(jfg::MouseCount::mailbox_nonzero);
    }
    state.pc_wheel.add(input.wheel);
  }
  const SlowHostWork timing(state, "host-controller");
  constexpr std::uint16_t kButtonA = 0x8000U;
  std::uint16_t buttons = 0U;
  int stick_x = 0;
  int stick_y = 0;
  std::uint8_t menu_kind=0,menu_target=0;
  const auto previous_menu=state.guest_menu;
  state.guest_menu=read_guest_menu(state);
  if(!(state.guest_menu==previous_menu))
    state.gameplay_trace.event("menu-state",{state.vi_retraces,static_cast<unsigned>(state.guest_menu.kind),
      static_cast<unsigned>(state.guest_menu.selected),state.guest_menu.enabled,state.guest_menu.identity});
  if(!state.input_replay_loaded)sample_controller_ports(state);
  else reload_controller_ports(state);
  state.pc_frames.fill({});state.pc_mouse_used.fill(false);
  bool connected = state.controller_ports.samples[0].connected;
  if (state.input_replay_loaded) {
    jfg::ControllerReplaySample replay;
    if (state.input_replay_gameplay_time && state.controller_samples >= state.replay_gameplay_first_poll) {
      const auto events = std::span<const jfg::InputReplayEvent>(state.input_replay.events()).subspan(state.replay_gameplay_first_poll);
      if (!state.replay_gameplay_clock_ready) {
        NativeGameMemory memory({state.rdram,kRdramSize});
        if (!jfg::mod::pc_gameplay_active(memory,state.phase9_player_actor) ||
            jfg::mod::scripted_camera_active(memory,state.phase9_player_actor))
          fail_closed_dispatch(state,"recorded-input","gameplay-landmark-mismatch",0U);
        state.replay_gameplay_origin_vi = state.vi_retraces;
        state.replay_gameplay_clock_ready = true;
        state.gameplay_trace.event("replay-landmark", {state.vi_retraces,events.front().first_retrace,
            state.controller_samples,state.phase9_player_actor,game_view(memory).u32(game_data_ref("globals.currentLevel"))});
      }
      const auto elapsed_vi = state.vi_retraces-state.replay_gameplay_origin_vi;
      if (events.front().first_retrace > UINT64_MAX-elapsed_vi)
        fail_closed_dispatch(state,"recorded-input","gameplay-time-overflow",0U);
      const auto recorded_vi = events.front().first_retrace + elapsed_vi;
      const auto sample = state.recorded_input_timeline.sample(recorded_vi,events);
      if (!sample) fail_closed_dispatch(state,"recorded-input","unrepresentable-gameplay-poll",0U);
      replay = *sample;
    } else if (state.input_replay_recorded_time) {
      const auto sample = state.recorded_input_timeline.sample(state.vi_retraces,state.input_replay.events());
      if (!sample) fail_closed_dispatch(state,"recorded-input","unrepresentable-poll",0U);
      replay = *sample;
    } else {
      replay = state.input_replay_by_poll
          ? state.input_replay.sample_by_poll(state.controller_samples)
          : state.input_replay.sample_at(state.vi_retraces);
    }
    if(state.modern_controls_active)state.pc_frames[0]=replay;
    menu_kind=replay.menu_kind;menu_target=replay.menu_target;
    connected = replay.connected;
    buttons = replay.buttons;
    stick_x = replay.stick_x;
    stick_y = replay.stick_y;
  } else {
    const auto sample=state.controller_ports.samples[0];
    buttons=sample.buttons;stick_x=sample.x;stick_y=sample.y;
  }

  const HWND root=state.native_window ? GetAncestor(static_cast<HWND>(state.native_window),GA_ROOT) : nullptr;
  const bool settings_capture=state.play_mode && root && GetPropW(root,L"JfgSettingsOpen")!=nullptr;
  const bool ui_capture=state.play_mode && root && (GetForegroundWindow()!=root || settings_capture);
  auto release_samples=state.controller_ports.samples;
  for(std::size_t p=0;p<4;++p) {
    if(modern_controls_selected(state,p)) {
      release_samples[p].buttons=state.modern_physical_neutral[p]?0:1;
      if(state.modern_physical_neutral[p])release_samples[p].x=release_samples[p].y=0;
    }
    if(state.pc_aim[p].x || state.pc_aim[p].y)release_samples[p].buttons|=1;
  }
  const bool block_physical=state.controller_input_gate.blocked(ui_capture,release_samples);
  const bool replay_suspended=state.input_replay_loaded &&
    state.vi_retraces>=state.diagnostic_input_suspend_begin &&
    state.vi_retraces<state.diagnostic_input_suspend_end;
  const bool previously_blocked=state.pc_input_blocked;
  state.pc_input_blocked=jfg::pc_input_motion_blocked(block_physical,state.input_replay_loaded,replay_suspended);
  if(previously_blocked!=state.pc_input_blocked)
    state.gameplay_trace.event("pc-input-suspended",{state.vi_retraces,state.pc_input_blocked?1U:0U});
  NativeGameMemory pc_memory({state.rdram,kRdramSize});
  const auto floyd=jfg::mod::pc_floyd_context(pc_memory);
  std::array<bool,4> actions{},free_view{};
  bool want_mouse=false;
  for(std::size_t p=0;p<4;++p) {
    const auto actor=jfg::mod::pc_player_for_port(pc_memory,static_cast<unsigned>(p));
    const bool landing=modern_landing_view_current(state,actor);
    const bool available=modern_controls_selected(state,p) && game_view(pc_memory).u8(game_data_ref("globals.pauseActive"))==0 &&
      !jfg::mod::scripted_camera_active(pc_memory,actor);
    actions[p]=available && (jfg::mod::pc_actions_active(pc_memory,actor) || landing || (floyd && floyd.port==p));
    free_view[p]=available && (jfg::mod::pc_gameplay_active(pc_memory,actor) || landing);
    want_mouse|=actions[p] && state.pc_devices[p]==-3 && active_pc_input(state,p).mouse_aim &&
      state.controller_ports.samples[p].connected;
  }
  want_mouse=want_mouse && state.pc_raw_available && !block_physical && !state.input_replay_loaded &&
    (state.input_record_path.empty() || state.pc_record_extended);
  if(want_mouse && state.native_window) {
    const HWND window=static_cast<HWND>(state.native_window);RECT rect{};GetClientRect(window,&rect);
    MapWindowPoints(window,nullptr,reinterpret_cast<POINT*>(&rect),2);ClipCursor(&rect);SetCursor(nullptr);
  } else {
    if(state.pc_mouse_captured){ClipCursor(nullptr);SetCursor(LoadCursorW(nullptr,MAKEINTRESOURCEW(32512)));}
    state.pc_mouse.clear();
  }
  state.pc_mouse_captured=want_mouse;
  if(state.pc_input_blocked){state.pc_aim.fill({});state.pc_wheel.clear();state.pc_mouse.clear();for(auto &motion:state.pc_stick_motion)motion.clear();for(auto &motion:state.pc_scope_motion)motion.clear();for(auto &motion:state.pc_boss_aim_motion)motion.clear();for(auto &motion:state.modern_scope_sensitivity)motion.clear();}
  for(std::size_t p=0;p<4;++p) {
    if(!actions[p]) {
      trace_modern_view_reset(state,p,2U);
      state.pc_stick_motion[p].clear();state.pc_scope_motion[p].clear();
      state.pc_boss_aim_motion[p].clear();state.modern_scope_sensitivity[p].clear();
    }
    if(!free_view[p]) {
      trace_modern_view_reset(state,p,3U);
      state.pc_orbits[p]={};state.pc_shoulders[p]={};
    }
    if(state.pc_input_blocked || !actions[p] || !floyd || floyd.port!=p)state.pc_floyd_look[p].clear();
  }
  if(state.modern_controls_active && !state.input_replay_loaded &&
     (state.input_record_path.empty() || state.pc_record_extended)) {
    for(std::size_t p=0;p<4;++p) {
      auto &frame=state.pc_frames[p];const auto &config=active_pc_input(state,p);
      frame.modern_flags=state.modern_live_flags[p];
      if(block_physical) {
        // Keep view identity while discarding input. The release gate below
        // still neutralizes buttons and movement until physical controls rest.
        if(modern_controls_selected(state,p) && state.controller_ports.samples[p].connected) {
          frame.modern_flags=static_cast<std::uint8_t>(jfg::kModernActionsFlag|(state.modern_live_flags[p]&jfg::kModernFreeMovementFlag));
          frame.pc_mode=state.pc_devices[p]==-3?3:5;
        }
        continue;
      }
      if(state.pc_devices[p]==-3 && config.mouse_aim && state.pc_mouse_captured) {
        frame.pc_mode=config.modern?3:1;
        jfg::PcLookDelta motion;
        if(config.modern)motion=state.pc_mouse.take_angles(config,(floyd && floyd.port==p) || (state.controller_ports.samples[p].buttons&0x10)!=0);
        else {const auto raw=state.pc_mouse.take(config);motion={raw.x,raw.y};}
        frame.look_x=static_cast<std::int16_t>(motion.x);frame.look_y=static_cast<std::int16_t>(motion.y);
      } else if(state.pc_devices[p]>=0 && config.dual_stick) {
        frame.pc_mode=config.modern?5:2;frame.look_x=static_cast<std::int16_t>(state.pc_aim[p].x);frame.look_y=static_cast<std::int16_t>(state.pc_aim[p].y);
      }
    }
  }
  if((block_physical && !state.input_replay_loaded) || replay_suspended) {
    for(auto& frame:state.pc_frames) {
      frame.look_x=frame.look_y=0;
      frame.modern_flags&=jfg::kModernActionsFlag|jfg::kModernFreeMovementFlag;
    }
    buttons=0;stick_x=stick_y=0;
    for(auto& sample:state.controller_ports.samples){sample.buttons=0;sample.x=sample.y=0;}
  }
  for(std::size_t p=0;p<4;++p) {
    const auto config=active_pc_input(state,p);
    const auto numeric=[](int v){return static_cast<std::uint16_t>(std::clamp(v,0,65535));};
    state.mouse_support_players[p]={static_cast<std::uint16_t>(p),
      static_cast<std::uint16_t>(state.pc_devices[p]==-3?1:state.pc_devices[p]>=0?2:0),
      static_cast<std::uint16_t>(modern_controls_selected(state,p)),
      static_cast<std::uint16_t>(state.controller_ports.samples[p].connected),numeric(config.mouse_aim),
      numeric(config.mouse_sensitivity),numeric(config.mouse_aim_sensitivity),numeric(config.mouse_vertical_sensitivity),
      numeric(config.mouse_invert_x),numeric(config.mouse_invert_y),static_cast<std::uint16_t>(actions[p]),
      static_cast<std::uint16_t>(free_view[p]),static_cast<std::uint16_t>(state.pc_frames[p].pc_mode)};
    if(state.pc_devices[p]==-3 && !state.input_replay_loaded && (state.pc_frames[p].look_x || state.pc_frames[p].look_y))
      state.mouse_diagnostics.increment(jfg::MouseCount::look_nonzero);
  }
  const bool pointer_probe=state.menu_pointer_replay.active() && state.input_replay_loaded && !state.play_mode;
  auto pointer=pointer_probe?state.menu_pointer_replay.sample(state.vi_retraces):state.menu_pointer_frame;
  if(pointer.left_press||pointer.right_press){pointer.x=pointer.press_x;pointer.y=pointer.press_y;}
  // v1 fixtures store logical menu coordinates; v2 stores actual client
  // pixels and exercises the same displayed-VI conversion as a live mouse.
  const bool logical_probe=pointer_probe && !state.menu_pointer_replay.pixel_coordinates();
  const auto pointer_presentation=pointer_probe?
    jfg::vi_presentation_size(state.vi_mode_horizontal_start,state.rt64_vi.vertical_start,state.rt64_vi.vertical_sync):state.window_presentation;
  const auto point=jfg::menu_pointer_point(pointer,
    logical_probe?4U:(pointer_presentation.valid()?pointer_presentation.width:4U),
    logical_probe?3U:(pointer_presentation.valid()?pointer_presentation.height:3U));
  const bool pointer_allowed=pointer_probe || (!state.input_replay_loaded && !block_physical &&
    modern_controls_selected(state,0) && state.pc_devices[0]==-3 && connected);
  const auto pointer_packet=state.menu_pointer.sample(state.guest_menu,point,pointer.moved,
    pointer.left_press,pointer.right_press,pointer_allowed,buttons!=0 || stick_x!=0 || stick_y!=0);
  if(pointer_packet.buttons || pointer_packet.target>=0 || pointer_packet.x || pointer_packet.y) {
    buttons=pointer_packet.buttons;stick_x=pointer_packet.x;stick_y=pointer_packet.y;
    if(pointer_packet.target>=0) {
      menu_kind=static_cast<std::uint8_t>(state.guest_menu.kind);
      menu_target=static_cast<std::uint8_t>(pointer_packet.target+1);
    }
    state.gameplay_trace.event("menu-pointer",{state.vi_retraces,static_cast<unsigned>(state.guest_menu.kind),
      static_cast<unsigned>(state.guest_menu.selected),buttons,menu_target});
  }
  if(menu_kind && !select_guest_menu(state,static_cast<jfg::GuestMenuKind>(menu_kind),int(menu_target)-1)) {
    // Stale/wrong-screen replay events must not activate an unrelated selection.
    menu_kind=menu_target=0;buttons=0;
  }
  // Map-driven automation may run while its tool window has focus. Settings
  // still suppress synthesized inputs below, as well as physical controller input.
  if (state.navigation_mod.enabled) {
    const bool escape = host_key_down(state, VK_ESCAPE) || (GetAsyncKeyState(VK_ESCAPE) & 0x8000) != 0;
    const bool manual = buttons != 0U || stick_x != 0 || stick_y != 0 || escape;
    // Retain manual cancellation across room resets and between map exports.
    if (manual) ++state.navigation_mod.manual_inputs;
    if (escape) state.navigation_mod.pilot.stop("manual_takeover");
    const auto ai = state.navigation_mod.pilot.sample(manual, state.input_replay_loaded, true);
    if (!manual && !state.input_replay_loaded && state.navigation_mod.pilot.active()) {
      buttons = ai.buttons; stick_x = ai.x; stick_y = ai.y;
    }
    if (state.controller_samples % 6U == 0U) {
      NativeGameMemory memory({state.rdram,kRdramSize});
      const auto dialogue=navigation_dialogue(state);
      if(dialogue.known&&dialogue.active) {
        state.navigation_mod.pilot.stop("dialogue_active");
        if(!manual&&!state.input_replay_loaded){buttons=0;stick_x=stick_y=0;}
      }
      std::ifstream request(state.navigation_output/L"ai-dialogue.txt",std::ios::binary|std::ios::ate);
      if(request&&request.tellg()<=256) {
        request.seekg(0);
        const auto now=std::chrono::duration_cast<std::chrono::milliseconds>(
          std::chrono::system_clock::now().time_since_epoch()).count();
        const int input=state.navigation_mod.dialogue_input.command(request,dialogue,manual,
          state.input_replay_loaded,game_view(memory).u32(game_data_ref("globals.currentLevel")),state.navigation_mod.generation,
          state.navigation_mod.manual_inputs,now);
        if(input!=0){buttons=input==1?kButtonA:0;stick_x=0;stick_y=input==2?60:input==3?-60:0;}
      }
    }
    if (state.controller_samples % 6U == 0U) {
      const auto path = state.navigation_output / L"ai-confirm.txt";
      std::ifstream command(path, std::ios::binary | std::ios::ate);
      if (command && command.tellg() <= 256) {
        command.seekg(0);
        NativeGameMemory memory({state.rdram, kRdramSize});
        const auto now = std::chrono::duration_cast<std::chrono::milliseconds>(
            std::chrono::system_clock::now().time_since_epoch()).count();
        if (state.navigation_mod.confirmation.command(command,
              jfg::mod::transition_confirmation(memory), manual, state.input_replay_loaded,
              game_view(memory).u32(game_data_ref("globals.currentLevel")), state.navigation_mod.generation,
              state.navigation_mod.manual_inputs, now)) {
          buttons = kButtonA; stick_x = stick_y = 0;
        }
      }
    }
  }
  if(settings_capture && !state.input_replay_loaded) {
    buttons=0;stick_x=stick_y=0;
  }

  // Record the logical gesture before consuming it. Playback reaches the same
  // confirmation path; no A/B/Start edge is delivered to the native cutscene.
  const auto recorded_buttons=buttons;
  const auto skip_scene=state.cutscene_skip_scene.load(std::memory_order_acquire);
  std::uint64_t skip_now=static_cast<std::uint64_t>(
    std::chrono::duration_cast<std::chrono::milliseconds>(
      std::chrono::steady_clock::now().time_since_epoch()).count());
  if(state.input_replay_loaded) {
    // Original-OS replay uses the hardware clock that owns SI/VI scheduling.
    // The historical cooperative profile retains its explicit nominal timebase.
    const auto replay_time=state.guest_os_probe
      ? clock_milliseconds(state.cpu_count,hardware_clocks().count_hz)
      : clock_milliseconds(state.vi_retraces,initial_tv_mode()==0U?50U:60U);
    if(!replay_time)fail_closed_dispatch(state,"replay-clock","skip-time-overflow",0U);
    skip_now=*replay_time;
  }
  const bool skip_focused=!state.pc_input_blocked && connected;
  // Observe changes only: distinguish physical actions, mapping and release/
  // focus gates without altering input or writing a trace line every frame.
  const std::array<std::uint64_t,4> skip_observation{
    skip_scene,state.cutscene_physical_actions,
    std::uint64_t(state.cutscene_mapped_buttons)|(std::uint64_t(buttons)<<16U),
    unsigned(ui_capture)|(unsigned(settings_capture)<<1U)|
      (unsigned(block_physical)<<2U)|(unsigned(state.pc_device_ready[0])<<3U)|
      (unsigned(state.modern_physical_neutral[0])<<4U)|(unsigned(connected)<<5U)|
      (std::uint64_t(static_cast<unsigned>(state.guest_menu.kind))<<8U)};
  if(skip_observation!=state.cutscene_input_observation) {
    if(skip_scene || state.cutscene_input_observation[0])
      state.gameplay_trace.event("cutscene-skip-input",{state.vi_retraces,
        skip_observation[0],skip_observation[1],skip_observation[2],skip_observation[3]});
    state.cutscene_input_observation=skip_observation;
  }
  if(state.cutscene_skip_hold.sample(skip_scene,skip_scene!=0,(buttons&0x8000U)!=0,
       skip_focused,skip_now,(buttons&0x5000U)!=0)) {
    state.cutscene_skip_request.store(skip_scene,std::memory_order_release);
    state.cutscene_skip_release=true;
    state.gameplay_trace.event("cutscene-skip-confirm",{state.vi_retraces,skip_scene});
  }
  state.cutscene_skip_gesture.store(state.cutscene_skip_hold.visible()
    ? 1U+static_cast<unsigned>(state.cutscene_skip_hold.progress(skip_now)*1000.0f) : 0U,
    std::memory_order_release);
  if((buttons&0xD000U)==0)state.cutscene_skip_release=false;
  if(skip_scene!=0 || state.cutscene_skip_release) {
    if(buttons&0xD000U)state.cutscene_skip_release=true;
    buttons&=static_cast<std::uint16_t>(~0xD000U);
  }
  state.controller_ports.samples[0]={buttons,static_cast<std::int8_t>(stick_x),static_cast<std::int8_t>(stick_y),connected};
  for(std::size_t p=0;p<4;++p) {
    if(block_physical && !state.input_replay_loaded) {
      // This flag identifies the retained Modern view, not a held action.
      // The earlier input gate already neutralized buttons, movement and look.
      // Clearing the identity here makes the shoulder scope reacquire the
      // native camera angle on focus loss.
      state.pc_frames[p].modern_flags&=jfg::kModernActionsFlag|jfg::kModernFreeMovementFlag;
      state.modern_aim_latch[p].cancel(false);
      state.modern_scope_zoom[p].reset();state.modern_scope_sensitivity[p].clear();continue;
    }
    if(!(state.pc_frames[p].modern_flags&jfg::kModernActionsFlag)) {
      state.modern_scope_zoom[p].reset();state.modern_scope_sensitivity[p].clear();continue;
    }
    const auto actor=jfg::mod::pc_player_for_port(pc_memory,static_cast<unsigned>(p));
    const auto control=pc_memory.valid(actor,0xA4U)?pc_memory.u32(actor+game_member("layout.actor.control")):0U;
    const auto character=pc_memory.valid(control,0x5C4U)?pc_memory.u8(control+game_member("layout.playerControl.characterFlags"))&3U:3U;
    const bool scoped=state.controller_ports.samples[p].connected &&
      (state.controller_ports.samples[p].buttons&0x10)!=0 &&
      jfg::mod::pc_actions_active(pc_memory,actor) && game_view(pc_memory).u8(game_data_ref("globals.pauseActive"))==0 &&
      !jfg::mod::scripted_camera_active(pc_memory,actor) &&
      character<3U && jfg::mod::pc_player_weapon(pc_memory,control)==7U;
    if(!state.input_replay_loaded) {
      auto &frame=state.pc_frames[p];const auto &config=state.modern_controls[p];
      const int sensitivity=frame.pc_mode==3?config.mouse_scope_sensitivity:config.pad_scope_sensitivity;
      const auto look=state.modern_scope_sensitivity[p].take({frame.look_x,frame.look_y},
        scoped && (jfg::modern_scope_sensitivity_active(true,pc_memory.u8(control+game_member("layout.playerControl.movement"))) ||
          jfg::pc_air_aim(true,pc_memory.u8(control+game_member("layout.playerControl.movement")),state.pc_shoulders[p].air_aim)) &&
        (frame.pc_mode==3 || frame.pc_mode==5),sensitivity,
        (std::uint64_t{actor}<<8U)|frame.pc_mode);
      frame.look_x=static_cast<std::int16_t>(look.x);frame.look_y=static_cast<std::int16_t>(look.y);
    } else state.modern_scope_sensitivity[p].clear();
    state.modern_scope_zoom[p].observe(state.pc_frames[p].modern_flags,scoped,actor);
  }
  // Even a short aim tap relinquishes free-camera orientation. Reacquire from
  // the guest aim camera when it ends, rather than snapping to a stale orbit.
  for(std::size_t p=0;p<4;++p)if(state.controller_ports.samples[p].buttons&0x10)state.pc_orbits[p]={};
  if(state.input_replay_loaded) for(std::size_t p=1;p<4;++p)state.controller_ports.samples[p]={};
  if (connected != state.latched_controller_connected) {
    if (connected)
      ++state.controller_reconnects;
    else
      ++state.controller_disconnects;
  }
  state.latched_controller_connected = connected;
  state.latched_controller_buttons = buttons;
  state.latched_controller_stick_x = static_cast<std::int8_t>(stick_x);
  state.latched_controller_stick_y = static_cast<std::int8_t>(stick_y);
  sync_pc_rumble(state);
  trace_phase9_event(state, "input-poll", state.controller_samples);
  // Record the effective packet and separate look channel, including an
  // explicitly requested replay-to-recording conversion for qualification.
  if (state.input_record.is_open()) {
    state.input_record << state.vi_retraces << ',' << state.vi_retraces + 1U
                       << ',' << (connected ? 1 : 0) << ',' << std::hex
                       << recorded_buttons << std::dec << ',' << stick_x << ','
                       << stick_y;
    if(state.pc_record_extended) {
      const auto &pc=state.pc_frames[0];
      state.input_record << ',' << int(pc.pc_mode) << ',' << pc.look_x << ',' << pc.look_y << ',' << int(pc.modern_flags) << ',' << int(menu_kind) << ',' << int(menu_target);
    }
    state.input_record << '\n';
  }
  if (state.phase95_poll_trace.is_open()) {
    hle::GuestMemory memory({state.rdram, kRdramSize},
                            hle::GuestMemory::Layout::native_word_big_endian);
    std::uint32_t level = 0U;
    std::uint32_t rng = 0U;
    (void)memory.read_u32(game_data("globals.currentLevel"), level);
    (void)memory.read_u32(game_data("diagnostic.rngState"), rng);
    state.phase95_poll_trace
        << state.controller_samples << '\t' << state.vi_retraces << '\t'
        << state.vi_frames << '\t'
        << static_cast<unsigned>(state.rdram[(game_data("globals.frontendMode")&0x1FFFFFFFU) ^ 3U]) << '\t'
        << level << '\t' << rng << '\t' << buttons << '\t'
        << stick_x << '\t' << stick_y << '\n';
  }
  ++state.controller_samples;
  state.gameplay_trace.event("input", {state.vi_retraces, state.controller_samples,
      connected ? 1U : 0U, buttons, static_cast<std::uint8_t>(stick_x),
      static_cast<std::uint8_t>(stick_y)});
  if (buttons != 0U || stick_x != 0 || stick_y != 0)
    ++state.non_neutral_controller_samples;
  if (!GetParent(static_cast<HWND>(state.native_window)) && !state.input_replay_loaded && !state.navigation_mod.enabled && host_key_down(state, VK_ESCAPE))
    state.exit_requested = true;
  state.host_key_presses.fill(false);
}


#endif
} // namespace jfg::boot::native::detail
