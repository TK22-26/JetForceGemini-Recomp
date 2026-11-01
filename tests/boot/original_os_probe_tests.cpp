#include "jfg/boot/original_os_probe.hpp"
#include <cstdlib>
#include <iostream>
static void check(bool ok,const char* name){if(!ok){std::cerr<<name<<'\n';std::exit(1);}}
int main() {
  using namespace jfg::boot;
  const std::string sample="{\"kind\":\"jfg-phase9-original-os-probe\",\"acceptance\":false,\"status\":\"retrace-target\",\"poll_target\":0,\"retrace_target\":3,\"vi_retraces\":3,\"controller_samples\":0,\"completed_updates\":0,\"cpu_count\":2800000,\"instructions\":1400000,\"graphics_tasks\":0,\"decoded_audio_tasks\":0,\"unsupported_accesses\":0,\"runtime_snapshot_complete\":false,\"state_hash\":\"0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef\"}\n";
  const auto parsed=parse_original_os_probe(sample,3,0);
  check(parsed.has_value(),"original OS three-VI observation is independent of cooperative scheduler counts");
  check(original_os_probe_json(*parsed)==sample,"canonical producer contract");
  auto windows=sample;windows.insert(windows.size()-1,"\r");
  check(parse_original_os_probe(windows,3,0).has_value(),"Windows line ending");
  check(!parse_original_os_probe(sample,4,0)&&!parse_original_os_probe(sample,3,1),"requested boundary must match");
  auto poll=*parsed;poll.poll_target=32;poll.retrace_target=UINT32_MAX;poll.controller_samples=32;poll.vi_retraces=73;
  check(parse_original_os_probe(original_os_probe_json(poll),3,32).has_value(),"poll target permits its actual VI count");
  check(!parse_original_os_probe(original_os_probe_json(poll),3,31),"no off-by-one poll acceptance");
  --poll.controller_samples;check(original_os_probe_json(poll).empty(),"producer refuses incomplete poll");
  for(const auto& change:std::array<std::pair<std::string,std::string>,8>{{
    {"\"acceptance\":false","\"acceptance\":true"},{"\"unsupported_accesses\":0","\"unsupported_accesses\":1"},
    {"\"runtime_snapshot_complete\":false","\"runtime_snapshot_complete\":true"},{"\"vi_retraces\":3","\"vi_retraces\":4"},
    {"\"cpu_count\":2800000","\"cpu_count\":0"},{"\"cpu_count\":2800000","\"cpu_count\":18446744073709551616"},
    {"\"retrace_target\":3","\"retrace_target\":4294967296"},{"\"vi_retraces\":3","\"vi_retraces\":03"}}}) {
    auto bad=sample;bad.replace(bad.find(change.first),change.first.size(),change.second);
    check(!parse_original_os_probe(bad,3,0),"malformed, overflowing or inflated evidence rejected");
  }
  check(!parse_original_os_probe(sample+sample,3,0)&&!parse_original_os_probe(sample+"garbage",3,0),"one bounded record only");
  std::cout<<"original OS probe protocol checks passed\n";
}
