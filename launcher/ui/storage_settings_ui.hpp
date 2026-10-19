#pragma once
#include "../native/storage_settings.hpp"
#include <RmlUi/Core.h>
#include <shobjidl.h>
#include <algorithm>
#include <functional>
#include <string>
namespace jfg_storage {
inline std::filesystem::path choose_directory(HWND owner,const std::filesystem::path& current) {
  const HRESULT init=CoInitializeEx(nullptr,COINIT_APARTMENTTHREADED);
  if(FAILED(init))throw std::runtime_error("Cannot open the folder picker.");
  IFileOpenDialog* dialog=nullptr;
  std::filesystem::path selected;
  HRESULT hr=CoCreateInstance(CLSID_FileOpenDialog,nullptr,CLSCTX_INPROC_SERVER,IID_PPV_ARGS(&dialog));
  if(SUCCEEDED(hr)) {
    DWORD options=0;hr=dialog->GetOptions(&options);
    if(SUCCEEDED(hr))hr=dialog->SetOptions(options|FOS_PICKFOLDERS|FOS_FORCEFILESYSTEM|FOS_PATHMUSTEXIST|FOS_NOCHANGEDIR);
    dialog->SetTitle(L"Choose a JFG data folder");
    IShellItem* initial=nullptr;
    if(SUCCEEDED(SHCreateItemFromParsingName(current.c_str(),nullptr,IID_PPV_ARGS(&initial)))) {
      dialog->SetFolder(initial);initial->Release();
    }
    if(SUCCEEDED(hr))hr=dialog->Show(owner);
    if(SUCCEEDED(hr)) {
      IShellItem* item=nullptr;hr=dialog->GetResult(&item);
      if(SUCCEEDED(hr)) {
        PWSTR path=nullptr;hr=item->GetDisplayName(SIGDN_FILESYSPATH,&path);
        if(SUCCEEDED(hr)){selected=path;CoTaskMemFree(path);}
        item->Release();
      }
    }
    dialog->Release();
  }
  CoUninitialize();
  if(FAILED(hr)&&hr!=HRESULT_FROM_WIN32(ERROR_CANCELLED))throw std::runtime_error("Cannot choose that folder.");
  return selected;
}
struct Ui final : Rml::EventListener {
  HWND window=nullptr, owner=nullptr;
  Rml::ElementDocument* doc=nullptr;
  bool locked=false, custom=false;
  std::filesystem::path location;
  std::string error;
  std::function<std::filesystem::path(HWND,const std::filesystem::path&)> pickFolder=choose_directory;
  Rml::Element* el(const char* id) const {return doc->GetElementById(id);}
  void init(HWND w,Rml::ElementDocument* d) {
    window=w;doc=d;owner=reinterpret_cast<HWND>(GetPropW(w,L"JfgLiveOwner"));
    DWORD_PTR state=0;
    if(!IsWindow(owner) || !SendMessageTimeoutW(owner,jfg::frontend::kStorageState,0,0,SMTO_ABORTIFHUNG,1000,&state))
      locked=true;
    locked=locked||(state&2)!=0;custom=(state&4)!=0;
    wchar_t root[32768]{};
    const auto count=GetEnvironmentVariableW(L"JFG_DATA_ROOT",root,32768);
    if(count>0&&count<32768)location=root;else locked=true;
    doc->AddEventListener("click",this);refresh();
  }
  void refresh() {
    const auto bytes=location.u8string();
    std::string label;
    for(char8_t c:bytes) {
      if(c==u8'&')label+="&amp;";else if(c==u8'<')label+="&lt;";
      else if(c==u8'>')label+="&gt;";else label+=static_cast<char>(c);
    }
    el("settings-location")->SetInnerRML(label);
    el("settings-note")->SetInnerRML(custom
      ?"This shortcut uses a custom profile. Open the launcher directly to change folders."
      :locked?"Stop the game before changing the data folder."
      :"Changing folders copies your data and restarts the launcher.");
    el("settings-error")->SetInnerRML(error);
    el("settings-error")->SetProperty("display",error.empty()?"none":"block");
    if(locked||custom)el("settings-change")->SetAttribute("disabled",true);
    else el("settings-change")->RemoveAttribute("disabled");
  }
  void ProcessEvent(Rml::Event& e) override {
    auto* target=e.GetTargetElement();
    while(target&&target->GetId().empty())target=target->GetParentNode();
    if(!target||target->HasAttribute("disabled"))return;
    auto id=target->GetId();
    if(id=="settings-done")PostMessageW(window,WM_CLOSE,0,0);
    else if(id=="settings-change") {
      try {
        const auto selected=pickFolder(window,location);
        if(selected.empty() || std::filesystem::weakly_canonical(selected)==std::filesystem::weakly_canonical(location))return;
        const auto path=selected.wstring();
        if(path.size()>=32768)throw std::runtime_error("Directory path is too long.");
        jfg::frontend::StorageRequest request{};
        std::copy(path.begin(),path.end(),request.directory);
        COPYDATASTRUCT packet{jfg::frontend::kStorageApply,sizeof(request),&request};
        // Keep the authenticated owner responsible for saving, copying and
        // restarting. A cancelled folder picker sends no request at all.
        const auto result=SendMessageW(owner,WM_COPYDATA,reinterpret_cast<WPARAM>(window),reinterpret_cast<LPARAM>(&packet));
        if(result==1)PostMessageW(window,WM_CLOSE,0,0);
        else if(result!=2)throw std::runtime_error("Cannot change data folder.");
      }catch(const std::exception&) {
        error="Could not change folders. Check that the launcher and selected folder are writable. Your current data stays in place.";
        refresh();
      }
    }
  }
  bool keyboard(UINT m,WPARAM key) {
    if(m!=WM_KEYDOWN)return false;
    if(key==VK_ESCAPE){PostMessageW(window,WM_CLOSE,0,0);return true;}
    auto* focused=doc->GetContext()->GetFocusElement();
    if(key==VK_TAB) {
      Rml::ElementList controls;doc->QuerySelectorAll(controls,"button");
      controls.erase(std::remove_if(controls.begin(),controls.end(),[](auto* e){return e->HasAttribute("disabled");}),controls.end());
      if(!controls.empty()){
        const bool back=(GetKeyState(VK_SHIFT)&0x8000)!=0;
        auto it=std::find(controls.begin(),controls.end(),focused);
        int n=it==controls.end()?(back?0:-1):int(it-controls.begin());
        n=(n+(back?-1:1)+int(controls.size()))%int(controls.size());controls[n]->Focus(true);
      }return true;
    }
    if((key==VK_RETURN||key==VK_SPACE)&&focused&&focused->GetTagName()=="button"){focused->Click();return true;}
    return false;
  }
};
}
