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
  {
    NavigationPilot terminal;terminal.camera_heading(true,0);
    auto send=[&](const std::string& command,std::int64_t now=1000) {
      std::istringstream in(command);return terminal.command(in,35,2,now);
    };
    check(send("JFGINTERACT1 35 2 1 1000 0 -50 0 0"));
    terminal.tick({0,0,0},true,35,2,1000);terminal.tick({0,0,0},true,35,2,1033);
    check(terminal.observed_input().x>0&&terminal.observed_input().x<=40&&terminal.observed_input().buttons==0);
    terminal.sample(true,false,true);check(!terminal.active());
    check(send("JFGINTERACT1 35 2 1 1000 0 -50 0 0")&&!terminal.active());
    check(!send("JFGINTERACT1 35 2 1 1000 1 -50 0 0"));
    terminal.camera_heading(true,0);
    check(send("JFGINTERACT1 35 2 2 1000 0 -50 0 0"));
    for(int i=0;i<10;i++)terminal.tick({-50,0,0},true,35,2,1000+i*33);
    check(!terminal.active()&&std::string(terminal.state)=="precision_complete");
    {
      NavigationPilot precision;precision.camera_heading(true,0);
      PilotPoint point{60,0,1};float vx=0,vz=0;bool done=false;
      for(int step=0;step<230;step++) {
        const auto now=1000+step*33;
        std::stringstream command;command<<"JFGINTERACT1 35 2 10 "<<now<<" 0 0 0 0";
        check(precision.command(command,35,2,now));precision.tick(point,true,35,2,now);
        if(!precision.active()){done=std::string(precision.state)=="precision_complete";break;}
        const auto in=precision.observed_input();
        if(point.x<20)check(in.x>=0); // Never turn away during the close approach.
        vx=vx*.9025f-in.x*.005f;vz=vz*.9025f+in.y*.005f;
        point.x+=vx;point.z+=vz;
      }
      check(done&&std::hypot(point.x,point.z)<=2);
    }
    check(send("JFGINTERACT1 35 2 3 1000 1 -50 0 0"));
    terminal.tick({-50,0,0},true,35,2,1000);terminal.tick({-50,0,0},true,35,2,1033);
    check(terminal.observed_input().buttons==0x8000);
    for(int i=2;i<10;i++)terminal.tick({-50,0,0},true,35,2,1000+i*33);
    check(!terminal.active()&&std::string(terminal.state)=="action_complete");
    check(send("JFGINTERACT1 35 2 3 1000 1 -50 0 0")&&!terminal.active());
    check(!send("JFGINTERACT1 35 2 3 1000 1 -50 0 0",2600));
    check(std::string(terminal.state)=="action_complete"); // Old file cannot overwrite a completed result.

    for(const char* bad:{"JFGINTERACT1 36 2 4 1000 0 0 0 0",
        "JFGINTERACT1 35 1 4 1000 0 0 0 0","JFGINTERACT1 35 2 4 1000 2 0 0 0",
        "JFGINTERACT1 35 2 4 -1 0 0 0 0","JFGINTERACT1 35 2 4 1001 0 0 0 0",
        "JFGINTERACT1 35 2 4 1000 0 0 0 0 extra",
        "JFGINTERACT1 35 2 4 1000 0 1e20 0 0"})check(!send(bad));
    check(send("JFGINTERACT1 35 2 4 1000 0 0 0 0"));terminal.tick({},true,36,2,1000);
    check(std::string(terminal.state)=="room_changed");
    check(send("JFGINTERACT1 35 2 5 1000 0 0 0 0"));terminal.tick({},true,35,2,2501);
    check(std::string(terminal.state)=="map_disconnected");
    check(send("JFGINTERACT1 35 2 6 1000 0 0 0 0"));terminal.tick({},false,35,2,1000);
    check(std::string(terminal.state)=="controls_suspended");
  }
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

  // Clear straight routes run; endpoints, stale/withdrawn clearance and older
  // launchers remain at walking speed. A speed refresh cannot replace a route.
  auto speed_command = [](NavigationPilot &v,int permit,std::int64_t stamp,float target=500) {
    std::stringstream c;c<<"JFGNAV2 35 2 501 "<<stamp<<" 0 1 "<<permit<<"\n0 0 "<<target<<"\n";
    return v.command(c,35,2,stamp);
  };
  auto strength = [](PilotInput i) {return std::hypot(float(i.x),float(i.y));};
  NavigationPilot fast;fast.camera_heading(true,0);check(speed_command(fast,0,1000));
  fast.tick({},true,35,2,1000);fast.tick({},true,35,2,1033);
  check(strength(fast.observed_input())>75);
  fast.tick({},true,35,2,1501);
  check(strength(fast.observed_input())<=40); // Clearance expires before movement heartbeat.
  check(speed_command(fast,0,1502));fast.tick({},true,35,2,1535);
  check(strength(fast.observed_input())>75);
  check(speed_command(fast,-1,1536));fast.tick({},true,35,2,1569);
  check(strength(fast.observed_input())<=40);
  check(!speed_command(fast,0,1570,600) && !fast.active());
  NavigationPilot approach;approach.camera_heading(true,0);check(speed_command(approach,0,1000,100));
  approach.tick({},true,35,2,1000);approach.tick({},true,35,2,1033);
  check(strength(approach.observed_input())<=40);
  NavigationPilot legacy;legacy.camera_heading(true,0);
  std::stringstream legacy_command("JFGNAV1 35 2 9 1000 0 1 0 0 500");
  check(legacy.command(legacy_command,35,2,1000));legacy.tick({},true,35,2,1000);legacy.tick({},true,35,2,1033);
  check(strength(legacy.observed_input())<=40);
  for(const char *bad:{"JFGNAV2 35 2 1 1000 0 1 1 0 0 500","JFGNAV2 35 2 1 1000 0 1 -2 0 0 500",
                      "JFGNAV2 35 2 1 1000 0 1 nope 0 0 500"}) {
    NavigationPilot invalid;std::stringstream c(bad);check(!invalid.command(c,35,2,1000));
  }
  NavigationPilot runner;PilotPoint rp{},rv{};now=1000;bool finished=false,ran=false,slowed=false;
  float deviation=0;
  for(unsigned frame=0;frame<2000;++frame) {
    now+=33;auto yaw=static_cast<std::int16_t>(int(frame)*53);runner.camera_heading(true,yaw);
    std::stringstream c;c<<"JFGNAV2 35 2 777 "<<now<<" 0 3 "<<runner.waypoint
                         <<"\n0 0 500\n500 0 500\n500 0 0\n";
    check(runner.command(c,35,2,now));runner.tick(rp,true,35,2,now);
    if(!runner.active()){finished=std::string(runner.state)=="approach_complete";break;}
    auto i=runner.observed_input();float magnitude=strength(i);ran=ran||magnitude>70;
    if(runner.waypoint==0 && rp.z>400 && magnitude<=40)slowed=true;
    float angle=float(yaw)*6.283185307179586f/65536;
    rv.x=rv.x*.9f+(-std::cos(angle)*i.x-std::sin(angle)*i.y)*.005f;
    rv.z=rv.z*.9f+(-std::sin(angle)*i.x+std::cos(angle)*i.y)*.005f;
    rp.x+=rv.x;rp.z+=rv.z;
    deviation=std::max(deviation,runner.waypoint==0?std::abs(rp.x):runner.waypoint==1?std::abs(rp.z-500):std::abs(rp.x-500));
  }
  check(finished && ran && slowed && deviation<20);

  // Dense waypoints are samples of a path, not 30 stop-and-go destinations.
  NavigationPilot continuous;PilotPoint cp{},cv{};now=1000;
  std::vector<PilotPoint> dense;
  for(int k=1;k<=10;k++)dense.push_back({0,0,float(k*40)});
  for(int k=1;k<=10;k++)dense.push_back({float(k*40),0,400});
  for(int k=1;k<=10;k++)dense.push_back({400,0,float(400-k*40)});
  double input_sum=0;unsigned moving_frames=0;float path_error=0;bool complete=false;
  for(unsigned frame=0;frame<1800;++frame) {
    now+=33;auto yaw=static_cast<std::int16_t>(int(frame)*67);continuous.camera_heading(true,yaw);
    std::stringstream c;c<<"JFGNAV3 35 2 901 "<<now<<" 0 "<<dense.size()<<" 0 "<<dense.size()-1<<"\n";
    for(auto v:dense)c<<v.x<<' '<<v.y<<' '<<v.z<<'\n';
    check(continuous.command(c,35,2,now));continuous.tick(cp,true,35,2,now);
    if(!continuous.active()){complete=std::string(continuous.state)=="approach_complete";break;}
    auto i=continuous.observed_input();input_sum+=strength(i);++moving_frames;
    auto a=float(yaw)*6.283185307179586f/65536;
    cv.x=cv.x*.9f+(-std::cos(a)*i.x-std::sin(a)*i.y)*.005f;
    cv.z=cv.z*.9f+(-std::sin(a)*i.x+std::cos(a)*i.y)*.005f;
    cp.x+=cv.x;cp.z+=cv.z;
    float err=continuous.waypoint<10?std::abs(cp.x):continuous.waypoint<20?std::abs(cp.z-400):std::abs(cp.x-400);
    path_error=std::max(path_error,err);
  }
  const auto average=input_sum/std::max(1U,moving_frames);
  std::cout<<"Continuous route: complete="<<complete<<" average_stick="<<average
           <<" frames="<<moving_frames<<" max_path_error="<<path_error<<"\n";
  check(complete && average>=70 && path_error<20 && moving_frames<450);
  for(const char *bad:{"JFGNAV3 35 2 1 1000 0 1 0 1 0 0 500",
                      "JFGNAV3 35 2 1 1000 0 1 -1 0 0 0 500",
                      "JFGNAV3 35 2 1 1000 0 1 0 -1 0 0 500"}) {
    NavigationPilot v;std::stringstream c(bad);check(!v.command(c,35,2,1000));
  }

}
