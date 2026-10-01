#include "jfg/boot/reference_event_commit.hpp"
#include <array>
#include <cstdlib>
#include <fstream>
#include <sstream>
#include <string>
#include <vector>
int main(int argc, char** argv) {
  using namespace jfg::boot;
  auto check = [](bool ok) { if (!ok) std::abort(); };
  const std::array jobs{ReferenceEventCandidate{ReferenceEvent::dp, 1000},
      ReferenceEventCandidate{ReferenceEvent::vi, 1002}, ReferenceEventCandidate{ReferenceEvent::sp, 1000}};
  check(!select_reference_event(jobs, 999).source);
  const auto first = select_reference_event(jobs, 1006);
  check(first.qualified && first.source == ReferenceEvent::sp);
  const auto second = select_reference_event(std::span(jobs).first(2), 1006);
  check(second.qualified && second.source == ReferenceEvent::dp);
  const std::array tied{ReferenceEventCandidate{ReferenceEvent::pi, 1000},
      ReferenceEventCandidate{ReferenceEvent::vi, 1000}};
  check(!select_reference_event(tied, 1006).qualified);
  const std::array earlier{ReferenceEventCandidate{ReferenceEvent::pi, 1000},
      ReferenceEventCandidate{ReferenceEvent::vi, 1000}, ReferenceEventCandidate{ReferenceEvent::si, 998}};
  check(select_reference_event(earlier, 1006).qualified &&
      select_reference_event(earlier, 1006).source == ReferenceEvent::si);
  // Optional independently captured CPU branch-boundary observations, not a
  // fitted delay. SP and DP have the same deadline; each commit takes one.
  if (argc == 2) {
    std::ifstream input(argv[1]);
    std::string line;
    check(static_cast<bool>(std::getline(input, line)));
    if (!line.empty() && line.back() == '\r') line.pop_back();
    check(line == "case\tpc\tcount\tmi_pending\tsp_status");
    unsigned current = 0, commits = 0;
    std::uint32_t status = 64, pending = 8;
    std::vector<ReferenceEventCandidate> events;
    while (std::getline(input, line)) {
      std::istringstream row(line);
      unsigned job; std::uint32_t pc, mi, sp; std::uint64_t count;
      check(static_cast<bool>(row >> job >> pc >> count >> mi >> sp));
      if (job != current) {
        check(job == current + 1 && job <= 16 && events.empty() && pc == 0x800991ecU);
        current = job; status = 64; pending = 8;
        events.push_back({ReferenceEvent::sp, count + (job <= 8 ? 1000 : 4000)});
        if (job <= 8) events.push_back({ReferenceEvent::dp, count + 1000});
      } else {
        check(pc == 0x80000808U || pc == 0x80000818U || pc == 0x8000082cU);
        const auto selected = select_reference_event(events, count);
        check(selected.qualified);
        if (selected.source) {
          ++commits;
          if (*selected.source == ReferenceEvent::sp) { status = 579; pending |= 1; }
          else { check(*selected.source == ReferenceEvent::dp); pending |= 32; }
          std::erase_if(events, [&](const auto& item) { return item.source == *selected.source; });
        }
      }
      check(mi == pending && sp == status);
    }
    check(current == 16 && commits == 24 && events.empty());
  } else check(argc == 1);
}
