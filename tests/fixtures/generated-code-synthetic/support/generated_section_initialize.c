#include "recomp.h"

JFG_SYNTHETIC_FUNCTION int jfg_generated_initialize_sections(
    int32_t* addresses,
    size_t capacity
) {
    if (capacity < 2) {
        return 0;
    }
    addresses[0] = 0;
    addresses[1] = 0;
    return 1;
}
