#include "jfg/runtime/cic_nus_6105.hpp"

#include <algorithm>
#include <array>
#include <cstdint>
#include <iostream>

namespace {

int failures = 0;

void check(const bool condition, const char *message) {
    if (!condition) {
        std::cerr << "FAIL: " << message << '\n';
        ++failures;
    }
}

} // namespace

int main() {
    std::array<std::uint8_t, jfg::kPifRamBytes> pif{};
    constexpr std::array<std::uint8_t, 16U> challenge = {
        0xECU, 0x3CU, 0xB6U, 0x76U, 0xB8U, 0x1DU, 0xBBU, 0x8FU,
        0x6BU, 0x3AU, 0x80U, 0xECU, 0xEDU, 0xEAU, 0x5BU, 0x02U,
    };
    constexpr std::array<std::uint8_t, 16U> expected = {
        0x13U, 0x6AU, 0xF7U, 0x4CU, 0xDBU, 0x4FU, 0x0BU, 0xDEU,
        0x45U, 0x40U, 0xC6U, 0x4AU, 0xE7U, 0x73U, 0x0BU, 0x00U,
    };
    std::copy(challenge.begin(), challenge.end(), pif.begin() + 48U);
    pif[46U] = 0x0FU;
    pif[47U] = 0x0FU;
    check(jfg::process_cic_nus_6105_challenge(pif),
          "6105 challenge command is recognized");
    check(std::equal(expected.begin(), expected.end(), pif.begin() + 48U),
          "JFG challenge produces the canonical CIC response");
    check(pif[46U] == 0U && pif[47U] == 0U,
          "CIC response clears the PIF challenge prefix");

    std::array<std::uint8_t, jfg::kPifRamBytes> ordinary{};
    ordinary.fill(0x5AU);
    ordinary[63U] = 0U;
    const auto before = ordinary;
    check(!jfg::process_cic_nus_6105_challenge(ordinary),
          "ordinary PIF traffic is not treated as a CIC challenge");
    check(ordinary == before, "non-challenge PIF traffic is unchanged");

    return failures == 0 ? 0 : 1;
}
