#include "jfg/renderer/presentation_cadence.hpp"
#include <cstdlib>
static void require(bool value) { if (!value) std::abort(); }
int main() {
    // Rational scheduling uses the same class as the RT64 workload adapter.
    // Long mixed PAL intervals must emit exactly floor(total VI * target / 50)
    // outputs, with no rounding to 16/17 FPS or phase reset on cadence changes.
    for (unsigned rate : {50U, 60U}) for (unsigned target : {60U, 120U, 144U, 165U, 360U, 1000U}) {
        jfg::PresentationCadence cadence;
        std::uint64_t elapsed = 0, outputs = 0;
        for (unsigned sample = 0; sample < 20000U; ++sample) {
            const unsigned ticks = 2U + sample % 5U;
            const jfg::PresentationInterval interval{ticks, rate};
            const auto count = cadence.begin(interval, target);
            elapsed += ticks;
            require(count && outputs + count == elapsed * target / rate);
            float previous = cadence.alpha();
            require(previous >= 0.0f && previous <= 1.0f);
            for (unsigned frame = 0; frame < count; ++frame) {
                cadence.advance();
                const auto alpha = cadence.alpha();
                require(alpha >= previous && alpha <= 1.0f);
                previous = alpha;
            }
            outputs += count;
        }
    }
    {
        jfg::PresentationCadence rendered, skipped;
        for (unsigned sample = 0; sample < 1000U; ++sample) {
            const jfg::PresentationInterval interval{3U + sample % 4U, 50U};
            const auto count = rendered.begin(interval,144U);
            require(skipped.begin(interval,144U) == count);
            // Frame reduction, early workload termination, and a costly frame
            // all consume presentation slots without altering the next phase.
            for (unsigned frame = 0; frame < count; ++frame) rendered.advance();
            skipped.advance(count);
            require(rendered.alpha() == skipped.alpha());
        }
        require(rendered.begin({3U,50U},120U) == 7U); // Output rate change resets.
        rendered.advance(7U);
        require(rendered.begin({3U,60U},120U) == 6U); // VI rate change resets.
        rendered.advance(6U);rendered.reset();
        require(rendered.begin({3U,50U},120U) == 7U);
        const jfg::PresentationInterval pal{3U,50U};
        require(pal.microseconds()==60000 && pal.seconds()==0.06);
        require(pal.below_rate(17U) && !pal.below_rate(16U));
        require(!jfg::PresentationInterval{}.below_rate(120U));
        bool rejected=false;try {rendered.begin({3U,50U},16U);}catch(const std::invalid_argument&){rejected=true;}
        require(rejected);
    }
    return 0;
}
