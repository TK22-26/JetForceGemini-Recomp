#pragma once
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
  std::vector<PilotPoint> route_;
  std::uint64_t nonce_ = 0, generation_ = 0;
  std::uint32_t level_ = 0;
  std::int64_t heartbeat_ = 0;
  PilotPoint last_{}, origin_{}, basis_x_{}, basis_y_{};
  bool initialized_ = false, allow_jump_ = false, active_ = false;
  unsigned frame_ = 0, phase_frame_ = 0, stalled_ = 0, stable_ = 0, flight_ = 0;
  float best_ = 1e30f;
  PilotInput input_{};
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
  bool active() const { return active_; }
  std::size_t count() const { return route_.size(); }
  void stop(const char *reason = "stopped") {
    active_ = false;
    input_ = {};
    state = reason;
  }
  void reset() {
    stop("room_changed");
    route_.clear();
    nonce_ = 0;
    initialized_ = false;
  }
  bool command(std::istream &in, std::uint32_t level, std::uint64_t generation,
               std::int64_t now) {
    std::string magic;
    std::uint32_t room;
    std::uint64_t gen, nonce;
    std::int64_t stamp;
    int jumps, count;
    if (!(in >> magic >> room >> gen >> nonce >> stamp >> jumps >> count) ||
        magic != "JFGNAV1" || room != level || gen != generation ||
        nonce == 0 || stamp < 0 || now < stamp || now - stamp > 1500 ||
        (jumps != 0 && jumps != 1) || count < 0 || count > 256) {
      if (active_)
        stop("invalid_command");
      return false;
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
    heartbeat_ = now;
    // A heartbeat may never re-arm after manual takeover or a failed run.
    if (nonce == nonce_)
      return true;
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
    state = "calibrating_forward";
    return true;
  }
  PilotInput sample(bool manual, bool replay, bool focused) {
    if (active_ && (manual || replay || !focused))
      stop(manual   ? "manual_takeover"
           : replay ? "replay_active"
                    : "focus_lost");
    return active_ ? input_ : PilotInput{};
  }
  void tick(PilotPoint p, bool gameplay, std::uint32_t level,
            std::uint64_t generation, std::int64_t now) {
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
    if (++frame_ > 1800) {
      stop("time_limit");
      return;
    }
    if (!initialized_) {
      origin_ = last_ = p;
      initialized_ = true;
      input_ = {0, 60, 0};
      return;
    }
    auto delta = difference(p, last_);
    last_ = p;
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
    }
    // Adapt the controller basis to camera rotation from measured movement.
    if (flight_ == 0 && std::hypot(delta.x, delta.z) > 0.5f &&
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
    while (waypoint < route_.size() && distance(p, route_[waypoint]) < 20 &&
           std::abs(p.y - route_[waypoint].y) < 45) {
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
    const auto dx = target.x - p.x, dz = target.z - p.z;
    auto x = (dx * basis_y_.z - dz * basis_y_.x) / det,
         y = (dz * basis_x_.x - dx * basis_x_.z) / det;
    const auto length = std::max(std::hypot(x, y), 1.0f),
               power = d < 50 ? 40.0f : 65.0f;
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
