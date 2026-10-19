#include "jfg/renderer/frame_diagnostics_state.hpp"
#include "jfg/renderer/presentation_policy.hpp"
#include "jfg/renderer/video_settings.hpp"
#include <iostream>
#include "jfg/renderer/native_blur_mode.hpp"
#include "jfg/renderer/fog_settings.hpp"
int main() {
  unsigned failures = 0;
  auto check = [&](bool ok) {
    if (!ok)
      ++failures;
  };
  for (auto mode : {jfg::FrameRateMode::original, jfg::FrameRateMode::custom,
                    jfg::FrameRateMode::unlimited}) {
    for (bool vsync : {false, true}) {
      const jfg::VideoSettings settings{mode, 360, vsync};
      auto loaded =
          jfg::parse_video_settings(jfg::serialize_video_settings(settings));
      check(loaded && loaded->mode == mode && loaded->fps == 360 &&
            loaded->vsync == vsync);
    }
  }
  check(!jfg::parse_video_settings(
      "version=2\nmode=unlimited\nfps=360\nvsync=0\n"));
  check(!jfg::parse_video_settings(
      "version=1\nmode=custom\nfps=360\nvsync=1\nvsync=0\n"));
  check(!jfg::parse_video_settings("version=1\nmode=custom\nfps=0\nvsync=1\n"));
  check(!jfg::parse_video_settings(
      "version=1\nmode=custom\nfps=1001\nvsync=1\n"));
  check(!jfg::parse_video_settings("mode=custom\nfps=360\nvsync=1\n"));
  check(!jfg::parse_video_fps({}));
  check(!jfg::parse_video_fps("360junk"));
  check(!jfg::parse_video_fps("-60"));
  check(!jfg::parse_video_fps("999999999999999999999999"));
  check(jfg::parse_video_fps("60") == 60U);
  check(jfg::parse_video_fps("1000") == 1000U);
  auto original = jfg::load_video_settings({});
  check(original && original->mode == jfg::FrameRateMode::original &&
        original->vsync);
  check(original && original->blur == jfg::BlurMode::reduced);
  const std::string legacy = "version=1\nmode=custom\nfps=120\nvsync=1\n";
  auto migrated = jfg::parse_video_settings(legacy);
  check(migrated && migrated->blur == jfg::BlurMode::reduced);
  for (auto blur : {jfg::BlurMode::off, jfg::BlurMode::reduced, jfg::BlurMode::original}) {
    jfg::VideoSettings choice{jfg::FrameRateMode::custom, 120, true, blur};
    auto restored = jfg::parse_video_settings(jfg::serialize_video_settings(choice));
    check(restored && restored->blur == blur && restored->fps == 120);
    jfg::configure_native_blur(blur);
    check(jfg::native_blur_render_mode() == (blur == jfg::BlurMode::off ? 5U : 4U));
    check(jfg::configured_blur_color(0xffffff80U) == jfg::blur_color_word(blur, 0xffffff80U));
  }
  check(!jfg::parse_video_settings(legacy + "blur=unknown\n"));
  check(!jfg::parse_video_settings(legacy + "blur=off\nblur=original\n"));
  check(!jfg::valid_video_settings({jfg::FrameRateMode::custom, 120, true, static_cast<jfg::BlurMode>(3)}));
  for (unsigned alpha = 0; alpha < 256; ++alpha) {
    const auto byte = static_cast<std::uint8_t>(alpha);
    check(jfg::blur_source_alpha(jfg::BlurMode::off, byte) == 255);
    check(jfg::blur_source_alpha(jfg::BlurMode::original, byte) == alpha);
    const auto reduced = jfg::blur_source_alpha(jfg::BlurMode::reduced, byte);
    check(reduced >= alpha && reduced >= 191);
    check((jfg::blur_color_word(jfg::BlurMode::reduced, 0x12345600U | alpha) & 0xffffff00U) == 0x12345600U);
    if (alpha) check(reduced >= jfg::blur_source_alpha(jfg::BlurMode::reduced, static_cast<std::uint8_t>(alpha-1)));
  }
  check(jfg::blur_source_alpha(jfg::BlurMode::reduced, 128) == 223);
  check(jfg::blur_source_alpha(jfg::BlurMode::reduced, 255) == 255);
  check(migrated && migrated->fog_percent==100);
  for(unsigned percent:{0U,25U,50U,75U,100U}) {
    jfg::VideoSettings choice{};choice.fog_percent=percent;
    const auto restored=jfg::parse_video_settings(jfg::serialize_video_settings(choice));
    check(restored&&restored->fog_percent==percent);
    jfg::configure_fog_strength(percent);
    check(jfg::fog_strength_preference().load()==percent);
    check(jfg::fog_coefficients(0x03e8fc18U,percent)==
      ((std::uint32_t(10*percent)<<16)|std::uint16_t(-int(10*percent))));
  }
  check(jfg::fog_coefficients(0x81234567U,100)==0x81234567U);
  check(jfg::parse_video_settings(legacy+"remove_fog=1\n")->fog_percent==0);
  check(jfg::parse_video_settings(legacy+"remove_fog=0\n")->fog_percent==100);
  for(const auto* bad:{"fog_percent=101\n","fog_percent=-1\n","fog_percent=50x\n","remove_fog=1\nfog_percent=50\n"})
    check(!jfg::parse_video_settings(legacy+bad));
  jfg::configure_fog_strength(100);
  jfg::configure_native_blur(jfg::BlurMode::reduced);
  jfg::configure_presentation_policy(true, false);
  check(jfg::presentation_target(360, 240) == 240);
  jfg::configure_presentation_policy(false, false);
  check(jfg::presentation_target(360, 240) == 360);
  jfg::configure_presentation_policy(true, true);
  check(jfg::presentation_target(60, 240) == 240);
  jfg::configure_presentation_policy(false, true);
  check(jfg::presentation_unlimited());
  check(jfg::presentation_target(60, 240) == jfg::kUnlimitedPresentation);
  jfg::configure_presentation_policy(true, false);
  // Boss capture: one 3D submission and one blur submission per two VI.
  // Starting at tick zero is valid, and duplicate passes must not reset age.
  jfg::FrameDiagnosticState diagnostics;
  diagnostics.scene(0);
  const auto first_time = diagnostics.scene_time.load();
  diagnostics.scene(0);
  check(diagnostics.scenes.load() == 1 && diagnostics.scene_time.load() == first_time);
  for (std::uint64_t tick = 2; tick <= 60; tick += 2) {
    diagnostics.scene(tick);
    diagnostics.scene(tick);
  }
  check(diagnostics.scenes.load() == 31 && diagnostics.vi.load() == 60);
  std::cout << "Video settings checks: " << failures << " failures\n";
  return failures ? 1 : 0;
}
