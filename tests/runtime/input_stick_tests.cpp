#include "jfg/runtime/input_stick.hpp"

#include <cmath>
#include <iostream>
#include <string_view>

namespace {

int failures = 0;

void check(const bool condition, const std::string_view message) {
    if (!condition) {
        ++failures;
        std::cerr << "FAIL: " << message << '\n';
    }
}

void test_deadzone_and_partial_travel() {
    check(jfg::scale_xinput_left_stick(0, 0) == jfg::N64StickSample{},
          "center is neutral");
    check(jfg::scale_xinput_left_stick(
              jfg::kXInputLeftStickDeadzone, 0) == jfg::N64StickSample{},
          "deadzone boundary is neutral");

    const auto just_outside = jfg::scale_xinput_left_stick(
        jfg::kXInputLeftStickDeadzone + 1, 0);
    check(std::abs(static_cast<int>(just_outside.x)) <= 1 &&
              just_outside.y == 0,
          "deadzone exit does not jump to a large N64 value");

    const auto halfway = jfg::scale_xinput_left_stick(
        (jfg::kXInputLeftStickDeadzone + jfg::kXInputStickMaximum) / 2,
        0);
    check(halfway.x == 40 && halfway.y == 0,
          "half of usable cardinal travel maps to half N64 travel");
}

void test_cardinal_and_diagonal_limits() {
    check(jfg::scale_xinput_left_stick(jfg::kXInputStickMaximum, 0) ==
              jfg::N64StickSample{80, 0},
          "positive cardinal maximum is 80");
    check(jfg::scale_xinput_left_stick(-32768, 0) ==
              jfg::N64StickSample{-80, 0},
          "negative XInput asymmetry still reaches negative 80");
    check(jfg::scale_xinput_left_stick(
              jfg::kXInputStickMaximum, jfg::kXInputStickMaximum) ==
              jfg::N64StickSample{80, 80},
          "full diagonal preserves both N64 axes");

    const auto diagonal = jfg::scale_xinput_left_stick(16384, 16384);
    check(diagonal.x == diagonal.y && diagonal.x > 0 && diagonal.x < 80,
          "partial diagonal preserves direction and remaining travel");
}

}  // namespace

int main() {
    test_deadzone_and_partial_travel();
    test_cardinal_and_diagonal_limits();
    return failures == 0 ? 0 : 1;
}
