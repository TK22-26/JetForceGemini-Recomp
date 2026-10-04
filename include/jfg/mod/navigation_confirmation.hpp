#pragma once
#include <cstdint>
#include <istream>
#include <string>

namespace jfg::mod {
// One-shot controller acknowledgement, scoped to an observed area-clear prompt.
// It never writes guest flags, advances dialogue, or starts a movement route.
class NavigationConfirmation {
  std::uint64_t last_nonce_ = 0;
public:
  std::uint64_t count = 0;
  bool command(std::istream &in, bool prompt, bool manual, bool replay,
               std::uint32_t level, std::uint64_t generation,
               std::uint64_t manual_inputs, std::int64_t now) {
    std::string magic, extra;
    std::uint32_t room;
    std::uint64_t gen, nonce, manual_at_send;
    std::int64_t stamp;
    if (!(in >> magic >> room >> gen >> nonce >> stamp >> manual_at_send) ||
        magic != "JFGCONFIRM1" || !nonce || nonce == last_nonce_ ||
        room != level || gen != generation || stamp < 0 || now < stamp ||
        now-stamp > 1500 || manual_at_send != manual_inputs || (in >> extra))
      return false;
    // Consume even a refused request so later prompt changes cannot arm it.
    last_nonce_ = nonce;
    if (!prompt || manual || replay) return false;
    ++count;
    return true;
  }
};
}
