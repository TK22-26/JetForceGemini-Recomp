#pragma once

#include <cstdint>

namespace jfg {
// Explicit replayed intent keeps old recordings without these bits unchanged.
// Scope commands occupy bits 0..2; Modern action identity occupies bit 7.
inline constexpr std::uint8_t kModernRollLeftFlag = 0x08;
inline constexpr std::uint8_t kModernRollRightFlag = 0x10;
inline constexpr std::uint8_t kModernRollFlags = kModernRollLeftFlag | kModernRollRightFlag;

enum class ModernRollSource { keyboard, controller };

// Inputs have already passed the selected device's ordinary movement deadzone.
// The controller's lateral eighth of the direction circle tolerates off-axis
// tilt but leaves diagonals for crawling. There is no extra strength threshold.
inline constexpr std::uint8_t modern_roll_intent_flags(ModernRollSource source,
    int move_x, int move_y, bool keyboard_forward_back_held) noexcept {
    if(move_x < -128 || move_x > 127 || move_y < -128 || move_y > 127 || move_x == 0)
        return 0;
    if(source == ModernRollSource::keyboard) {
        // Actual held actions matter: W+S cancels Y, but is not A/D alone.
        if(keyboard_forward_back_held || move_y != 0)return 0;
    } else if(source == ModernRollSource::controller) {
        const int x = move_x < 0 ? -move_x : move_x;
        const int y = move_y < 0 ? -move_y : move_y;
        // y/x <= tan(22.5 degrees), expressed exactly without floating point.
        if(y*y + 2*x*y > x*x)return 0;
    } else return 0;
    return move_x < 0 ? kModernRollLeftFlag : kModernRollRightFlag;
}

// The native consumer still qualifies Modern ownership, current actor, input
// locks and gameplay context. Character is the native normalized low two bits.
inline constexpr bool modern_roll_stance(unsigned character, unsigned stance) noexcept {
    return character < 2U && (stance == 1U || stance == 2U);
}

inline constexpr std::uint16_t modern_roll_side_buttons(std::uint8_t flags) noexcept {
    const auto intent = flags & kModernRollFlags;
    // Conflicting recorded intent cancels instead of selecting a direction.
    return intent == kModernRollLeftFlag ? 0x2U : intent == kModernRollRightFlag ? 0x1U : 0U;
}
} // namespace jfg
