#pragma once
#include "jfg/mod/box_jump.hpp"
#include <algorithm>
#include <cmath>
#include <cstdint>
#include <istream>
#include <string>
#include <vector>

namespace jfg::mod {
struct PilotPoint {
  float x{}, y{}, z{};
};
struct PilotInput {
  int x{}, y{};
  std::uint16_t buttons{};
};
// Experimental feedback controller. All commands are scoped to one loaded room.
// Jump assist is a single bounded recovery attempt, not a ballistic route
// solver.
class NavigationPilot {
  BoxJumpPilot box_jump_;
  bool box_mode_ = false;
  int interaction_mode_ = -1;
  std::vector<PilotPoint> route_;
  std::uint64_t nonce_ = 0, generation_ = 0;
  std::uint32_t level_ = 0;
  std::int64_t heartbeat_ = 0;
  PilotPoint last_{}, origin_{}, basis_x_{}, basis_y_{};
  bool initialized_ = false, allow_jump_ = false, active_ = false;
  bool basis_valid_ = false, reuse_basis_ = false;
  bool camera_known_ = false, corner_braking_ = false, endpoint_braking_ = false;
  PilotPoint velocity_{};
  std::int64_t basis_time_ = 0;
  unsigned frame_ = 0, phase_frame_ = 0, stalled_ = 0, stable_ = 0, flight_ = 0;
  float best_ = 1e30f;
  PilotInput input_{};
  int running_waypoint_ = -1, running_through_ = -1;
  bool continuous_ = false;
  std::int64_t running_stamp_ = 0;
  static float distance(PilotPoint a, PilotPoint b) {
    return std::hypot(a.x - b.x, a.z - b.z);
  }
  static PilotPoint difference(PilotPoint a, PilotPoint b) {
    return {a.x - b.x, a.y - b.y, a.z - b.z};
  }

public:
  const char *state = "off";
  unsigned waypoint = 0, jump_attempts = 0;
  std::uint64_t nonce() const { return nonce_; }
  bool active() const { return active_ || box_jump_.active(); }
  PilotInput observed_input() const { if(box_mode_){const auto i=box_jump_.input();return {i.x,i.y,i.buttons};}return input_; }
  void write_box_jump(std::ostream &out) const {box_jump_.write(out);}
  std::size_t count() const { return route_.size(); }
  void stop(const char *reason = "stopped") {
    box_jump_.stop(reason);
    active_ = false;
    input_ = {};
    state = reason;
    if (std::string(reason) != "stopped" && std::string(reason) != "approach_complete")
      basis_valid_ = false;
  }
  // The live game supplies a validated control-camera heading each update.
  // This avoids interpreting turn inertia as a change in camera orientation.
  void camera_heading(bool known, std::int16_t yaw) {
    box_jump_.camera(known,yaw);
    if (!known && camera_known_ && active_) stop("camera_unavailable");
    camera_known_ = known;
    if (!known) return;
    const auto angle = float(yaw) * (6.283185307179586f / 65536.0f);
    basis_x_ = {-std::cos(angle), 0, -std::sin(angle)};
    basis_y_ = {-std::sin(angle), 0, std::cos(angle)};
    basis_valid_ = true;
  }
  void reset() {
    stop("room_changed");
    box_jump_.reset();box_mode_=false;interaction_mode_=-1;
    route_.clear();
    nonce_ = 0;
    initialized_ = false;
    camera_known_ = false;
  }
  bool command(std::istream &in, std::uint32_t level, std::uint64_t generation,
               std::int64_t now) {
    std::string magic;
    std::uint32_t room;
    std::uint64_t gen, nonce;
    std::int64_t stamp;
    int jumps, count, running = -1, through = -1;
    if (!(in >> magic)) {stop("invalid_command");return false;}
    // Bounded terminal movement or one A press. Collision planning remains
    // in the map client; no position, animation or inventory writes occur.
    if(magic=="JFGINTERACT1") {
      PilotPoint p;int mode;std::string extra;
      if(!(in>>room>>gen>>nonce>>stamp>>mode>>p.x>>p.y>>p.z) ||
          room!=level || gen!=generation || nonce==0 || stamp<0 || now<stamp || now-stamp>1500 ||
          (mode!=0&&mode!=1) || !std::isfinite(p.x)||!std::isfinite(p.y)||!std::isfinite(p.z)||
          std::abs(p.x)>1000000||std::abs(p.y)>1000000||std::abs(p.z)>1000000||(in>>extra)) {
        if(active())stop("invalid_interaction");return false;
      }
      if(nonce==nonce_) {
        if(interaction_mode_!=mode||route_.size()!=1||route_[0].x!=p.x||route_[0].y!=p.y||route_[0].z!=p.z) {
          stop("invalid_interaction");return false;
        }
        heartbeat_=now;return true; // A heartbeat cannot rearm a finished/cancelled command.
      }
      box_jump_.stop();box_mode_=false;interaction_mode_=mode;
      nonce_=nonce;level_=room;generation_=gen;heartbeat_=now;
      route_={p};initialized_=false;frame_=stable_=0;input_={};active_=true;
      state=mode==0?"precision_approach":"interaction_press";return true;
    }
    if(magic=="JFGJUMP1" || magic=="JFGJUMP2") {
      JumpPoint p;float radius=0,lift=0;int mode=0,button=8;std::string extra;
      if(!(in>>room>>gen>>nonce>>stamp>>mode>>p.x>>p.y>>p.z>>radius>>button) ||
          (magic=="JFGJUMP2" && !(in>>lift)) || room!=level || gen!=generation || (in>>extra)) {stop("invalid_jump_command");return false;}
      const bool accepted=box_jump_.command(room,gen,nonce,stamp,now,mode,p,radius,button,lift);
      if(accepted){interaction_mode_=-1;active_=false;box_mode_=true;nonce_=nonce;state=box_jump_.state;}
      return accepted;
    }
    if (!(in >> room >> gen >> nonce >> stamp >> jumps >> count) ||
        (magic != "JFGNAV1" && magic != "JFGNAV2" && magic != "JFGNAV3") || room != level || gen != generation ||
        nonce == 0 || stamp < 0 || now < stamp || now - stamp > 1500 ||
        (jumps != 0 && jumps != 1) || count < 0 || count > 256) {
      if (active_)
        stop("invalid_command");
      return false;
    }
    if (magic != "JFGNAV1") {
      if (!(in >> running)) { if(active_)stop("invalid_command");return false; }
      through=running;
      if (magic=="JFGNAV3" && !(in >> through)) { if(active_)stop("invalid_command");return false; }
      if(running < -1 || through < running || through >= count || (running==-1 && through!=-1)) {
        if(active_)stop("invalid_command");return false;
      }
    }
    std::vector<PilotPoint> points;
    for (int i = 0; i < count; ++i) {
      PilotPoint p;
      if (!(in >> p.x >> p.y >> p.z) || !std::isfinite(p.x) ||
          !std::isfinite(p.y) || !std::isfinite(p.z) ||
          std::abs(p.x) > 1000000 || std::abs(p.y) > 1000000 ||
          std::abs(p.z) > 1000000) {
        if (active_)
          stop("invalid_route");
        return false;
      }
      points.push_back(p);
    }
    std::string extra;
    if (in >> extra) {
      if (active_)
        stop("invalid_route");
      return false;
    }
    if (count == 0) {
      nonce_ = nonce;
      stop();
      return true;
    }
    box_jump_.stop();box_mode_=false;interaction_mode_=-1;
    heartbeat_ = now;
    // A heartbeat may never re-arm after manual takeover or a failed run.
    if (nonce == nonce_) {
      // A clearance heartbeat can change speed permission, never the route.
      if (points.size() != route_.size()) { stop("invalid_route"); return false; }
      for (std::size_t i=0;i<points.size();++i)
        if (points[i].x != route_[i].x || points[i].y != route_[i].y || points[i].z != route_[i].z) {
          stop("invalid_route"); return false;
        }
      running_waypoint_ = running; running_through_ = through; running_stamp_ = stamp;continuous_=magic=="JFGNAV3";
      return true;
    }
    running_waypoint_ = running; running_through_ = through; running_stamp_ = stamp;continuous_=magic=="JFGNAV3";
    reuse_basis_ = camera_known_ || (basis_valid_ && room == level_ && gen == generation_ &&
                   now >= basis_time_ && now - basis_time_ <= 8000);
    nonce_ = nonce;
    level_ = room;
    generation_ = gen;
    route_ = std::move(points);
    allow_jump_ = jumps != 0;
    active_ = true;
    initialized_ = false;
    frame_ = phase_frame_ = stalled_ = stable_ = flight_ = 0;
    waypoint = jump_attempts = 0;
    best_ = 1e30f;
    input_ = {};
    velocity_ = {};
    corner_braking_ = false;endpoint_braking_=false;
    state = reuse_basis_ ? "following" : "calibrating_forward";
    return true;
  }
  PilotInput sample(bool manual, bool replay, bool focused) {
    if (manual || replay || !focused) basis_valid_ = false;
    if (active() && (manual || replay || !focused))
      stop(manual   ? "manual_takeover"
           : replay ? "replay_active"
                    : "focus_lost");
    return active() ? observed_input() : PilotInput{};
  }
  void tick(PilotPoint p, bool gameplay, std::uint32_t level,
            std::uint64_t generation, std::int64_t now) {
    if(box_mode_) {
      box_jump_.tick({p.x,p.y,p.z},gameplay,level,generation,now);
      state=box_jump_.state;return;
    }
    if (!active_)
      return;
    if (!gameplay) {
      stop("controls_suspended");
      return;
    }
    if (level != level_ || generation != generation_) {
      stop("room_changed");
      return;
    }
    if (now < heartbeat_ || now - heartbeat_ > 1500) {
      stop("map_disconnected");
      return;
    }
    if(interaction_mode_>=0) {
      if(!camera_known_){stop("camera_unavailable");return;}
      if(++frame_>240){stop("interaction_timeout");return;}
      if(!initialized_){initialized_=true;last_=origin_=p;input_={};return;}
      if(interaction_mode_==1) {
        if(frame_>6){stop("action_complete");return;}
        input_={0,0,0x8000};return;
      }
      const auto delta=difference(p,last_);last_=p;
      const auto goal=route_.front();
      // The launcher verifies floor/body clearance for the terminal segment.
      // Follow its small floor rise instead of requiring the entire approach
      // to start at the destination height. Drops away from that segment stop.
      const auto line=difference(goal,origin_);
      const auto horizontal2=line.x*line.x+line.z*line.z;
      const auto along=horizontal2>1 ? std::clamp(
          ((p.x-origin_.x)*line.x+(p.z-origin_.z)*line.z)/horizontal2,0.0f,1.0f) : 1.0f;
      const auto floor_height=origin_.y+line.y*along;
      if(horizontal2>180*180 || std::abs(line.y)>24 ||
         std::abs(p.y-floor_height)>6) {stop("interaction_height_changed");return;}
      // A close approach can settle slightly beside the centerline while
      // preserving facing. Three units remain inside the launcher's five-unit
      // activation margin; the client still checks the actual trigger and yaw.
      if(distance(p,goal)<=3.0f && std::hypot(delta.x,delta.z)<.2f)++stable_;else stable_=0;
      if(stable_>=6){stop("precision_complete");return;}
      float ex=goal.x-p.x-delta.x*(1.0f/(1.0f-.9025f));
      float ez=goal.z-p.z-delta.z*(1.0f/(1.0f-.9025f));
      const float length=distance(origin_,goal);
      // The final chest approach must preserve facing. Reverse corrections
      // can stop precisely but turn the player away from the A-button trigger.
      // Settle under neutral drag when braking would demand backward input.
      if(length>1 && distance(p,goal)<20) {
        const float ux=(goal.x-origin_.x)/length,uz=(goal.z-origin_.z)/length;
        const float forward=std::max(0.0f,ex*ux+ez*uz);
        ex=ux*forward;ez=uz*forward;
      }
      const float error=std::hypot(ex,ez);
      input_={};
      if(error>1.0f) {
        const float power=std::min(40.0f,8.0f+1.3f*error);
        input_.x=int(std::round((ex*basis_x_.x+ez*basis_x_.z)/error*power));
        input_.y=int(std::round((ex*basis_y_.x+ez*basis_y_.z)/error*power));
      }
      return;
    }
    if (++frame_ > 3600) {
      stop("time_limit");
      return;
    }
    if (!initialized_) {
      origin_ = last_ = p;
      initialized_ = true;
      if (reuse_basis_ && basis_valid_) {
        frame_ = 19;
        state = "following";
        input_ = {};
        return;
      }
      input_ = {0, 60, 0};
      return;
    }
    auto delta = difference(p, last_);
    last_ = p;
    velocity_.x = (velocity_.x + delta.x) * .5f;
    velocity_.z = (velocity_.z + delta.z) * .5f;
    stable_ = std::abs(delta.y) < 0.75f ? stable_ + 1 : 0;
    if (frame_ <= 9) {
      input_ = {0, 60, 0};
      return;
    }
    if (frame_ == 10) {
      basis_y_ = difference(p, origin_);
      const auto length = distance(p, origin_);
      if (length < 4) {
        stop("calibration_blocked");
        return;
      }
      basis_y_.x /= length;
      basis_y_.z /= length;
      origin_ = p;
      state = "calibrating_right";
    }
    if (frame_ <= 18) {
      input_ = {60, 0, 0};
      return;
    }
    if (frame_ == 19) {
      basis_x_ = difference(p, origin_);
      const auto length = distance(p, origin_);
      if (length < 4) {
        stop("calibration_blocked");
        return;
      }
      basis_x_.x /= length;
      basis_x_.z /= length;
      if (std::abs(basis_x_.x * basis_y_.z - basis_x_.z * basis_y_.x) < 0.4f) {
        stop("calibration_uncertain");
        return;
      }
      state = "following";
      basis_valid_ = true;
    }
    if (basis_valid_) basis_time_ = now;
    // Adapt the controller basis to camera rotation from measured movement.
    if (!camera_known_ && flight_ == 0 && std::hypot(delta.x, delta.z) > 0.5f &&
        (input_.x != 0 || input_.y != 0)) {
      const auto x = basis_x_.x * input_.x + basis_y_.x * input_.y;
      const auto z = basis_x_.z * input_.x + basis_y_.z * input_.y;
      const auto angle = std::clamp(
          std::atan2(x * delta.z - z * delta.x, x * delta.x + z * delta.z),
          -0.06f, 0.06f);
      auto rotate = [&](PilotPoint &v) {
        auto old = v;
        v.x = old.x * std::cos(angle) - old.z * std::sin(angle);
        v.z = old.x * std::sin(angle) + old.z * std::cos(angle);
      };
      rotate(basis_x_);
      rotate(basis_y_);
    }
    if (corner_braking_) {
      input_ = {};
      if (std::hypot(velocity_.x, velocity_.z) > .7f) return;
      corner_braking_ = false;
      ++waypoint;best_ = 1e30f;stalled_ = 0;state = "following";
    }
    const auto permitted = [&] {
      return camera_known_ && int(waypoint)>=running_waypoint_ && running_waypoint_>=0 &&
          int(waypoint)<=running_through_ && now>=running_stamp_ && now-running_stamp_<=500;
    };
    if(camera_known_ && waypoint+1==route_.size()) {
      const float remain=distance(p,route_[waypoint]),speed=std::hypot(velocity_.x,velocity_.z);
      const auto to=difference(route_[waypoint],p);
      const float alignment=speed>.1f?(to.x*velocity_.x+to.z*velocity_.z)/std::max(.01f,remain*speed):1;
      if(!endpoint_braking_ && speed>.25f &&
         (remain<8 || (alignment>.85f && remain<=speed*10.3f+3)))endpoint_braking_=true;
      if(endpoint_braking_) {
        input_={};state="approach_braking";
        if(speed>.2f)return;
        endpoint_braking_=false;best_=1e30f;stalled_=0;
        if(remain<8 && std::abs(p.y-route_[waypoint].y)<45){stop("approach_complete");return;}
      }
    }
    const auto reached = [&] {
      if(waypoint>=route_.size() || std::abs(p.y-route_[waypoint].y)>=45)return false;
      if(distance(p,route_[waypoint]) < (continuous_ && waypoint+1<route_.size()?16:8))return true;
      // Crossing an intermediate waypoint plane counts as progress if still
      // close to the path; do not turn back to chase a point already passed.
      if(!continuous_ || waypoint+1>=route_.size() || distance(p,route_[waypoint])>64)return false;
      auto a=waypoint?route_[waypoint-1]:origin_,b=route_[waypoint],v=difference(b,a);
      auto length=std::hypot(v.x,v.z);
      auto ahead=(p.x-b.x)*v.x+(p.z-b.z)*v.z;
      auto lateral=std::abs((p.x-a.x)*v.z-(p.z-a.z)*v.x)/std::max(1.0f,length);
      return ahead>=0 && lateral<16;
    };
    while (reached()) {
      if (camera_known_ && waypoint + 1 < route_.size()) {
        auto before = difference(route_[waypoint], waypoint ? route_[waypoint-1] : origin_);
        auto after = difference(route_[waypoint+1], route_[waypoint]);
        const auto alignment = (before.x*after.x + before.z*after.z) /
            std::max(.001f, std::hypot(before.x,before.z)*std::hypot(after.x,after.z));
        if (alignment < (continuous_ && permitted() ? -.25f : .8f) && std::hypot(velocity_.x,velocity_.z) > .7f) {
          corner_braking_ = true;input_ = {};state = "corner_braking";return;
        }
      }
      ++waypoint;
      best_ = 1e30f;
      stalled_ = 0;
    }
    if (waypoint == route_.size()) {
      stop("approach_complete");
      return;
    }
    const auto target = route_[waypoint];
    const auto d = distance(p, target);
    if (d > 1000 || std::abs(target.y - p.y) > 200) {
      stop("route_deviation");
      return;
    }
    if (d < best_ - 1) {
      best_ = d;
      stalled_ = 0;
    } else
      ++stalled_;
    const auto det = basis_x_.x * basis_y_.z - basis_x_.z * basis_y_.x;
    auto dx = target.x - p.x - (camera_known_ ? velocity_.x * 8 : 0),
               dz = target.z - p.z - (camera_known_ ? velocity_.z * 8 : 0);
    auto x = (dx * basis_y_.z - dz * basis_y_.x) / det,
         y = (dz * basis_x_.x - dx * basis_x_.z) / det;
    // Running requires a fresh wider-corridor check for this exact segment.
    // Brake early for every waypoint, including doors/endpoints, and walk while
    // correcting lateral drift or changing direction. Missing hints stay slow.
    const auto speed = std::hypot(velocity_.x, velocity_.z);
    const auto segment_start = waypoint ? route_[waypoint-1] : origin_;
    const auto segment = difference(target, segment_start);
    const auto cross_track = std::abs(segment.x*(p.z-segment_start.z) -
                                     segment.z*(p.x-segment_start.x)) /
                             std::max(1.0f,std::hypot(segment.x,segment.z));
    const auto alignment = speed < .5f ? 1.0f :
        ((target.x-p.x)*velocity_.x + (target.z-p.z)*velocity_.z) / std::max(1.0f,d*speed);
    const bool may_run = camera_known_ && running_waypoint_ == int(waypoint) &&
        now >= running_stamp_ && now-running_stamp_ <= 500 && flight_ == 0 &&
        std::abs(delta.y) < 1 && std::abs(target.y-p.y) < 24 &&
        cross_track < 12 && alignment > .94f;
    const auto braking_distance = std::max(120.0f,speed*18.0f);
    const auto run_blend = may_run ? std::clamp((d-braking_distance)/140.0f,0.0f,1.0f) : 0.0f;
    const auto speed_cap = 40.0f + 40.0f*run_blend;
    auto length = std::max(std::hypot(x, y), 1.0f),
               power = camera_known_ ? (std::hypot(dx,dz) < 4 ? 0.0f :
                   std::clamp(18.0f + std::hypot(dx,dz)*.22f,18.0f,speed_cap)) :
                   d < 18 ? 24.0f : d < 80 ? 32.0f : 50.0f;

    if(continuous_) {
      bool running=permitted() && flight_==0 && cross_track<32 && std::abs(delta.y)<4;
      const auto brake=std::max(32.0f,speed*8.0f);
      PilotPoint aim=target;
      bool end_or_hairpin=waypoint+1==route_.size();
      if(!end_or_hairpin) {
        auto next=difference(route_[waypoint+1],target);
        const auto bend=(segment.x*next.x+segment.z*next.z) /
            std::max(1.0f,std::hypot(segment.x,segment.z)*std::hypot(next.x,next.z));
        end_or_hairpin=bend<-.25f;
        // Bounded lookahead rounds ordinary turns without taking a large
        // diagonal shortcut. Wider route clearance is checked by the launcher.
        if(!end_or_hairpin && int(waypoint+1)<=running_through_ && d<24) {
          const auto fraction=std::min(1.0f,(24-d)/std::max(1.0f,std::hypot(next.x,next.z)));
          aim={target.x+next.x*fraction,target.y+next.y*fraction,target.z+next.z*fraction};
        }
      }
      if(end_or_hairpin && d<brake)running=false;
      dx=aim.x-p.x;dz=aim.z-p.z;
      if(running) {
        // Counter lateral momentum while preserving forward velocity.
        const auto aim_length=std::max(1.0f,std::hypot(dx,dz));
        const auto along=std::max(0.0f,(velocity_.x*dx+velocity_.z*dz)/aim_length);
        const auto ux=dx/aim_length,uz=dz/aim_length;
        dx-=(velocity_.x-along*ux)*8;
        dz-=(velocity_.z-along*uz)*8;
        power=80;
      } else {
        dx-=velocity_.x*8;dz-=velocity_.z*8;
        power=std::hypot(dx,dz)<4?0.0f:std::clamp(18.0f+std::hypot(dx,dz)*.22f,18.0f,40.0f);
      }
      x=(dx*basis_y_.z-dz*basis_y_.x)/det;
      y=(dz*basis_x_.x-dx*basis_x_.z)/det;
      length=std::max(std::hypot(x,y),1.0f);
    }
    input_ = {int(std::clamp(x / length * power, -80.0f, 80.0f)),
              int(std::clamp(y / length * power, -80.0f, 80.0f)), 0};
    if (flight_ != 0) {
      ++flight_;
      input_.buttons = flight_ <= 3 ? 0x8000U : 0;
      if (flight_ > 90) {
        stop("jump_timeout");
        return;
      }
      if (flight_ > 15 && stable_ >= 5) {
        flight_ = 0;
        state = "following";
        stalled_ = 0;
        best_ = d;
      }
    } else if (stalled_ >= 50) {
      if (allow_jump_ && jump_attempts == 0 && stable_ >= 5) {
        ++jump_attempts;
        flight_ = 1;
        input_.buttons = 0x8000U;
        state = "jump_assist";
      } else
        stop("blocked_needs_manual");
    }
  }
};
} // namespace jfg::mod
