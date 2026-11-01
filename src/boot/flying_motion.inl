// Included after State inside the native host namespace.
// No generated code, global game clock, AI timer or animation clock is replaced.
namespace flying_motion_detail {
struct Frame {
  State* owner{};
  std::uint32_t actor{}, control{}, descriptor{}, record{}, base{};
  float elapsed{};
  bool active{}, moving{}, death_ready{};
  std::array<float,3> integrated_velocity{}, death_velocity{}, distance{};
  std::array<std::uint16_t,3> death_angles{};
  unsigned acceleration_depth{}, collision_depth{};
};
struct Execution { Frame* current{}; };
struct Tag {};
inline Execution& execution() {
  return jfg::runtime::execution_local<Execution,Tag>();
}
class Arithmetic {
  std::fenv_t saved_{};
  bool saved_ok_{};
public:
  Arithmetic():saved_ok_(std::feholdexcept(&saved_)==0) {
    if(saved_ok_)std::fesetround(FE_TONEAREST);
  }
  ~Arithmetic(){if(saved_ok_)std::fesetenv(&saved_);}
};
inline void put_float(State& state,std::uint32_t address,float value) {
  std::memcpy(state.rdram+(address&0x1FFFFFFFU),&value,sizeof(value));
}
inline std::uint32_t overlay_word(const Frame& frame,unsigned offset) {
  std::uint32_t result{};
  std::memcpy(&result,frame.owner->rdram+
      static_cast<std::uint32_t>(frame.base-kKseg0)+offset,4);
  return result;
}
inline float overlay_float(const Frame& frame,unsigned offset) {
  return std::bit_cast<float>(overlay_word(frame,offset));
}
inline std::uint16_t overlay_half(const Frame& frame,unsigned offset) {
  const auto at=static_cast<std::uint32_t>(frame.base-kKseg0)+offset;
  return static_cast<std::uint16_t>((frame.owner->rdram[at^3U]<<8U)|
      frame.owner->rdram[(at+1U)^3U]);
}
inline void resolve(Frame& frame) {
  frame.active=false;
  auto& state=*frame.owner;
  NativeGameMemory ram({state.rdram,kRdramSize});
  JfgGeneratedSectionMetadata metadata{};
  if(!section_addresses || !state.active_overlay_sections.contains(game_module(OriginalModule::collision)) ||
     !jfg_generated_section_metadata(game_module(OriginalModule::collision),&metadata) || metadata.is_overlay!=1U)return;
  frame.base=static_cast<std::uint32_t>(section_addresses[game_module(OriginalModule::collision)]);
  const auto offset=static_cast<std::uint32_t>(frame.base-kKseg0);
  const std::uint64_t extent=std::uint64_t(metadata.text_size)+metadata.data_size+metadata.bss_size;
  if(frame.base!=metadata.linked_vram || (frame.base&3U) ||
     extent<game_overlay_extent(OriginalModule::collision) || extent>0x40000U || offset>kGuestAddressSpan ||
     extent>kGuestAddressSpan-offset || !ram.valid(frame.actor,0xA4U) ||
     ram.u16(frame.actor+game_member("layout.actor.type"))!=24U ||
     overlay_word(frame,game_overlay_data("flight.actor",OriginalModule::collision))!=frame.actor)return;
  frame.control=overlay_word(frame,game_overlay_data("flight.control",OriginalModule::collision));
  frame.descriptor=overlay_word(frame,game_overlay_data("flight.descriptor",OriginalModule::collision));
  frame.record=overlay_word(frame,game_overlay_data("flight.record",OriginalModule::collision));
  if(!ram.valid(frame.control,0xACU) ||
     ram.u32(frame.actor+game_member("layout.actor.control"))!=frame.control ||
     !ram.valid(frame.descriptor,0x30U) || !ram.valid(frame.record,0x80U))return;
  frame.active=jfg::flight::supported(ram.u8(frame.record+0x2BU),
                                     ram.u8(frame.record+0x2AU));
}
} // namespace flying_motion_detail

class FlyingMotionScope {
  State& state_;
  recomp_context& context_;
  std::uint32_t target_{};
  flying_motion_detail::Frame local_{};
  flying_motion_detail::Frame* frame_{};
  flying_motion_detail::Frame* previous_{};
  float speed_{};
  std::uint16_t angle_{};
  bool relevant_{}, outer_{}, acceleration_{}, drag_{}, turn_{}, move_{}, collision_{};
public:
  FlyingMotionScope(State& state,std::uint32_t target,recomp_context& context)
      :state_(state),context_(context),target_(target) {
    using namespace flying_motion_detail;
    switch(target) {
      case game_overlay_token("overlay.collision.squaddie_control"): case game_overlay_token("overlay.collision.prepare_squaddie"): case game_overlay_token("overlay.collision.accelerate"):
      case game_overlay_token("overlay.collision.drag"): case game_overlay_token("overlay.collision.smooth_acceleration"): case game_overlay_token("overlay.collision.turn"):
      case game_overlay_token("overlay.collision.move"): case game_overlay_token("overlay.collision.update_animation"): case game_overlay_token("overlay.collision.collision_move"): case game_overlay_token("overlay.collision.death_move"):
      case game_code("game.objMoveXYZ"): relevant_=true;break;
      default:return;
    }
    auto& execution_state=execution();
    if(target==game_overlay_token("overlay.collision.squaddie_control")) {
      outer_=true;previous_=execution_state.current;
      local_.owner=&state;local_.actor=static_cast<std::uint32_t>(context.r4);
      const auto elapsed=static_cast<std::uint32_t>(context.r5);
      // Instruction-timed parity/oracle runs retain the original behavior.
      if(state.diagnostic_host_clock && state.flying_motion_adapter_enabled &&
         elapsed>0U && elapsed<=0x7FFFFFFFU)
        local_.elapsed=jfg::flight::ticks(elapsed);
      frame_=&local_;execution_state.current=frame_;
      return;
    }
    frame_=execution_state.current;
    if(!frame_ || frame_->owner!=&state || frame_->elapsed<=0.0f)return;
    if(target==game_overlay_token("overlay.collision.prepare_squaddie"))return;
    if(!frame_->active)return;
    if(overlay_word(*frame_,game_overlay_data("flight.actor",OriginalModule::collision))!=frame_->actor) {frame_=nullptr;return;}
    auto& f=*frame_;
    NativeGameMemory ram({state.rdram,kRdramSize});
    Arithmetic arithmetic;
    if(target==game_overlay_token("overlay.collision.death_move") && f.moving) {
      ++f.collision_depth;collision_=true;
    }
    if(target==game_overlay_token("overlay.collision.accelerate") || target==game_overlay_token("overlay.collision.drag")) {
      ++f.acceleration_depth;acceleration_=true;
    }
    if(target==game_overlay_token("overlay.collision.turn")) {angle_=ram.u16(f.actor);turn_=true;}
    if(target==game_overlay_token("overlay.collision.move")) {
      speed_=ram.f32(f.control+0x20U);drag_=true;
    }
    // The death initializer may apply a launch impulse. Capture after that,
    // immediately before the original per-tick drag, gravity and spin.
    if(target==game_overlay_token("overlay.collision.update_animation") && static_cast<std::uint32_t>(context.r4)==12U &&
       ram.s16(f.control+0xA6U)<=0) {
      for(unsigned i=0;i<3;++i) {
        f.death_velocity[i]=ram.f32(f.actor+0x1CU+i*4U);
        f.death_angles[i]=ram.u16(f.actor+i*2U);
      }
      f.death_ready=true;
    }
    if(target==game_overlay_token("overlay.collision.collision_move")) {
      f.moving=true;move_=true;
      for(unsigned i=0;i<3;++i)f.distance[i]=ram.f32(f.actor+0x1CU+i*4U)*f.elapsed;
      if(f.death_ready) {
        const float retention=overlay_float(f,game_overlay_data("flight.death_retention",OriginalModule::collision));
        for(unsigned i=0;i<3;++i) {
          const float before=f.death_velocity[i];
          const float after=i==1 ? before-f.elapsed : jfg::flight::damp(before,retention,f.elapsed);
          put_float(state,f.actor+0x1CU+i*4U,after);
          f.distance[i]=i==1 ? jfg::flight::accelerated_distance(before,after,f.elapsed) :
              jfg::flight::damped_distance(before,retention,f.elapsed);
          const auto spin=ram.s16(f.control+0x44U+i*2U);
          ram.put16(f.actor+i*2U,static_cast<std::uint16_t>(
              static_cast<std::int64_t>(f.death_angles[i])+std::llround(spin*static_cast<double>(f.elapsed))));
        }
      }
      for(unsigned i=0;i<3;++i)f.integrated_velocity[i]=ram.f32(f.actor+0x1CU+i*4U);
    }
    if(target==game_code("game.objMoveXYZ") && f.moving &&
       static_cast<std::uint32_t>(context.r4)==f.actor) {
      // Only displacements change units. Canonical actor velocity remains
      // available to the native collision/steering code in legacy units.
      std::array<std::uint32_t,3> args{static_cast<std::uint32_t>(context.r5),
          static_cast<std::uint32_t>(context.r6),static_cast<std::uint32_t>(context.r7)};
      if(f.collision_depth && f.elapsed!=1.0f) {
        // The contact helper applies retention after its bounce/stop decision.
        // Normalize that force at the movement boundary, preserving the
        // collision result and all original collision tests.
        const float retention=overlay_float(f,game_overlay_data("flight.collision_retention",OriginalModule::collision));
        const bool gravity=(ram.u32(f.record+0x24U)&0x400U)!=0U &&
            (ram.u32(f.control)&0x1000U)==0U;
        for(unsigned i=0;i<3;++i) {
          float velocity=std::bit_cast<float>(args[i])/retention;
          if(i==1 && gravity)velocity+=1.0f-f.elapsed;
          velocity=jfg::flight::damp(velocity,retention,f.elapsed);
          put_float(state,f.actor+0x1CU+i*4U,velocity);
          args[i]=std::bit_cast<std::uint32_t>(velocity);
        }
      }
      std::array<std::uint32_t,3> displacement{};
      for(unsigned i=0;i<3;++i) {
        const float velocity=std::bit_cast<float>(args[i]);
        // A contact can stop a falling body entirely. Never retain a residual
        // analytic fall displacement after the original collision stopped it.
        const float distance=f.collision_depth || velocity!=f.integrated_velocity[i] ?
            velocity*f.elapsed : f.distance[i];
        displacement[i]=std::bit_cast<std::uint32_t>(distance);
      }
      context.r5=static_cast<std::int32_t>(displacement[0]);
      context.r6=static_cast<std::int32_t>(displacement[1]);
      context.r7=static_cast<std::int32_t>(displacement[2]);
    }
  }
  ~FlyingMotionScope() {
    using namespace flying_motion_detail;
    if(!relevant_)return;
    if(outer_) {execution().current=previous_;return;}
    if(!frame_ || frame_->owner!=&state_ || frame_->elapsed<=0.0f)return;
    auto& f=*frame_;
    if(target_==game_overlay_token("overlay.collision.prepare_squaddie")) {resolve(f);return;}
    if(!f.active)return;
    Arithmetic arithmetic;
    NativeGameMemory ram({state_.rdram,kRdramSize});
    if(target_==game_overlay_token("overlay.collision.smooth_acceleration") && f.acceleration_depth)
      context_.f0.fl*=f.elapsed;
    if(turn_)ram.put16(f.actor,jfg::flight::approach_angle(angle_,
        overlay_half(f,game_overlay_data("flight.turn_target",OriginalModule::collision)),f.elapsed));
    if(drag_) {
      const float original=ram.f32(f.control+0x20U);
      const bool apply=ram.f32(f.record+0x10U)>0.0f || overlay_float(f,game_overlay_data("flight.speed",OriginalModule::collision))>20.0f;
      float corrected=apply ? jfg::flight::damp(speed_,overlay_float(f,game_overlay_data("flight.drag_retention",OriginalModule::collision)),f.elapsed) : speed_;
      const float maximum=static_cast<float>(static_cast<std::int8_t>(ram.u8(f.descriptor+0x24U)));
      const float minimum=static_cast<float>(static_cast<std::int8_t>(ram.u8(f.descriptor+0x25U)));
      corrected=std::max(minimum,std::min(maximum,corrected));
      put_float(state_,f.control+0x20U,corrected);
      if(original!=0.0f)for(unsigned offset:{0x1CU,0x24U})
        put_float(state_,f.actor+offset,ram.f32(f.actor+offset)*(corrected/original));
    }
    if(acceleration_)--f.acceleration_depth;
    if(collision_)--f.collision_depth;
    if(move_) {
      f.moving=false;
      state_.gameplay_trace.event("flight-time-step",{state_.vi_retraces,f.actor,
          std::bit_cast<std::uint32_t>(f.elapsed),f.death_ready,
          std::bit_cast<std::uint32_t>(f.distance[0]),
          std::bit_cast<std::uint32_t>(f.distance[1]),
          std::bit_cast<std::uint32_t>(f.distance[2])});
      f.death_ready=false;
    }
  }
};
