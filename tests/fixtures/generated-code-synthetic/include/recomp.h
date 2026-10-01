#ifndef JFG_TESTS_SYNTHETIC_RECOMP_H
#define JFG_TESTS_SYNTHETIC_RECOMP_H

#include <stdint.h>
#include <stddef.h>

#if defined(_MSC_VER)
#define RECOMP_FUNC __declspec(noinline)
#elif defined(__clang__) || defined(__GNUC__)
#define RECOMP_FUNC __attribute__((noinline))
#else
#error "Synthetic generated-code fixture does not support this compiler"
#endif

#define JFG_SYNTHETIC_FUNCTION RECOMP_FUNC

typedef uint64_t gpr;

typedef struct recomp_context {
    gpr r0,  r1,  r2,  r3,  r4,  r5,  r6,  r7,
        r8,  r9,  r10, r11, r12, r13, r14, r15,
        r16, r17, r18, r19, r20, r21, r22, r23,
        r24, r25, r26, r27, r28, r29, r30, r31;
} recomp_context;

#define MEM_W(offset, reg) \
    (*(int32_t*)(rdram + ((((reg) + (offset))) - UINT64_C(0xFFFFFFFF80000000))))

#ifdef __cplusplus
extern "C" {
#endif

typedef void(recomp_func_t)(uint8_t* rdram, recomp_context* ctx);
typedef int (*jfg_generated_dispatch_call_callback_t)(
    void* opaque,
    int32_t vram,
    uint8_t* rdram,
    recomp_context* ctx);

void cop0_status_write(recomp_context* ctx, gpr value);
gpr cop0_status_read(recomp_context* ctx);
void cop0_write(recomp_context* ctx, uint32_t cop0_reg, gpr value);
gpr cop0_read(recomp_context* ctx, uint32_t cop0_reg);
void cop0_eret(uint8_t* rdram, recomp_context* ctx);
void cache_op(uint8_t* rdram, recomp_context* ctx, uint32_t operation, gpr address);
void cop0_tlb_op(recomp_context* ctx, uint32_t operation);
void reserved_instruction(uint8_t* rdram, recomp_context* ctx, uint32_t vram, uint32_t word);
void switch_error(const char* func, uint32_t vram, uint32_t jtbl);
void do_break(uint32_t vram);
recomp_func_t* get_function(int32_t vram);
extern int32_t* section_addresses;
void recomp_syscall_handler(uint8_t* rdram, recomp_context* ctx, int32_t instruction_vram);
void pause_self(uint8_t* rdram);
size_t jfg_minimal_runtime_section_capacity(void);
int jfg_minimal_runtime_initialize(void);
int jfg_minimal_runtime_bind_dispatch(jfg_generated_dispatch_call_callback_t callback, void* opaque);
int jfg_minimal_runtime_unbind_dispatch(jfg_generated_dispatch_call_callback_t callback, void* opaque);
int jfg_minimal_runtime_bind_cpu(int (*callback)(void*, void*, uint32_t, uint32_t, uint64_t*), void* opaque);
int jfg_minimal_runtime_unbind_cpu(int (*callback)(void*, void*, uint32_t, uint32_t, uint64_t*), void* opaque);
size_t jfg_generated_section_count(void);
int jfg_generated_initialize_sections(int32_t* addresses, size_t capacity);

#ifdef __cplusplus
}
#endif

#endif
