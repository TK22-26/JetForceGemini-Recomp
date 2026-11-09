#pragma once
#include <cstdint>

namespace jfg::game::records {
// Generation's qualify_record_arrays verifies the original accessor arithmetic
// in every admitted revision. Individual fields use qualified member bindings.
inline constexpr std::uint32_t character_array_offset=0x15cU;
inline constexpr std::uint32_t character_stride=0x76U;
inline constexpr std::uint32_t bridge_matrix_offset=0x80U;
inline constexpr std::uint32_t bridge_matrix_stride=64U;
// Generation also verifies these exact original draw-bank formulas.
inline constexpr std::uint32_t beam_vertex_bank_stride=80U;
inline constexpr std::uint32_t shockwave_vertex_bank_stride=200U;
// Qualified constructor loops and nested pickup payload.
inline constexpr std::uint32_t ammo_entry_stride=2U,ammo_entry_count=16U;
inline constexpr std::uint32_t pickup_weapon_index_offset=0x88U;
// Original track loader and plane builders qualify these packed array sizes.
inline constexpr std::uint32_t track_block_stride=72U,track_vertex_stride=10U,
  track_face_stride=16U,track_batch_stride=16U,track_plane_stride=16U,
  track_plane_index_stride=8U;
} // namespace jfg::game::records
