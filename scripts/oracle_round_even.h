#ifndef JFG_ORACLE_ROUND_EVEN_H
#define JFG_ORACLE_ROUND_EVEN_H

/* Independently authored diagnostic oracle helper, not native game runtime.
 * Nearest/ties-to-even is explicit and independent of host rounding mode.
 * This corrects finite rounding only, not Mupen's exception/overflow model.
 */
#include <math.h>
static inline double jfg_oracle_round_even(double value) {
    if (!isfinite(value) || value == 0.0) return value;
    const double lower = floor(value);
    const double fraction = value - lower;
    if (fraction < 0.5) return lower;
    if (fraction > 0.5) return lower + 1.0;
    return fmod(lower, 2.0) == 0.0 ? lower : lower + 1.0;
}
#endif
