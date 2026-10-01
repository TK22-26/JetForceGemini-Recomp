#include "recomp.h"

#if defined(JFG_NEGATIVE_RUNTIME_DATA_OWNER)
int32_t* section_addresses = 0;
#endif

#if defined(JFG_NEGATIVE_EXTRA_GENERATED_DATA)
int jfg_negative_extra_generated_data = 1;
#endif

#if defined(JFG_NEGATIVE_COMPILER_DATA_NEAR_NAME)
const unsigned int jfg_Fenv1 = 0;
#endif

int jfg_synthetic_support_data = 4;

void synthetic_core(uint8_t* rdram, recomp_context* ctx);

JFG_SYNTHETIC_FUNCTION recomp_func_t* jfg_generated_lookup_function(int32_t vram) {
    if (vram == 1) {
        return synthetic_core;
    }
    return 0;
}
