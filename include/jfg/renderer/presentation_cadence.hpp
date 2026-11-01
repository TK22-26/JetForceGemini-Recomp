#pragma once
#include <algorithm>
#include <cstdint>
#include <stdexcept>

namespace jfg {
// An authored frame lasts ticks/rate seconds. PAL's 3/50 second interval
// cannot be represented by an integer FPS value. Keep this ratio through
// ownership, scheduling, interpolation weights and the presentation deadline.
struct PresentationInterval {
    unsigned ticks = 0;
    unsigned rate = 0;
    explicit operator bool() const noexcept { return ticks != 0U && rate != 0U; }
    bool operator==(const PresentationInterval& other) const noexcept {
        return ticks == other.ticks && rate == other.rate;
    }
    bool operator!=(const PresentationInterval& other) const noexcept { return !(*this == other); }
    bool below_rate(unsigned target) const noexcept {
        return bool(*this) && std::uint64_t(target) * ticks > rate;
    }
    double seconds() const noexcept { return *this ? double(ticks) / rate : 0.0; }
    std::int64_t microseconds() const noexcept {
        return *this ? static_cast<std::int64_t>(std::uint64_t(ticks) * 1000000U / rate) : 0;
    }
    // Compatibility/diagnostic hint only. Scheduling never divides by this.
    unsigned rate_hint() const noexcept {
        return *this ? static_cast<unsigned>((std::uint64_t(rate) + ticks - 1U) / ticks) : 0U;
    }
};

// Integer phase accumulation in units of 1/(VI rate * target rate) seconds.
// Changing the authored VI interval preserves the fractional output remainder.
// Changing the VI clock or output rate starts a new timeline. Offscreen tasks
// must not call begin/reset, because they do not own presentation time.
class PresentationCadence {
public:
    void reset() noexcept { *this = PresentationCadence{}; }
    unsigned begin(PresentationInterval interval, unsigned target) {
        if (!interval.below_rate(target))
            throw std::invalid_argument("Presentation target must exceed the authored rate");
        if (rate_ != interval.rate || target_ != target) reset();
        rate_ = interval.rate;
        target_ = target;
        // Remove elapsed time without discarding the fractional phase. This
        // also bounds the arithmetic during arbitrarily long sessions.
        const auto elapsed = (std::min)(logical_, display_);
        logical_ -= elapsed;
        display_ -= elapsed;
        step_ = std::uint64_t(target) * interval.ticks;
        logical_ += step_;
        return static_cast<unsigned>((logical_ - display_) / rate_);
    }
    float alpha() const noexcept {
        if (!step_) return 1.0f;
        return static_cast<float>(std::clamp(
            (double(step_) + double(display_) - double(logical_)) / double(step_), 0.0, 1.0));
    }
    // A skipped/reduced output consumes the same interval as a rendered one.
    void advance(unsigned count = 1U) noexcept { display_ += std::uint64_t(rate_) * count; }
private:
    unsigned rate_ = 0, target_ = 0;
    std::uint64_t logical_ = 0, display_ = 0, step_ = 0;
};
} // namespace jfg
