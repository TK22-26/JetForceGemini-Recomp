#include "jfg/audio/latency_recovery.hpp"
#include <array>
#include <cstdlib>
#include <iostream>

static void check(bool value, const char* message) {
  if (!value) { std::cerr << message << '\n'; std::abort(); }
}
int main() {
  for (const std::uint32_t rate : {8000U, 22018U, 32000U, 44100U, 48000U, 96000U}) {
    jfg::audio::LatencyRecovery policy;
    std::uint64_t consumed = 0;
    // An hour of ordinary playback, including callback-sized queue oscillation.
    for (std::uint64_t ms = 0; ms < 3600000; ms += 10) {
      consumed += rate * 4U / 100U;
      const auto queue = rate * (ms % 40 == 0 ? 8U : 4U) / 10U;
      check(!policy.observe(ms, queue, rate, consumed, true), "normal playback changed");
    }
    policy.reset(); consumed = 0;
    // Stationary consumer must never be repeatedly cleared.
    for (std::uint64_t ms = 0; ms < 5000; ms += 10)
      check(!policy.observe(ms, rate * 5U, rate, consumed, true), "stalled consumer cleared");
    bool recovered = false;
    for (std::uint64_t ms = 5000; ms <= 6500; ms += 10) {
      consumed += rate * 4U / 100U;
      if (policy.observe(ms, rate * 5U, rate, consumed, true)) {
        check(ms >= 6000, "recovered before sustained consumption");
        policy.recovered(ms); recovered = true;
      }
    }
    check(recovered, "persistent backlog did not recover");
    for (std::uint64_t ms = 6510; ms < 10000; ms += 10) {
      consumed += rate * 4U / 100U;
      check(!policy.observe(ms, rate * 5U, rate, consumed, true), "recovery cooldown bypassed");
    }
    policy.reset(); consumed = 0;
    for (std::uint64_t ms = 0; ms < 6000; ms += 10) {
      consumed += rate * 4U / 100U;
      const bool excess = ms % 1000 < 500;
      check(!policy.observe(ms, excess ? rate * 5U : rate / 2U, rate, consumed, true),
          "transient spike cleared");
    }
    // Loading, pause and skip exclusions continually re-arm; re-entry warms up.
    for (std::uint64_t ms = 6000; ms < 10000; ms += 10) {
      consumed += rate * 4U / 100U;
      check(!policy.observe(ms, rate * 5U, rate, consumed, false), "excluded state recovered");
    }
    check(!policy.observe(10000, rate * 5U, rate, consumed, true), "no re-entry warmup");
    check(!policy.observe(9999, rate * 5U, rate, consumed, true), "backwards clock recovered");
    check(!policy.observe(20000, rate * 5U, rate, consumed, true), "service gap recovered");

    jfg::audio::RecoveryPcmHistory history; history.configure(rate);
    const auto total = std::size_t{rate} * 20U; // wrap the four-second history
    std::vector<std::uint8_t> pcm(total);
    for (std::size_t i = 0; i < total; ++i) pcm[i] = static_cast<std::uint8_t>((i * 53U + 29U) % 256U);
    for (std::size_t i = 0; i < total; i += 400U)
      history.append(std::span(pcm).subspan(i, (std::min)(std::size_t{400U}, total - i)));
    const auto pending = rate * 4U;
    auto replacement = history.replacement(pending);
    const auto keep = std::size_t{rate / 10U} * 4U;
    const auto blend = std::size_t{rate} * 5U / 1000U * 4U;
    check(replacement.size() == keep, "incorrect retained duration");
    for (std::size_t i = 0; i < 4U; ++i)
      check(replacement[i] == pcm[total - pending + i], "splice does not start at old head");
    for (std::size_t i = blend - 4U; i < keep; ++i)
      check(replacement[i] == pcm[total - keep + i], "recent PCM changed beyond blend");
    // Check every blended sample against independent signed integer arithmetic.
    const auto decode = [](const std::uint8_t* p) {
      const int n = int{p[0]} + int{p[1]} * 256; return n > 32767 ? n - 65536 : n;
    };
    const auto frames = blend / 4U;
    for (std::size_t i = 0; i < frames; ++i) for (std::size_t channel = 0; channel < 2U; ++channel) {
      const auto at = i * 4U + channel * 2U;
      const auto old_sample = decode(pcm.data() + total - pending + at);
      const auto new_sample = decode(pcm.data() + total - keep + at);
      const auto expected = (old_sample * static_cast<int>(frames - 1U - i) +
          new_sample * static_cast<int>(i)) / static_cast<int>(frames - 1U);
      check(decode(replacement.data() + at) == expected, "crossfade sample/channel mismatch");
    }
    auto long_fault = history.replacement(rate * 24U);
    check(long_fault.size() == keep && decode(long_fault.data()) == 0 &&
        decode(long_fault.data() + 2U) == 0, "long fault fade-in invalid");
    check(history.replacement(static_cast<std::uint32_t>(keep)).empty(), "small queue trimmed");
    check(history.replacement(pending + 1U).empty(), "unaligned queue accepted");
    history.clear(); check(history.replacement(pending).empty(), "empty history accepted");
    history.append(replacement);
    check(history.replacement(static_cast<std::uint32_t>(keep + 4U)).size() == keep,
        "post-recovery history not reusable");
  }
  jfg::audio::RecoveryPcmHistory invalid; invalid.configure(0);
  check(invalid.replacement(10000U).empty(), "invalid format accepted");
  std::cout << "latency policy and stereo PCM recovery checks passed\n";
}
