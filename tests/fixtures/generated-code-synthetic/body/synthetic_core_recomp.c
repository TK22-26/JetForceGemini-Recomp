#include "recomp.h"

int jfg_synthetic_body_data = 1;

JFG_SYNTHETIC_FUNCTION void synthetic_core_recomp(uint8_t* rdram, recomp_context* ctx) {
    (void)rdram;
    ctx->r2 = UINT64_C(7);
}
