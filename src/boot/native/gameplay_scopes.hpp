#pragma once
#include "runtime_services.hpp"
namespace jfg::boot::native::detail {
#if defined(_WIN32) && defined(JFG_PHASE8_LIVE_RUNTIME)
class ModernAirAimPresentationScope {
  State &state_;std::uint32_t control_=0;std::uint16_t movement_=0,heading_=0;
public:
  ModernAirAimPresentationScope(State &state,std::uint32_t target,const recomp_context &context):state_(state) {
    if(target!=game_code("game.controlApplyPose") && target!=game_code("game.controlUpdateWeapon") && target!=game_code("game.controlFadePlayer") && target!=game_overlay_token("overlay.instruments.single"))return;
    NativeGameMemory ram({state.rdram,kRdramSize});
    const auto actor=target==game_code("game.controlFadePlayer")?state.pc_shoulder_actor:static_cast<std::uint32_t>(context.r4);
    const auto control=target==game_overlay_token("overlay.instruments.single")?(ram.valid(actor,0xA4U)?ram.u32(actor+game_member("layout.actor.control")):0U):
      static_cast<std::uint32_t>(target==game_code("game.controlFadePlayer")?context.r4:context.r5);
    if(!modern_air_aim_active(state,actor,control))return;
    const auto port=jfg::mod::pc_input_port(ram,ram.u8(control));control_=control;movement_=ram.u16(control+game_member("layout.playerControl.movement"));heading_=ram.u16(control+game_member("layout.playerControl.heading"));
    ram.put16(control+game_member("layout.playerControl.movement"),static_cast<std::uint16_t>(0xB00U|(movement_&0xFFU)));
    ram.put16(control+game_member("layout.playerControl.heading"),static_cast<std::uint16_t>(state.pc_shoulders[port].yaw));
    state.gameplay_trace.event("pc-air-aim-consumer",{state.vi_retraces,actor,target,static_cast<unsigned>(movement_>>8U)});
  }
  ~ModernAirAimPresentationScope() {
    if(!control_)return;
    NativeGameMemory ram({state_.rdram,kRdramSize});
    ram.put16(control_+game_member("layout.playerControl.movement"),movement_);ram.put16(control_+game_member("layout.playerControl.heading"),heading_);
  }
};
#endif

#if defined(_WIN32) && defined(JFG_PHASE8_LIVE_RUNTIME)
class ModernShoulderScope {
  State &state_;
  std::uint32_t actor_=0,control_=0,update_ticks_=0;
  std::size_t port_=0;
public:
  ModernShoulderScope(State &state,std::uint32_t target,const recomp_context &context):state_(state) {
    if(target!=game_code("game.controlPlayer"))return;
    state.pc_shoulder_actor=0;
    NativeGameMemory ram({state.rdram,kRdramSize});
    const auto actor=static_cast<std::uint32_t>(context.r4);
    const auto control=ram.valid(actor,0xA4U)?ram.u32(actor+game_member("layout.actor.control")):0U;
    if(!ram.valid(control,0x5D0U))return;
    const auto port=jfg::mod::pc_input_port(ram,ram.u8(control));
    if(port>=4)return;
    auto &view=state.pc_shoulders[port];
    const auto &frame=state.pc_frames[port];
    const auto movement=ram.u8(control+game_member("layout.playerControl.movement"));
    const bool landing_view=modern_landing_view_current(state,actor);
    const bool ledge_view=modern_ledge_view_current(state,actor);
    // A session or Modern-mode change may begin while already swimming.
    // Acquire that native view too; identity changes still go through acquire().
    const bool swimming_view=state.modern_controls[port].enabled && movement==4U &&
      jfg::mod::pc_gameplay_active(ram,actor);
    const bool view_only=landing_view || ledge_view || swimming_view;
    // Camera ownership follows the new room/player even while physical
    // input is suspended by the map or desktop. Deferring first acquisition
    // until focus returns visibly replaces the native camera at that click.
    if(!modern_controls_selected(state,port) ||
       !(frame.modern_flags&jfg::kModernActionsFlag) ||
       (frame.pc_mode!=3 && frame.pc_mode!=5) || !state.controller_ports.samples[port].connected ||
       (ram.u8(control+game_member("layout.playerControl.characterFlags"))&3U)>=3U || (!jfg::pc_shoulder_state(movement) && !ledge_view && !swimming_view) ||
       (!jfg::mod::pc_gameplay_active(ram,actor) && !landing_view) || game_view(ram).u8(game_data_ref("globals.pauseActive"))!=0 ||
       jfg::mod::scripted_camera_active(ram,actor) ||
       !ram.instruction_matches("guard.game.controlPlayer.entry0") || !ram.instruction_matches("guard.game.controlPlayer.entry4")) {
       trace_modern_view_reset(state,port,4U);view={};return;
     }
    actor_=actor;control_=control;port_=port;state.pc_shoulder_actor=actor;
    update_ticks_=static_cast<std::uint32_t>(context.r5);
    // The native landing-to-aim transition clears its pitch field. Retain
    // the airborne view when it reaches grounded aim on the following update.
    if(view.air_aim && (movement==10U || movement==11U) &&
       (game_view(ram).u32(game_data_ref("globals.controlButtons"))&0x10U)!=0 && !state.pc_input_blocked)
      ram.put16(control+game_member("layout.playerControl.manualPitch"),static_cast<std::uint16_t>(-view.pitch));
    view.air_aim=jfg::pc_air_aim((game_view(ram).u32(game_data_ref("globals.controlButtons"))&0x10U)!=0,movement,view.air_aim) && !state.pc_input_blocked;
    const bool aiming=!view_only && (movement==10U || movement==11U || view.air_aim);
    const auto camera=game_data("globals.cameraActors")+static_cast<std::uint32_t>(ram.u8(control))*0x4CU;
    const int native_pitch=aiming?-ram.s16(control+game_member("layout.playerControl.manualPitch")):
      ram.valid(camera,0x4CU)?ram.s16(camera+game_member("layout.camera.pitch")):0;
    // A new area's camera may still be looking back at its entrance. The
    // native player owns entry facing; focus loss is not a new player/view.
    if(view.acquire(actor,control,ram.s16(control+game_member("layout.playerControl.heading")),native_pitch))
      state.gameplay_trace.event("pc-shoulder-acquire",{state.vi_retraces,actor,control,
        static_cast<std::uint16_t>(view.yaw),static_cast<std::uint16_t>(view.pitch)});
    view.free_movement=(frame.modern_flags&jfg::kModernFreeMovementFlag)!=0;
    view.track_water_origin(movement);
    view.landing_recovery=landing_view;
    view.movement_before_state=movement;
    view.movement_before_yaw=ram.s16(control+game_member("layout.playerControl.heading"));
    // Capture before the native action handler eases its own velocity. The
    // optional modern easing must start here, never from the already-eased value.
    view.movement_before_update={std::bit_cast<float>(ram.u32(control+game_member("layout.playerControl.sideVelocity"))),
                                 std::bit_cast<float>(ram.u32(control+game_member("layout.playerControl.forwardVelocity")))};
    view.retrace=state.vi_retraces;view.aiming=aiming;
    if(!aiming && !state.pc_input_blocked) {
      auto look=jfg::PcLookDelta{frame.look_x,frame.look_y};
      if(frame.pc_mode==3) {
        if(state.pc_mouse_used[port])look={};
        state.pc_mouse_used[port]=true;
      } else look=state.pc_stick_motion[port].take(look,
        static_cast<float>(static_cast<std::uint32_t>(context.r5)),actor);
      const auto after=jfg::pc_direct_aim(view.yaw,view.pitch,look,-10922,10922);
      view.yaw=after.x;view.pitch=after.y;
    }
    if(view_only) {
      state.gameplay_trace.event(swimming_view?"pc-swimming-view":ledge_view?"pc-ledge-view":"pc-landing-view",{state.vi_retraces,actor,
        ram.u8(control+game_member("layout.playerControl.animationTimer")),static_cast<std::uint16_t>(view.yaw),
        static_cast<std::uint16_t>(view.pitch),game_view(ram).u32(game_data_ref("globals.controllerDisabled"))});
      return; // Camera only: no facing, velocity, action or recovery-timer writes.
    }
    // Free movement retains native turning, animation and acceleration. The
    // independent Modern camera stays acquired; Aim temporarily uses strafing.
    if(modern_free_movement_current(state,port))return;
    // The original airborne handler owns momentum heading and air steering.
    // Body/view orientation is restored after physics consumes that heading.
    if(movement==3U)ram.put16(actor,ram.u16(control+game_member("layout.playerControl.heading")));
    else {
      view.movement_before_update=jfg::pc_velocity_in_view(view.movement_before_update,
        view.movement_before_yaw,view.yaw);
      view.movement_before_yaw=view.yaw;
      ram.put16(actor,static_cast<std::uint16_t>(view.yaw));
      ram.put16(control+game_member("layout.playerControl.heading"),static_cast<std::uint16_t>(view.yaw));
      ram.put16(control+game_member("layout.playerControl.turnDelta"),0);
    }
  }
  ~ModernShoulderScope() {
    if(!actor_)return;
    NativeGameMemory ram({state_.rdram,kRdramSize});
    const auto &view=state_.pc_shoulders[port_];
    const auto camera=game_view(ram).u32(game_data_ref("globals.controlledCamera"));
    state_.gameplay_trace.event("pc-shoulder",{state_.vi_retraces,actor_,
      ram.u8(control_+game_member("layout.playerControl.movement")),static_cast<std::uint16_t>(view.yaw),
      static_cast<std::uint16_t>(view.pitch),ram.u16(actor_),ram.u16(control_+game_member("layout.playerControl.heading")),
      ram.u32(actor_+game_member("layout.actor.x")),ram.u32(actor_+game_member("layout.actor.y")),ram.u32(actor_+game_member("layout.actor.z")),
      ram.u32(control_+game_member("layout.playerControl.forwardVelocity")),ram.u32(control_+game_member("layout.playerControl.sideVelocity")),
      ram.valid(camera,0x4CU)?ram.u16(camera+game_member("layout.camera.yaw")):0U,
      ram.valid(camera,0x4CU)?ram.u16(camera+game_member("layout.camera.pitch")):0U,update_ticks_});
    state_.pc_shoulder_actor=0;
  }
};
#endif

#if defined(_WIN32) && defined(JFG_PHASE8_LIVE_RUNTIME)
class ModernAirPhysicsScope {
  State& state_;std::uint32_t actor_=0;std::size_t port_=0;
public:
  ModernAirPhysicsScope(State& state,std::uint32_t target,const recomp_context& context):state_(state) {
    if(target!=game_overlay_token("overlay.vela.update") && target!=game_overlay_token("overlay.juno.update") && target!=game_overlay_token("overlay.lupus.update"))return;
    NativeGameMemory ram({state.rdram,kRdramSize});
    const auto actor=static_cast<std::uint32_t>(context.r4),control=static_cast<std::uint32_t>(context.r5);
    if(!ram.valid(actor,0xA4U) || !ram.valid(control,0x5D0U) || ram.u32(actor+game_member("layout.actor.control"))!=control ||
       ram.u8(control+game_member("layout.playerControl.movement"))!=3U)return;
    const auto port=jfg::mod::pc_input_port(ram,ram.u8(control));
    if(modern_shoulder_current(state,port,actor) && !modern_free_movement_current(state,port) &&
       state.pc_shoulders[port].movement_before_state!=4U &&
       (!state.pc_shoulders[port].water_origin || modern_air_aim_active(state,actor,control))) {
      actor_=actor;port_=port;
    }
  }
  ~ModernAirPhysicsScope() {
    if(!actor_ || !modern_shoulder_current(state_,port_,actor_) || modern_free_movement_current(state_,port_))return;
    NativeGameMemory ram({state_.rdram,kRdramSize});
    ram.put16(actor_,static_cast<std::uint16_t>(state_.pc_shoulders[port_].yaw));
  }
};
#endif

#if defined(_WIN32) && defined(JFG_PHASE8_LIVE_RUNTIME)
class ModernAnimationScope {
  State &state_;std::uint32_t previous_;
public:
  ModernAnimationScope(State &state,std::uint32_t target,recomp_context &context):state_(state),previous_(state.pc_animation_actor) {
    if(target==game_overlay_token("overlay.vela.animation") || target==game_overlay_token("overlay.juno.animation") || target==game_overlay_token("overlay.lupus.animation"))
      state.pc_animation_actor=static_cast<std::uint32_t>(context.r4);
    if(target!=game_overlay_token("overlay.vela.control_finalize") && target!=game_overlay_token("overlay.juno.control_finalize") && target!=game_overlay_token("overlay.lupus.control_finalize"))return;
    NativeGameMemory ram({state.rdram,kRdramSize});
    const auto actor=static_cast<std::uint32_t>(context.r4),control=static_cast<std::uint32_t>(context.r5);
    if(!ram.valid(actor,0xA4U) || !ram.valid(control,0x5D0U) || ram.u32(actor+game_member("layout.actor.control"))!=control ||
       actor!=state.pc_animation_actor || !modern_shoulder_current(state,jfg::mod::pc_input_port(ram,ram.u8(control)),actor) ||
       modern_free_movement_current(state,jfg::mod::pc_input_port(ram,ram.u8(control))))return;
    const auto requested=static_cast<std::uint32_t>(context.r6);
    const unsigned character=ram.u8(control+game_member("layout.playerControl.characterFlags"))&3U;
    const auto family=modern_animation_family(state,character,requested);
    if(ram.u8(control+game_member("layout.playerControl.movement"))==0U)
      context.r6=jfg::pc_ground_animation(character,requested,family,
        {std::bit_cast<float>(ram.u32(control+game_member("layout.playerControl.sideVelocity"))),std::bit_cast<float>(ram.u32(control+game_member("layout.playerControl.forwardVelocity")))});
    state.gameplay_trace.event("pc-locomotion",{state.vi_retraces,actor,ram.u8(control+game_member("layout.playerControl.movement")),
      ram.u8(actor+game_member("layout.actor.animation")),static_cast<std::uint32_t>(context.r6),ram.u8(control+game_member("layout.playerControl.direction")),
      ram.u32(control+game_member("layout.playerControl.forwardVelocity")),ram.u32(control+game_member("layout.playerControl.sideVelocity")),ram.u16(control+game_member("layout.playerControl.turnBank")),ram.u32(actor+game_member("layout.actor.animationFrame")),requested,family});
  }
  ~ModernAnimationScope(){state_.pc_animation_actor=previous_;}
};
#endif

#if defined(_WIN32) && defined(JFG_PHASE8_LIVE_RUNTIME)
class DiagnosticWeatherScope {
  State& state_;
  const recomp_context& context_;
  std::uint32_t target_=0, address_=0;
  std::vector<std::uint8_t> before_;
  inline static thread_local unsigned post_depth_=0;
  void weather(const char* event) const {
    NativeGameMemory ram({state_.rdram,kRdramSize});
    state_.gameplay_trace.event(event,{state_.vi_retraces,target_,
      ram.u32(game_data("diagnostic.weatherState0")),ram.u32(game_data("diagnostic.weatherState1")),ram.u32(game_data("diagnostic.weatherState2")),
      ram.u32(game_data("diagnostic.weatherState3")),ram.u32(game_data("diagnostic.weatherState4")),ram.u32(game_data("diagnostic.weatherState5")),
      ram.u32((game_data("diagnostic.weatherVectors")+0xCU)),ram.u32((game_data("diagnostic.weatherVectors")+0x18U)),ram.u32((game_data("diagnostic.weatherVectors")+0x24U)),
      ram.u32(game_data("diagnostic.weatherPostState")),game_view(ram).u32(game_data_ref("globals.currentScreen"))});
  }
public:
  DiagnosticWeatherScope(State& state,std::uint32_t target,const recomp_context& context):
      state_(state),context_(context) {
    constexpr auto weather_module=jfg::game::linked::descriptor.sections[game_module(OriginalModule::starfield)];
    const bool ordinary=target==game_code("game.setupWeather") || target==game_code("game.doWeather") ||
      target==game_code("game.weatherDrawPrimary") || target==game_code("game.weatherDrawSecondary") || target==game_code("game.mainCPUeffects") ||
      target==game_code("game.rainFastDraw") || (target>=weather_module.linked_address && target-weather_module.linked_address<weather_module.text_size);
    const bool gating=post_depth_ && (target==game_code("game.fxFadeOn") || target==game_code("game.runlinkIsModuleLoaded"));
    if((!ordinary && !gating) || !state.gameplay_trace || !diagnostic_weather())return;
    target_=target;
    if(target_==game_code("game.mainCPUeffects"))++post_depth_;
    NativeGameMemory ram({state.rdram,kRdramSize});
    const auto stack=static_cast<std::uint32_t>(context.r29);
    state.gameplay_trace.event("weather-call",{state.vi_retraces,target,
      static_cast<std::uint32_t>(context.r4),static_cast<std::uint32_t>(context.r5),
      static_cast<std::uint32_t>(context.r6),static_cast<std::uint32_t>(context.r7),
      ram.valid(stack,0x20U)?ram.u32(stack+0x10U):0U,
      ram.valid(stack,0x20U)?ram.u32(stack+0x14U):0U,
      ram.valid(stack,0x20U)?ram.u32(stack+0x18U):0U,
      ram.valid(stack,0x20U)?ram.u32(stack+0x1CU):0U});
    if(target==game_code("game.setupWeather") || target==game_code("game.mainCPUeffects") || target==game_code("game.doWeather"))
      weather("weather-state");
    if(target!=game_code("game.rainFastDraw"))return;
    const auto address=static_cast<std::uint32_t>(context.r4);
    const auto width=static_cast<std::uint32_t>(context.r5);
    const auto height=static_cast<std::uint32_t>(context.r6);
    if(width==0U || height==0U || width>1024U || height>512U)return;
    const auto bytes=width*height*2U;
    if(bytes>512U*1024U || !ram.valid(address,bytes))return;
    address_=address&0x1FFFFFFFU;
    before_.assign(state.rdram+address_,state.rdram+address_+bytes);
  }
  ~DiagnosticWeatherScope() {
    if(!target_)return;
    if(!before_.empty()) {
      unsigned changed=0;
      for(std::size_t i=0;i<before_.size();i+=2U)
        changed+=before_[i]!=state_.rdram[address_+i] ||
                 before_[i+1U]!=state_.rdram[address_+i+1U];
      state_.gameplay_trace.event("rain-pixel-output",
        {state_.vi_retraces,address_,before_.size()/2U,changed});
    }
    state_.gameplay_trace.event("weather-return",{state_.vi_retraces,target_,
      static_cast<std::uint32_t>(context_.r2)});
    if(target_==game_code("game.setupWeather") || target_==game_code("game.weatherDrawPrimary"))weather("weather-after-setup");
    if(target_==game_code("game.mainCPUeffects"))--post_depth_;
  }
};
#endif

#if defined(_WIN32) && defined(JFG_PHASE8_LIVE_RUNTIME)
class DiagnosticLineOutputScope {
  State& state_; std::uint32_t address_=0;
  std::vector<std::uint8_t> before_;
public:
  DiagnosticLineOutputScope(State& state,std::uint32_t target):state_(state) {
    if(target!=game_code("game.fxOutputLines") || !state.gameplay_trace || !diagnostic_reticle_lines())return;
    NativeGameMemory ram({state.rdram,kRdramSize});
    const auto address=game_view(ram).u32(game_data_ref("globals.currentScreen"));
    if(!ram.valid(address,320U*240U*2U))return;
    address_=address&0x1FFFFFFFU;
    before_.assign(state.rdram+address_,state.rdram+address_+320U*240U*2U);
    state.gameplay_trace.event("reticle-line-queue",{state.vi_retraces,address,
        ram.u32(game_data("diagnostic.dialogueMode")),ram.u32(game_data("diagnostic.dialogueState")),ram.u32((game_data("diagnostic.dialogueState")+4U))});
  }
  ~DiagnosticLineOutputScope() {
    if(before_.empty())return;
    unsigned changed=0;
    for(std::size_t i=0;i<before_.size();i+=2U)
      changed+=before_[i]!=state_.rdram[address_+i] || before_[i+1U]!=state_.rdram[address_+i+1U];
    state_.gameplay_trace.event("reticle-line-output",{state_.vi_retraces,address_,changed});
  }
};
#endif

#if defined(_WIN32) && defined(JFG_PHASE8_LIVE_RUNTIME)
class DiagnosticReticleDrawScope {
  NativeGameMemory ram_;
  std::uint8_t *bytes_;
  std::uint32_t address_ = 0;
  std::uint8_t saved_ = 0;
public:
  DiagnosticReticleDrawScope(State &state,std::uint32_t target,const recomp_context &context):
      ram_({state.rdram,kRdramSize}), bytes_(state.rdram) {
    if (target != game_overlay_token("overlay.target.draw") || state.play_mode || !state.input_replay_loaded ||
        jfg::requested_capture_phase() < 0) return;
    static const bool enabled = [] {
      char value[2]{};
      return GetEnvironmentVariableA("JFG_DIAGNOSTIC_SHURIKEN_DRAW",value,2U)==1U && value[0]=='1';
    }();
    if (!enabled) return;
    const auto control=static_cast<std::uint32_t>(context.r4);
    const auto game=game_view(ram_).u32(game_data_ref("globals.selectedPlayer"));
    if (!ram_.valid(control,0x5C4U) || !ram_.valid(game,0x538U) || ram_.u8(control)!=0) return;
    const auto character=ram_.u8(control+game_member("layout.playerControl.characterFlags"))&3U;
    if (character>=3U) return;
    address_=game+jfg::game::records::character_array_offset+character*jfg::game::records::character_stride+0x70U;
    saved_=ram_.u8(address_);bytes_[(address_ & 0x1FFFFFFFU) ^ 3U]=9U;
    state.gameplay_trace.event("reticle-draw-fixture",{state.vi_retraces,control,address_,saved_,9U});
  }
  ~DiagnosticReticleDrawScope() { if(address_)bytes_[(address_ & 0x1FFFFFFFU) ^ 3U]=saved_; }
};
#endif

#if defined(_WIN32) && defined(JFG_PHASE8_LIVE_RUNTIME)
class ModernGuestTableScope {
  State& state_;
  State::ModernRollUpdate saved_roll_{};
  hle::GuestMemory memory_;
  bool active_=false;
public:
  ModernGuestTableScope(State &state,std::uint32_t target,std::uint32_t actor):
      state_(state),memory_({state.rdram,kRdramSize},hle::GuestMemory::Layout::native_word_big_endian) {
    if(target!=game_code("game.controlPlayer") || !state.modern_controls_active || state.pc_input_blocked)return;
    NativeGameMemory ram({state.rdram,kRdramSize});
    const auto control=ram.valid(actor,0xA4U)?ram.u32(actor+game_member("layout.actor.control")):0U;
    const auto port=modern_actor_port(state,actor);
    if(!modern_controls_selected(state,port) || !(state.pc_frames[port].modern_flags&jfg::kModernActionsFlag))return;
    if(!ram.valid(actor,0xA4U) || !ram.valid(control,0x5C4U) ||
       !jfg::mod::pc_actions_active(ram,actor) || game_view(ram).u8(game_data_ref("globals.pauseActive"))!=0 ||
       jfg::mod::scripted_camera_active(ram,actor) ||
       !ram.instruction_matches("guard.game.controlPlayer.entry0") || !ram.instruction_matches("guard.game.controlPlayer.entry4"))return;
    for(std::size_t i=0;i<9;++i)
      if(ram.u32(game_data("globals.normalControlTable")+static_cast<std::uint32_t>(i*4))!=jfg::kNormalGuestTable[i] ||
         ram.u32(game_data("globals.expertControlTable")+static_cast<std::uint32_t>(i*4))!=jfg::kExpertGuestTable[i])return;
    active_=true;
    saved_roll_=state.modern_roll_update;
    const auto& frame=state.pc_frames[port];
    state.modern_roll_update={actor,control,frame.modern_flags,frame.pc_mode,frame.connected};
    for(std::size_t i=0;i<9;++i) {
      (void)memory_.write_u32(game_data("globals.normalControlTable")+static_cast<std::uint32_t>(i*4),jfg::kModernGuestTable[i]);
      (void)memory_.write_u32(game_data("globals.expertControlTable")+static_cast<std::uint32_t>(i*4),jfg::kModernGuestTable[i]);
    }
    state.gameplay_trace.event("modern-actions",{state.vi_retraces,actor,state.pc_frames[port].modern_flags});
  }
  ~ModernGuestTableScope() {
    if(!active_)return;
    state_.modern_roll_update=saved_roll_;
    for(std::size_t i=0;i<9;++i) {
      (void)memory_.write_u32(game_data("globals.normalControlTable")+static_cast<std::uint32_t>(i*4),jfg::kNormalGuestTable[i]);
      (void)memory_.write_u32(game_data("globals.expertControlTable")+static_cast<std::uint32_t>(i*4),jfg::kExpertGuestTable[i]);
    }
  }
};
#endif

#if defined(_WIN32) && defined(JFG_PHASE8_LIVE_RUNTIME)
class ModernRollScope {
  hle::GuestMemory memory_;
  std::uint32_t saved_keys_=0;
  bool active_=false;
public:
  ModernRollScope(State& state,std::uint32_t target,const recomp_context& context):
      memory_({state.rdram,kRdramSize},hle::GuestMemory::Layout::native_word_big_endian) {
    if(target!=game_overlay_token("overlay.vela.movement") && target!=game_overlay_token("overlay.juno.movement"))return;
    const auto& update=state.modern_roll_update;
    const auto port=modern_actor_port(state,update.actor);
    if(!modern_controls_selected(state,port))return;
    const auto side=jfg::modern_roll_side_buttons(update.flags);
    if(!side || !state.rdram || !state.modern_controls_active ||
       !state.modern_controls[port].enabled || state.pc_input_blocked ||
       !update.connected || !state.controller_ports.samples[port].connected ||
       !(update.flags&jfg::kModernActionsFlag) ||
       (update.mode!=0U && update.mode!=3U && update.mode!=5U))return;
    const auto actor=static_cast<std::uint32_t>(context.r4);
    const auto control=static_cast<std::uint32_t>(context.r5);
    const auto mode=static_cast<std::uint32_t>(context.r6);
    if(!actor || actor!=update.actor || control!=update.control)return;
    NativeGameMemory ram({state.rdram,kRdramSize});
    if(!ram.valid(actor,0xA4U) || !ram.valid(control,0x5F0U) ||
       ram.u32(actor+game_member("layout.actor.control"))!=control ||
       !jfg::mod::pc_gameplay_active(ram,actor) || game_view(ram).u8(game_data_ref("globals.pauseActive"))!=0U)return;
    const auto character=ram.u8(control+game_member("layout.playerControl.characterFlags"))&3U;
    if(!jfg::modern_roll_stance(character,mode) || ram.u8(control+game_member("layout.playerControl.movement"))!=mode)return;
    const auto table=game_view(ram).u32(game_data_ref("globals.controlModeTable"));
    if(table!=game_data("globals.normalControlTable") && table!=game_data("globals.expertControlTable"))return;
    for(std::size_t i=0;i<jfg::kModernGuestTable.size();++i)
      if(ram.u32(table+static_cast<std::uint32_t>(i*4U))!=jfg::kModernGuestTable[i])return;
    saved_keys_=game_view(ram).u32(game_data_ref("globals.controlButtons"));
    active_=memory_.write_u32(game_data("globals.controlButtons"),saved_keys_|side);
  }
  ~ModernRollScope() {
    if(active_)(void)memory_.write_u32(game_data("globals.controlButtons"),saved_keys_);
  }
};
#endif

#if defined(_WIN32) && defined(JFG_PHASE8_LIVE_RUNTIME)
class ModernCrawlDirectionScope {
  State& state_;std::uint32_t actor_=0,control_=0;std::uint8_t direction_=0;unsigned port_=4;
public:
  ModernCrawlDirectionScope(State& state,std::uint32_t target,const recomp_context& context):state_(state) {
    const auto port=modern_actor_port(state,static_cast<std::uint32_t>(context.r4));
    if(!modern_controls_selected(state,port))return;
    if(target!=game_code("game.controlWalkingBack") || !state.rdram || !state.modern_controls_active ||
       !state.modern_controls[port].enabled || state.pc_input_blocked ||
       !state.controller_ports.samples[port].connected)return;
    const auto& frame=state.pc_frames[port];
    if(!frame.connected || !(frame.modern_flags&jfg::kModernActionsFlag) ||
       (frame.pc_mode!=3U && frame.pc_mode!=5U))return;
    const auto actor=static_cast<std::uint32_t>(context.r4);
    const auto control=static_cast<std::uint32_t>(context.r5);
    NativeGameMemory ram({state.rdram,kRdramSize});
    if(!ram.valid(actor,0xA4U) || !ram.valid(control,0x5F0U) ||
       ram.u32(actor+game_member("layout.actor.control"))!=control ||
       (ram.u8(control+game_member("layout.playerControl.characterFlags"))&3U)>=2U || ram.u8(control+game_member("layout.playerControl.movement"))!=2U ||
       ram.u8(control+game_member("layout.playerControl.crawlTransition"))!=0U || game_view(ram).u8(game_data_ref("globals.pauseActive"))!=0U ||
       !modern_shoulder_current(state,port,actor) || modern_free_movement_current(state,port))return;
    const auto forward=static_cast<std::int32_t>(game_view(ram).u32(game_data_ref("globals.controlStickY")));
    direction_=forward<0?1U:forward>0?0U:ram.u8(control+game_member("layout.playerControl.direction"));
    actor_=actor;control_=control;port_=port;
  }
  ~ModernCrawlDirectionScope() {
    if(!control_)return;
    NativeGameMemory ram({state_.rdram,kRdramSize});
    if(ram.u8(control_+game_member("layout.playerControl.movement"))==2U && ram.u8(control_+game_member("layout.playerControl.crawlTransition"))==0U &&
       ram.u32(actor_+game_member("layout.actor.control"))==control_ && modern_shoulder_current(state_,port_,actor_)) {
      // The fixed view replaces the native delayed turn; do not accumulate
      // its signed-short timeout while retaining backward crawl indefinitely.
      ram.put16(game_data("globals.crawlTurnTimeout"),0);
      ram.put16(control_+game_member("layout.playerControl.movement"),static_cast<std::uint16_t>(0x200U|direction_));
    }
  }
};
#endif

#if defined(_WIN32) && defined(JFG_PHASE8_LIVE_RUNTIME)
class ModernProneRollMotionScope {
  hle::GuestMemory memory_;std::uint32_t saved_x_=0,saved_y_=0;bool active_=false;
public:
  ModernProneRollMotionScope(State& state,std::uint32_t target,recomp_context& context):
      memory_({state.rdram,kRdramSize},hle::GuestMemory::Layout::native_word_big_endian) {
    const bool direction=target==game_code("game.controlWalkingBack");
    if(!direction && target!=game_code("game.controlHalfTurn"))return;
    const auto& update=state.modern_roll_update;
    const auto port=modern_actor_port(state,update.actor);
    if(!modern_controls_selected(state,port))return;
    if(!jfg::modern_roll_side_buttons(update.flags) || !state.rdram ||
       !state.modern_controls_active || !state.modern_controls[port].enabled ||
       state.pc_input_blocked || !update.connected || !state.pc_frames[port].connected ||
       !state.controller_ports.samples[port].connected ||
       !(update.flags&jfg::kModernActionsFlag) ||
       (update.mode!=0U && update.mode!=3U && update.mode!=5U))return;
    const auto actor=static_cast<std::uint32_t>(context.r4);
    const auto control=static_cast<std::uint32_t>(context.r5);
    const auto magnitude=static_cast<std::uint32_t>(context.r6);
    const auto yaw=static_cast<std::uint32_t>(context.r7);
    NativeGameMemory ram({state.rdram,kRdramSize});
    if(!actor || actor!=update.actor || control!=update.control ||
       !ram.valid(actor,0xA4U) || !ram.valid(control,0x5F0U) ||
       ram.u32(actor+game_member("layout.actor.control"))!=control ||
       (ram.u8(control+game_member("layout.playerControl.characterFlags"))&3U)>=2U || ram.u8(control+game_member("layout.playerControl.movement"))!=2U ||
       (ram.u8(control+game_member("layout.playerControl.crawlTransition"))!=3U && ram.u8(control+game_member("layout.playerControl.crawlTransition"))!=4U) ||
       !jfg::mod::pc_gameplay_active(ram,actor) || game_view(ram).u8(game_data_ref("globals.pauseActive"))!=0U ||
       !ram.valid(magnitude,4U) || (magnitude&3U) ||
       (!direction && (!ram.valid(yaw,2U) || (yaw&1U))))return;
    const auto table=game_view(ram).u32(game_data_ref("globals.controlModeTable"));
    if(table!=game_data("globals.normalControlTable") && table!=game_data("globals.expertControlTable"))return;
    for(std::size_t i=0;i<jfg::kModernGuestTable.size();++i)
      if(ram.u32(table+static_cast<std::uint32_t>(i*4U))!=jfg::kModernGuestTable[i])return;
    saved_x_=game_view(ram).u32(game_data_ref("globals.controlStickX"));saved_y_=game_view(ram).u32(game_data_ref("globals.controlStickY"));
    (void)memory_.write_u32(magnitude,0U);
    if(direction)context.r7=static_cast<std::uint64_t>(static_cast<std::int64_t>(ram.s16(control+game_member("layout.playerControl.heading"))));
    else ram.put16(yaw,ram.u16(control+game_member("layout.playerControl.heading")));
    (void)memory_.write_u32(game_data("globals.controlStickX"),0U);
    active_=memory_.write_u32(game_data("globals.controlStickY"),0U);
  }
  ~ModernProneRollMotionScope() {
    if(!active_)return;
    (void)memory_.write_u32(game_data("globals.controlStickX"),saved_x_);
    (void)memory_.write_u32(game_data("globals.controlStickY"),saved_y_);
  }
};
#endif

#if defined(_WIN32) && defined(JFG_PHASE8_LIVE_RUNTIME)
class DiagnosticHostStage {
  State& state_;const char* label_;bool enabled_,cycles_valid_=false;
  std::chrono::steady_clock::time_point start_{};std::uint64_t cycles_=0;
public:
  DiagnosticHostStage(State& state,const char* label):state_(state),label_(label),
      enabled_(state.diagnostic_host_stages && bool(state.gameplay_trace)) {
    if(!enabled_)return;
    start_=std::chrono::steady_clock::now();
#if defined(_WIN32)
    ULONG64 value=0;cycles_valid_=QueryThreadCycleTime(GetCurrentThread(),&value)!=0;cycles_=value;
#endif
  }
  ~DiagnosticHostStage() {
    if(!enabled_)return;
    const auto elapsed=std::chrono::duration_cast<std::chrono::microseconds>(
        std::chrono::steady_clock::now()-start_).count();
    if(elapsed<1000)return;
    std::uint64_t delta=0;bool valid=false;
#if defined(_WIN32)
    ULONG64 end=0;valid=cycles_valid_ && QueryThreadCycleTime(GetCurrentThread(),&end) && end>=cycles_;
    if(valid)delta=end-cycles_;
#endif
    state_.gameplay_trace.event(label_,{state_.vi_retraces,state_.controller_samples,
        static_cast<std::uint64_t>(elapsed),delta,valid?1U:0U});
  }
};
#endif

#if defined(_WIN32) && defined(JFG_PHASE8_LIVE_RUNTIME)
class SlowHostWork {
 public:
  SlowHostWork(State &state, const char *label, bool selected = true)
      : state_(state), label_(label),
        enabled_(selected && state.timing_trace.is_open()),
        start_(enabled_ ? std::chrono::steady_clock::now()
                        : std::chrono::steady_clock::time_point{}) {}
  ~SlowHostWork() {
    if (!enabled_) return;
    const auto us = std::chrono::duration_cast<std::chrono::microseconds>(
        std::chrono::steady_clock::now() - start_).count();
    if (us >= 4000)
      state_.timing_trace << label_ << '\t' << state_.vi_frames << '\t'
                          << state_.vi_retraces << '\t' << us << '\n';
  }
 private:
  State &state_;
  const char *label_;
  bool enabled_;
  std::chrono::steady_clock::time_point start_;
};
#endif

} // namespace jfg::boot::native::detail
