#pragma once
#include <windows.h>
#include <filesystem>
#include <fstream>
#include <stdexcept>
#include <string>

namespace jfg::frontend {
inline constexpr UINT kStorageState = WM_APP + 41;
inline constexpr ULONG_PTR kStorageApply = 0x4a464753U;
struct StorageRequest { wchar_t directory[32768]{}; };
inline std::filesystem::path portable_root(const std::filesystem::path& launcher) {
  return launcher.parent_path() / L"userdata";
}
inline bool portable_marker(const std::filesystem::path& launcher) {
  const auto marker=launcher.parent_path()/L"portable.txt";
  if(std::filesystem::exists(marker) && !std::filesystem::is_regular_file(marker))
    throw std::runtime_error("Invalid portable marker.");
  return std::filesystem::is_regular_file(marker);
}
inline std::filesystem::path default_profile(const std::filesystem::path& root) {
  return root / L"profiles" / L"default";
}
inline bool linked_path(const std::filesystem::path& path) {
  const auto attributes = GetFileAttributesW(path.c_str());
  return attributes != INVALID_FILE_ATTRIBUTES &&
         (attributes & FILE_ATTRIBUTE_REPARSE_POINT) != 0;
}

// The selected root is remembered beside this launcher. Descendants use a
// relative path so moving a portable package keeps its data with it.
inline std::filesystem::path configured_storage_root(
    const std::filesystem::path& launcher, const std::filesystem::path& fallback) {
  namespace fs=std::filesystem;
  const auto config=launcher.parent_path()/L"storage-location.txt";
  if(!fs::exists(config))return portable_marker(launcher)?portable_root(launcher):fallback;
  if(!fs::is_regular_file(config) || linked_path(config))
    throw std::runtime_error("Invalid storage location file.");
  std::ifstream in(config,std::ios::binary);
  std::string text((std::istreambuf_iterator<char>(in)),{});
  while(!text.empty() && (text.back()=='\n'||text.back()=='\r'))text.pop_back();
  if(text.empty() || text.size()>131072 || text.find('\0')!=std::string::npos)
    throw std::runtime_error("Invalid storage location.");
  fs::path selected(std::u8string(text.begin(),text.end()));
  if(selected.is_relative())selected=launcher.parent_path()/selected;
  return fs::weakly_canonical(selected);
}
inline void set_storage_root(const std::filesystem::path& launcher,
                             const std::filesystem::path& selected) {
  namespace fs=std::filesystem;
  const auto root=fs::weakly_canonical(selected);
  if(!root.is_absolute() || !fs::is_directory(root) || linked_path(selected))
    throw std::runtime_error("Choose an accessible directory.");
  const auto config=launcher.parent_path()/L"storage-location.txt";
  if(linked_path(config))throw std::runtime_error("Linked storage location file.");
  auto stored=root;
  const auto relative=root.lexically_relative(fs::weakly_canonical(launcher.parent_path()));
  if(!relative.empty() && *relative.begin()!=L"..")stored=relative;
  const auto temporary=launcher.parent_path()/
      (L".storage-location-"+std::to_wstring(GetCurrentProcessId())+L".tmp");
  if(fs::exists(temporary))throw std::runtime_error("Storage configuration is busy.");
  const auto bytes=stored.generic_u8string();
  {std::ofstream out(temporary,std::ios::binary);
   out.write(reinterpret_cast<const char*>(bytes.data()),bytes.size());out.put('\n');out.close();
   if(!out)throw std::runtime_error("Cannot save data location.");}
  if(!MoveFileExW(temporary.c_str(),config.c_str(),MOVEFILE_REPLACE_EXISTING|MOVEFILE_WRITE_THROUGH)) {
    // Only our exact temporary file; a failed update must remain retryable.
    if(!linked_path(temporary) && fs::is_regular_file(temporary)) {
      std::error_code cleanup;fs::remove(temporary,cleanup);
    }
    throw std::runtime_error("Cannot update data location.");
  }
}

inline void copy_settings_tree(const std::filesystem::path& source,
                               const std::filesystem::path& destination) {
  namespace fs=std::filesystem;
  if(linked_path(source))throw std::runtime_error("Linked settings directory.");
  fs::create_directories(destination);
  for(const auto& entry:fs::directory_iterator(source)) {
    if(linked_path(entry.path()))throw std::runtime_error("Linked settings file.");
    if(entry.is_directory())copy_settings_tree(entry.path(),destination/entry.path().filename());
    else if(entry.is_regular_file())fs::copy_file(entry.path(),destination/entry.path().filename());
  }
}
// Publish a staged copy into an existing profile without replacing any file.
// This also handles a destination containing only first-run settings/cache.
inline void publish_missing_settings(const std::filesystem::path& source,
                                     const std::filesystem::path& destination) {
  namespace fs=std::filesystem;
  if(linked_path(destination))throw std::runtime_error("Linked destination.");
  fs::create_directories(destination);
  for(const auto& entry:fs::directory_iterator(source)) {
    const auto target=destination/entry.path().filename();
    if(linked_path(target))throw std::runtime_error("Linked destination file.");
    if(entry.is_directory())publish_missing_settings(entry.path(),target);
    else if(!fs::exists(target))fs::rename(entry.path(),target);
  }
}
// Copy only persistent profile files and the imported ROM. Never traverse
// diagnostics/cache junctions or overwrite an existing destination profile.
// A partial copy stays in staging. Existing files win; missing files are added.
inline void copy_profile_preserving_existing(const std::filesystem::path& source,
                                const std::filesystem::path& destination) {
  namespace fs = std::filesystem;
  if (source == destination || !fs::is_directory(source)) return;
  if (linked_path(source) || linked_path(destination))
    throw std::runtime_error("Linked profiles must be moved manually.");
  if (fs::exists(destination) && !fs::is_directory(destination))
    throw std::runtime_error("Profile destination is not a directory.");

  const auto staging = destination.parent_path() /
      (L".profile-copy-" + std::to_wstring(GetCurrentProcessId()) +
       L"-" + std::to_wstring(GetTickCount64()));
  if (!fs::create_directories(staging))
    throw std::runtime_error("Cannot create profile copy.");
  for (const auto& entry : fs::directory_iterator(source)) {
    const auto name = entry.path().filename().wstring();
    const auto ext = entry.path().extension().wstring();
    const bool persistent = ext == L".flash" || ext == L".pak" || ext == L".ini" ||
                            name == L"launcher.json" || name == L"controllers.json" ||
                            name == L"audio.json" || name == L"frontend-window.txt" ||
                            name == L"frontend-mods.txt";
    if (persistent && entry.is_regular_file()) {
      if (linked_path(entry.path())) throw std::runtime_error("Linked profile file.");
      fs::copy_file(entry.path(), staging / entry.path().filename());
    }
  }
  if(fs::is_directory(source/L"map-settings"))
    copy_settings_tree(source/L"map-settings",staging/L"map-settings");
  const auto rom = source / L"roms" / L"jfg-us.z64";
  if (fs::is_regular_file(rom)) {
    if (linked_path(source / L"roms") || linked_path(rom))
      throw std::runtime_error("Linked ROM must be imported manually.");
    fs::create_directory(staging / L"roms");
    fs::copy_file(rom, staging / L"roms" / L"jfg-us.z64");
  }
  if (fs::exists(destination)) {
    publish_missing_settings(staging,destination);
    // Remove only this operation's disposable copies. Source and destination
    // saves are retained; verify the complete staging location before cleanup.
    if(!linked_path(staging) &&
       fs::weakly_canonical(staging.parent_path())==fs::weakly_canonical(destination.parent_path()) &&
       staging.filename().wstring().starts_with(L".profile-copy-"+std::to_wstring(GetCurrentProcessId())+L"-")) {
      std::error_code cleanup;fs::remove_all(staging,cleanup);
    }
  } else fs::rename(staging, destination);
}
inline void set_portable_marker(const std::filesystem::path& launcher, bool enabled) {
  namespace fs = std::filesystem;
  const auto marker = launcher.parent_path() / L"portable.txt";
  if (linked_path(marker)) throw std::runtime_error("Linked portable marker.");
  if (enabled) {
    if (fs::is_regular_file(marker)) return;
    const auto temporary = launcher.parent_path() /
        (L"portable-" + std::to_wstring(GetCurrentProcessId()) + L".tmp");
    { std::ofstream out(temporary, std::ios::binary | std::ios::trunc);
      out << "Store JFG data in the adjacent userdata folder.\n";
      out.close(); if (!out) throw std::runtime_error("Cannot save portable setting."); }
    fs::rename(temporary, marker);
  } else if (fs::exists(marker)) {
    if (!fs::is_regular_file(marker)) throw std::runtime_error("Invalid portable marker.");
    fs::remove(marker);
  }
}
} // namespace jfg::frontend
