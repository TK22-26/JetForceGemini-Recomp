#include "runtime_services.hpp"
#include "jfg/game/save_namespace.hpp"
#include <cstdlib>
#include <memory>
namespace jfg::boot::native::detail {
#if defined(JFG_PHASE8_LIVE_RUNTIME)
bool validate_persistent_profile_paths(bool play_mode) {
  constexpr const auto& revision=jfg::roms::known_revision(jfg::game::linked::descriptor.revision);
  // Both paths must pass before either device can create or open storage.
  // Preserve legacy US/raw diagnostic inputs without assigning them a region.
  const bool allow_unmarked=!play_mode || revision.id=="jfg-us-r0";
  for(const auto* name:{"JFG_PHASE8_SAVE_PATH","JFG_PHASE8_CONTROLLER_PAK_PATH"}) {
#if defined(_WIN32)
    char* owned_value=nullptr;
    std::size_t value_size=0;
    if(_dupenv_s(&owned_value,&value_size,name)!=0) {
      std::fputs("native boot setup failed: profile environment\n",stderr);
      return false;
    }
    const std::unique_ptr<char,decltype(&std::free)> storage(owned_value,&std::free);
    const char* value=storage.get();
#else
    const char* value=std::getenv(name);
#endif
    if(!value || !*value) continue;
    if(std::string_view(value).size()>32767U) return false;
    try {
      const auto result=jfg::game::inspect_save_namespace(std::filesystem::path(value),revision,allow_unmarked);
      if(!jfg::game::save_namespace_accepted(result)) {
        std::fprintf(stderr,"native boot setup failed: %s: %s\n",name,jfg::game::save_namespace_message(result));
        return false;
      }
    } catch(const std::exception&) {
      std::fputs("native boot setup failed: profile identity inspection\n",stderr);
      return false;
    }
  }
  return true;
}

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
