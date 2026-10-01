#include "recomp.h"

JFG_SYNTHETIC_FUNCTION void synthetic_replaceable_recomp(uint8_t* rdram, recomp_context* ctx) {
    (void)rdram;
    ctx->r2 = UINT64_C(11);
}
