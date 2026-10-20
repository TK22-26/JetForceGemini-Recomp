#include "jfg/renderer/rain_fade.hpp"
#include <array>
#include <cstdint>
#include <iostream>
#include <span>
#include <vector>

namespace {
unsigned failures = 0;
unsigned checks = 0;
void check(bool condition, const char* expression, int line) {
  ++checks;
  if (!condition) {
    ++failures;
    std::cerr << "rain_fade_tests.cpp:" << line << ": " << expression << '\n';
  }
}
#define CHECK(expression) check(bool(expression), #expression, __LINE__)
using jfg::rain::Call;
using jfg::rain::Dispatch;
using jfg::rain::Fade;
using jfg::rain::Memory;
using jfg::rain::Runtime;
using jfg::rain::Tracker;
constexpr std::uint32_t kBuffer = 0x80135700U;
constexpr std::uint32_t kNextBuffer = 0x8010FF00U;
constexpr std::uint32_t kList = 0x80200000U;
constexpr std::uint32_t kNextList = 0x80220000U;
constexpr std::uint32_t kCursor = 0x800FB408U;
constexpr std::uint32_t kStack = 0x803F0000U;
constexpr std::uint32_t kPixels = 320U * 240U * 2U;
constexpr std::uint32_t kColor = 0x2080E002U;
constexpr std::uint32_t kQuarterFadedColor = 0x1860A802U;
constexpr std::uint32_t kThreeQuarterFadedColor = 0x08203702U;

struct Fixture {
  std::vector<std::uint8_t> bytes = std::vector<std::uint8_t>(4U * 1024U * 1024U);
  Runtime runtime;
  std::uint32_t list = kList, end = kList + 0x60U, buffer = kBuffer;
  Memory memory() { return Memory(std::span<std::uint8_t>(bytes)); }
  void put8(std::uint32_t address, std::uint8_t value) {
    CHECK(memory().valid(address, 1U));
    bytes[jfg::rain::physical(address) ^ 3U] = value;
  }
  std::uint64_t call(std::uint32_t target, Call args = {}, std::uint64_t result = 0U) {
    Dispatch scope(runtime, bytes, target, args);
    return scope.finish(result);
  }
  Fixture() {
    auto ram = memory();
    ram.put32(0x80045AB8U, 0x0C01AE5EU);
    ram.put32(0x80045160U, 0x0C0143A4U);
    ram.put32(0x800455A8U, 0x0C011691U);
    ram.put32(0x800A392CU, 320U);
    ram.put32(0x800A3930U, 240U);
    ram.put32(0x800A6784U, 1U);
    call(0x80044FACU);
    CHECK(runtime.supported);
  }
  void build(std::uint8_t alpha = 64U, bool record_fade = true,
             std::uint32_t target_buffer = kBuffer, std::uint32_t base = kList,
             std::uint32_t bind_ra = 0x80045168U) {
    list = base; end = base + 0x60U; buffer = target_buffer;
    auto ram = memory();
    ram.put32(0x800FD7C0U, 0U);
    ram.put32(0x800FB400U, list);
    ram.put32(0x800FECB8U, buffer);
    ram.put32(kCursor, list + 8U);
    put8(0x800FECA8U, 0U);
    put8(0x80102D88U, alpha);
    Dispatch main(runtime, bytes, 0x80044FACU, {});
    call(0x80050E90U, {kCursor, 1U, buffer, 0U, 0U, bind_ra});
    call(0x8006BD54U);
    if (record_fade) {
      Dispatch fade(runtime, bytes, 0x8006C124U,
                    {kCursor, 0U, 0U, 0U, 0U, 0x8006BE18U});
      ram.put32(kCursor, list + 0x40U);
      fade.finish(0U);
    }
    ram.put32(kCursor, end);
    main.finish(0U);
  }
  void submit(std::uint32_t ra = 0x80045090U, std::uint64_t result = 0U) {
    call(0x8004DA10U, {list, end, 0U, buffer, 0U, ra}, result);
  }
  std::uint64_t gate(std::uint32_t ra = 0x80045AC0U,
                     std::uint64_t native_result = 1U) {
    return call(0x8006B978U, {0U, 0U, 0U, 0U, 0U, ra}, native_result);
  }
};

void source_and_memory() {
  CHECK(jfg::rain::fade_source(kColor, 0U, 64U) == kQuarterFadedColor);
  CHECK(jfg::rain::fade_source(kColor, 0U, 192U) == kThreeQuarterFadedColor);
  for (unsigned exponent = 0; exponent < 256U; ++exponent) {
    const auto color = 0x2080E000U | exponent;
    CHECK(jfg::rain::fade_source(color, 0x80FF0000U, 0U) == color);
    CHECK(jfg::rain::fade_source(color, 0x80FF0000U, 255U) == (0x80FF0000U | exponent));
    CHECK((jfg::rain::fade_source(color, 0U, 127U) & 255U) == exponent);
  }
  std::array<std::uint8_t, 16> bytes{};
  Memory ram(bytes);
  ram.put32(0x80000004U, 0x12345678U);
  CHECK(bytes[4] == 0x78U && bytes[7] == 0x12U);
  CHECK(ram.u8(0x80000004U) == 0x12U);
  CHECK(ram.u32(0xA0000004U) == 0x12345678U);
  CHECK(!ram.valid(4U, 4U));
  CHECK(!ram.valid(0xC0000004U, 4U));
  CHECK(!ram.valid(0x8000000DU, 4U));
  CHECK(!ram.valid(0xFFFFFFFCU, 8U));
  const auto before = bytes;
  ram.put32(0x8000000DU, 0xFFFFFFFFU);
  CHECK(bytes == before);
  CHECK(ram.u32(0x8000000DU) == 0U);
  Memory unaligned_length(std::span<std::uint8_t>(bytes.data(), 15U));
  CHECK(!unaligned_length.valid(0x80000000U, 1U));
}

void tracker_ownership() {
  const Fade fade{true, 64U, 0U, 7U};
  Tracker tracker;
  const auto pending = [&] {
    tracker.begin(kList, kBuffer, kPixels);
    tracker.record(kList + 8U, kList + 0x40U, fade);
  };
  pending();
  CHECK(tracker.frame(kBuffer).buffer == 0U);
  tracker.submit(kList, kList + 0x60U, kBuffer, true);
  CHECK(tracker.frame(kBuffer).buffer == 0U); // Unsealed ownership is rejected.
  pending(); tracker.seal(kList + 0x60U);
  tracker.submit(kList, kList + 0x60U, kBuffer, true);
  CHECK(tracker.frame(0xA0135700U).fade.alpha == 64U);
  CHECK(tracker.frame(kNextBuffer).buffer == 0U);
  tracker.submit(kList, kList + 0x60U, kBuffer, true);
  CHECK(tracker.frame(kBuffer).buffer == 0U); // A sealed stamp is consumed once.
  for (unsigned mismatch = 0; mismatch < 4U; ++mismatch) {
    pending(); tracker.seal(kList + 0x60U);
    tracker.submit(mismatch == 0U ? kNextList : kList,
                   mismatch == 1U ? kList + 0x68U : kList + 0x60U,
                   mismatch == 2U ? kNextBuffer : kBuffer, mismatch != 3U);
    CHECK(tracker.frame(kBuffer).buffer == 0U);
  }
  pending(); tracker.seal(kList + 0x38U); // Cannot seal before the recorded fade ends.
  tracker.submit(kList, kList + 0x38U, kBuffer, true);
  CHECK(tracker.frame(kBuffer).buffer == 0U);
  for (auto invalid_end : {kList, kList + 0x41U, kList + 0x20008U}) {
    pending(); tracker.seal(invalid_end);
    tracker.submit(kList, invalid_end, kBuffer, true);
    CHECK(tracker.frame(kBuffer).buffer == 0U);
  }
  pending(); tracker.seal(kList + 0x60U);
  tracker.record(kList + 8U, kList + 0x40U, fade);
  tracker.submit(kList, kList + 0x60U, kBuffer, true);
  CHECK(tracker.frame(kBuffer).buffer == 0U); // Recording after seal invalidates it.
  pending(); tracker.unsupported(); tracker.seal(kList + 0x60U);
  tracker.submit(kList, kList + 0x60U, kBuffer, true);
  CHECK(!tracker.frame(kBuffer).fade.simple_in);
  for (auto invalid_base : {0U, kList + 1U}) {
    tracker.begin(invalid_base, kBuffer, kPixels);
    tracker.record(kList + 8U, kList + 0x40U, fade);
    tracker.seal(kList + 0x60U);
    tracker.submit(invalid_base, kList + 0x60U, kBuffer, true);
    CHECK(tracker.frame(kBuffer).buffer == 0U);
  }
}

void submitted_frame_color_and_scopes() {
  Fixture f;
  f.build(64U); f.submit();
  f.build(192U, true, kNextBuffer, kNextList); // New globals belong to a pending frame.
  auto ram = f.memory();
  ram.put32(0x801008B4U, 0U); // Leave native previous-frame warmup untouched.
  ram.put32(kStack + 0x1CU, kColor);
  {
    Dispatch post(f.runtime, f.bytes, 0x80045A44U, {kBuffer});
    CHECK(f.runtime.post && f.runtime.post->fade.alpha == 64U);
    CHECK(f.gate() == 0U);
    CHECK(f.gate(0x80045AC4U) == 1U);
    CHECK(f.gate(0x800455B0U) == 1U);
    CHECK(f.gate(0x80045AC0U, 0U) == 0U);
    CHECK(ram.u32(0x801008B4U) == 0U);
    CHECK(f.call(0x8006B97CU, {0U, 0U, 0U, 0U, 0U, 0x80045AC0U}, 1U) == 1U);
    {
      Dispatch unrelated_line(f.runtime, f.bytes, 0x80023600U,
                              {0U, 0U, 0U, 0U, kStack});
      CHECK(ram.u32(kStack + 0x1CU) == kColor);
    }
    Dispatch rain(f.runtime, f.bytes, 0x800237D8U, {kBuffer, 320U, 240U});
    CHECK(f.runtime.rain_draw);
    {
      Dispatch line(f.runtime, f.bytes, 0x80023600U, {0U, 0U, 0U, 0U, kStack});
      CHECK(ram.u32(kStack + 0x1CU) == kQuarterFadedColor);
      const auto outer_post = f.runtime.post;
      {
        Dispatch nested_post(f.runtime, f.bytes, 0x80045A44U, {kNextBuffer});
        CHECK(f.runtime.post == nullptr);
        CHECK(f.gate() == 1U);
      }
      CHECK(f.runtime.post == outer_post);
      {
        Dispatch wrong_rain(f.runtime, f.bytes, 0x800237D8U, {kNextBuffer, 320U, 240U});
        CHECK(!f.runtime.rain_draw);
      }
      CHECK(f.runtime.rain_draw);
      ram.put32(kStack + 0x5CU, kColor);
      {
        Dispatch nested_line(f.runtime, f.bytes, 0x80023600U,
                             {0U, 0U, 0U, 0U, kStack + 0x40U});
        CHECK(ram.u32(kStack + 0x5CU) == kQuarterFadedColor);
      }
      CHECK(ram.u32(kStack + 0x5CU) == kColor);
      CHECK(ram.u32(kStack + 0x1CU) == kQuarterFadedColor);
    }
    CHECK(ram.u32(kStack + 0x1CU) == kColor);
    CHECK(ram.u32(0x801008B4U) == 0U);
  }
  CHECK(f.runtime.post == nullptr && !f.runtime.rain_draw);
  f.submit();
  {
    Dispatch post(f.runtime, f.bytes, 0x80045A44U, {kNextBuffer});
    CHECK(f.runtime.post && f.runtime.post->fade.alpha == 192U);
    Dispatch rain(f.runtime, f.bytes, 0x800237D8U, {kNextBuffer, 320U, 240U});
    Dispatch line(f.runtime, f.bytes, 0x80023600U, {0U, 0U, 0U, 0U, kStack});
    CHECK(ram.u32(kStack + 0x1CU) == kThreeQuarterFadedColor);
  }
  CHECK(ram.u32(kStack + 0x1CU) == kColor);
}

void gate_rejections_and_buffer_phase() {
  for (unsigned scenario = 0; scenario < 8U; ++scenario) {
    Fixture f;
    f.build(scenario == 0U ? 255U : 64U, scenario != 1U);
    f.submit();
    auto ram = f.memory();
    if (scenario == 2U) f.call(0x8006B9CCU); // A new transition forbids gate override.
    if (scenario == 3U) ram.put32(0x80102D38U, 1U); // Nonlinear fade.
    if (scenario == 4U) f.put8(0x800A67A0U, 1U); // Fade out.
    if (scenario == 5U) ram.put32(0x800A6784U, 0U); // No current fade.
    if (scenario == 6U) ram.put32(0x800A32ACU, 8U); // Recovery bypasses ownership.
    const auto target = scenario == 7U ? kNextBuffer : kBuffer;
    Dispatch post(f.runtime, f.bytes, 0x80045A44U, {target});
    CHECK(f.gate() == 1U);
    if (scenario == 6U || scenario == 7U) CHECK(f.runtime.post == nullptr);
    if (scenario >= 2U && scenario <= 5U) {
      // A naturally open native gate still draws into the older faded buffer.
      // New globals must not erase that submitted buffer's color attenuation.
      CHECK(f.gate(0x80045AC0U, 0U) == 0U);
      ram.put32(kStack + 0x1CU, kColor);
      Dispatch rain(f.runtime, f.bytes, 0x800237D8U, {kBuffer, 320U, 240U});
      {
        Dispatch line(f.runtime, f.bytes, 0x80023600U,
                      {0U, 0U, 0U, 0U, kStack});
        CHECK(ram.u32(kStack + 0x1CU) == kQuarterFadedColor);
      }
      CHECK(ram.u32(kStack + 0x1CU) == kColor);
    }
  }
  for (unsigned scenario = 0; scenario < 2U; ++scenario) {
    Fixture f;
    if (scenario == 0U) f.memory().put32(0x80102D38U, 1U);
    else f.put8(0x800A67A0U, 1U);
    f.build(); f.submit();
    CHECK(!f.runtime.tracker.frame(kBuffer).fade.simple_in);
  }
}

void fail_closed_inputs() {
  for (auto address : {0x80045AB8U, 0x80045160U, 0x800455A8U}) {
    Fixture f;
    f.memory().put32(address, 0U);
    f.build(); f.submit();
    CHECK(!f.runtime.supported);
    Dispatch post(f.runtime, f.bytes, 0x80045A44U, {kBuffer});
    CHECK(f.gate() == 1U && f.runtime.post == nullptr);
  }
  for (unsigned scenario = 0; scenario < 4U; ++scenario) {
    Fixture f;
    f.build(64U, true, kBuffer, kList, scenario == 0U ? 0x8004516CU : 0x80045168U);
    if (scenario == 1U) f.end += 8U;
    if (scenario == 2U) f.buffer = kNextBuffer;
    f.submit(0x80045090U, scenario == 3U ? 1U : 0U);
    CHECK(f.runtime.tracker.frame(kBuffer).buffer == 0U);
  }
  Fixture f;
  f.build(); f.submit();
  auto ram = f.memory();
  ram.put32(kStack + 0x1CU, kColor);
  Dispatch post(f.runtime, f.bytes, 0x80045A44U, {kBuffer});
  for (auto dimensions : {std::array<std::uint32_t, 3>{kBuffer, 0U, 240U},
       {kBuffer, 1025U, 240U}, {kBuffer, 320U, 513U},
       {kBuffer - 2U, 320U, 240U}, {kBuffer + 2U, 320U, 240U},
       {0x803FFFFEU, 320U, 240U}}) {
    Dispatch rain(f.runtime, f.bytes, 0x800237D8U,
                  {dimensions[0], dimensions[1], dimensions[2]});
    CHECK(!f.runtime.rain_draw);
    Dispatch line(f.runtime, f.bytes, 0x80023600U, {0U, 0U, 0U, 0U, kStack});
    CHECK(ram.u32(kStack + 0x1CU) == kColor);
  }
  {
    Dispatch viewport(f.runtime, f.bytes, 0x800237D8U, {kBuffer + 640U, 320U, 239U});
    CHECK(f.runtime.rain_draw);
    for (auto invalid_stack : {0U, 0xFFFFFFF0U, 0x803FFFF0U}) {
      Dispatch line(f.runtime, f.bytes, 0x80023600U,
                    {0U, 0U, 0U, 0U, invalid_stack});
      CHECK(ram.u32(kStack + 0x1CU) == kColor);
    }
  }
  Fixture short_memory;
  short_memory.bytes.resize(1024U);
  short_memory.call(0x80044FACU);
  CHECK(!short_memory.runtime.supported);
  CHECK(short_memory.gate() == 1U);
}

void auxiliary_task_ownership() {
  constexpr std::uint32_t aux_list = 0x80300000U;
  constexpr std::uint32_t aux_buffer = 0x80320000U;
  const Fade old_fade{true, 64U, 0U, 0U}, next_fade{true, 192U, 0U, 0U};
  for (bool sealed : {false, true}) {
    Tracker tracker;
    tracker.begin(kList, kBuffer, kPixels);
    tracker.record(kList + 8U, kList + 0x40U, old_fade);
    tracker.seal(kList + 0x60U);
    tracker.submit(kList, kList + 0x60U, kBuffer, true);
    tracker.begin(kNextList, kNextBuffer, kPixels);
    tracker.record(kNextList + 8U, kNextList + 0x40U, next_fade);
    if (sealed) tracker.seal(kNextList + 0x60U);
    tracker.auxiliary(aux_list, aux_list + 0x80U, aux_buffer, 4096U, kNextList + 0x60U);
    CHECK(tracker.frame(kBuffer).fade.alpha == 64U);
    if (!sealed) tracker.seal(kNextList + 0x60U);
    tracker.submit(kNextList, kNextList + 0x60U, kNextBuffer, true);
    CHECK(tracker.frame(kNextBuffer).fade.alpha == 192U);
  }
  for (unsigned conflict = 0; conflict < 5U; ++conflict) {
    Tracker tracker;
    tracker.begin(kList, kBuffer, kPixels);
    tracker.record(kList + 8U, kList + 0x40U, old_fade);
    tracker.seal(kList + 0x60U);
    tracker.submit(kList, kList + 0x60U, kBuffer, true);
    tracker.begin(kNextList, kNextBuffer, kPixels);
    tracker.record(kNextList + 8U, kNextList + 0x40U, next_fade);
    const auto base = conflict == 1U ? 0xA0220000U : conflict == 3U ? 0xA0135700U : aux_list;
    const auto target = conflict == 0U ? 0xA0135700U : conflict == 2U ? 0xA0220000U : aux_buffer;
    tracker.auxiliary(base, conflict == 4U ? base + 1U : base + 0x80U,
                      target, 4096U, kNextList + 0x60U);
    const bool submitted_lost = conflict == 0U || conflict == 3U || conflict == 4U;
    CHECK((tracker.frame(kBuffer).buffer == 0U) == submitted_lost);
    tracker.seal(kNextList + 0x60U);
    tracker.submit(kNextList, kNextList + 0x60U, kNextBuffer, true);
    const bool pending_lost = conflict == 1U || conflict == 2U || conflict == 4U;
    CHECK((tracker.frame(kNextBuffer).buffer == 0U) == pending_lost);
  }
  const std::array<std::uint32_t, 3> scopes{0x004001BCU, 0x00200788U, 0x030006F0U};
  for (unsigned index = 0; index < scopes.size(); ++index) {
    Fixture f;
    f.build(64U); f.submit();
    f.build(192U, true, kNextBuffer, kNextList);
    const auto type = index + 3U;
    {
      Dispatch auxiliary(f.runtime, f.bytes, scopes[index], {});
      CHECK(f.runtime.auxiliary_type == type);
      {
        Dispatch nested(f.runtime, f.bytes, scopes[(index + 1U) % scopes.size()], {});
        CHECK(f.runtime.auxiliary_type != type);
      }
      CHECK(f.runtime.auxiliary_type == type);
      f.call(0x8004DA10U, {aux_list, aux_list + 0x80U, type, aux_buffer});
    }
    CHECK(f.runtime.auxiliary_type == 0U);
    CHECK(f.runtime.tracker.frame(kBuffer).fade.alpha == 64U);
    f.submit();
    CHECK(f.runtime.tracker.frame(kNextBuffer).fade.alpha == 192U);
  }
  for (unsigned rejected = 0; rejected < 3U; ++rejected) {
    Fixture f;
    f.build(); f.submit();
    Dispatch auxiliary(f.runtime, f.bytes, rejected == 0U ? 0x0020078CU : 0x00200788U, {});
    f.call(0x8004DA10U, {aux_list, aux_list + 0x80U,
           rejected == 1U ? 3U : 4U, rejected == 2U ? 0x803FFFF0U : aux_buffer});
    CHECK(f.runtime.tracker.frame(kBuffer).buffer == 0U);
  }
  Fixture f;
  f.build(64U); f.submit();
  f.memory().put32(0x800A6784U, 0U);
  f.put8(0x80102D88U, 0U);
  {
    Dispatch type_four(f.runtime, f.bytes, 0x00200788U, {});
    f.call(0x8004DA10U, {aux_list, aux_list + 0x80U, 4U, aux_buffer});
  }
  {
    Dispatch post(f.runtime, f.bytes, 0x80045A44U, {kBuffer});
    CHECK(f.runtime.post && f.runtime.post->fade.alpha == 64U);
    CHECK(f.gate(0x80045AC0U, 0U) == 0U);
    f.memory().put32(kStack + 0x1CU, kColor);
    Dispatch rain(f.runtime, f.bytes, 0x800237D8U, {kBuffer, 320U, 240U});
    {
      Dispatch line(f.runtime, f.bytes, 0x80023600U, {0U, 0U, 0U, 0U, kStack});
      CHECK(f.memory().u32(kStack + 0x1CU) == kQuarterFadedColor);
    }
    CHECK(f.memory().u32(kStack + 0x1CU) == kColor);
  }
  for (auto target : scopes) CHECK(Dispatch::observes(target));
  CHECK(Dispatch::observes(0x8006B978U));
  CHECK(!Dispatch::observes(0x8006B97CU));
  CHECK(!Dispatch::observes(0x80200788U)); // Module observations use canonical IDs.
}


void spatial_scissor_and_owned_pixel_replay() {
  Tracker provenance;
  provenance.begin(kList, kBuffer, kPixels, 320U, 240U);
  provenance.record_scissor(kList + 8U, kList + 56U, {0, 0, 320, 240, true});
  CHECK(provenance.scissor_for_mesh(kList + 72U).verified);
  CHECK(!provenance.scissor_for_mesh(kList + 64U).verified);
  CHECK(!provenance.scissor_for_mesh(kList + 80U).verified);
  provenance.unsupported(); // Resetting fade kind retains proven clipping.
  CHECK(provenance.scissor_for_mesh(kList + 72U).verified);
  provenance.record_scissor(kList + 56U, kList + 64U, {});
  CHECK(!provenance.scissor_for_mesh(kList + 80U).verified);
  provenance.record_scissor(kList + 8U, kList + 56U, {0, 0, 320, 240, true});
  provenance.seal(kList + 96U);
  CHECK(!provenance.scissor_for_mesh(kList + 72U).verified);
  provenance.submit(kList, kList + 96U, kBuffer, true);
  CHECK(provenance.frame(kBuffer).width == 320U);
  CHECK(provenance.frame(kBuffer).height == 240U);
  provenance.begin(kNextList, kNextBuffer, kPixels, 320U, 240U);
  CHECK(!provenance.scissor_for_mesh(kList + 72U).verified);

  Fixture f;
  auto ram = f.memory();
  ram.put32(0x80102D38U, 3U);
  f.runtime.transition = 7U;
  Fade fade;
  fade.transition = 7U;
  fade.spatial.supported = true;
  fade.spatial.partially_visible = true;
  fade.spatial.scissor = {0, 0, 320, 240, true};
  fade.spatial.y_scale = double(0x13333U) / 65536.0;
  fade.spatial.shift = 160.0;
  CHECK(fade.spatial.opacity(160, 120) == 191U);
  f.runtime.tracker.begin(kList, kBuffer, kPixels, 320U, 240U);
  f.runtime.tracker.record(kList + 8U, kList + 40U, fade);
  f.runtime.tracker.seal(kList + 48U);
  f.runtime.tracker.submit(kList, kList + 48U, kBuffer, true);
  fade.spatial.shift = 0.0;
  CHECK(f.runtime.tracker.frame(kBuffer).fade.spatial.shift == 160.0);
  constexpr std::uint32_t point = kBuffer + 2U * (120U * 320U + 160U);
  for (unsigned phase = 0; phase < 3U; ++phase) {
    if (phase == 1U) ++f.runtime.transition;
    if (phase == 2U) {
      ram.put32(0x80102D38U, 0U);
      ram.put32(0x800A6784U, 0U);
    }
    Dispatch post(f.runtime, f.bytes, 0x80045A44U, {kBuffer});
    CHECK(f.gate() == (phase == 0U ? 0U : 1U));
    CHECK(f.gate(0x80045AC0U, 0U) == 0U);
    Dispatch rain(f.runtime, f.bytes, 0x800237D8U, {kBuffer, 320U, 240U});
    CHECK(f.runtime.rain_draw);
    ram.put32(point, 0U);
    ram.put32(kStack + 0x10U, 120U);
    ram.put32(kStack + 0x14U, 160U);
    ram.put32(kStack + 0x18U, 120U);
    ram.put32(kStack + 0x1CU, kColor);
    {
      Dispatch line(f.runtime, f.bytes, 0x80023600U, {kBuffer, 320U, 240U, 160U, kStack});
      CHECK(ram.u32(kStack + 0x1CU) == kColor);
      // Native point blend of (32,128,224), exponent2, over black is0x090F.
      // Replaying its source at opacity191 yields RGB5(0,1,1), or0x0043.
      ram.put32(point, 0x090F0000U);
      CHECK(line.finish(123U) == 123U);
      CHECK(ram.u32(point) == 0x00430000U);
    }
    CHECK(ram.u32(kStack + 0x1CU) == kColor);
    {
      // Width0 is rejected by both native clipping and the bounded snapshot.
      // Failure uses a temporary black source, preserving exponent and ABI.
      Dispatch invalid(f.runtime, f.bytes, 0x80023600U, {kBuffer, 0U, 240U, 160U, kStack});
      CHECK(ram.u32(kStack + 0x1CU) == 2U);
      invalid.finish(0U);
    }
    CHECK(ram.u32(kStack + 0x1CU) == kColor);
  }
  {
    Dispatch wrong(f.runtime, f.bytes, 0x80045A44U, {kNextBuffer});
    CHECK(!f.runtime.post);
    CHECK(f.gate() == 1U);
  }
}

} // namespace

int main() {
  source_and_memory();
  tracker_ownership();
  submitted_frame_color_and_scopes();
  gate_rejections_and_buffer_phase();
  fail_closed_inputs();
  auxiliary_task_ownership();
  spatial_scissor_and_owned_pixel_replay();
  std::cout << checks << " rain fade checks, " << failures << " failures\n";
  return failures ? 1 : 0;
}
