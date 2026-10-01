#include "recomp.h"

void synthetic_replaceable_recomp(uint8_t* rdram, recomp_context* ctx);

JFG_SYNTHETIC_FUNCTION void synthetic_replaceable(uint8_t* rdram, recomp_context* ctx) {
    synthetic_replaceable_recomp(rdram, ctx);
}
