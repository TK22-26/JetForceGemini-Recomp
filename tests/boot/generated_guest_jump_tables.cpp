extern "C" {
#include "recomp.h"
void table_observe(uint8_t*, recomp_context*);
void table_clobber(uint8_t*, recomp_context*);
}
#include <cstdint>
#include <cstdlib>
#include <cstring>
#include <iostream>
#include <vector>
#include "table_addresses.h"
static std::int32_t section_bases[64];
extern "C" { std::int32_t* section_addresses = section_bases; }
extern "C" recomp_func_t* get_function(int32_t) { std::abort(); }
extern "C" void switch_error(const char*, uint32_t, uint32_t) {
    std::cout << "rejected-target\n";
    std::exit(86);
}
static gpr extended(std::uint32_t value) {
    return static_cast<gpr>(static_cast<std::int64_t>(static_cast<std::int32_t>(value)));
}
int main(int argc, char** argv) {
    for (auto& base : section_bases) base = static_cast<std::int32_t>(0x80001000U + TABLE_SHIFT);
    std::vector<std::uint32_t> memory(0x200000 / 4);
    auto* rdram = reinterpret_cast<uint8_t*>(memory.data());
    const std::uint32_t tables[] = {TABLE_OBSERVE_TABLE, TABLE_CLOBBER_TABLE};
    const std::uint32_t targets[][4] = {
        {TABLE_OBSERVE_CASE0, TABLE_OBSERVE_CASE1, TABLE_OBSERVE_CASE1, TABLE_OBSERVE_CASE2},
        {TABLE_CLOBBER_CASE0, TABLE_CLOBBER_CASE1, TABLE_CLOBBER_CASE1, TABLE_CLOBBER_CASE2}};
    recomp_func_t* functions[] = {table_observe, table_clobber};
    unsigned passed = 0, total = 0;
    for (unsigned f = 0; f < 2; ++f) {
        const auto table = extended(tables[f] + TABLE_SHIFT);
        for (unsigned variant = 0; variant < 2; ++variant) {
            for (unsigned i = 0; i < 4; ++i) {
                // Variant one changes the table, not the generated member set.
                const auto member = variant ? (3 - i) : i;
                MEM_W(i * 4, table) = static_cast<std::int32_t>(targets[f][member] + TABLE_SHIFT);
            }
            for (unsigned i = 0; i < 4; ++i) {
                recomp_context ctx{};
                ctx.r31 = extended(0x80200000U);
                ctx.r4 = i * 4;
                if (argc > 1) {
                    auto bad = targets[f][0] + TABLE_SHIFT + 2; // Unaligned, still within function.
                    if (std::strcmp(argv[1], "unknown") == 0) bad = 0x80090000U;
                    MEM_W(i * 4, table) = static_cast<std::int32_t>(bad);
                }
                functions[f](rdram, &ctx);
                const auto member = variant ? (3 - i) : i;
                const auto expected = extended(targets[f][member] + TABLE_SHIFT);
                const auto result = member == 0 ? 10U : member == 3 ? 30U : 20U;
                const bool ok = ctx.r16 == expected && ctx.r10 == (f ? 7 : expected) &&
                    ctx.r5 == (f ? 0 : expected) && ctx.r2 == result && ctx.r31 == extended(0x80200000U);
                passed += ok;
                ++total;
                std::cout << f << '\t' << variant << '\t' << i << '\t' << ok << '\t'
                          << std::hex << ctx.r16 << '\t' << expected << std::dec << '\n';
            }
        }
    }
    std::cout << "matched\t" << passed << '\t' << total << '\n';
    return passed == total ? 0 : 1;
}
