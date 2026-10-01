#include "recomp.h"

void synthetic_core_recomp(uint8_t* rdram, recomp_context* ctx);
int jfg_synthetic_wrapper_data = 2;

JFG_SYNTHETIC_FUNCTION void synthetic_core(uint8_t* rdram, recomp_context* ctx) {
    synthetic_core_recomp(rdram, ctx);
}
