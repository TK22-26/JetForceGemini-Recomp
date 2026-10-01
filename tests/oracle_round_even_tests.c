#include "../scripts/oracle_round_even.h"
#include <fenv.h>
#include <stdio.h>

int main(void) {
    const double inputs[] = {558.5,559.5,-558.5,-559.5,0.5,-0.5,1.5,-1.5,
                             558.25,558.75,-558.25,-558.75,0.0,2147483646.5};
    const double expected[] = {558,560,-558,-560,0,0,2,-2,
                               558,559,-558,-559,0,2147483646};
    const int modes[] = {FE_TONEAREST, FE_DOWNWARD, FE_UPWARD, FE_TOWARDZERO};
    for (unsigned m = 0; m < sizeof(modes)/sizeof(modes[0]); ++m) {
        if (fesetround(modes[m])) return 1;
        for (unsigned i = 0; i < sizeof(inputs)/sizeof(inputs[0]); ++i) {
            if (jfg_oracle_round_even(inputs[i]) != expected[i] ||
                fegetround() != modes[m]) return 2;
        }
    }
    if (fesetround(FE_TONEAREST)) return 3;
    puts("oracle finite-rounding tests passed: 56 cases");
    return 0;
}
