extern "C" {
#include "recomp.h"
void state_read(uint8_t*, recomp_context*);
void state_write(uint8_t*, recomp_context*);
void state_mult(uint8_t*, recomp_context*);
void state_multu(uint8_t*, recomp_context*);
void state_dmult(uint8_t*, recomp_context*);
void state_dmultu(uint8_t*, recomp_context*);
void state_div(uint8_t*, recomp_context*);
void state_divu(uint8_t*, recomp_context*);
void state_ddiv(uint8_t*, recomp_context*);
void state_ddivu(uint8_t*, recomp_context*);
void state_fp_compare(uint8_t*, recomp_context*);
void state_fp_read(uint8_t*, recomp_context*);
void state_fp_write(uint8_t*, recomp_context*);
void state_fp_branch(uint8_t*, recomp_context*);
void do_break(uint32_t) { abort(); }
}
#include <cstdint>
#include <iostream>
static unsigned cases, passed;
static void check(bool value) { ++cases; if (value) ++passed; }
static std::uint64_t sx(std::uint32_t v) { return static_cast<std::uint64_t>(static_cast<std::int64_t>(static_cast<std::int32_t>(v))); }
int main() {
  recomp_context ctx{};
  ctx.mips3_float_mode = 1;
  ctx.f_odd = &ctx.f1.u32l;
  ctx.hi = 0x123456789abcdef0ULL; ctx.lo = 0xfedcba9876543210ULL;
  state_read(nullptr, &ctx);
  check(ctx.r2 == ctx.hi && ctx.r3 == ctx.lo);
  ctx.r4 = 0xffffffffffff0001ULL; ctx.r5 = 0x8123456789abcdefULL;
  state_write(nullptr, &ctx);
  check(ctx.hi == ctx.r4 && ctx.lo == ctx.r5);
  struct Case { recomp_func_t* function; std::uint64_t a, b, hi, lo; };
  const Case samples[] = {
    {state_mult, sx(0xfffffff9), 3, sx(0xffffffff), sx(0xffffffeb)},
    {state_multu, 0xffffffff, 0xffffffff, sx(0xfffffffe), 1},
    {state_dmult, 0xfffffffffffffff9ULL, 3, ~0ULL, 0xffffffffffffffebULL},
    {state_dmultu, ~0ULL, ~0ULL, 0xfffffffffffffffeULL, 1},
    {state_div, sx(0xfffffff9), 3, ~0ULL, 0xfffffffffffffffeULL},
    {state_divu, 0xffffffff, 3, 0, 0x55555555},
    {state_ddiv, 0xfffffffffffffff9ULL, 3, ~0ULL, 0xfffffffffffffffeULL},
    {state_ddivu, ~0ULL, 3, 0, 0x5555555555555555ULL}};
  for (const auto& test : samples) {
    ctx.hi = 0xabc; ctx.lo = 0xdef; ctx.r4 = test.a; ctx.r5 = test.b;
    test.function(nullptr, &ctx);
    state_read(nullptr, &ctx);
    check(ctx.hi == test.hi && ctx.lo == test.lo && ctx.r2 == test.hi && ctx.r3 == test.lo);
  }
  for (unsigned rounding = 0; rounding < 4; ++rounding) {
    ctx.r4 = 0x01000004U | rounding;
    state_fp_write(nullptr, &ctx);
    state_fp_read(nullptr, &ctx);
    check(ctx.r2 == ctx.r4 && get_cop1_cs() == rounding);
    for (bool equal : {true, false}) {
      ctx.f0.fl = 1.0f; ctx.f2.fl = equal ? 1.0f : 2.0f;
      state_fp_compare(nullptr, &ctx);
      state_fp_branch(nullptr, &ctx);
      check(ctx.r2 == (equal ? 1U : 0U));
      state_fp_read(nullptr, &ctx);
      check(ctx.r2 == (ctx.r4 | (equal ? 0x00800000U : 0U)));
    }
  }
  set_cop1_cs(0);
  std::cout << "matched\t" << passed << '\t' << cases << '\n';
  return passed == cases && cases == 30 ? 0 : 1;
}
