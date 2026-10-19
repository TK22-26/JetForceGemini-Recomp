#include "../native_ui.cpp"
#include <stdexcept>
static unsigned stateBits=0,applies=0,checks=0;
static std::wstring selected;
static LRESULT CALLBACK ownerProc(HWND w,UINT m,WPARAM p,LPARAM l){
 if(m==jfg::frontend::kStorageState)return stateBits;
 if(m==WM_COPYDATA){
  const auto* packet=reinterpret_cast<const COPYDATASTRUCT*>(l);
  if(packet&&packet->dwData==jfg::frontend::kStorageApply&&packet->cbData==sizeof(jfg::frontend::StorageRequest)){
   selected=static_cast<const jfg::frontend::StorageRequest*>(packet->lpData)->directory;++applies;return 1;
  }
 }return DefWindowProcW(w,m,p,l);
}
static void demand(bool ok,const char* why){if(!ok)throw std::runtime_error(why);++checks;}
static void frame(){for(unsigned i=0;i<3;++i)FrontendUiFrame({});}
int WINAPI wWinMain(HINSTANCE instance,HINSTANCE,PWSTR,int){
 const auto root=fs::temp_directory_path()/(L"jfg-storage-ui-"+std::to_wstring(GetCurrentProcessId()));
 fs::create_directories(root);HWND owner=nullptr,window=nullptr;bool ready=false;
 try {
  const auto desktopName=L"JfgStorageUi-"+std::to_wstring(GetCurrentProcessId());
  HDESK desktop=CreateDesktopW(desktopName.c_str(),nullptr,nullptr,0,GENERIC_ALL,nullptr);
  demand(desktop&&SetThreadDesktop(desktop),"isolated desktop");
  WNDCLASSW cls{};cls.lpfnWndProc=ownerProc;cls.hInstance=instance;cls.lpszClassName=L"JfgStorageUiFixture";
  RegisterClassW(&cls);
  owner=CreateWindowExW(0,cls.lpszClassName,L"Owner",WS_OVERLAPPEDWINDOW,100,100,900,700,nullptr,nullptr,instance,nullptr);
  auto open=[&](unsigned bits){
   stateBits=bits;window=CreateWindowExW(0,cls.lpszClassName,L"Settings",WS_OVERLAPPEDWINDOW,150,150,760,360,owner,nullptr,instance,nullptr);
   SetPropW(window,L"JfgLiveOwner",owner);
   demand(FrontendUiInit(window,root,[](const std::string&){},"settings"),"settings RmlUi document loads");ready=true;
   ShowWindow(window,SW_SHOWNOACTIVATE);FrontendUiResize();frame();
  };
  auto close=[&](){FrontendUiShutdown();ready=false;DestroyWindow(window);window=nullptr;};
  SetEnvironmentVariableW(L"JFG_DATA_ROOT",root.c_str());
  open(0);
  auto& ui=*surface->storage;
  demand(ui.el("settings-change")&&ui.el("settings-done"),"directory picker with standard Done");
  Rml::ElementList toggles;ui.doc->QuerySelectorAll(toggles,".switch");demand(toggles.empty(),"no portable toggle");
  demand(ui.location==root&&!ui.el("settings-change")->HasAttribute("disabled"),"actual data folder shown");
  demand(ui.el("settings-done")->GetBox().GetSize(Rml::BoxArea::Border).x<110,"Done matches standard compact button");
  demand(ui.el("settings-note")->GetAbsoluteOffset(Rml::BoxArea::Border).y+
    ui.el("settings-note")->GetBox().GetSize(Rml::BoxArea::Border).y <
    ui.el("settings-done")->GetAbsoluteOffset(Rml::BoxArea::Border).y,"folder and note fit above footer");
  const UINT_PTR cancelTimer=SetTimer(nullptr,0,300,[](HWND,UINT,UINT_PTR,DWORD){
    EnumThreadWindows(GetCurrentThreadId(),[](HWND dialog,LPARAM)->BOOL{
      wchar_t title[128]{};GetWindowTextW(dialog,title,128);
      if(std::wstring(title)==L"Choose a JFG data folder")PostMessageW(dialog,WM_COMMAND,IDCANCEL,0);
      return TRUE;
    },0);
  });
  const auto cancelled=jfg_storage::choose_directory(window,root);
  KillTimer(nullptr,cancelTimer);
  demand(cancelled.empty(),"real Windows folder picker cancellation");
  unsigned picks=0;
  ui.pickFolder=[&](HWND,const fs::path& current){++picks;demand(current==root,"picker opens at current folder");return fs::path{};};
  ui.el("settings-change")->Click();demand(picks==1&&applies==0,"cancel does not apply or restart");
  ui.pickFolder=[&](HWND,const fs::path&){return root;};
  ui.el("settings-change")->Click();demand(applies==0,"same directory does not restart");
  const auto chosen=root/L"selected & data";fs::create_directory(chosen);
  ui.pickFolder=[&](HWND,const fs::path&){return chosen;};
  ui.el("settings-change")->Click();demand(applies==1&&selected==chosen.wstring(),"chosen directory sent to authenticated owner");
  close();
  open(2);demand(surface->storage->el("settings-change")->HasAttribute("disabled"),"active game prevents migration");
  demand(!surface->storage->el("settings-done")->HasAttribute("disabled"),"Done still closes while locked");close();
  open(4);demand(surface->storage->el("settings-change")->HasAttribute("disabled"),"custom profile not silently migrated");close();
  window=CreateWindowExW(0,cls.lpszClassName,L"Menu",WS_OVERLAPPEDWINDOW,100,100,1280,780,nullptr,nullptr,instance,nullptr);
  std::string routed;demand(FrontendUiInit(window,root,[&](const std::string& a){routed=a;}),"home loads");ready=true;
  ShowWindow(window,SW_SHOWNOACTIVATE);FrontendUiResize();frame();surface->ui.modal("menu-game");frame();
  auto* settings=surface->ui.el("action-settings");demand(settings!=nullptr,"Game menu contains Settings");
  settings->Click();demand(routed=="settings","Settings routes to separate window");demand(!FrontendUiCapturing(),"Game menu closes before settings window");close();DestroyWindow(owner);
  std::ofstream(root/"result.txt")<<checks<<" settings UI checks passed\n";return 0;
 }catch(const std::exception& e){std::ofstream(root/"error.txt")<<e.what();if(ready)FrontendUiShutdown();if(window)DestroyWindow(window);if(owner)DestroyWindow(owner);return 1;}
}
