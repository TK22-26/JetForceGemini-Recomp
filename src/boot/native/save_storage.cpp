#include "runtime_services.hpp"
namespace jfg::boot::native::detail {
#if defined(JFG_PHASE8_LIVE_RUNTIME)
bool configure_flash_path(State &state, const char *path) {
  if (path == nullptr || *path == '\0')
    return true;
  state.flash_path = std::filesystem::path(path);
  if (state.flash_path.empty() || state.flash_path.filename().empty())
    return false;
  std::error_code error;
  const std::filesystem::path parent = state.flash_path.parent_path();
  if (!parent.empty()) {
    std::filesystem::create_directories(parent, error);
    if (error)
      return false;
  }
  const bool exists = std::filesystem::exists(state.flash_path, error);
  if (error)
    return false;
  if (exists) {
    if (!std::filesystem::is_regular_file(state.flash_path, error) || error ||
        !state.flashram.reload(state.flash_path).ok())
      return false;
    state.flash_image_loaded = true;
    return true;
  }
  if (!state.flashram.persist_atomic(state.flash_path).ok())
    return false;
  state.flash_image_created = true;
  return true;
}

bool configure_controller_pak_path(State &state, const char *path) {
  if (path == nullptr || *path == '\0')
    return true;
  state.controller_pak_path = std::filesystem::path(path);
  if (state.controller_pak_path.empty() ||
      state.controller_pak_path.filename().empty())
    return false;
  std::error_code error;
  const std::filesystem::path parent =
      state.controller_pak_path.parent_path();
  if (!parent.empty()) {
    std::filesystem::create_directories(parent, error);
    if (error)
      return false;
  }
  state.controller_accessory_bus =
      std::make_unique<jfg::ControllerAccessoryBus>(
          jfg::ControllerPakGeometry{32U * 1024U, 16U});
  if (!state.controller_accessory_bus
           ->set_accessory(0U, jfg::ControllerAccessoryKind::controller_pak)
           .ok())
    return false;
  const jfg::ControllerPakProbeResult probe =
      state.controller_accessory_bus->probe_controller_pak(0U);
  if (!probe.ok())
    return false;
  state.controller_pak_session = probe.session;
  const bool exists = std::filesystem::exists(state.controller_pak_path, error);
  if (error)
    return false;
  if (exists) {
    if (!std::filesystem::is_regular_file(state.controller_pak_path, error) ||
        error ||
        !state.controller_accessory_bus
             ->reload(state.controller_pak_session, state.controller_pak_path)
             .ok())
      return false;
    state.controller_pak_loaded = true;
    return true;
  }
  if (!state.controller_accessory_bus
           ->persist(state.controller_pak_session, state.controller_pak_path)
           .ok())
    return false;
  state.controller_pak_created = true;
  return true;
}

bool persist_controller_pak(State &state) {
  return state.controller_pak_path.empty() ||
         (state.controller_accessory_bus != nullptr &&
          state.controller_accessory_bus
              ->persist(state.controller_pak_session,
                        state.controller_pak_path)
              .ok());
}


#endif
} // namespace jfg::boot::native::detail
