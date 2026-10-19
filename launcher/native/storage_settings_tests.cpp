#define WIN32_LEAN_AND_MEAN
#define NOMINMAX
#include "storage_settings.hpp"
#include <iostream>
namespace fs=std::filesystem;
std::string read(const fs::path& p){std::ifstream f(p,std::ios::binary);return {std::istreambuf_iterator<char>(f),{}};}
int main(){
 const auto base=fs::temp_directory_path()/(L"jfg-storage-check-"+std::to_wstring(GetCurrentProcessId())+L"-"+std::to_wstring(GetTickCount64()));
 unsigned count=0;
 auto check=[&](bool ok,const char* why){if(!ok)throw std::runtime_error(why);++count;};
 try {
  fs::create_directories(base/L"game");const auto exe=base/L"game"/L"JFG-Launcher.exe";
  const auto source=base/L"original";
  fs::create_directories(source/L"roms");fs::create_directories(source/L"performance");
  std::ofstream(source/L"jfg.flash")<<"existing-save";
  std::ofstream(source/L"controller.ini")<<"user-mapping";
  std::ofstream(source/L"video.ini")<<"120";
  std::ofstream(source/L"roms"/L"jfg-us.z64")<<"fixture-rom";
  std::ofstream(source/L"performance"/L"huge.csv")<<"not-portable-profile-state";
  std::ofstream(source/L"live.json")<<"stale-session";
  fs::create_directory(source/L"map-settings");std::ofstream(source/L"map-settings"/L"view.ini")<<"map-preference";
  check(!jfg::frontend::portable_marker(exe),"default must remain AppData");
  jfg::frontend::set_portable_marker(exe,true);
  check(jfg::frontend::portable_marker(exe),"portable marker enabled");
  const auto destination=jfg::frontend::default_profile(jfg::frontend::portable_root(exe));
  jfg::frontend::copy_profile_preserving_existing(source,destination);
  check(read(destination/L"jfg.flash")=="existing-save","save copied");
  check(read(destination/L"controller.ini")=="user-mapping","mapping copied");
  check(read(destination/L"video.ini")=="120","video copied");
  check(read(destination/L"map-settings"/L"view.ini")=="map-preference","map preferences copied");
  check(read(destination/L"roms"/L"jfg-us.z64")=="fixture-rom","imported ROM copied");
  check(!fs::exists(destination/L"performance")&&!fs::exists(destination/L"live.json"),"transient state excluded");
  std::ofstream(destination/L"jfg.flash")<<"destination-progress";
  jfg::frontend::copy_profile_preserving_existing(source,destination);
  check(read(destination/L"jfg.flash")=="destination-progress","existing destination never overwritten");
  check(read(source/L"jfg.flash")=="existing-save","source save unchanged");
  fs::remove(destination/L"video.ini");
  jfg::frontend::copy_profile_preserving_existing(source,destination);
  check(read(destination/L"video.ini")=="120","missing settings filled in existing profile");
  check(read(destination/L"jfg.flash")=="destination-progress","merge preserves destination progress");
  fs::rename(base/L"game",base/L"moved game");
  const auto moved=base/L"moved game"/L"JFG-Launcher.exe";
  check(jfg::frontend::portable_marker(moved),"marker moves with package");
  check(read(jfg::frontend::default_profile(jfg::frontend::portable_root(moved))/L"jfg.flash")=="destination-progress","profile resolves after moving");
  jfg::frontend::set_portable_marker(moved,false);
  check(!jfg::frontend::portable_marker(moved),"portable mode can be disabled");
  check(read(source/L"jfg.flash")=="existing-save","disabling retains AppData profile");
  check(fs::exists(jfg::frontend::portable_root(moved)),"disabling retains portable profile");
  fs::create_directory(base/L"moved game"/L"portable.txt");
  bool rejected=false;try{jfg::frontend::set_portable_marker(moved,true);}catch(const std::exception&){rejected=true;}
  check(rejected,"invalid marker rejects rather than silently falling back");
  const auto invalid=base/L"not-a-profile";std::ofstream(invalid).close();
  rejected=false;try{jfg::frontend::copy_profile_preserving_existing(source,invalid);}catch(const std::exception&){rejected=true;}
  check(rejected&&fs::is_regular_file(invalid),"invalid destination preserved");
  fs::remove(base/L"moved game"/L"portable.txt"); // empty fixture directory
  fs::create_directories(base/L"external data");
  jfg::frontend::set_storage_root(moved,base/L"external data");
  check(jfg::frontend::configured_storage_root(moved,source)==fs::weakly_canonical(base/L"external data"),"external folder restored");
  check(read(base/L"moved game"/L"storage-location.txt").find("external data")!=std::string::npos,"selected root recorded");
  jfg::frontend::set_storage_root(moved,jfg::frontend::portable_root(moved));
  check(read(base/L"moved game"/L"storage-location.txt")=="userdata\n","portable root stored relatively");
  fs::rename(base/L"moved game",base/L"moved again");
  const auto again=base/L"moved again"/L"JFG-Launcher.exe";
  check(jfg::frontend::configured_storage_root(again,source)==fs::weakly_canonical(base/L"moved again"/L"userdata"),"relative chosen folder survives package move");
  std::cout<<count<<" storage checks passed\n";
  // The fixture is a fresh immediate child of temp; never use arbitrary input.
  if(fs::weakly_canonical(base.parent_path())==fs::weakly_canonical(fs::temp_directory_path())&&base.filename().wstring().starts_with(L"jfg-storage-check-"))
    fs::remove_all(base);
  return 0;
 }catch(const std::exception& e){std::cerr<<e.what()<<"\nEvidence: "<<base<<"\n";return 1;}
}
