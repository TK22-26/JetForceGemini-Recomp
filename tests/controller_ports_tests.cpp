#include "jfg/boot/reference_si_dma.hpp"
#include "jfg/runtime/controller_ports.hpp"
#include "jfg/runtime/controller_status_query.hpp"
#include <cstdlib>
#include <iostream>
static void check(bool ok) {
  if (!ok) {
    std::cerr << "controller ports check failed\n";
    std::exit(1);
  }
}
int main() {
  jfg::ControllerInputGate gate;
  std::array<jfg::ControllerPortSample, 4> raw{};
  check(!gate.blocked(false, raw));
  raw[3] = {0x1000, 0, 0, true};
  check(gate.blocked(true, raw));
  check(gate.blocked(false,
                     raw)); // fourth player's held Start must not reach game
  raw[3] = {};
  raw[1] = {0, 0, -30, true};
  check(gate.blocked(false, raw));
  raw[1] = {};
  check(!gate.blocked(false, raw));
  raw[0] = {0x8000, 0, 0, true};
  check(!gate.blocked(false, raw)); // new press is admitted
  jfg::ControllerPorts discovered;
  auto empty=discovered.devices({false,false,false,false});
  check(empty[0]==-3 && empty[1]==-2 && empty[2]==-2 && empty[3]==-2);
  auto all=discovered.devices({true,true,true,true});
  check(all[0]==0 && all[1]==1 && all[2]==2 && all[3]==3);
  // The picker must use resolved automatic ownership, not just saved choices.
  jfg::ControllerPorts selection;
  std::array<bool,4> present{true,true,false,false};
  auto assigned=selection.devices(present);
  auto available=[&](std::size_t player,int device){return jfg::controller_device_available(player,device,selection.mappings,assigned,present);};
  check(available(0,0) && !available(1,0));
  check(available(1,1) && !available(0,1));
  check(!available(0,2) && !available(0,3));
  check(available(2,-1) && available(2,-2));
  check(!available(0,-4) && !available(0,4) && !available(4,0));
  auto selected=selection.mappings[1];selected.device=-2;selection.configure(1,selected);
  selected.device=-2;selection.configure(2,selected);selection.configure(3,selected);
  assigned=selection.devices(present);check(available(0,1));
  present[0]=false;assigned=selection.devices(present);
  check(!available(0,0) && !available(1,0));
  check(selection.mappings[0].device==-1 && assigned[0]==0);
  present[0]=true;assigned=selection.devices(present);
  check(available(0,0) && !available(1,0));
  selected.device=1;selection.configure(2,selected);assigned=selection.devices(present);
  check(!available(0,1) && available(2,1));
  selection=jfg::ControllerPorts{};present.fill(false);assigned=selection.devices(present);
  check(available(0,-3) && !available(1,-3));
  selected.device=-2;selection.configure(0,selected);assigned=selection.devices(present);
  check(available(1,-3));
  selected.device=-3;selection.configure(1,selected);assigned=selection.devices(present);
  check(!available(0,-3) && available(1,-3));
  jfg::ControllerPorts ports;
  check(ports.devices({false, false, false, false})[0] == -3);
  check(ports.devices({true, true, false, false})[0] == 0);
  auto m = ports.mappings[1];
  m.device = 1;
  ports.configure(1, m);
  auto d = ports.devices({true, true, false, false});
  check(d[0] == 0 && d[1] == 1 && d[2] == -2);
  d = ports.devices({false, true, true, false});
  check(d[0] == 0 && d[1] == 1);
  m.device = 0;
  ports.configure(1, m);
  d = ports.devices({true, true, false, false});
  check(d[0] == 1 && d[1] == 0);
  ports.configure(0, m);
  d = ports.devices({true, true, true, true});
  check(d[0] == 0 && d[1] == -2);
  for (std::size_t p = 0; p < 4; ++p) {
    m.device = static_cast<int>(p);
    ports.configure(p, m);
  }
  d = ports.devices({true, true, true, true});
  for (int p = 0; p < 4; ++p)
    check(d[static_cast<std::size_t>(p)] == p);
  ports.samples[0] = {0x8000, 80, 0, true};
  ports.samples[2] = {0x4000, 0, -80, true};
  check(ports.mask() == 5);
  jfg::boot::ReferenceSiDma si;
  std::array<jfg::ControllerPortSample, 4> samples{};
  for (std::size_t p = 0; p < 4; ++p)
    samples[p] = {static_cast<std::uint16_t>(0x8000U >> p),
                  static_cast<std::int8_t>(p * 10),
                  static_cast<std::int8_t>(-int(p) * 10), true};
  si.sample(samples);
  std::array<std::uint8_t, 128> memory{};
  std::array<std::uint8_t, 64> packet{};
  for (std::size_t p = 0; p < 4; ++p) {
    packet[p * 7] = 1;
    packet[p * 7 + 1] = 4;
    packet[p * 7 + 2] = 1;
  }
  packet[28] = 0xfe;
  packet[63] = 1;
  for (std::size_t i = 0; i < 64; ++i)
    memory[i ^ 3] = packet[i];
  check(si.write(0, 0, 0, memory));
  check(si.write(16, 0x1fc007c0, 0, memory));
  check(si.write(4, 0x1fc007c0, 0, memory));
  for (std::size_t p = 0; p < 4; ++p) {
    check(memory[(p * 7 + 3) ^ 3] ==
          static_cast<std::uint8_t>(samples[p].buttons >> 8));
    check(memory[(p * 7 + 5) ^ 3] == static_cast<std::uint8_t>(samples[p].x));
  }
  samples[1] = {};
  si.sample(samples);
  check(si.write(4, 0x1fc007c0, 0, memory));
  check((memory[(7 + 1) ^ 3] & 0x80) != 0);
  check((memory[(14 + 1) ^ 3] & 0x80) == 0);
  std::array<std::uint8_t, 64> status{};
  for (std::size_t p = 0; p < 4; ++p) {
    status[p * 6] = 1;
    status[p * 6 + 1] = 3;
  }
  status[24] = 0xfe;
  status[63] = 1;
  check(jfg::process_controller_status_query(status, 0x0d));
  check(status[4] == 0 && status[3] == 5);
  check((status[7] & 0x80) != 0);
  check(status[15] == 5 && status[21] == 5);
  std::cout << "controller ports and SI passed\\n";
}
