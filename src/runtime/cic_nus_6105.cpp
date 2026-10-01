/*
 * Copyright 2011 X-Scale. All rights reserved.
 *
 * Redistribution and use in source and binary forms, with or without 
 * modification, are permitted provided that the following conditions are met:
 *
 *    1. Redistributions of source code must retain the above copyright notice,
 *       this list of conditions and the following disclaimer.
 *    2. Redistributions in binary form must reproduce the above copyright 
 *       notice, this list of conditions and the following disclaimer in the 
 *       documentation and/or other materials provided with the distribution.
 *
 * THIS SOFTWARE IS PROVIDED BY X-Scale ``AS IS'' AND ANY EXPRESS OR IMPLIED 
 * WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF
 * MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO 
 * EVENT SHALL X-Scale OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, 
 * INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
 * LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, 
 * OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF 
 * LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING 
 * NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE,
 * EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
 *
 * The views and conclusions contained in the software and documentation are 
 * those of the authors and should not be interpreted as representing official 
 * policies, either expressed or implied, of X-Scale.
 *
 */

// Challenge-response algorithm attributed to X-Scale (2011).
// Project integration uses std::span, packed PIF RAM and C++ integer types.
// See patches/cic/LICENSE.upstream and THIRD_PARTY_NOTICES.md.

#include "jfg/runtime/cic_nus_6105.hpp"

#include <array>

namespace jfg {

bool process_cic_nus_6105_challenge(
    const std::span<std::uint8_t, kPifRamBytes> pif_ram) noexcept {
    if (pif_ram[63U] != 0x02U)
        return false;

    // The 6105 consumes 30 challenge nibbles from PIF bytes 48..62. This is
    // the published challenge-response state machine used by N64 hardware
    // implementations; keeping it here also lets the SI runtime model the
    // transfer rather than special-casing JFG's expected checksum.
    static constexpr std::array<std::uint8_t, 32U> kLookup = {
        0x4U, 0x7U, 0xAU, 0x7U, 0xEU, 0x5U, 0xEU, 0x1U,
        0xCU, 0xFU, 0x8U, 0xFU, 0x6U, 0x3U, 0x6U, 0x9U,
        0x4U, 0x1U, 0xAU, 0x7U, 0xEU, 0x5U, 0xEU, 0x1U,
        0xCU, 0x9U, 0x8U, 0x5U, 0x6U, 0x3U, 0xCU, 0x9U,
    };

    std::array<std::uint8_t, 30U> nibbles{};
    for (std::size_t index = 0U; index < 15U; ++index) {
        nibbles[index * 2U] =
            static_cast<std::uint8_t>(pif_ram[48U + index] >> 4U);
        nibbles[index * 2U + 1U] =
            static_cast<std::uint8_t>(pif_ram[48U + index] & 0x0FU);
    }

    std::uint8_t key = 0x0BU;
    bool alternate = false;
    for (std::uint8_t &nibble : nibbles) {
        const std::uint8_t response =
            static_cast<std::uint8_t>((key + 5U * nibble) & 0x0FU);
        nibble = response;
        key = kLookup[(alternate ? 16U : 0U) + response];

        bool modifier = (response & 0x08U) != 0U;
        std::uint8_t magnitude =
            static_cast<std::uint8_t>(response & 0x07U);
        if (modifier)
            magnitude = static_cast<std::uint8_t>((~magnitude) & 0x07U);
        if (magnitude % 3U != 1U)
            modifier = !modifier;
        if (alternate && (response == 0x01U || response == 0x09U))
            modifier = true;
        if (alternate && (response == 0x0BU || response == 0x0EU))
            modifier = false;
        alternate = modifier;
    }

    pif_ram[46U] = 0U;
    pif_ram[47U] = 0U;
    for (std::size_t index = 0U; index < 15U; ++index) {
        pif_ram[48U + index] = static_cast<std::uint8_t>(
            (nibbles[index * 2U] << 4U) | nibbles[index * 2U + 1U]);
    }
    pif_ram[63U] = 0U;
    return true;
}

} // namespace jfg
