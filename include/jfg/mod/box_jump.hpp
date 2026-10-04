#pragma once
#include <algorithm>
#include <cmath>
#include <cstdint>
#include <ostream>
#include <vector>

namespace jfg::mod {
struct JumpPoint { float x{}, y{}, z{}; };
struct JumpInput { int x{}, y{}; std::uint16_t buttons{}; };
// Opt-in, one-jump experiment. It never writes position, velocity or physics.
// A measured standing jump supplies the discrete arc; landing still requires
// observed descent, matching height/footprint and several stable updates.
class BoxJumpPilot {
  bool active_ = false, initialized_ = false, camera_ = false, airborne_ = false, descended_ = false;
  int mode_ = 0, settle_ = 0, age_ = 0, flight_ = 0, landed_ = 0;
  std::uint32_t level_ = 0;
  std::uint64_t generation_ = 0, nonce_ = 0;
  std::int64_t heartbeat_ = 0;
  float yaw_ = 0, radius_ = 0, lift_ = 0;
  int jump_button_ = 8, calibrated_button_ = 8;
  JumpPoint target_{}, origin_{}, last_{};
  JumpInput input_{};
  std::vector<float> heights_;
  void steer(float wx, float wz) {
    const float sx=-std::cos(yaw_)*wx-std::sin(yaw_)*wz;
    const float sy=-std::sin(yaw_)*wx+std::cos(yaw_)*wz;
    const float scale=80.0f/std::max(80.0f,std::hypot(sx,sy));
    input_.x=int(std::round(sx*scale));input_.y=int(std::round(sy*scale));
  }
  void fit() {
    double aa=0,ab=0,bb=0,ay=0,by=0;
    for(std::size_t i=0;i<heights_.size();++i) {
      double a=double(i+1),b=a*a,y=heights_[i];
      aa+=a*a;ab+=a*b;bb+=b*b;ay+=a*y;by+=b*y;
    }
    const double det=aa*bb-ab*ab;
    if(det<=0 || heights_.size()<8)return;
    const double v=(ay*bb-by*ab)/det,g=-2*(by*aa-ay*ab)/det;
    double sum=0;
    for(std::size_t i=0;i<heights_.size();++i) {
      const double n=double(i+1),error=heights_[i]-(v*n-.5*g*n*n);sum+=error*error;
    }
    const double rms=std::sqrt(sum/double(heights_.size()));
    if(v<=0 || v>200 || g<.01 || g>20 || rms>8 || apex<8)return;
    launch_velocity=float(v);gravity=float(g);fit_error=float(rms);calibrated=true;
  }
public:
  const char *state="off";
  bool calibrated=false;
  float launch_velocity=0,gravity=0,fit_error=0,apex=0;
  unsigned completed=0;
  bool active() const {return active_;}
  std::uint64_t nonce() const {return nonce_;}
  JumpInput input() const {return input_;}
  void camera(bool known,std::int16_t yaw) {
    camera_=known;yaw_=float(yaw)*(6.283185307179586f/65536.0f);
    if(active_&&!known)stop("jump_camera_unavailable");
  }
  void stop(const char *reason="stopped") {active_=false;input_={};state=reason;}
  void reset() {stop("room_changed");calibrated=false;nonce_=0;completed=0;}
  bool command(std::uint32_t room,std::uint64_t generation,std::uint64_t nonce,
      std::int64_t stamp,std::int64_t now,int mode,JumpPoint target,float radius,int button=8,float lift=0) {
    if((button!=8 && button!=32768) || nonce==0 || stamp<0 || now<stamp || now-stamp>1500 || mode<0 || mode>1 || !std::isfinite(lift) || lift<0 || lift>500 ||
       !std::isfinite(target.x)||!std::isfinite(target.y)||!std::isfinite(target.z) ||
       std::abs(target.x)>1000000 || std::abs(target.y)>1000000 || std::abs(target.z)>1000000 ||
       !std::isfinite(radius)||radius<8||radius>100) {stop("invalid_jump_command");return false;}
    if(nonce==nonce_) {
      if(room!=level_||generation!=generation_||mode!=mode_||target.x!=target_.x||
         target.y!=target_.y||target.z!=target_.z||radius!=radius_||button!=jump_button_||lift!=lift_) {
        stop("changed_jump_command");return false;
      }
      heartbeat_=now;return true; // Cannot rearm after manual cancellation.
    }
    if(mode>0&&(!calibrated||calibrated_button_!=button)){stop("jump_needs_calibration");return false;}
    if(!camera_){stop("jump_camera_unavailable");return false;}
    level_=room;generation_=generation;nonce_=nonce;heartbeat_=now;
    jump_button_=button;lift_=lift;mode_=mode;target_=target;radius_=radius;active_=true;initialized_=airborne_=descended_=false;
    settle_=age_=flight_=landed_=0;input_={};heights_.clear();
    if(mode==0){calibrated=false;apex=0;calibrated_button_=button;}
    state="jump_settling";return true;
  }
  void tick(JumpPoint p,bool gameplay,std::uint32_t room,std::uint64_t generation,std::int64_t now) {
    if(!active_)return;
    if(!gameplay||room!=level_||generation!=generation_){stop("jump_controls_or_room_changed");return;}
    if(!camera_){stop("jump_camera_unavailable");return;}
    if(now<heartbeat_||now-heartbeat_>1500){stop("jump_map_disconnected");return;}
    if(++age_>240){stop("jump_timeout");return;}
    if(!initialized_){last_=origin_=p;initialized_=true;return;}
    const JumpPoint delta{p.x-last_.x,p.y-last_.y,p.z-last_.z};last_=p;
    if(flight_==0) {
      input_={};
      if(std::hypot(delta.x,delta.z)<.6f && std::abs(delta.y)<.5f)++settle_;else settle_=0;
      if(settle_<8)return;
      origin_=p;
      if(mode_>0) {
        const float total_rise=target_.y-p.y;
        const float rise=total_rise;
        const float disc=launch_velocity*launch_velocity-2*gravity*rise;
        if(total_rise>apex-8 || lift_>apex-4 || rise < -160 || disc<=0){stop("jump_height_unreachable");return;}
        const float ticks=(launch_velocity+std::sqrt(disc))/gravity;
        if(std::hypot(target_.x-p.x,target_.z-p.z)>ticks*5.0f) {stop("jump_range_unreachable");return;}
      }
      flight_=1;state="jump_takeoff";input_.buttons=static_cast<std::uint16_t>(jump_button_);return;
    }
    ++flight_;
    input_.buttons=flight_<=24?static_cast<std::uint16_t>(jump_button_):0U;
    const float height=p.y-origin_.y;
    if(height>3)airborne_=true;
    if(mode_==0 && height>apex)apex=height;
    if(!airborne_ && flight_>15){stop("jump_no_takeoff");return;}

    if(delta.y<-.5f)descended_=true;

    if(airborne_) {
      state=delta.y>0?"jump_ascending":"jump_descending";
      // Fit only airborne samples; landing collision must not affect gravity.
      if(mode_==0 && height>1)heights_.push_back(height);
      if(descended_ && std::abs(delta.y)<.5f && (mode_==0 || std::hypot(delta.x,delta.z)<.25f))++landed_;else landed_=0;
      if(landed_>=6) {
        if(mode_==0) {
          // A standing calibration may not drift off its starting support.
          if(std::hypot(p.x-origin_.x,p.z-origin_.z)>8 || std::abs(height)>3){stop("jump_calibration_wrong_floor");return;}
          fit();stop(calibrated?"jump_calibrated":"jump_calibration_fit_failed");
        } else {
          if(std::hypot(p.x-target_.x,p.z-target_.z)<=radius_ && std::abs(p.y-target_.y)<=6) {
            ++completed;stop("jump_landed");
          }else stop("jump_missed_landing");
        }
        return;
      }
    }
    if(mode_>0 && airborne_) {
      if(lift_>0 && !descended_ && height<lift_) {
        input_.x=0;input_.y=0;state="jump_vertical_clearance";return;
      }

      // Predict the full neutral-input stopping position in both axes.
      // Distance-only braking can release while still turning and then
      // permanently strand the player beside the target. Re-evaluate every
      // update, including the supported touchdown, so lateral error is fixed.
      constexpr float tail=1.0f/(1.0f-.9025f);
      const float ex=target_.x-p.x-delta.x*tail;
      const float ez=target_.z-p.z-delta.z*tail;
      const float error=std::hypot(ex,ez);
      if(error<2.0f) {input_.x=0;input_.y=0;}
      else {
        const float gain=1.3f+1.2f*std::clamp((error-40.0f)/20.0f,0.0f,1.0f);
        const float strength=std::min(80.0f,8.0f+gain*error);
        steer(ex/error*strength,ez/error*strength);
      }

    } else {input_.x=0;input_.y=0;}
  }
  void write(std::ostream &out) const {
    out<<"{\"state\":\""<<state<<"\",\"active\":"<<(active_?"true":"false")
       <<",\"calibrated\":"<<(calibrated?"true":"false")<<",\"velocity\":"<<launch_velocity
       <<",\"gravity\":"<<gravity<<",\"apex\":"<<apex<<",\"fit_error\":"<<fit_error
       <<",\"button\":"<<calibrated_button_<<",\"completed\":"<<completed<<",\"nonce\":"<<nonce_<<",\"flight_update\":"<<flight_<<"}";
  }
};
} // namespace jfg::mod
