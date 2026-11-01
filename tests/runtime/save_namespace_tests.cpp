#include "jfg/game/save_namespace.hpp"
#include <chrono>
#include <cstdlib>
#include <iostream>
static void check(bool ok,const char* text) {if(!ok){std::cerr<<text<<'\n';std::exit(1);}}
int main() {
  using namespace jfg::game;
  const auto root=std::filesystem::temp_directory_path()/("jfg-save-namespace-"+
    std::to_string(std::chrono::steady_clock::now().time_since_epoch().count()));
  check(std::filesystem::create_directory(root),"fresh fixture directory");
  const auto marker=root/"rom-revision.txt",save=root/"save.flash";
  const auto write=[&](const std::string& text){std::ofstream out(marker,std::ios::binary|std::ios::trunc);out<<text;out.close();check(bool(out),"write fixture marker");};
  for(const auto& expected:jfg::roms::kRevisions) {
    check(inspect_save_namespace(save,expected,true)==SaveNamespaceStatus::unmarked,"explicit raw/legacy policy");
    check(inspect_save_namespace(save,expected,false)==SaveNamespaceStatus::missing,"regional profile cannot be inferred");
  }
  for(const auto& owner:jfg::roms::kRevisions) {
    const auto text=std::string("jfg-save-namespace-1\n")+std::string(owner.id)+"\n"+std::string(owner.sha1)+"\n";
    write(text);
    for(const auto& expected:jfg::roms::kRevisions)
      check(inspect_save_namespace(save,expected,true)==(owner.id==expected.id?SaveNamespaceStatus::matching:SaveNamespaceStatus::mismatch),"cross-region rejection includes diagnostics");
    write(text+"extra\n");check(inspect_save_namespace(save,owner,true)==SaveNamespaceStatus::malformed,"trailing content rejected");
    write(text.substr(0,text.size()-1));check(inspect_save_namespace(save,owner,true)==SaveNamespaceStatus::malformed,"truncated marker rejected");
  }
  const auto& revision=jfg::roms::kRevisions.front();
  write(std::string(257,'x'));check(inspect_save_namespace(save,revision,true)==SaveNamespaceStatus::malformed,"bounded marker read");
  check(std::filesystem::remove(marker),"remove owned marker fixture");
  check(std::filesystem::create_directory(marker),"wrong-type fixture");
  check(inspect_save_namespace(save,revision,true)==SaveNamespaceStatus::malformed,"marker must be a file");
  check(!std::filesystem::exists(save),"identity check cannot open or create save data");
  check(std::filesystem::remove(marker)&&std::filesystem::remove(root),"remove only owned empty fixture directories");
  std::cout<<"regional save namespace checks passed\n";
}
