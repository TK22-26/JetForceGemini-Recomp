#pragma once
#include "jfg/game/rom_catalog.hpp"
#include <array>
#include <filesystem>
#include <fstream>
#include <string>
#include <string_view>

namespace jfg::game {
enum class SaveNamespaceStatus { matching, unmarked, missing, mismatch, malformed, io_error };
inline bool save_namespace_accepted(SaveNamespaceStatus status) noexcept {
  return status == SaveNamespaceStatus::matching || status == SaveNamespaceStatus::unmarked;
}
// This is a read-only admission check. The launcher/build tool owns marker
// creation and migration; the native runtime never assigns a region to data.
inline SaveNamespaceStatus inspect_save_namespace(const std::filesystem::path& data_path,
    const roms::RomRevision& revision, bool allow_unmarked) {
  const auto* known=roms::find_revision(revision.id);
  if(!known || known->sha1!=revision.sha1 || data_path.empty()) return SaveNamespaceStatus::malformed;
  std::error_code error;
  const auto absolute=std::filesystem::absolute(data_path,error);
  if(error || absolute.filename().empty()) return SaveNamespaceStatus::io_error;
  const auto marker=absolute.lexically_normal().parent_path()/"rom-revision.txt";
  const auto status=std::filesystem::symlink_status(marker,error);
  if(error==std::errc::no_such_file_or_directory || (!error && status.type()==std::filesystem::file_type::not_found))
    return allow_unmarked?SaveNamespaceStatus::unmarked:SaveNamespaceStatus::missing;
  if(error) return SaveNamespaceStatus::io_error;
  if(!std::filesystem::is_regular_file(status) || std::filesystem::is_symlink(status)) return SaveNamespaceStatus::malformed;
  std::ifstream stream(marker,std::ios::binary);
  if(!stream) return SaveNamespaceStatus::io_error;
  std::array<char,257> buffer{};
  stream.read(buffer.data(),static_cast<std::streamsize>(buffer.size()));
  if(stream.bad()) return SaveNamespaceStatus::io_error;
  if(!stream.eof() || stream.gcount()>256) return SaveNamespaceStatus::malformed;
  const std::string_view content(buffer.data(),static_cast<std::size_t>(stream.gcount()));
  for(const auto& candidate:roms::kRevisions) {
    const auto expected=std::string("jfg-save-namespace-1\n")+std::string(candidate.id)+"\n"+std::string(candidate.sha1)+"\n";
    if(content==expected) return candidate.id==revision.id?SaveNamespaceStatus::matching:SaveNamespaceStatus::mismatch;
  }
  return SaveNamespaceStatus::malformed;
}
inline const char* save_namespace_message(SaveNamespaceStatus status) noexcept {
  switch(status) {
    case SaveNamespaceStatus::matching:return "matching region";
    case SaveNamespaceStatus::unmarked:return "unmarked diagnostic or legacy US data";
    case SaveNamespaceStatus::missing:return "regional Play requires a marked profile; select it through the launcher";
    case SaveNamespaceStatus::mismatch:return "profile belongs to another ROM revision";
    case SaveNamespaceStatus::malformed:return "invalid profile identity marker";
    case SaveNamespaceStatus::io_error:return "cannot inspect profile identity marker";
  }
  return "unknown profile identity error";
}
} // namespace jfg::game
