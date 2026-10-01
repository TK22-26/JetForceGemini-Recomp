#pragma once
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif
enum JfgCpuOperation {
    JFG_CPU_READ_REGISTER = 0,
    JFG_CPU_WRITE_REGISTER = 1,
    JFG_CPU_TLB_OPERATION = 2,
    JFG_CPU_CACHE_OPERATION = 3,
    JFG_CPU_EXCEPTION_RETURN = 4
};
// Return one only for a fully handled operation. Unknown operations retain
// the generated runtime's fatal trap. Context belongs to the running guest.
typedef int (*JfgCpuOperationCallback)(void* owner, void* context,
    uint32_t operation, uint32_t selector, uint64_t* value);
int jfg_minimal_runtime_bind_cpu(JfgCpuOperationCallback callback, void* owner);
int jfg_minimal_runtime_unbind_cpu(JfgCpuOperationCallback callback, void* owner);
#ifdef __cplusplus
}
#endif
