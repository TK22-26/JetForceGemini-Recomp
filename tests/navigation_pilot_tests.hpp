#pragma once
static void navigation_pilot_tests() {
  using namespace jfg::mod;
  auto start = [](NavigationPilot &pilot, int jumps = 0,
                  std::uint64_t nonce = 1, std::int64_t now = 1000) {
    std::stringstream command;
    command << "JFGNAV1 35 2 " << nonce << ' ' << now << ' ' << jumps
            << " 2\n0 0 150\n150 0 150\n";
    return pilot.command(command, 35, 2, now);
  };
  NavigationPilot pilot;
  check(!pilot.active());
  check(start(pilot));
  PilotPoint p{};
  std::int64_t now = 1000;
  for (unsigned frame = 0; frame < 500 && pilot.active(); ++frame) {
    now += 33;
    check(start(pilot, 0, 1, now));
    pilot.tick(p, true, 35, 2, now);
    auto input = pilot.sample(false, false, true);
    p.x += input.x / 30.0f;
    p.z += input.y / 30.0f;
  }
  check(!pilot.active() && std::string(pilot.state) == "approach_complete" &&
        pilot.waypoint == 2);
  check(start(pilot, 0, 1, now));
  check(!pilot.active()); // Heartbeat cannot restart completed movement.
  check(start(pilot, 0, 2, now));
  check(pilot.active());
  (void)pilot.sample(true, false, true);
  check(!pilot.active() && std::string(pilot.state) == "manual_takeover");
  check(start(pilot, 0, 2, now) && !pilot.active());
  check(start(pilot, 0, 3, now));
  pilot.tick(p, false, 35, 2, now);
  check(!pilot.active());
  check(start(pilot, 0, 4, now));
  pilot.tick(p, true, 36, 2, now);
  check(std::string(pilot.state) == "room_changed");
  check(start(pilot, 0, 5, now));
  pilot.tick(p, true, 35, 2, now + 1501);
  check(std::string(pilot.state) == "map_disconnected");
  check(start(pilot, 0, 6, now));
  (void)pilot.sample(false, true, true);
  check(!pilot.active());
  check(start(pilot, 0, 7, now));
  (void)pilot.sample(false, false, false);
  check(!pilot.active());
  for (const char *bad :
       {"JFGNAV1 35 2 8 -9223372036854775808 0 0",
        "JFGNAV1 36 2 8 1000 0 1 0 0 0", "JFGNAV1 35 2 8 1000 0 257",
        "JFGNAV1 35 2 8 1000 0 1 nan 0 0",
        "JFGNAV1 35 2 8 1000 0 1 0 0 0 junk"}) {
    std::stringstream command(bad);
    check(!pilot.command(command, 35, 2, 1000));
  }
  for (int jump = 0; jump <= 1; ++jump) {
    NavigationPilot blocked;
    check(start(blocked, jump));
    p = {};
    now = 1000;
    unsigned jumpFrames = 0;
    for (unsigned frame = 0; frame < 350 && blocked.active(); ++frame) {
      now += 33;
      check(start(blocked, jump, 1, now));
      blocked.tick(p, true, 35, 2, now);
      auto input = blocked.sample(false, false, true);
      p.x += input.x / 30.0f;
      p.z = std::min(70.0f, p.z + input.y / 30.0f);
      if (input.buttons & 0x8000U)
        ++jumpFrames;
    }
    check(!blocked.active() &&
          std::string(blocked.state) == "blocked_needs_manual");
    check(blocked.jump_attempts == unsigned(jump));
    check(jump == 0 ? jumpFrames == 0 : jumpFrames > 0 && jumpFrames <= 3);
  }
  // A supervised stop/replan in the same room can retain recent calibration.
  NavigationPilot recovery;
  check(start(recovery));p={};now=1000;
  for(unsigned frame=0;frame<30;++frame) {
    now+=33;check(start(recovery,0,1,now));recovery.tick(p,true,35,2,now);
    auto input=recovery.sample(false,false,true);p.x+=input.x/30.0f;p.z+=input.y/30.0f;
  }
  std::stringstream stopCommand;stopCommand<<"JFGNAV1 35 2 2 "<<now<<" 0 0";
  check(recovery.command(stopCommand,35,2,now));check(!recovery.active());
  now+=1000;check(start(recovery,0,3,now));recovery.tick(p,true,35,2,now);
  check(std::string(recovery.state)=="following" && recovery.sample(false,false,true).y==0);
  now+=33;recovery.tick(p,true,35,2,now);check(std::string(recovery.state)=="following");
  recovery.stop();(void)recovery.sample(true,false,true); // Manual input while stopped invalidates the cache too.
  check(start(recovery,0,4,now));recovery.tick(p,true,35,2,now);
  check(std::string(recovery.state)=="calibrating_forward");
  recovery.reset();now+=33;check(start(recovery,0,5,now));recovery.tick(p,true,35,2,now);
  check(std::string(recovery.state)=="calibrating_forward");

  // Camera rotation and coasting must not turn a right-angle route into arcs.
  NavigationPilot guided;PilotPoint position{},velocity{};now=1000;
  bool reached=false;float largest_error=0;
  for(unsigned frame=0;frame<1600;++frame) {
    now+=33;auto yaw=static_cast<std::int16_t>(-32768 + int(frame)*71);
    guided.camera_heading(true,yaw);
    std::stringstream command;command<<"JFGNAV1 35 2 99 "<<now<<" 0 3\n0 0 -200\n200 0 -200\n200 0 0\n";
    check(guided.command(command,35,2,now));guided.tick(position,true,35,2,now);
    if(!guided.active()) {reached=std::string(guided.state)=="approach_complete";break;}
    auto input=guided.sample(false,false,true);auto angle=float(yaw)*6.283185307179586f/65536;
    float wx=-std::cos(angle)*input.x-std::sin(angle)*input.y,
          wz=-std::sin(angle)*input.x+std::cos(angle)*input.y;
    velocity.x=velocity.x*.9f+wx*.005f;velocity.z=velocity.z*.9f+wz*.005f;
    position.x+=velocity.x;position.z+=velocity.z;
    float error=guided.waypoint==0?std::abs(position.x):guided.waypoint==1?std::abs(position.z+200):std::abs(position.x-200);
    largest_error=std::max(largest_error,error);
  }
  check(reached && largest_error<20);
  check(start(guided,0,100,now));guided.camera_heading(false,0);
  check(!guided.active() && std::string(guided.state)=="camera_unavailable");

}
