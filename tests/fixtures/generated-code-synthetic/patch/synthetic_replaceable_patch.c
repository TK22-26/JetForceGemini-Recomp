#include "recomp.h"

int jfg_synthetic_patch_data = 3;

JFG_SYNTHETIC_FUNCTION void synthetic_replaceable(uint8_t* rdram, recomp_context* ctx) {
    (void)rdram;
    ctx->r2 = UINT64_C(29);
}
