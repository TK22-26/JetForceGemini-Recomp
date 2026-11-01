#pragma once
#include <array>
#include <cstdint>
#include <string_view>
namespace jfg {
struct RendererInstructionGuard {
  std::uint32_t address{},word{};
  template<class Memory> bool matches(const Memory& memory) const {
    return memory.valid(address,4U) && memory.u32(address)==word;
  }
};
// Immutable per-session inputs to game-specific presentation. No default ROM
// coordinates live in the shared renderer. Generic RSP tests omit this layout.
enum class RainOperation { none, main, transition, segment, debug, geometry, clear, simple, effects, rain, line, submit, enabled, shadow, blur, reflection };
struct RendererGameLayout {
  std::string_view revision;
  unsigned vi_rate{}; // Nominal retrace clock for presentation, independent of output FPS.
  std::uint32_t level{};
  std::uint32_t objects{};
  std::uint32_t object_count{};
  std::uint32_t camera_mode{};
  std::uint32_t camera_number{};
  std::uint32_t world_matrix{};
  std::uint32_t view_matrix{};
  std::uint32_t projection_matrix{};
  std::uint32_t shadow_polygon_count{};
  std::uint32_t shadow_polygons{};
  std::uint32_t shadow_vertices{};
  std::uint32_t shadow_batches{};
  std::uint32_t shadow_unclipped{};
  std::uint32_t shadow_clipped{};
  std::uint32_t sky_actor{};
  std::uint32_t matrix_queue_count{};
  std::uint32_t matrix_queue{};
  std::uint32_t track{};
  std::uint32_t render_detail{};
  std::uint32_t camera_transform{};
  std::uint32_t inverse_matrix{};
  std::uint32_t draw_model{};
  std::uint32_t draw_object{};
  std::uint32_t shadow_bounds{};
  std::uint32_t cosine{};
  std::uint32_t sine{};
  std::uint32_t shadow_bounds_return{};
  RendererInstructionGuard lod_entry;
  RendererInstructionGuard lod_detail;
  RendererInstructionGuard lod_threshold;
  RendererInstructionGuard lod_selector;
  RendererInstructionGuard camera_entry;
  RendererInstructionGuard camera_flags;
  RendererInstructionGuard camera_mask;
  std::array<std::uint32_t,3> rpy_sine{},rpy_cosine{},ypr_sine{},ypr_cosine{};
  std::uint32_t vi_mode{};
  std::uint32_t resolution_modes{};
  std::uint32_t fade_type{};
  std::uint32_t fade_mode{};
  std::uint32_t fade_enabled{};
  std::uint32_t fade_alpha{};
  std::uint32_t fade_red{};
  std::uint32_t fade_green{};
  std::uint32_t fade_blue{};
  std::uint32_t fade_vertices{};
  std::uint32_t fade_triangles{};
  std::uint32_t fade_bank{};
  std::uint32_t fade_commands{};
  std::uint32_t viewports{};
  std::uint32_t sp_setup{};
  std::uint32_t dp_setup{};
  std::uint32_t font_commands{};
  std::uint32_t debug_end{};
  std::uint32_t debug_buffer{};
  std::uint32_t game_scene_mode{};
  std::uint32_t dl_cursor{};
  std::uint32_t dl_banks{};
  std::uint32_t dl_bank{};
  std::uint32_t render_framebuffer{};
  std::uint32_t blur_enabled{};
  std::uint32_t rain_submit_return{};
  std::uint32_t rain_segment_return{};
  std::uint32_t rain_debug_return{};
  std::uint32_t rain_fade_return{};
  std::uint32_t rain_simple_return{};
  std::uint32_t rain_spatial_return{};
  RendererInstructionGuard rain_fade_call;
  RendererInstructionGuard rain_segment_call;
  RendererInstructionGuard rain_effects_call;
  std::array<RendererInstructionGuard,4> blur_getter{};
  std::array<std::uint32_t,15> rain_targets{};
  std::uint32_t actor_control{};
  std::uint32_t actor_type{};
  std::uint32_t actor_properties{};
  std::uint32_t actor_objectData{};
  std::uint32_t actor_animation{};
  std::uint32_t actor_animationFrame{};
  std::uint32_t actor_header{};
  std::uint32_t actor_models{};
  std::uint32_t actor_variant{};
  std::uint32_t actor_flags{};
  std::uint32_t actor_scale{};
  std::uint32_t actor_x{};
  std::uint32_t actor_y{};
  std::uint32_t actor_z{};
  std::uint32_t actor_physics{};
  std::uint32_t actor_deleted{};
  std::uint32_t actor_customBank{};
  constexpr RainOperation rain_operation(std::uint32_t target) const noexcept {
    if (target) for (unsigned i=0;i<rain_targets.size();++i)
      if (target==rain_targets[i]) return static_cast<RainOperation>(i+1U);
    return RainOperation::none;
  }

};
} // namespace jfg
