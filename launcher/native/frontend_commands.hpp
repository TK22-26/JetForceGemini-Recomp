#pragma once
#include <windows.h>
#include <string_view>
namespace jfg::frontend {
enum Command : UINT {
  Play = 100,
  Stop,
  Setup,
  Cancel,
  Rom,
  Runtime,
  Controllers,
  Audio,
  Fullscreen,
  Map,
  Inventory,
  Support,
  Saves,
  Guide,
  Quit,
  Mods,
  Video,
  Settings,
  About,
  Project,
  KnownIssues,
  Notices
};
// About forwards only these existing launcher actions to its owner.
inline UINT about_command(std::string_view action) {
    if (action == "guide") return Guide;
    if (action == "support") return Support;
    if (action == "project") return Project;
    if (action == "known-issues") return KnownIssues;
    if (action == "notices") return Notices;
    return 0;
}
}
