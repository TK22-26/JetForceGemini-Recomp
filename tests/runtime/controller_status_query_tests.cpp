#include "jfg/runtime/controller_status_query.hpp"
#include <algorithm>
#include <cassert>
#include <iostream>

int main() {
  std::array<std::uint8_t, 64> request{};
  const std::array<std::uint8_t, 8> packet{0xff, 1, 3, 0, 0xff, 0xff, 0xff, 0xff};
  for (unsigned port = 0; port < 4; ++port)
    std::copy(packet.begin(), packet.end(), request.begin() + port * 8);
  request[32] = 0xfe;
  request[63] = 1;
  auto expected = request;
  expected[4] = 5; expected[5] = 0; expected[6] = 0;
  for (unsigned port = 1; port < 4; ++port) expected[port * 8 + 2] = 0x83;
  expected[63] = 0;
  auto reply = request;
  assert(jfg::process_controller_status_query(reply));
  assert(reply == expected);
  auto mixed = request;
  mixed[11] = 1; // A later input-read command must not partially alter status.
  const auto original_mixed = mixed;
  assert(!jfg::process_controller_status_query(mixed));
  assert(mixed == original_mixed);
  auto reset = request;
  for (unsigned port = 0; port < 4; ++port) reset[port * 8 + 3] = 0xff;
  assert(jfg::process_controller_status_query(reset, 0));
  for (unsigned port = 0; port < 4; ++port) assert(reset[port * 8 + 2] == 0x83);
  auto malformed = request;
  malformed[32] = 1;
  auto before = malformed;
  assert(!jfg::process_controller_status_query(malformed));
  assert(malformed == before);
  std::cout << "controller status query checks passed\n";
}
